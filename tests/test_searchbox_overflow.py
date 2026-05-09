"""mN too small must raise RuntimeError, not just print."""
import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import constSet as cs
from atomSystemClass import AtomSystem
from searchBox import searchBox


def test_overflow_raises():
    N = 50
    rng = np.random.default_rng(0)
    pos = rng.uniform(0.1, 9.9, (N, 3))
    pos[:, 2] = 0.0
    box = [10.0, 0, 0, 0, 10.0, 0, 0, 0, 10.0]
    masses = np.ones(N)

    A = AtomSystem(num_atoms=N, n=3, cutoff=8.0, ndim=2)
    A.initData(pos, masses, 1.0, box, groups=None)

    sb = searchBox(choose=2, mN=2, cutoffNegh=9.0, full_list=False)
    sb.register(A)
    try:
        sb.findNegh()
    except RuntimeError as e:
        assert "overflow" in str(e).lower()
        print(f"OK: raised RuntimeError as expected: {e}")
        return
    raise AssertionError("expected RuntimeError, got nothing")


def test_invalid_cutoff_raises():
    N = 4
    pos = np.zeros((N, 3))
    box = [10.0, 0, 0, 0, 10.0, 0, 0, 0, 10.0]
    A = AtomSystem(num_atoms=N, n=3, cutoff=10.0, ndim=2)
    A.initData(pos, np.ones(N), 1.0, box, groups=None)

    try:
        sb = searchBox(choose=2, mN=10, cutoffNegh=5.0, full_list=False)
        sb.register(A)
    except ValueError as e:
        assert "cutoff" in str(e).lower()
        print(f"OK: raised ValueError: {e}")
        return
    raise AssertionError("expected ValueError")


if __name__ == "__main__":
    test_overflow_raises()
    test_invalid_cutoff_raises()
    print("OK: all tests passed")
