"""
Artifact shape checker for data/analysis_output/scale_alignment.json (Phase 4).

Verifies:
  - File exists at data/analysis_output/scale_alignment.json.
  - "computed_after_alignment" is True.
  - "per_frame" is a list whose non-skipped frame_idx set == {1,2,3,4,6,7,8,9}
    (skipped records are allowed but must still carry a known frame_idx).
  - Every non-skipped record: finite rigid_rms_mm in (0, 50] mm, n_inliers >= 3,
    finite scale_factor in [0.8, 1.2], finite board_size_mm in (40, 80) mm.
  - "pooled" block has a finite pooled rigid RMSE.
  - "note" block: non-empty circularity_caveat AND a maas_2015_context containing
    "factor" (case-insensitive).
  - The banned misread substrings "0.5 %" and "0.5%" appear NOWHERE in the
    serialized artifact.

Exits 0 on pass, 1 on failure.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ARTIFACT_PATH = Path("data/analysis_output/scale_alignment.json")
EXPECTED_FRAME_IDXS = {1, 2, 3, 4, 6, 7, 8, 9}


def check(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    check(ARTIFACT_PATH.exists(), f"artifact not found at {ARTIFACT_PATH}")

    raw = ARTIFACT_PATH.read_text()
    data = json.loads(raw)

    # ── Banned misread substrings (the '0.5 % of dimension' error) ────────────
    check("0.5 %" not in raw, "banned substring '0.5 %' present in artifact")
    check("0.5%" not in raw, "banned substring '0.5%' present in artifact")

    # ── Top-level keys ────────────────────────────────────────────────────────
    check(data.get("computed_after_alignment") is True,
          f"computed_after_alignment must be True, got {data.get('computed_after_alignment')!r}")
    check("per_frame" in data, "missing key: per_frame")
    check("pooled" in data, "missing key: pooled")
    check("note" in data, "missing key: note")

    # ── per_frame records ─────────────────────────────────────────────────────
    per_frame = data["per_frame"]
    check(isinstance(per_frame, list), "per_frame must be a list")

    non_skipped_idxs = set()
    for rec in per_frame:
        check("frame_idx" in rec, f"record missing frame_idx: {rec}")
        fidx = rec["frame_idx"]
        check(fidx in EXPECTED_FRAME_IDXS,
              f"unexpected frame_idx {fidx!r}; expected one of {EXPECTED_FRAME_IDXS}")

        if rec.get("skipped_reason"):
            continue  # skipped records allowed

        non_skipped_idxs.add(fidx)

        rms = rec.get("rigid_rms_mm")
        check(isinstance(rms, (int, float)) and math.isfinite(rms),
              f"frame {fidx}: rigid_rms_mm={rms!r} not finite")
        check(0.0 < rms <= 50.0,
              f"frame {fidx}: rigid_rms_mm={rms:.4f} not in (0, 50] mm")

        n_inliers = rec.get("n_inliers")
        check(isinstance(n_inliers, int) and n_inliers >= 3,
              f"frame {fidx}: n_inliers={n_inliers!r} must be >= 3")

        sf = rec.get("scale_factor")
        check(isinstance(sf, (int, float)) and math.isfinite(sf),
              f"frame {fidx}: scale_factor={sf!r} not finite")
        check(0.8 <= sf <= 1.2,
              f"frame {fidx}: scale_factor={sf:.4f} not near 1 (0.8..1.2)")

        size = rec.get("board_size_mm")
        check(isinstance(size, (int, float)) and math.isfinite(size),
              f"frame {fidx}: board_size_mm={size!r} not finite")
        check(40.0 < size < 80.0,
              f"frame {fidx}: board_size_mm={size:.4f} not in (40, 80) mm")

    check(non_skipped_idxs == EXPECTED_FRAME_IDXS,
          f"non-skipped frame_idxs {non_skipped_idxs} != expected {EXPECTED_FRAME_IDXS}")

    # ── pooled block ──────────────────────────────────────────────────────────
    pooled = data["pooled"]
    pooled_rms = pooled.get("rigid_rms_mm_pooled")
    check(isinstance(pooled_rms, (int, float)) and math.isfinite(pooled_rms),
          f"pooled rigid_rms_mm_pooled={pooled_rms!r} not finite")
    check(0.0 < pooled_rms <= 50.0,
          f"pooled rigid_rms_mm_pooled={pooled_rms:.4f} not in (0, 50] mm")

    # ── note block ────────────────────────────────────────────────────────────
    note = data["note"]
    caveat = note.get("circularity_caveat", "")
    check(isinstance(caveat, str) and len(caveat.strip()) > 0,
          "note.circularity_caveat must be a non-empty string")

    maas = note.get("maas_2015_context", "")
    check(isinstance(maas, str) and len(maas.strip()) > 0,
          "note.maas_2015_context must be a non-empty string")
    check("factor" in maas.lower(),
          "note.maas_2015_context must mention 'factor' (factor-of-two benchmark)")

    print("check_scale_alignment_artifact OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
