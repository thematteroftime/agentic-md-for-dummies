"""Verify read_inputParams returns dict + defaults for missing keys."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from toolClass import fileOperator


def _write(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".in", delete=False, encoding="utf-8")
    f.write(text); f.close()
    return f.name


def test_legacy_3line_run_in_uses_defaults():
    p = _write("velocity 348\ntime_step 0.01\nrun 100000\n")
    out = fileOperator.read_inputParams(p)
    assert out["velocity"] == 348.0
    assert out["time_step"] == 0.01
    assert out["run"] == 100000
    assert out["dimension"] == 3   # default
    assert out["units"] == "macro"  # default
    assert out["log"] is False
    assert out["debug"] is False
    assert out["profiler"] is False
    assert out["nu"] == 0.0


def test_full_schema_run_in():
    p = _write(
        "velocity 1.0\n"
        "time_step 0.004\n"
        "run 500000\n"
        "dimension 2\n"
        "units reduced\n"
        "log on\n"
        "debug off\n"
        "profiler on\n"
        "nu 0.05\n"
    )
    out = fileOperator.read_inputParams(p)
    assert out["dimension"] == 2
    assert out["units"] == "reduced"
    assert out["log"] is True
    assert out["debug"] is False
    assert out["profiler"] is True
    assert out["nu"] == 0.05


def test_missing_required_raises():
    p = _write("dimension 3\n")
    try:
        fileOperator.read_inputParams(p)
    except ValueError as e:
        assert "missing required" in str(e).lower()
        return
    raise AssertionError("expected ValueError for missing required keys")


def test_unknown_keyword_raises():
    p = _write("velocity 1\ntime_step 1\nrun 1\nbogus xx\n")
    try:
        fileOperator.read_inputParams(p)
    except ValueError as e:
        assert "unknown" in str(e).lower()
        return
    raise AssertionError("expected ValueError for unknown keyword")


def test_inline_comment_stripped():
    p = _write("velocity 1.0   # T0*\ntime_step 0.5\nrun 10\n")
    out = fileOperator.read_inputParams(p)
    assert out["velocity"] == 1.0


if __name__ == "__main__":
    test_legacy_3line_run_in_uses_defaults()
    test_full_schema_run_in()
    test_missing_required_raises()
    test_unknown_keyword_raises()
    test_inline_comment_stripped()
    print("OK: all tests passed")
