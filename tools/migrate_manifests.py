"""Backfill canonical §3.2 fields into older manifests.

Some adapters initially wrote only paper-specific names (e.g. `T0_star`,
`T0_K`, `dt_ms`, `nu_inv_ms`). This tool adds the canonical aliases
(`T0`, `dt`, `nu`, `force_class`, `units`, ...) in-place WITHOUT removing
the original keys.

Idempotent — running twice is a no-op.

Usage:
    python tools/migrate_manifests.py             # dry-run (show changes)
    python tools/migrate_manifests.py --apply     # write changes
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paper-specific name → canonical name map. Order matters: first existing key wins.
ALIAS_MAP = {
    "force_class": [],     # filled by run_type lookup below
    "units":       [],     # ditto
    "T0":          ["T0_star", "T0_K"],
    "dt":          ["dt", "dt_ms"],
    "nu":          ["nu", "nu_inv_ms"],
    "N":           ["N", "N_A"],   # N_A only — total = 2*N_A; we record per-species
}

RUN_TYPE_TO_FORCE_CLASS = {
    "prx": "HertzianNonreciprocal",
    "prx_nonreciprocal": "HertzianNonreciprocal",
    "hertzian_nonreciprocal": "HertzianNonreciprocal",
    "er_plasma": "ERPotential",
}

RUN_TYPE_TO_UNITS = {
    "hertzian_nonreciprocal": "reduced",
    "prx": "reduced",
    "prx_nonreciprocal": "reduced",
    "er_plasma": "macro",
}


def infer_run_type(m: dict) -> str | None:
    """Infer run_type from manifest content if not explicit."""
    if m.get("run_type"):
        return m["run_type"]
    if "MT" in m or "Z_eff" in m or "lambda_screen_mm" in m:
        return "er_plasma"
    if "phi_target" in m or "T0_star" in m:
        return "hertzian_nonreciprocal"
    return None


def backfill(m: dict) -> tuple[dict, list[str]]:
    """Return (new_manifest, list_of_changes). Does not modify input."""
    out = dict(m)
    changes = []

    # 1. run_type
    rt = infer_run_type(out)
    if rt and not out.get("run_type"):
        out["run_type"] = rt
        changes.append(f"run_type ← '{rt}' (inferred)")
    rt = out.get("run_type")

    # 2. force_class
    if not out.get("force_class") and rt in RUN_TYPE_TO_FORCE_CLASS:
        out["force_class"] = RUN_TYPE_TO_FORCE_CLASS[rt]
        changes.append(f"force_class ← '{out['force_class']}'")

    # 3. units
    if not out.get("units") and rt in RUN_TYPE_TO_UNITS:
        out["units"] = RUN_TYPE_TO_UNITS[rt]
        changes.append(f"units ← '{out['units']}'")

    # 4. canonical numeric aliases
    for canonical, sources in ALIAS_MAP.items():
        if canonical in out and out[canonical] is not None:
            continue
        for src in sources:
            if src in out and out[src] is not None:
                out[canonical] = out[src]
                changes.append(f"{canonical} ← {src}={out[src]} (alias)")
                break

    # 5. actual_step_rate: compute from steps/wall_seconds if missing
    if not out.get("actual_step_rate"):
        steps = out.get("steps")
        wall = out.get("wall_seconds")
        if isinstance(steps, (int, float)) and isinstance(wall, (int, float)) and wall > 0:
            rate = steps / wall
            out["actual_step_rate"] = rate
            changes.append(f"actual_step_rate ← {rate:.2f} step/s (computed from steps/wall)")

    return out, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="outputFiles")
    ap.add_argument("--apply", action="store_true",
                    help="write changes (default: dry-run)")
    args = ap.parse_args()

    root = ROOT / args.path if not Path(args.path).is_absolute() else Path(args.path)
    manifests = sorted(root.rglob("manifest.json"))
    if not manifests:
        print(f"no manifest.json under {root}")
        return

    total_changes = 0
    files_touched = 0
    for mp in manifests:
        m = json.loads(mp.read_text(encoding="utf-8"))
        new, changes = backfill(m)
        if changes:
            files_touched += 1
            total_changes += len(changes)
            print(f"{mp.relative_to(ROOT)}:")
            for c in changes:
                print(f"  + {c}")
            if args.apply:
                mp.write_text(json.dumps(new, indent=2), encoding="utf-8")
    print()
    if args.apply:
        print(f"applied {total_changes} changes across {files_touched} manifests")
    else:
        print(f"dry-run: {total_changes} changes across {files_touched} manifests "
              f"(re-run with --apply to write)")


if __name__ == "__main__":
    main()
