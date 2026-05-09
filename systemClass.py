# systemClass.py
from constSet import *      # legacy: keeps np, ti, time, etc. exposed
import constSet as cs        # explicit handle for runtime UNITS / LOG / PROFILER
from toolClass import fileOperator
from tqdm import tqdm
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

@ti.data_oriented
class simulator:
    def __init__(self, runStep,chunk_size=500, dist_list=np.array([3, 4, 6, 6, 4, 2]), change_size=False,
                 profiler_check=True, ax_out=2, write_stride=1, output_format="xyz"):
        self.runStep = int(runStep)
        self.changeSize = change_size
        self.profiler_check = profiler_check
        self.ax_out = ax_out
        # write_stride: only every K-th physics step is captured into the XYZ.
        # 1 = capture every step (legacy); >1 = subsample for long runs to keep
        # output size manageable. dt-aware time stamps are still correct because
        # the writer uses (frame_idx * write_stride * dt) implicitly via dt scaling.
        self.write_stride = max(1, int(write_stride))
        # output_format: "xyz" (legacy ASCII; OVITO-readable but slow on N>1000)
        # or "hdf5" (binary chunked + LZF; ~50x faster, ~10x smaller).
        if output_format not in ("xyz", "hdf5"):
            raise ValueError(f"output_format must be 'xyz' or 'hdf5', got {output_format!r}")
        self.output_format = output_format

        if ti.static(change_size):
            chunk_sizes = np.array(dist_list / sum(dist_list) * runStep, dtype=np.int32)
            if sum(chunk_sizes) < runStep:
                chunk_sizes[-1] += (runStep - sum(chunk_sizes))

            self.chunksize = chunk_sizes
            self.chunkCal_Idx = 0
        else:
            self.chunksize = [chunk_size]

        return

    def register(self, atomSystem, forceField, integrator, searchBox):
        self.atomSystem = atomSystem
        self.forceField = forceField
        self.integrator = integrator
        self.searchBox = searchBox

        if ti.static(self.changeSize):
            chunk_dim = max(self.chunksize)
            self.data_pos = ti.Vector.field(self.atomSystem.n, dtype=ti.f64,
                                            shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_vel = ti.Vector.field(self.atomSystem.n, dtype=ti.f64,
                                            shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_T = ti.field(dtype=ti.f64, shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_ke = ti.Vector.field(1, dtype=ti.f64,
                                           shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_pe = ti.Vector.field(1, dtype=ti.f64,
                                           shape=(chunk_dim, self.atomSystem.num_atoms))
        else:
            chunk_dim = self.chunksize[0]
            self.data_pos = ti.Vector.field(self.atomSystem.n, dtype=ti.f64,
                                            shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_vel = ti.Vector.field(self.atomSystem.n, dtype=ti.f64,
                                            shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_T = ti.field(dtype=ti.f64, shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_ke = ti.Vector.field(1, dtype=ti.f64,
                                           shape=(chunk_dim, self.atomSystem.num_atoms))
            self.data_pe = ti.Vector.field(1, dtype=ti.f64,
                                           shape=(chunk_dim, self.atomSystem.num_atoms))

        return

    def simuWithData(self, outputPath):
        ext = ".h5" if self.output_format == "hdf5" else ".xyz"
        self.outputPath = outputPath + f"_{self.runStep}{ext}"

        # Hoist Taichi field reads to main thread BEFORE starting the writer.
        # Taichi 1.7.4 asserts to_numpy() is main-thread only.
        self._writer_static = {
            "species": self.atomSystem.group.to_numpy().astype(np.int32),
            "box": self.atomSystem.boxList.to_numpy()[0].astype(np.float64),
            "physics_dt": float(self.integrator.delta_t),
            "dt_per_frame": float(self.integrator.delta_t) * self.write_stride,
            "num_atoms": int(self.atomSystem.num_atoms),
        }

        data_queue = queue.Queue(maxsize=8)
        writer_target = (self._async_writer_hdf5 if self.output_format == "hdf5"
                         else self._async_writer)
        writer_thread = threading.Thread(target=writer_target, args=(data_queue,))
        writer_thread.start()

        begin = time.time()
        self.searchBox.findNegh()
        self.integrator.inteBegin()
        self.searchBox.applyPbc()
        end = time.time()
        print("compiling cost ", end - begin)

        if cs.PROFILER:
            ti.profiler.print_kernel_profiler_info('trace')
            ti.profiler.clear_kernel_profiler_info()

        begin = time.time()
        cal_store = 0

        for i in tqdm(range(self.runStep), desc="Simulation", unit="step"):
            self.searchBox.findNegh()
            self.integrator.inteBegin()
            self.searchBox.applyPbc()

            # write_stride: only capture every K-th step (default 1 = every step).
            if i % self.write_stride != 0:
                continue

            if ti.static(self.changeSize):
                if cal_store >= self.chunksize[self.chunkCal_Idx]:
                    n = self.chunksize[self.chunkCal_Idx]
                    data_queue.put([
                        self.data_pos.to_numpy()[:n],
                        self.data_vel.to_numpy()[:n],
                        self.data_T.to_numpy()[:n]
                    ])
                    self.data_pos.fill(0)
                    self.data_vel.fill(0)
                    self.data_T.fill(0)
                    self.chunkCal_Idx += 1
                    cal_store = 0

                self.copyData(cal_store)
                self.copyTemperature(cal_store)
                cal_store += 1

            else:
                if cal_store >= self.chunksize[0]:
                    data_queue.put([
                        self.data_pos.to_numpy(),
                        self.data_vel.to_numpy(),
                        self.data_T.to_numpy()
                    ])
                    self.data_pos.fill(0)
                    self.data_vel.fill(0)
                    self.data_T.fill(0)
                    cal_store = 0

                self.copyData(cal_store)
                self.copyTemperature(cal_store)
                cal_store += 1

        try:
            if cal_store != 0:
                data_queue.put([
                    self.data_pos.to_numpy()[:cal_store],
                    self.data_vel.to_numpy()[:cal_store],
                    self.data_T.to_numpy()[:cal_store]
                ])

            if cs.PROFILER:
                # Long runs (>1M steps) accumulate enough kernel records
                # that print_kernel_profiler_info can OOM. Don't let that
                # take down the writer cleanup (HDF5 close needs to run).
                try:
                    ti.profiler.print_kernel_profiler_info()
                except MemoryError as e:
                    print(f"[WARN] profiler print skipped (OOM): {e}")

            end = time.time()
            print("cost ", end - begin)
        finally:
            # Always signal writer to drain + close, even if anything above
            # threw. Without this, HDF5 file is left with no superblock
            # checksum and h5py refuses to reopen ("bad object header").
            data_queue.put(None)
            writer_thread.join()

        return

    def simuNoData(self):
        begin = time.time()

        for i in range(int(self.runStep)):
            self.searchBox.findNegh()
            # self.searchBox.debugNeighbors()
            self.integrator.inteBegin()
            print(f"{i}")

        end = time.time()
        print("cost ", end - begin)

        return None

    @ti.kernel
    def copyData(self, idx: int):
        for i in range(self.atomSystem.num_atoms):
            self.data_pos[idx, i] = self.atomSystem.pos[i]
            self.data_vel[idx, i] = self.atomSystem.vel[i]

        return

    def copyTemperature(self, idx: int):
        """先计算每粒子动力学温度，再拷贝到 data_T。"""
        self.atomSystem.computeTemperaturePerParticle()
        self._copyTToData(idx)

    @ti.kernel
    def _copyTToData(self, idx: int):
        for i in range(self.atomSystem.num_atoms):
            self.data_T[idx, i] = self.atomSystem.T_per_particle[i]

    @ti.kernel
    def copyEnergy(self, idx: int):
        self.data_ke[idx, 0] = self.atomSystem.KineticEnergy()
        self.data_pe[idx, 0] = self.atomSystem.pe[None]

        return

    def _async_writer(self, data_queue):
        # 大缓冲区加速大体系 xyz 写入（默认 8KB 对 500 帧×2000 粒子 极慢）
        with open(self.outputPath, 'w', buffering=2**20) as f:
            buffers = {"pos": [], "vel": [], "temp": []}
            frame_idx = 0

            while True:
                data = data_queue.get()
                if data is None:
                    if buffers["pos"]:
                        frame_idx = self._flush_buffers(f, buffers, frame_idx)
                    break

                buffers["pos"].extend(data[0])
                buffers["vel"].extend(data[1])
                buffers["temp"].extend(data[2])

                if len(buffers["pos"]) != 0:
                    frame_idx = self._flush_buffers(f, buffers, frame_idx)

    def _flush_buffers(self, f, buffers, frame_idx_start=0):
        """OVITO extended XYZ: ID, species, pos, vel, Temperature; per-frame Lattice + Time.

        Uses numpy.savetxt for batch C-level formatting (5-10x faster than per-particle
        f-strings for N>500). Caches invariant per-run state (group / box / dt) on first call.
        Returns the next frame_idx after writing all buffered frames.
        """
        num_atoms = self.atomSystem.num_atoms

        if not hasattr(self, '_writer_cache'):
            species = self.atomSystem.group.to_numpy().astype(np.int32)
            box = self.atomSystem.boxList.to_numpy()[0]   # 3x3 row-major
            lattice_str = " ".join(f"{box[i, j]:.6f}"
                                    for i in range(3) for j in range(3))
            ids = np.arange(1, num_atoms + 1, dtype=np.int32)
            self._writer_cache = {
                "species": species,
                "lattice_str": lattice_str,
                "ids": ids,
                # Effective dt between captured frames = physics dt × stride.
                "dt": float(self.integrator.delta_t) * self.write_stride,
            }
        cache = self._writer_cache

        properties = "Properties=ID:I:1:species:I:1:pos:R:3:vel:R:3:Temperature:R:1"
        fmt = "%d %d %.6f %.6f %.6f %.6f %.6f %.6f %.6f"

        frame_idx = frame_idx_start
        for pos, vel, temp in zip(buffers["pos"], buffers["vel"], buffers["temp"]):
            time_val = frame_idx * cache["dt"]
            f.write(f'{num_atoms}\n'
                    f'Lattice="{cache["lattice_str"]}" '
                    f'Time={time_val:.6f} {properties}\n')
            arr = np.column_stack([
                cache["ids"], cache["species"],
                pos[:, 0], pos[:, 1], pos[:, 2],
                vel[:, 0], vel[:, 1], vel[:, 2],
                temp,
            ])
            np.savetxt(f, arr, fmt=fmt)
            frame_idx += 1

        buffers["pos"].clear()
        buffers["vel"].clear()
        buffers["temp"].clear()
        return frame_idx

    def _async_writer_hdf5(self, data_queue):
        """Stream chunks into an HDF5 file with LZF-compressed extendable datasets.

        Layout:
            /pos      (n_frames, num_atoms, 3) float64  chunked + LZF
            /vel      (n_frames, num_atoms, 3) float64  chunked + LZF
            /T        (n_frames, num_atoms)    float64  chunked + LZF
            /time     (n_frames,)              float64
        Attrs on root: num_atoms, dt, write_stride, physics_dt
        Datasets:    /species (num_atoms,) int32, /box (3,3) float64

        Equivalent information to the OVITO XYZ but ~50x faster to write and
        ~10x smaller on disk for typical Hertzian / LJ runs.
        """
        static = self._writer_static
        num_atoms = static["num_atoms"]
        dt_per_frame = static["dt_per_frame"]
        species = static["species"]
        box = static["box"]

        chunk_rows = int(self.chunksize[0]) if not self.changeSize else 500
        with h5py.File(self.outputPath, "w") as h5:
            # Static metadata
            h5.attrs["num_atoms"] = num_atoms
            h5.attrs["dt"] = dt_per_frame
            h5.attrs["write_stride"] = self.write_stride
            h5.attrs["physics_dt"] = static["physics_dt"]
            h5.create_dataset("species", data=species)
            h5.create_dataset("box", data=box)

            # Extendable per-frame datasets
            ds_pos = h5.create_dataset(
                "pos", shape=(0, num_atoms, 3),
                maxshape=(None, num_atoms, 3),
                dtype=np.float64,
                chunks=(chunk_rows, num_atoms, 3),
                compression="lzf",
            )
            ds_vel = h5.create_dataset(
                "vel", shape=(0, num_atoms, 3),
                maxshape=(None, num_atoms, 3),
                dtype=np.float64,
                chunks=(chunk_rows, num_atoms, 3),
                compression="lzf",
            )
            ds_T = h5.create_dataset(
                "T", shape=(0, num_atoms),
                maxshape=(None, num_atoms),
                dtype=np.float64,
                chunks=(chunk_rows, num_atoms),
                compression="lzf",
            )
            ds_time = h5.create_dataset(
                "time", shape=(0,),
                maxshape=(None,),
                dtype=np.float64,
                chunks=(chunk_rows,),
            )

            frame_idx = 0
            while True:
                data = data_queue.get()
                if data is None:
                    break
                # data is [pos_chunk, vel_chunk, T_chunk] each (n_in_chunk, num_atoms, ...)
                pos_chunk = np.asarray(data[0], dtype=np.float64)
                vel_chunk = np.asarray(data[1], dtype=np.float64)
                T_chunk = np.asarray(data[2], dtype=np.float64)
                n_new = pos_chunk.shape[0]
                if n_new == 0:
                    continue
                old = ds_pos.shape[0]
                ds_pos.resize(old + n_new, axis=0)
                ds_vel.resize(old + n_new, axis=0)
                ds_T.resize(old + n_new, axis=0)
                ds_time.resize(old + n_new, axis=0)
                ds_pos[old:old + n_new] = pos_chunk
                ds_vel[old:old + n_new] = vel_chunk
                ds_T[old:old + n_new] = T_chunk
                ds_time[old:old + n_new] = (
                    np.arange(frame_idx, frame_idx + n_new) * dt_per_frame
                )
                frame_idx += n_new


class systemRun:
    def __init__(self, paramFile, coorFile):
        num_atoms, positions, masses, lattice_params, groups = \
            fileOperator.read_inputPos(coorFile)
        params = fileOperator.read_inputParams(paramFile)

        # Apply run.in flags BEFORE any AtomSystem field allocation.
        cs.reconfigure(
            units=params["units"],
            log=params["log"],
            debug=params["debug"],
            profiler=params["profiler"],
        )

        self.num_atoms = num_atoms
        self.positions = positions
        self.masses = masses
        self.boxList = lattice_params
        self.groups = groups
        self.temperature = params["velocity"]
        self.timeStep = params["time_step"]
        self.runStep = params["run"]
        self.ndim = params["dimension"]
        self.nu = params["nu"]
        return

    def initParams(self, fFieldParams, atomParams={}, inteParams={},
                   simuParams={}, boxParams={}):
        atomParams.update({"num_atoms": self.num_atoms})
        atomParams.update({"ndim": self.ndim})
        atomParams.update({"groups": self.groups})
        inteParams.update({"timeStep": self.timeStep
                           / cs.UNITS.TIME_UNIT_CONVERSION})
        # Use run.in nu if caller didn't override
        inteParams.setdefault("nu", self.nu)
        simuParams.update({"runStep": self.runStep})

        # full_list driven by ForceField.requires_full_list — do not set here.

        self.atomParams = atomParams
        self.inteParams = inteParams
        self.simuParams = simuParams
        self.fFieldParams = fFieldParams
        self.boxParams = boxParams
        return

    def _printDebugInfo(self, Atom):
        """调试模式：打印所有参数，不执行模拟。"""
        print("=" * 60)
        print("[DEBUG] System Parameters")
        print("=" * 60)
        print(f"num_atoms: {self.num_atoms}")
        print(f"boxList: {self.boxList}")
        print(f"ndim: {self.ndim}")
        print(f"temperature: {self.temperature}")
        print(f"timeStep: {self.timeStep}")
        print(f"runStep: {self.runStep}")
        print(f"atomParams: {self.atomParams}")
        print(f"boxParams: {self.boxParams}")
        print(f"fFieldParams: {self.fFieldParams}")
        print(f"inteParams: {self.inteParams}")
        if hasattr(self, "groups") and self.groups is not None:
            unique, counts = np.unique(self.groups, return_counts=True)
            print(f"groups: {dict(zip(unique.tolist(), counts.tolist()))}")
        print("=" * 60)

    def register(self, atomSystem, integrator, simulator, forceField, searchBox):
        self.atomSystem = atomSystem
        self.integrator = integrator
        self.simulator = simulator
        self.forceField = forceField
        self.searchBox = searchBox

        return

    def runWithData(self, outputPath="outputData.xyz", withData=False):
        # AtomSystem 构造函数仅接受 num_atoms, n, cutoff, ndim；groups 通过 initData 传入
        _ctor_params = {k: v for k, v in self.atomParams.items() if k not in ('groups',)}
        Atom = self.atomSystem(**_ctor_params)
        Atom.initData(self.positions, self.masses, self.temperature, self.boxList, self.groups)

        seaBox = self.searchBox(**self.boxParams)
        fField = self.forceField(**self.fFieldParams)
        seaBox.register(atomSystem=Atom, forceField=fField)
        fField.register(atomSystem=Atom, searchBox=seaBox)

        inte = self.integrator(**self.inteParams)
        inte.register(atomSystem=Atom, forceField=fField)

        simu = self.simulator(**self.simuParams)
        simu.register(atomSystem=Atom, forceField=fField, integrator=inte, searchBox=seaBox)

        if cs.LOG:
            self._printDebugInfo(Atom)
        if withData:
            simu.simuWithData(outputPath)
        else:
            simu.simuNoData()

        return
