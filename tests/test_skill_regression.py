"""Skill regression test: ensure the templates + schema + validator + registry
collectively reject bad configs and accept the existing approved configs.
This protects against future schema/registry drift.

Run:
    python -m pytest tests/test_skill_regression.py -v
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / ".claude" / "skills" / "paper-to-experiment"
SCHEMA_PATH = SKILL_DIR / "templates" / "plan_config.schema.json"
VALIDATOR = ROOT / "scripts" / "validate_config.py"
EXAMPLES = SKILL_DIR / "references" / "examples"
PYBIN = sys.executable


def run_validator(cfg_path: Path, strict=False):
    cmd = [PYBIN, str(VALIDATOR), str(cfg_path)]
    if strict:
        cmd.append("--strict")
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def test_schema_file_exists_and_parses():
    assert SCHEMA_PATH.exists(), f"schema missing at {SCHEMA_PATH}"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("$schema", "").startswith("http"), "schema must declare $schema"
    assert "campaign" in schema["properties"]
    assert schema["properties"]["campaign"]["maxItems"] == 16


def test_validator_accepts_examples():
    """Existing approved configs must validate (warnings OK in non-strict)."""
    for ex in EXAMPLES.glob("*.json"):
        result = run_validator(ex, strict=False)
        assert result.returncode == 0, (
            f"approved example {ex.name} failed validation:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def test_validator_rejects_unknown_force_type(tmp_path):
    bad = {
        "campaign": [{
            "force_type": "made_up_force",
            "tag": "T1", "steps": 1000, "stride": 10,
        }],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True}
    }
    p = tmp_path / "bad_force.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    result = run_validator(p)
    assert result.returncode != 0
    assert "unknown force_type" in result.stdout or "is not one of" in result.stdout


def test_validator_rejects_duplicate_tags(tmp_path):
    bad = {
        "campaign": [
            {"force_type": "er_plasma", "tag": "DUP", "MT": 0.8, "Z_eff": 10000,
             "lambda_mm": 0.05, "T0_K": 348, "dt_ms": 0.01, "steps": 1000, "stride": 10},
            {"force_type": "er_plasma", "tag": "DUP", "MT": 0.6, "Z_eff": 10000,
             "lambda_mm": 0.05, "T0_K": 348, "dt_ms": 0.01, "steps": 1000, "stride": 10},
        ],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True}
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    result = run_validator(p)
    assert result.returncode != 0
    assert "duplicate tag" in result.stdout


def test_validator_rejects_overcap_parallel(tmp_path):
    bad = {
        "campaign": [{"force_type": "er_plasma", "tag": "T1", "MT": 0.8,
                      "Z_eff": 10000, "lambda_mm": 0.05, "T0_K": 348,
                      "dt_ms": 0.01, "steps": 1000, "stride": 10}],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True,
                     "max_parallel": 8}
    }
    p = tmp_path / "overcap.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    result = run_validator(p)
    assert result.returncode != 0


def test_validator_rejects_missing_required_fields(tmp_path):
    """er_plasma requires MT, Z_eff, lambda_mm, T0_K, dt_ms."""
    bad = {
        "campaign": [{"force_type": "er_plasma", "tag": "T1",
                      "steps": 1000, "stride": 10}],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True}
    }
    p = tmp_path / "missing.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    result = run_validator(p)
    assert result.returncode != 0


def test_validator_warns_supercritical_damping(tmp_path):
    """ν > ν_c should produce a warning (not error) — gives user a chance to confirm."""
    cfg = {
        "_paper_ref": "test",
        "_comment": "test",
        "campaign": [{"force_type": "hertzian_nonreciprocal", "tag": "T1",
                      "phi": 0.3, "T0": 0.3, "nu": 0.01,
                      "steps": 1000, "stride": 10}],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True}
    }
    p = tmp_path / "supercrit.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    result = run_validator(p, strict=False)
    assert result.returncode == 0  # warning only
    assert "ν_c" in result.stdout

    result_strict = run_validator(p, strict=True)
    assert result_strict.returncode == 2  # warnings fail in strict


def test_validator_warns_tag_pattern(tmp_path):
    """Tags with dashes/spaces violate schema pattern."""
    bad = {
        "campaign": [{"force_type": "er_plasma", "tag": "BAD-TAG", "MT": 0.8,
                      "Z_eff": 10000, "lambda_mm": 0.05, "T0_K": 348,
                      "dt_ms": 0.01, "steps": 1000, "stride": 10}],
        "pipeline": {"preflight": True, "production": True, "halt_on_fail": True}
    }
    p = tmp_path / "badtag.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    result = run_validator(p)
    assert result.returncode != 0


def test_force_types_registry_lists_both_known_types():
    """Registry must enumerate every force_type currently in the schema enum."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["definitions"]["experiment"]["properties"]["force_type"]["enum"]
    registry = (SKILL_DIR / "references" / "force_types.md").read_text(encoding="utf-8")
    for ft in enum:
        assert ft in registry, f"force_type '{ft}' is in schema but not documented in registry"


def test_template_required_sections_present():
    tpl = (SKILL_DIR / "templates" / "physics_design.md").read_text(encoding="utf-8")
    for section in ["§0 Metadata", "§1 Physics observables", "§2 Force field",
                    "§3 Simulation setup", "§4 Sweep dimensions",
                    "§5 Run phases", "§6 Pass criteria", "§7 Expected costs",
                    "§8 Existing assets", "§9 Deliverables",
                    "§10 Decision log", "§11 Validation plan", "§12 Output config"]:
        assert section in tpl, f"template missing required section: {section}"


def test_skill_md_has_frontmatter():
    sm = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert sm.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    assert "name: paper-to-experiment" in sm
    assert "description:" in sm
