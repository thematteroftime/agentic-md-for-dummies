from constSet import *
import io
from tempfile import NamedTemporaryFile
from concurrent.futures import ProcessPoolExecutor
import os


def _bool(s):
    s = s.strip().lower()
    if s in ("on", "true", "1", "yes"):
        return True
    if s in ("off", "false", "0", "no"):
        return False
    raise ValueError(f"invalid bool: {s}")


def _dim(s):
    n = int(s)
    if n not in (2, 3):
        raise ValueError(f"dimension must be 2 or 3, got {n}")
    return n


_PARSERS = {
    "velocity":  float,
    "time_step": float,
    "run":       int,
    "dimension": _dim,
    "units":     str,
    "log":       _bool,
    "debug":     _bool,
    "profiler":  _bool,
    "nu":        float,
}

_DEFAULTS = {
    "dimension": 3,
    "units":     "macro",
    "log":       False,
    "debug":     False,
    "profiler":  False,
    "nu":        0.0,
}

_REQUIRED = {"velocity", "time_step", "run"}


@ti.data_oriented
class fileOperator:
    @staticmethod
    def read_inputPos(filename):
        """
        读取 .xyz 坐标文件。
        第一列解析为粒子名称（name），按首次出现顺序映射为 group_id (1, 2, 3, ...)。
        若无名称区分则 groups 全为 1。

        Returns:
            num_atoms, positions, masses, lattice_params, groups
        """
        with open(filename, 'r') as f:
            num_atoms = int(f.readline().strip())
            lattice_params = list(map(float, f.readline().strip().split()))

            positions = []
            masses = []
            names = []
            name_to_id = {}
            next_id = 1
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    name = parts[0]
                    x, y, z = map(float, parts[1:4])
                    mass = float(parts[4])
                    positions.append([x, y, z])
                    masses.append(mass)
                    if name not in name_to_id:
                        name_to_id[name] = next_id
                        next_id += 1
                    names.append(name_to_id[name])

            positions = np.array(positions)
            masses = np.array(masses)
            groups = np.array(names, dtype=np.int32)

        return num_atoms, positions, masses, lattice_params, groups

    @staticmethod
    def read_inputParams(filename):
        """Parse run.in as key/value pairs. Returns a dict.

        Required: velocity, time_step, run.
        Defaults: dimension=3, units=macro, log=off, debug=off,
                  profiler=off, nu=0.0.
        """
        out = dict(_DEFAULTS)
        seen = set()
        with open(filename, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                tokens = line.split()
                if len(tokens) < 2:
                    continue
                key, val = tokens[0], tokens[1]
                if key not in _PARSERS:
                    raise ValueError(f"unknown keyword in run.in: {key}")
                out[key] = _PARSERS[key](val)
                seen.add(key)
        missing = _REQUIRED - seen
        if missing:
            raise ValueError(
                f"run.in missing required keys: {sorted(missing)}")
        return out

    @staticmethod
    def writeOutputFile(pos, vel, K_E, P_E, boxList, filePath='simulation_output.txt'):
        frames, num_particles = pos.shape[0], pos.shape[1]
        output_lines = []

        output_lines.append(f'{frames} # frames\n')
        output_lines.append(f'{num_particles} # num_particles\n')
        output_lines.append(
            f'{boxList[0]} {boxList[1]} {boxList[2]} {boxList[3]} {boxList[4]} {boxList[5]} {boxList[6]} {boxList[7]} {boxList[8]} # boxList\n\n')

        for frame in range(frames):
            output_lines.append(f'#第{frame + 1}帧数据\n')
            output_lines.append(f'{K_E[frame]} {P_E[frame]}\n')

            frame_data = np.hstack((pos[frame], vel[frame]))

            frame_strings = [' '.join(map(str, particle_data)) + '\n' for particle_data in frame_data]
            output_lines.extend(frame_strings)
            output_lines.append('\n')

        # 一次性写入文件
        with open(filePath, 'w') as f:
            f.writelines(output_lines)

    @staticmethod
    def readOutputFile(filePath):
        frames_data = []
        with open(filePath, 'r') as f:
            frames_line = f.readline()
            num_frames = int(frames_line.strip().split()[0])

            num_particles_line = f.readline()
            num_particles = int(num_particles_line.strip().split()[0])

            boxList_line = f.readline()
            boxList = list(map(float, boxList_line.strip().split()[:3]))

            f.readline()  # 跳过空行

            while True:
                line = f.readline()
                if not line:
                    break  # 文件结束
                if line.startswith('#'):
                    frame_info = {}
                    # 跳过 "第X帧数据" 行
                    K_E_line = f.readline()
                    K_E, P_E = map(float, K_E_line.strip().split())
                    frame_info['K_E'] = K_E
                    frame_info['P_E'] = P_E

                    positions = []
                    velocities = []
                    for _ in range(num_particles):
                        data_line = f.readline()
                        x, y, z, vx, vy, vz = map(float, data_line.strip().split())
                        positions.append([x, y, z])
                        velocities.append([vx, vy, vz])
                    frame_info['pos'] = np.array(positions)
                    frame_info['vel'] = np.array(velocities)
                    frames_data.append(frame_info)

                    f.readline()  # 跳过空行
                else:
                    continue  # 跳过其他非预期的行

        return frames_data, boxList

    @staticmethod
    def writeOutputFile_npz(pos, vel, K_E, P_E, boxList, filePath='simulation_output.npz'):
        np.savez(filePath, pos=pos, vel=vel, K_E=K_E, P_E=P_E, boxList=boxList)
        return

    @staticmethod
    def readOutputFile_npz(filePath):
        data = np.load(filePath)
        pos = data['pos']
        vel = data['vel']
        K_E = data['K_E']
        P_E = data['P_E']
        boxList = data['boxList']
        return pos, vel, K_E, P_E, boxList

    @staticmethod
    def writeOutputFile_hdf5(pos, vel, K_E, P_E, boxList, filePath='simulation_output.h5'):
        with h5py.File(filePath, 'w') as f:
            f.create_dataset('pos', data=pos)
            f.create_dataset('vel', data=vel)
            f.create_dataset('K_E', data=K_E)
            f.create_dataset('P_E', data=P_E)
            f.create_dataset('boxList', data=boxList)

    @staticmethod
    def readOutputFile_hdf5(filePath):
        with h5py.File(filePath, 'r') as f:
            pos = f['pos'][:]
            vel = f['vel'][:]
            K_E = f['K_E'][:]
            P_E = f['P_E'][:]
            boxList = f['boxList'][:]
        return pos, vel, K_E, P_E, boxList

    @staticmethod
    def read_xyz_with_temperature(xyz_path):
        """
        读取 OVITO 兼容的 extended XYZ（含 Temperature 列）。
        Properties=ID:I:1:pos:R:3:vel:R:3:Temperature:R:1

        Returns:
            num_frames (int)
            num_atoms (int)
            pos (np.ndarray): (num_frames, num_atoms, 3)
            vel (np.ndarray): (num_frames, num_atoms, 3)
            T (np.ndarray): (num_frames, num_atoms) 每粒子动力学温度
        """
        frames_pos, frames_vel, frames_T = [], [], []
        with open(xyz_path, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                num_atoms = int(line.strip())
                props = f.readline().strip()
                has_T = 'Temperature' in props
                # Layouts:
                #   legacy: ID  x y z  vx vy vz  [Temperature]
                #   v2    : ID species  x y z  vx vy vz  Temperature
                has_species = 'species' in props
                pos_off = 2 if has_species else 1
                vel_off = pos_off + 3
                t_off = vel_off + 3
                pos_f, vel_f, T_f = [], [], []
                for _ in range(num_atoms):
                    parts = f.readline().strip().split()
                    if has_T and len(parts) >= t_off + 1:
                        pos_f.append([float(parts[pos_off]),
                                      float(parts[pos_off + 1]),
                                      float(parts[pos_off + 2])])
                        vel_f.append([float(parts[vel_off]),
                                      float(parts[vel_off + 1]),
                                      float(parts[vel_off + 2])])
                        T_f.append(float(parts[t_off]))
                    elif len(parts) >= vel_off + 3:
                        pos_f.append([float(parts[pos_off]),
                                      float(parts[pos_off + 1]),
                                      float(parts[pos_off + 2])])
                        vel_f.append([float(parts[vel_off]),
                                      float(parts[vel_off + 1]),
                                      float(parts[vel_off + 2])])
                        T_f.append(np.nan)
                frames_pos.append(pos_f)
                frames_vel.append(vel_f)
                frames_T.append(T_f)
        num_frames = len(frames_pos)
        if num_frames == 0:
            return 0, 0, np.array([]), np.array([]), np.array([])
        pos = np.array(frames_pos)
        vel = np.array(frames_vel)
        T = np.array(frames_T)
        n_atoms = pos.shape[1]
        return num_frames, n_atoms, pos, vel, T

    @staticmethod
    def writeOutputFile_xyz(pos, vel, xyzPath='outputXYZ.xyz'):
        """
        将NumPy数组直接转换为OVITO兼容的XYZ文件

        Args:
            xyzPath (str): path
            pos (np.ndarray): (frames, num_atoms, 3)
            vel (np.ndarray): (frames, num_atoms, 3)
        """
        num_frames = pos.shape[0]
        num_atoms = pos.shape[1]

        with open(xyzPath, "w") as f2:
            for frame_idx in range(num_frames):
                coordinates = pos[frame_idx]  # (num_atoms, 3)
                velocities = vel[frame_idx]  # (num_atoms, 3)

                combined_data = np.hstack((coordinates, velocities))

                f2.write(f"{num_atoms}\n")
                f2.write(
                    "Properties=Position.x:R:6:3:Position.y:R:6:3:Position.z:R:6:3:Velocity.x:R:6:3:Velocity.y:R:6:3:Velocity.z:R:6:3\n")
                np.savetxt(f2, combined_data, fmt="%.6f %.6f %.6f %.6f %.6f %.6f")

        return

    @staticmethod
    def h5py2XYZ(h5Path, xyzPath):
        with h5py.File(h5Path, "r") as f:
            pos_dataset = f["pos"]
            vel_dataset = f["vel"]
            num_frames = pos_dataset.shape[0]

            with open(xyzPath, "w") as f2:
                for frame_idx in range(num_frames):
                    coordinates = pos_dataset[frame_idx]  # (32000,3)
                    velocities = vel_dataset[frame_idx]  # (32000,3)

                    combined_data = np.hstack((coordinates, velocities))  # 形状 (32000,6)

                    f2.write(f"{coordinates.shape[0]}\n")  # 粒子数
                    f2.write(
                        "Properties=Position.x:R:6:3:Position.y:R:6:3:Position.z:R:6:3:Velocity.x:R:6:3:Velocity.y:R:6:3:Velocity.z:R:6:3\n")
                    np.savetxt(f2, combined_data, fmt="%.6f %.6f %.6f %.6f %.6f %.6f")
        return

    @staticmethod
    def h5py2XYZ_chunked(h5Path, xyzPath, chunk_size=100):
        with h5py.File(h5Path, "r", rdcc_nslots=100 * chunk_size, rdcc_nbytes=16 * 1024 * 1024 * chunk_size) as f:
            pos_dataset = f["pos"]
            vel_dataset = f["vel"]
            num_frames = pos_dataset.shape[0]
            num_atoms = pos_dataset.shape[1]
            header_line = "Properties=Position.x:R:6:3:Position.y:R:6:3:Position.z:R:6:3:Velocity.x:R:6:3:Velocity.y:R:6:3:Velocity.z:R:6:3\n"

            with open(xyzPath, "w") as f2:
                buffer = io.StringIO()
                for start_idx in range(0, num_frames, chunk_size):
                    end_idx = min(start_idx + chunk_size, num_frames)
                    # 分块读取数据 [[4]][[9]]
                    pos_chunk = pos_dataset[start_idx:end_idx]  # (chunk_size, num_atoms, 3)
                    vel_chunk = vel_dataset[start_idx:end_idx]

                    # 合并并逐帧处理 [[2]][[8]]
                    for frame_idx in range(pos_chunk.shape[0]):
                        combined = np.hstack((pos_chunk[frame_idx], vel_chunk[frame_idx]))

                        buffer.write(f"{num_atoms}\n")
                        buffer.write(header_line)
                        np.savetxt(buffer, combined, fmt="%.6f %.6f %.6f %.6f %.6f %.6f")

                        # 缓冲区达到阈值时写入文件 [[5]]
                        if buffer.tell() > 1e8:  # 100MB
                            f2.write(buffer.getvalue())
                            buffer.seek(0)
                            buffer.truncate()

                # 写入剩余数据
                f2.write(buffer.getvalue())
        return

    @staticmethod
    def process_chunk(pos_chunk, vel_chunk, num_atoms, header_line):
        """将单个数据块写入临时文件"""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".xyz") as f:
            for frame_idx in range(pos_chunk.shape[0]):
                combined = np.hstack((pos_chunk[frame_idx], vel_chunk[frame_idx]))
                f.write(f"{num_atoms}\n{header_line}")
                np.savetxt(f, combined, fmt="%.6f %.6f %.6f %.6f %.6f %.6f")
            return f.name

    def split_to_temp_files(self, h5Path, chunk_size=100):
        """分批次生成临时文件"""
        temp_files = []
        with h5py.File(h5Path, "r") as f:
            pos = f["pos"]
            vel = f["vel"]
            num_frames = pos.shape[0]
            num_atoms = pos.shape[1]
            header_line = "Properties=Position.x:R:6:3:Position.y:R:6:3:Position.z:R:6:3:Velocity.x:R:6:3:Velocity.y:R:6:3:Velocity.z:R:6:3\n"

            # 并行处理数据块 [[9]][[10]]
            with ProcessPoolExecutor() as executor:
                futures = []
                for start in range(0, num_frames, chunk_size):
                    end = min(start + chunk_size, num_frames)
                    pos_chunk = pos[start:end]
                    vel_chunk = vel[start:end]
                    future = executor.submit(self.process_chunk, pos_chunk, vel_chunk, num_atoms, header_line)
                    futures.append(future)

                # 收集临时文件路径
                for future in futures:
                    temp_files.append(future.result())
        return temp_files

    @staticmethod
    def merge_files(temp_files, output_path):
        """合并临时文件到最终输出"""
        with open(output_path, "w") as f_out:
            for temp_file in temp_files:
                with open(temp_file, "r") as f_in:
                    f_out.write(f_in.read())
                # 删除临时文件 [[6]]
                os.remove(temp_file)

    def h5py2XYZ_chunked_parallel(self, h5Path, xyzPath, chunk_size=100):
        temp_files = self.split_to_temp_files(h5Path, chunk_size)
        self.merge_files(temp_files, xyzPath)


# ---------------------------------------------------------------------------
# PRX 2015 reproduction toolkit — analysis, plotting, run lifecycle.
#
# These classes consolidate logic that used to live in N one-off scripts under
# scripts/. The rule going forward:
#   - any new analysis primitive lives here, not in a fresh script
#   - scripts/ contains only thin entry points + standalone tools
#
# Pure Python (numpy + h5py + matplotlib). No Taichi dependency, so they can
# run in environments that don't have a GPU.
# ---------------------------------------------------------------------------

