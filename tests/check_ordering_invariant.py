"""
Ordering-invariant proof: Phase 4 never disturbs Phase 3 and lands on a separate path.

Run directly:
    python tests/check_ordering_invariant.py

Procedure:
  1. sha256 the two Phase 3 artifacts
     (data/analysis_output/scale_independent_metrics/{flatness_consistency.json,
      cross_camera_agreement.json}). If either is missing, print SKIP and exit 0
      (they are gitignored; CI without data should not hard-fail). If present, enforce.
  2. Run analysis/compute_scale_alignment.py via subprocess using the SAME interpreter
     (sys.executable) — i.e. the way the grader runs it under conda. Assert exit code 0.
  3. Re-sha256 both Phase 3 artifacts; assert both hashes are UNCHANGED (byte-identical).
  4. Assert data/analysis_output/scale_alignment.json now exists AND that its parent
     directory is data/analysis_output (NOT .../scale_independent_metrics).

Exits 0 on success, 1 on any violation.

SCOPE NOTE: this task creates the ordering-invariant proof ONLY. It does NOT modify
analysis/entrypoint.py or add any --run-metrics / run_pipeline orchestration. That
one-command regeneration wiring is OUT-05, deferred to Phase 5 per 04-CONTEXT.md.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE3_DIR = REPO_ROOT / "data" / "analysis_output" / "scale_independent_metrics"
PHASE3_ARTIFACTS = (
    PHASE3_DIR / "flatness_consistency.json",
    PHASE3_DIR / "cross_camera_agreement.json",
)
COMPUTE_SCRIPT = REPO_ROOT / "analysis" / "compute_scale_alignment.py"
PHASE4_ARTIFACT = REPO_ROOT / "data" / "analysis_output" / "scale_alignment.json"
PHASE4_PARENT_NAME = "analysis_output"
FORBIDDEN_PARENT_NAME = "scale_independent_metrics"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # ── 1. Pre-run hashes (or SKIP if data absent) ────────────────────────────
    missing = [p for p in PHASE3_ARTIFACTS if not p.exists()]
    if missing:
        print(
            "SKIP: Phase 3 artifacts not present (gitignored data) — "
            f"missing {[str(p) for p in missing]}. Ordering invariant not enforced."
        )
        sys.exit(0)

    before = {p: sha256(p) for p in PHASE3_ARTIFACTS}

    # ── 2. Run the Phase 4 compute via subprocess (same interpreter) ──────────
    proc = subprocess.run(
        [sys.executable, str(COMPUTE_SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        fail(
            f"compute_scale_alignment.py exited {proc.returncode} "
            "(Phase 4 compute is broken)"
        )

    # ── 3. Post-run hashes must be byte-identical ─────────────────────────────
    for p in PHASE3_ARTIFACTS:
        after = sha256(p)
        if after != before[p]:
            fail(f"Phase 3 artifact CHANGED by Phase 4 run: {p}")

    # ── 4. Phase 4 artifact exists on the SEPARATE path ───────────────────────
    if not PHASE4_ARTIFACT.exists():
        fail(f"Phase 4 artifact not written at {PHASE4_ARTIFACT}")

    parent_name = PHASE4_ARTIFACT.parent.name
    if parent_name == FORBIDDEN_PARENT_NAME:
        fail(
            f"Phase 4 artifact landed inside {FORBIDDEN_PARENT_NAME}/ "
            "(must be on the separate analysis_output path)"
        )
    if parent_name != PHASE4_PARENT_NAME:
        fail(
            f"Phase 4 artifact parent is {parent_name!r}, expected {PHASE4_PARENT_NAME!r}"
        )

    print("check_ordering_invariant OK")
    print(f"  Phase 3 hashes byte-identical before/after Phase 4 run ({len(before)} files).")
    print(f"  Phase 4 artifact on separate path: {PHASE4_ARTIFACT.relative_to(REPO_ROOT)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
