"""Validate manifest.json against the §3.2 contract from docs/ARCHITECTURE.md.

Walks outputFiles/ (or a path you pass) and reports which manifests are
non-conforming. Used as a post-run safety check.

Usage:
    python tools/validate_manifest.py                       # walk outputFiles/
    python tools/validate_manifest.py --path outputFiles/E1
    python tools/validate_manifest.py --strict              # exit 1 on any fail

Exit codes:
    0 = all manifests conform
    1 = at least one missing required field (or other contract violation)
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN = "\033[32m"; RED = "\033[31m"; YELLOW = "\033[33m"; CYAN = "\033[36m"; END = "\033[0m"

# §3.2 required fields (every adapter must write these)
REQUIRED = [
    "tag", "run_type", "force_class", "units",
    "run_dir", "h5_path",
    "started_at", "finished_at", "wall_seconds",
    "git_sha",
    "steps", "write_stride", "actual_step_rate",
]
# These are recommended but not strictly required (legacy configs may lack them)
RECOMMENDED = ["dt", "N", "T0", "nu", "notes", "preflight", "units_regime"]


def _known_units() -> set:
    """Allowed values for the manifest's `units` field — sourced dynamically
    from the units/ directory so adding units/<new>.yaml auto-extends what
    the validator accepts (no edits to this file required)."""
    udir = ROOT / "units"
    if not udir.is_dir():
        return {"reduced", "macro"}
    return {p.stem for p in udir.glob("*.yaml")}


def _registered_run_types() -> set:
    """Parse force_types.md for canonical force_type names. Each registered
    type is documented under `## N. \`<name>\`` headings."""
    reg = ROOT / ".claude" / "skills" / "paper-to-experiment" / "references" / "force_types.md"
    if not reg.exists():
        return set()
    import re
    return set(re.findall(r"^##\s+\d+\.\s+`([a-z_]+)`",
                            reg.read_text(encoding="utf-8"), re.MULTILINE))


def validate_one(manifest_path: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one manifest.json."""
    errors, warnings = [], []
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"unreadable: {e}"], []
    if not isinstance(m, dict):
        return ["not a JSON object"], []

    # Required fields presence
    for k in REQUIRED:
        if k not in m or m[k] in (None, ""):
            errors.append(f"missing required field '{k}'")

    # Recommended fields
    for k in RECOMMENDED:
        if k not in m:
            warnings.append(f"missing recommended field '{k}'")

    # h5 trajectory file actually exists
    h5p = m.get("h5_path")
    if h5p:
        if not Path(h5p).exists():
            # Try resolving relative to run_dir as fallback
            run_dir = Path(m.get("run_dir", manifest_path.parent))
            if not (run_dir / Path(h5p).name).exists():
                errors.append(f"h5_path points to missing file: {h5p}")

    # Sanity: actual_step_rate looks like step/sec, not totally absurd
    rate = m.get("actual_step_rate")
    if rate is not None and not isinstance(rate, (int, float)):
        errors.append(f"actual_step_rate not numeric: {rate}")
    elif isinstance(rate, (int, float)) and (rate < 1 or rate > 5000):
        warnings.append(f"actual_step_rate suspicious: {rate:.1f} step/s "
                        f"(typical 50-500)")

    # Sanity: wall_seconds positive
    ws = m.get("wall_seconds")
    if isinstance(ws, (int, float)) and ws < 0:
        errors.append(f"wall_seconds negative: {ws}")

    # `units` must reference a yaml file under units/. The known set is
    # discovered at validation time, so adding units/<new>.yaml auto-extends
    # what the validator accepts — no edits to this file needed.
    known = _known_units()
    if "units" in m and m["units"] not in known:
        errors.append(f"units='{m['units']}' not under units/ "
                       f"(known yaml files: {sorted(known)})")

    # `run_type` validated against the force_types.md registry.
    rt = m.get("run_type")
    if rt is not None:
        registry = _registered_run_types()
        if registry and rt not in registry:
            warnings.append(f"unknown run_type '{rt}' — "
                              f"register in references/force_types.md "
                              f"(known: {sorted(registry)})")

    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="outputFiles", help="root to scan")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any failure")
    args = ap.parse_args()

    root = ROOT / args.path if not Path(args.path).is_absolute() else Path(args.path)
    manifests = sorted(root.rglob("manifest.json")) if root.is_dir() else [root]
    if not manifests:
        print(f"{YELLOW}no manifest.json found under {root}{END}")
        sys.exit(0)

    n_pass = 0; n_warn = 0; n_fail = 0
    for mp in manifests:
        rel = mp.relative_to(ROOT) if mp.is_relative_to(ROOT) else mp
        errors, warnings = validate_one(mp)
        if errors:
            n_fail += 1
            print(f"{RED}FAIL{END}  {rel}")
            for e in errors: print(f"   ✗ {e}")
            for w in warnings: print(f"   {YELLOW}△ {w}{END}")
        elif warnings:
            n_warn += 1
            print(f"{YELLOW}WARN{END}  {rel}")
            for w in warnings: print(f"   △ {w}")
        else:
            n_pass += 1
            # Quiet on PASS unless verbose
    print()
    print(f"summary: {GREEN}{n_pass} pass{END}, "
          f"{YELLOW}{n_warn} warn{END}, "
          f"{RED}{n_fail} fail{END}  "
          f"(of {len(manifests)} manifests)")
    if n_fail and args.strict:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
