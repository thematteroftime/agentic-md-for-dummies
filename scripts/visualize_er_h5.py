#!/usr/bin/env python3
"""GPU-accelerated trajectory animation for ER plasma HDF5 outputs.

Uses Taichi 1.7.4 ti.ui (Vulkan/D3D backend) — renders N≈10⁴ particles at 60+ FPS,
no plotly/matplotlib bottleneck. Loads the entire HDF5 frame list into a Taichi
field once, then per-frame just rebinds positions (zero-copy from numpy).

Controls:
    SPACE     play/pause
    ← / →     step ±1 frame (when paused)
    ↑ / ↓     speed up / slow down playback (1× → 64×)
    R         restart from frame 0
    H         toggle help overlay
    C         cycle color mode: index → z-position → speed → chain-membership
    B         toggle box outline
    F         toggle E-field arrow
    + / -     zoom in / out (10% per press)
    [ / ]     shrink / grow particle render radius
    V         reset camera to default isometric view
    T         switch to top-down view (along z, looking from +z)
    Y         switch to side view (looking along +x, z vertical)
    W A S D   first-person walk (relative to camera, hold for continuous motion)
    Q E       move down / up
    ESC       quit
    mouse     right-drag to orbit (yaw/pitch around lookat)

Examples:
    # Auto-pick the .h5 in a run dir
    python scripts/visualize_er_h5.py outputFiles/20260507_142444_ER4L_MT08

    # Direct .h5 path
    python scripts/visualize_er_h5.py path/to/ER_plasma_*.h5

    # Compare two runs side-by-side (one window, two scenes)
    python scripts/visualize_er_h5.py runA runB --compare

    # Headless render to mp4
    python scripts/visualize_er_h5.py runDir --record movie.mp4 --fps 60
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import h5py
import numpy as np
import taichi as ti


def find_h5(arg: str) -> Path:
    p = Path(arg)
    if p.is_file() and p.suffix == ".h5":
        return p
    if p.is_dir():
        cands = sorted(p.glob("*.h5"))
        if not cands:
            raise FileNotFoundError(f"No .h5 in {p}")
        return cands[0]
    raise FileNotFoundError(arg)


def load_h5(path: Path):
    """Returns (positions [F,N,3] float32, time [F] float64, box [3] float32, meta dict)."""
    with h5py.File(path, "r") as f:
        pos = f["pos"][...].astype(np.float32)
        t = f["time"][...].astype(np.float64) if "time" in f else np.arange(len(pos))
        if "box" in f:
            box = np.asarray(f["box"], dtype=np.float32)
        elif "boxList" in f:
            box = np.asarray(f["boxList"], dtype=np.float32)
        else:
            box = (pos.max(axis=(0, 1)) - pos.min(axis=(0, 1))).astype(np.float32)
        meta = {k: f.attrs[k] for k in f.attrs.keys()} if hasattr(f, "attrs") else {}
    if box.ndim == 2:
        diag = np.array([box[0, 0], box[1, 1], box[2, 2]], dtype=np.float32)
        if (diag > 0).all():
            box = diag
        else:
            box = np.linalg.norm(box, axis=1).astype(np.float32)
    if box.size == 1:
        box = np.array([box.item()] * 3, dtype=np.float32)
    return pos, t, box, meta


def precompute_speed(pos: np.ndarray, dt_unit: float = 1.0) -> np.ndarray:
    """|v| at each frame from finite-difference. shape [F,N]."""
    F = len(pos)
    v = np.zeros((F, pos.shape[1]), dtype=np.float32)
    if F > 1:
        v[1:] = np.linalg.norm(pos[1:] - pos[:-1], axis=2) / max(dt_unit, 1e-12)
        v[0] = v[1]
    return v


def chain_membership(pos_frame: np.ndarray, r_max: float, theta_deg: float) -> np.ndarray:
    """Boolean: particle has at least one neighbor within angular cone of E-axis (z) and r<r_max."""
    N = len(pos_frame)
    cos_t = np.cos(np.deg2rad(theta_deg))
    diff = pos_frame[:, None, :] - pos_frame[None, :, :]
    r2 = (diff ** 2).sum(axis=2)
    np.fill_diagonal(r2, np.inf)
    r = np.sqrt(r2)
    cos = np.abs(diff[..., 2]) / (r + 1e-12)
    in_cone = (cos > cos_t) & (r < r_max)
    return in_cone.any(axis=1)


def build_box_lines(box: np.ndarray) -> np.ndarray:
    """12 edges of a box centered at origin with extents ±box/2. Returns [24, 3]."""
    bx, by, bz = box / 2
    corners = np.array([(sx * bx, sy * by, sz * bz)
                        for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
                        dtype=np.float32)
    edges = []
    for i in range(8):
        for j in range(i + 1, 8):
            d = corners[i] - corners[j]
            if np.count_nonzero(np.abs(d) > 1e-6) == 1:
                edges.append(corners[i]); edges.append(corners[j])
    return np.asarray(edges, dtype=np.float32)


def color_from_mode(mode: str, frame_pos: np.ndarray, idx_color: np.ndarray,
                    speed_at_frame: np.ndarray, chain_mask: np.ndarray) -> np.ndarray:
    if mode == "index":
        return idx_color
    if mode == "z":
        z = frame_pos[:, 2]
        zn = (z - z.min()) / max(z.max() - z.min(), 1e-12)
        c = np.zeros((len(z), 3), dtype=np.float32)
        c[:, 0] = zn
        c[:, 1] = 0.4 + 0.4 * (1 - zn)
        c[:, 2] = 1 - zn
        return c
    if mode == "speed":
        v = speed_at_frame
        vn = np.clip(v / max(np.percentile(v, 95), 1e-12), 0, 1)
        c = np.zeros((len(v), 3), dtype=np.float32)
        c[:, 0] = vn
        c[:, 1] = 0.6 * (1 - vn)
        c[:, 2] = 1 - vn
        return c
    if mode == "chain":
        c = np.tile(np.array([0.4, 0.4, 0.5], dtype=np.float32), (len(frame_pos), 1))
        c[chain_mask] = np.array([1.0, 0.4, 0.1], dtype=np.float32)
        return c
    return idx_color


def run(h5_path: Path, args):
    ti.init(arch=ti.cuda, default_fp=ti.f32)
    print(f"[viz] loading {h5_path}")
    pos, t, box, meta = load_h5(h5_path)
    F, N, _ = pos.shape
    print(f"[viz] {F} frames × {N} atoms, box ≈ {box.tolist()}")

    pos -= pos.mean(axis=(0, 1))
    box_lines_np = build_box_lines(box)

    dt_unit = float(t[1] - t[0]) if F > 1 else 1.0
    print(f"[viz] dt between frames = {dt_unit:.4g} (assumed time unit = ms)")

    speed_all = precompute_speed(pos, dt_unit)

    rng = np.random.default_rng(0)
    idx_color = rng.uniform(0.3, 1.0, size=(N, 3)).astype(np.float32)

    particles = ti.Vector.field(3, dtype=ti.f32, shape=N)
    particle_color = ti.Vector.field(3, dtype=ti.f32, shape=N)
    box_lines = ti.Vector.field(3, dtype=ti.f32, shape=len(box_lines_np))
    box_lines.from_numpy(box_lines_np)
    arrow_pts = ti.Vector.field(3, dtype=ti.f32, shape=2)
    arrow_pts.from_numpy(np.array([[0, 0, -box[2] / 2 * 1.2],
                                    [0, 0,  box[2] / 2 * 1.2]], dtype=np.float32))

    radius_world = float(0.012 * np.linalg.norm(box))
    print(f"[viz] particle render radius = {radius_world:.4g}")

    title = f"ER plasma trajectory — {h5_path.name}"
    window = ti.ui.Window(title, (1280, 800), vsync=True, show_window=not args.record)
    canvas = window.get_canvas()
    canvas.set_background_color((0.05, 0.05, 0.08))
    scene = window.get_scene()
    camera = ti.ui.Camera()
    cam_dist = float(np.linalg.norm(box) * 1.6)

    def _set_iso():
        camera.position(cam_dist, cam_dist * 0.6, cam_dist)
        camera.lookat(0, 0, 0)
        camera.up(0, 0, 1)

    def _set_top():
        camera.position(0, 0, cam_dist * 1.4)
        camera.lookat(0, 0, 0)
        camera.up(0, 1, 0)

    def _set_side():
        camera.position(cam_dist * 1.4, 0, 0)
        camera.lookat(0, 0, 0)
        camera.up(0, 0, 1)

    _set_iso()

    state = {
        "frame": 0,
        "playing": True,
        "speed": 1,
        "color_mode": "index",
        "show_box": True,
        "show_field": True,
        "show_help": True,
        "zoom": 1.0,
        "radius_mul": 1.0,
    }
    color_modes = ["index", "z", "speed", "chain"]

    if args.record:
        try:
            import imageio.v2 as imageio
        except Exception:
            print("ERROR: --record requires imageio (pip install imageio imageio-ffmpeg)")
            sys.exit(1)
        writer = imageio.get_writer(args.record, fps=args.fps, quality=8)
        record_max_frames = F
    else:
        writer = None

    chain_r_max = float(0.5 * np.linalg.norm(box) / max(N ** (1 / 3), 1) * 2.0)
    chain_theta = 30.0

    accum = 0.0
    while window.running:
        for e in window.get_events(ti.ui.PRESS):
            if e.key == ti.ui.ESCAPE:
                window.running = False
            elif e.key == ti.ui.SPACE:
                state["playing"] = not state["playing"]
            elif e.key == ti.ui.LEFT:
                state["frame"] = max(0, state["frame"] - 1)
                state["playing"] = False
            elif e.key == ti.ui.RIGHT:
                state["frame"] = min(F - 1, state["frame"] + 1)
                state["playing"] = False
            elif e.key == ti.ui.UP:
                state["speed"] = min(64, max(1, state["speed"] * 2))
            elif e.key == ti.ui.DOWN:
                state["speed"] = max(1, state["speed"] // 2)
            elif e.key == "r":
                state["frame"] = 0
            elif e.key == "h":
                state["show_help"] = not state["show_help"]
            elif e.key == "c":
                i = (color_modes.index(state["color_mode"]) + 1) % len(color_modes)
                state["color_mode"] = color_modes[i]
            elif e.key == "b":
                state["show_box"] = not state["show_box"]
            elif e.key == "f":
                state["show_field"] = not state["show_field"]
            elif e.key in ("=", "+"):
                state["zoom"] = max(0.05, state["zoom"] * 0.9)
            elif e.key == "-":
                state["zoom"] = min(10.0, state["zoom"] / 0.9)
            elif e.key == "[":
                state["radius_mul"] = max(0.1, state["radius_mul"] * 0.8)
            elif e.key == "]":
                state["radius_mul"] = min(8.0, state["radius_mul"] / 0.8)
            elif e.key == "v":
                _set_iso(); state["zoom"] = 1.0
            elif e.key == "t":
                _set_top(); state["zoom"] = 1.0
            elif e.key == "y":
                _set_side(); state["zoom"] = 1.0

        if state["playing"]:
            accum += state["speed"]
            while accum >= 1.0:
                state["frame"] = (state["frame"] + 1) % F
                accum -= 1.0

        i = state["frame"]
        cur = pos[i]
        particles.from_numpy(cur)

        if state["color_mode"] == "chain":
            cm = chain_membership(cur, chain_r_max, chain_theta)
        else:
            cm = np.zeros(N, dtype=bool)
        col = color_from_mode(state["color_mode"], cur, idx_color, speed_all[i], cm)
        particle_color.from_numpy(col)

        if not args.record:
            camera.track_user_inputs(window, movement_speed=cam_dist * 0.02,
                                     hold_key=ti.ui.RMB)
        cur_pos = camera.curr_position
        cur_look = camera.curr_lookat
        zoomed_pos = cur_look + (cur_pos - cur_look) * state["zoom"]
        camera.position(zoomed_pos[0], zoomed_pos[1], zoomed_pos[2])
        scene.set_camera(camera)
        scene.ambient_light((0.5, 0.5, 0.5))
        scene.point_light(pos=(cam_dist, cam_dist, cam_dist), color=(1, 1, 1))

        scene.particles(particles, radius=radius_world * state["radius_mul"],
                         per_vertex_color=particle_color)
        if state["show_box"]:
            scene.lines(box_lines, color=(0.6, 0.6, 0.7), width=1.5)
        if state["show_field"]:
            scene.lines(arrow_pts, color=(0.2, 0.9, 0.4), width=3.0)
        canvas.scene(scene)

        win = window.get_gui()
        win.text(f"frame {i+1}/{F}    t = {t[i]:.3g}    speed × {state['speed']}   "
                 f"{'PLAY' if state['playing'] else 'PAUSE'}    color={state['color_mode']}    "
                 f"zoom × {1/state['zoom']:.2f}    rsize × {state['radius_mul']:.2f}")
        if state["show_help"]:
            win.text("SPACE play/pause  ←/→ step  ↑/↓ speed  +/- zoom  [/] particle size")
            win.text("V iso  T top  Y side  C color  B box  F field  R restart  H help  ESC quit")
            win.text("right-drag to orbit, WASDQE to fly through the box")

        if writer is not None:
            img = window.get_image_buffer_as_numpy()
            img8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
            writer.append_data(img8)
            if i + 1 >= record_max_frames or not state["playing"]:
                pass
            if i + 1 == F:
                window.running = False

        window.show()

    if writer is not None:
        writer.close()
        print(f"[viz] wrote {args.record}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", help="Run directory (auto-find .h5) or .h5 file")
    p.add_argument("--record", default=None,
                   help="Render to mp4 instead of interactive window")
    p.add_argument("--fps", type=int, default=60, help="mp4 fps (default 60)")
    p.add_argument("--compare", action="store_true",
                   help="(reserved) side-by-side compare two runs")
    args, extras = p.parse_known_args()
    h5 = find_h5(args.path)
    run(h5, args)


if __name__ == "__main__":
    main()
