"""
Synthetic unit tests for analysis/alignment.py.

No pytest dependency — run directly:
    python tests/test_alignment.py

Checks:
  1. umeyama_fit(with_scale=True) recovers a known (R, t, s) to ~1e-6, rms ~ 0.
  2. umeyama_fit(with_scale=False) recovers a pure rotation+translation (s == 1),
     rms_mm < 1e-6.
  3. rigid_inlier_fit rejects exactly the injected gross outliers and reports
     sub-mm inlier RMSE.
  4. Scale-error sign: scaling dst by 1.01 recovers s ~ 1.01 (scale_error ~ +0.01).
  5. Degenerate guard: N < 3 returns nan rms / nan s.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from analysis.alignment import umeyama_fit, rigid_inlier_fit


def _random_rotation(rng: np.random.Generator) -> np.ndarray:
    """Build a random proper rotation matrix via QR of a random matrix."""
    A = rng.normal(size=(3, 3))
    Q, R = np.linalg.qr(A)
    # Make it a proper rotation (det = +1)
    Q = Q @ np.diag(np.sign(np.diag(R)))
    if np.linalg.det(Q) < 0:
        Q[:, 0] = -Q[:, 0]
    return Q


# ── Test 1: exact recovery of known R, t, s (with scale) ───────────────────────

def test_umeyama_with_scale_exact() -> None:
    rng = np.random.default_rng(0)
    R_true = _random_rotation(rng)
    t_true = rng.uniform(-1.0, 1.0, size=3)
    s_true = 1.37

    src = rng.uniform(-0.3, 0.3, size=(40, 3))
    dst = (s_true * (R_true @ src.T).T) + t_true

    fit = umeyama_fit(src, dst, with_scale=True)

    assert abs(fit["s"] - s_true) < 1e-6, f"s={fit['s']} != {s_true}"
    assert fit["rms_mm"] < 1e-6, f"rms_mm={fit['rms_mm']} not ~0"
    assert np.allclose(fit["R"], R_true, atol=1e-6), "R not recovered"
    assert np.allclose(fit["t"], t_true, atol=1e-6), "t not recovered"


# ── Test 2: pure rotation+translation, no scale ────────────────────────────────

def test_umeyama_no_scale_rigid() -> None:
    rng = np.random.default_rng(1)
    R_true = _random_rotation(rng)
    t_true = rng.uniform(-1.0, 1.0, size=3)

    src = rng.uniform(-0.3, 0.3, size=(40, 3))
    dst = (R_true @ src.T).T + t_true  # s == 1

    fit = umeyama_fit(src, dst, with_scale=False)

    assert fit["s"] == 1.0, "with_scale=False must force s == 1.0"
    assert fit["rms_mm"] < 1e-6, f"rms_mm={fit['rms_mm']} not ~0 for exact rigid"
    assert np.allclose(fit["R"], R_true, atol=1e-6), "R not recovered"
    assert np.allclose(fit["t"], t_true, atol=1e-6), "t not recovered"


# ── Test 3: gross-outlier rejection (rigid_inlier_fit) ─────────────────────────

def test_rigid_inlier_fit_rejects_outliers() -> None:
    rng = np.random.default_rng(2)
    R_true = _random_rotation(rng)
    t_true = rng.uniform(-1.0, 1.0, size=3)

    src = rng.uniform(-0.3, 0.3, size=(30, 3))
    dst = (R_true @ src.T).T + t_true
    # small clean noise (~0.2 mm)
    dst = dst + rng.normal(0, 0.0002, size=dst.shape)

    # Corrupt exactly 2 corners by +50 mm in X
    corrupt_idx = [5, 17]
    dst_bad = dst.copy()
    dst_bad[corrupt_idx, 0] += 0.050

    fit = rigid_inlier_fit(src, dst_bad)

    mask = fit["inlier_mask"]
    # The two corrupted corners must be excluded
    for i in corrupt_idx:
        assert not mask[i], f"corner {i} (50 mm outlier) should be excluded"
    # No other corner should be excluded
    assert fit["n_inliers"] == len(src) - 2, (
        f"expected {len(src) - 2} inliers, got {fit['n_inliers']}"
    )
    assert not fit["degenerate"], "fit should not be degenerate"
    assert fit["rms_mm"] < 1.0, f"inlier rms_mm={fit['rms_mm']} should be sub-mm"


# ── Test 4: scale-error sign ───────────────────────────────────────────────────

def test_scale_error_sign() -> None:
    rng = np.random.default_rng(3)
    R_true = _random_rotation(rng)
    t_true = rng.uniform(-1.0, 1.0, size=3)

    src = rng.uniform(-0.3, 0.3, size=(40, 3))
    # Reconstruction is 1% LARGER than ideal -> s should be ~1.01
    dst = (1.01 * (R_true @ src.T).T) + t_true

    fit = umeyama_fit(src, dst, with_scale=True)
    scale_error = fit["s"] - 1.0

    assert abs(fit["s"] - 1.01) < 1e-6, f"s={fit['s']} != 1.01"
    assert scale_error > 0, "scale_error must be positive when reconstruction is larger"
    assert abs(scale_error - 0.01) < 1e-6, f"scale_error={scale_error} != 0.01"


# ── Test 5: degenerate guard ───────────────────────────────────────────────────

def test_degenerate_guard() -> None:
    src = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    dst = src.copy()
    fit = umeyama_fit(src, dst, with_scale=True)
    assert np.isnan(fit["rms_mm"]), "rms_mm must be nan for N < 3"
    assert np.isnan(fit["s"]), "s must be nan for N < 3"
    assert fit["n"] == 2


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running test_alignment ...")

    test_umeyama_with_scale_exact()
    print("  [PASS] test_umeyama_with_scale_exact")

    test_umeyama_no_scale_rigid()
    print("  [PASS] test_umeyama_no_scale_rigid")

    test_rigid_inlier_fit_rejects_outliers()
    print("  [PASS] test_rigid_inlier_fit_rejects_outliers")

    test_scale_error_sign()
    print("  [PASS] test_scale_error_sign")

    test_degenerate_guard()
    print("  [PASS] test_degenerate_guard")

    print("test_alignment OK")
