"""
OUT-03: Per-camera board-localization agreement output.

Reads cross_camera_agreement.json via load_cross_camera() and produces:
  results/per_camera_agreement.md  — intro + per-camera table + per-frame table
  results/per_camera_agreement.csv — per-camera roll-up (camera_id, frames_included, frames_excluded)

Board-blind / low-coverage cameras are NON-EVENTS, not errors.
Exclusion means a camera did not co-observe enough corners in that frame;
this is an expected rig characteristic, not a failure.

Run as a module:
  python -m analysis.deliverables.make_per_camera
or import and call main().
"""

import csv
import io
from collections import defaultdict
from pathlib import Path

from analysis.deliverables._artifacts import RESULTS_DIR, load_cross_camera

# Strings that must never appear in any deliverable
_BANNED = ("58.5", "173.7", "0.5 %")


def _check_banned(text: str) -> None:
    for banned in _BANNED:
        if banned in text:
            raise ValueError(
                f"Banned string {banned!r} found in output. "
                "Check artifact values."
            )


def _build_per_camera_rollup(per_frame: list[dict]) -> dict[str, dict[str, int]]:
    """
    Roll up per-frame inclusion/exclusion data to a per-camera summary.

    Returns a dict keyed by camera_id with keys:
      frames_included  (int)
      frames_excluded  (int)
    """
    rollup: dict[str, dict[str, int]] = defaultdict(
        lambda: {"frames_included": 0, "frames_excluded": 0}
    )
    for frame in per_frame:
        for cam in frame.get("cameras_included", []):
            rollup[cam]["frames_included"] += 1
        for cam in frame.get("cameras_excluded", {}).keys():
            rollup[cam]["frames_excluded"] += 1
    return dict(sorted(rollup.items()))


def _write_markdown(
    per_camera: dict[str, dict[str, int]],
    per_frame: list[dict],
    path: Path,
) -> None:
    """Write the Markdown per-camera agreement summary."""
    lines: list[str] = []

    # Intro sentence — non-event framing
    lines.append(
        "# Per-Camera Board-Localization Agreement\n"
    )
    lines.append(
        "Camera exclusions from a given frame indicate that the camera did not "
        "co-observe enough calibration-board corners to contribute to the "
        "cross-camera agreement estimate in that frame.  "
        "This is a non-event (expected rig characteristic), not an error or failure.\n"
    )

    # Per-camera table
    lines.append("## Per-Camera Inclusion Summary\n")
    lines.append("| Camera | Frames Included | Frames Excluded |")
    lines.append("| --- | --- | --- |")
    for cam, counts in per_camera.items():
        lines.append(
            f"| {cam} | {counts['frames_included']} | {counts['frames_excluded']} |"
        )
    lines.append("")

    # Per-frame table
    lines.append("## Per-Frame Agreement\n")
    lines.append("| Frame | Cameras Included | RMS (mm) |")
    lines.append("| --- | --- | --- |")
    for frame in per_frame:
        lines.append(
            f"| {frame['frame_idx']} "
            f"| {frame['n_cameras_included']} "
            f"| {frame['frame_rms_mm']:.3f} |"
        )
    lines.append("")

    text = "\n".join(lines)
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def _write_csv(
    per_camera: dict[str, dict[str, int]],
    path: Path,
) -> None:
    """Write per-camera roll-up CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["camera_id", "frames_included", "frames_excluded"])
    for cam, counts in per_camera.items():
        writer.writerow([cam, counts["frames_included"], counts["frames_excluded"]])
    text = buf.getvalue()
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def main() -> None:
    """Generate results/per_camera_agreement.{md,csv} from cross_camera_agreement.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Building per-camera agreement output from artifacts...")
    data = load_cross_camera()
    per_frame: list[dict] = data["per_frame"]

    per_camera = _build_per_camera_rollup(per_frame)

    _write_markdown(per_camera, per_frame, RESULTS_DIR / "per_camera_agreement.md")
    _write_csv(per_camera, RESULTS_DIR / "per_camera_agreement.csv")

    print("OUT-03 complete: results/per_camera_agreement.{md,csv} written.")


if __name__ == "__main__":
    main()
