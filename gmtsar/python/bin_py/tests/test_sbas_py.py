#!/usr/bin/env python3
"""test_sbas_py.py — guards for the sbas port and its dispatcher.

The real parity evidence is the C-vs-Python comparison on the ALOS Indio SBAS
set, recorded in docs/dev_notes/NOTES_SBAS.md (8 of 9 flags, worst rms 1.9e-06
against compare.py's DEFAULT_GRD_RMS of 1e-2). That run needs a 1.1 GB dataset
and ~50 s, so it is not a unit test. What IS unit-testable is everything that
would silently undo it, and the algebra that has a closed form.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

_SBAS = Path(__file__).resolve().parent.parent / "sbas_py"
sys.path.insert(0, str(_SBAS))
import sbas_ref  # noqa: E402

_UTILS = Path(__file__).resolve().parent.parent.parent / "utils"


def test_truncated_constant_not_silently_corrected():
    """C uses -79.58, a truncated 1000/(4*pi)=79.5775. 'Fixing' it to the exact
    value shifts every velocity by ~0.003% and breaks parity."""
    assert sbas_ref.C_MM == -79.58


def test_rcond_matches_c():
    assert sbas_ref.RCOND == 1e-3


def test_build_G_structure():
    """Row i is 1 on the increments interferogram i spans, plus the bperp column;
    the last S-2 rows are the second-difference smoothing block."""
    L = np.array([0, 10, 20, 30], dtype=np.int64)
    H = np.array([[0, 10], [10, 20], [0, 20]], dtype=np.int64)
    time = np.array([0.0, 10.0, 20.0, 30.0])
    bperp = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    N, S = 3, 4
    m, n = N + S - 2, S
    G = sbas_ref.build_G(N, S, m, n, L, H, time, 1.0, bperp, 2.0)
    assert G.shape == (m, n)
    np.testing.assert_array_equal(G[0, :S - 1], [1, 0, 0])      # spans 0->10
    np.testing.assert_array_equal(G[1, :S - 1], [0, 1, 0])      # spans 10->20
    np.testing.assert_array_equal(G[2, :S - 1], [1, 1, 0])      # spans 0->20
    np.testing.assert_allclose(G[:N, n - 1], bperp * 2.0)       # bperp column (intf rows only)
    assert np.all(G[N:, n - 1] == 0.0)                          # smoothing rows untouched there
    assert G[N, 0] == pytest.approx(1.0 / 10.0)                 # smoothing
    assert G[N, 1] == pytest.approx(-1.0 / 10.0)


def test_build_G_smoothing_scales_with_sf():
    L = np.array([0, 10, 20, 30], dtype=np.int64)
    H = np.array([[0, 10]], dtype=np.int64)
    time = np.array([0.0, 10.0, 20.0, 30.0])
    bperp = np.array([1.0], dtype=np.float32)
    N, S = 1, 4
    m, n = N + S - 2, S
    g1 = sbas_ref.build_G(N, S, m, n, L, H, time, 1.0, bperp, 1.0)
    g2 = sbas_ref.build_G(N, S, m, n, L, H, time, 2.0, bperp, 1.0)
    np.testing.assert_allclose(g2[N:], 2.0 * g1[N:])


def test_compute_noise_zero_sum_returns_zero():
    """C returns 0.0 when the finite sum is exactly zero, not the true rms."""
    s = np.array([[1.0, -1.0], [2.0, -2.0]], dtype=np.float32)
    assert sbas_ref.compute_noise(s) == 0.0


def test_compute_noise_ignores_nan():
    s = np.array([[1.0, np.nan], [3.0, 5.0]], dtype=np.float32)
    v = np.array([1.0, 3.0, 5.0])
    assert sbas_ref.compute_noise(s) == pytest.approx(v.std())


def test_rank_double_orders_by_abs_then_appends_zeros():
    """Descending |value|; exact zeros go last, in index order."""
    seq = sbas_ref.rank_double(np.array([0.0, -5.0, 2.0, 0.0, 9.0]), 5)
    assert list(seq[:3]) == [4, 1, 2]
    assert sorted(seq[3:]) == [0, 3]


def test_smoothing_ramp_endpoints_and_monotonicity():
    """sfs[0]=1000, sfs[n_atm]=sf, geometric in between (sbas.c:262-278)."""
    sfs = sbas_ref.smoothing_ramp(1.0, 2)
    assert sfs[0] == 1000.0
    assert sfs[2] == pytest.approx(1.0)
    assert sfs[1] == pytest.approx(np.sqrt(1000.0), rel=1e-6)
    assert sfs[0] > sfs[1] > sfs[2]


def test_smoothing_ramp_handles_sf_zero():
    """C branches to log(0.01) when sf <= 0, rather than log(0)."""
    sfs = sbas_ref.smoothing_ramp(0.0, 3)
    assert np.all(np.isfinite(sfs[:4]))
    assert sfs[0] == 1000.0


def test_connect_signs_and_zero_for_unrelated_scene():
    L = np.array([0, 10, 20], dtype=np.int64)
    H = np.array([[0, 10], [10, 20]], dtype=np.int64)
    time = np.array([0.0, 10.0, 20.0])
    hit = sbas_ref.build_hit(L, H, 2, 3)
    mark = sbas_ref.connect(L, H, time, hit, 2, 3, 1, 0)
    assert mark[0] == -1     # pair ending at scene 1
    assert mark[1] == 1      # pair starting at scene 1


def test_sum_intfs_all_zero_marks_gives_zero_screen():
    phi = np.ones((3, 4, 2), dtype=np.float32)
    out = sbas_ref.sum_intfs(phi, np.zeros(2, dtype=np.int64), 4, 3, 2)
    assert out.shape == (3, 4)
    assert np.all(out == 0.0)


def test_dispatcher_falls_back_to_c_for_atm_ge_2():
    """-atm n>=2 has no reproducible reference; the dispatcher must not use the
    port for it, and must say so rather than falling back silently (Rule 1)."""
    r = subprocess.run([sys.executable, str(_UTILS / "sbas"),
                        "x", "y", "1", "2", "3", "4", "-atm", "2"],
                       capture_output=True, text=True,
                       env={**os.environ, "PATH": "/usr/bin:/bin"})
    assert "C binary" in r.stderr
    assert "-atm 2" in r.stderr


def test_dispatcher_env_override_forces_c():
    r = subprocess.run([sys.executable, str(_UTILS / "sbas"),
                        "x", "y", "1", "2", "3", "4"],
                       capture_output=True, text=True,
                       env={**os.environ, "GMTSAR_SBAS_PY": "0",
                            "PATH": "/usr/bin:/bin"})
    assert "GMTSAR_SBAS_PY=0" in r.stderr


def test_dispatcher_atm_1_stays_in_python():
    """-atm 1 IS at parity, so it must not be diverted to C."""
    sys.path.insert(0, str(_UTILS))
    src = (_UTILS / "sbas").read_text().split("if __name__")[0]
    ns: dict = {"__file__": str(_UTILS / "sbas")}
    exec(compile(src, "sbas", "exec"), ns)
    assert ns["_n_atm"](["a", "-atm", "1"]) == 1
    assert ns["_n_atm"](["a", "-atm", "2"]) == 2
    assert ns["_n_atm"](["a"]) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
