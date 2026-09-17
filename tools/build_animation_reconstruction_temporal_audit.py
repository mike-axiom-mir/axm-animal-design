#!/usr/bin/env python3
"""Build Animation evidence from an exact retained Rigging reconstruction artifact."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from axm_animal_design.animation_reconstruction_temporal_audit import (
    HOLD_STATE,
    PASS_STATE,
    build_temporal_spike_negative_control,
    inspect_reconstruction_temporal_stability,
)

RIGGING_ARTIFACT_ID = 10476642320
RIGGING_ARTIFACT_SHA256 = "2d11836cc7c1ada5146752d0b6205d0e4f476cd085ee8be4964e2f024f70fa58"
RIGGING_HEAD = "81ab44eab2e13bed95187610a476be2b2c4667a7"
ANIMATION_BASELINE_HEAD = "731ce2d8bf3481bde1a9731f361fb9820efcdfc1"
CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"


def _canonical_digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rigging-artifact-zip", type=Path, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--current-animation-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    archive_bytes = args.rigging_artifact_zip.read_bytes()
    observed_archive_sha = hashlib.sha256(archive_bytes).hexdigest()
    if observed_archive_sha != RIGGING_ARTIFACT_SHA256:
        raise SystemExit("exact Rigging reconstruction artifact SHA-256 drift")

    clip = json.loads(args.clip.read_text(encoding="utf-8"))
    observed_clip_digest = _canonical_digest(clip)
    if observed_clip_digest != CLIP_DIGEST:
        raise SystemExit("exact Animation clip digest drift")
    if clip.get("rig_weighting_profile") != "smoothstep-v0":
        raise SystemExit("Animation weighting identity drift")
    if clip.get("duration_seconds") != 1.0 or clip.get("sample_rate_hz") != 40:
        raise SystemExit("Animation timing identity drift")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(args.rigging_artifact_zip, "r") as archive:
            archive.extractall(tmp_path)
        rigging_head = (tmp_path / "exact-rigging-head.txt").read_text(encoding="utf-8").strip()
        if rigging_head != RIGGING_HEAD:
            raise SystemExit("exact Rigging reconstruction head drift")
        receipt = json.loads(
            (tmp_path / "post-skin-owner-frame-reconstruction-receipt.json").read_text(encoding="utf-8")
        )

    report = inspect_reconstruction_temporal_stability(receipt)
    if report["gate"] != PASS_STATE:
        raise SystemExit(f"Animation temporal reconstruction audit did not pass: {report['gate']}")
    negative = build_temporal_spike_negative_control(receipt)
    if negative["gate"] != HOLD_STATE:
        raise SystemExit("temporal spike negative control did not fail closed")

    args.out.mkdir(parents=True, exist_ok=True)
    _write_json(args.out / "animation-transport-reconstruction-temporal-audit-receipt.json", report)
    _write_json(
        args.out / "summary.json",
        {
            "gate": report["gate"],
            "schema": report["schema"],
            "current_animation_head": args.current_animation_head,
            "animation_baseline_head": ANIMATION_BASELINE_HEAD,
            "clip_digest": CLIP_DIGEST,
            "rigging_reconstruction_head": RIGGING_HEAD,
            "rigging_artifact_id": RIGGING_ARTIFACT_ID,
            "rigging_artifact_sha256": RIGGING_ARTIFACT_SHA256,
            "timing": report["timing"],
            "motion_identity": report["motion_identity"],
            "reconstruction_error_temporal": report["reconstruction_error_temporal"],
            "negative_control_gate": negative["gate"],
            "truth_boundary": report["truth_boundary"],
        },
    )
    (args.out / "exact-animation-head.txt").write_text(args.current_animation_head + "\n", encoding="utf-8")
    (args.out / "animation-baseline-head.txt").write_text(ANIMATION_BASELINE_HEAD + "\n", encoding="utf-8")
    (args.out / "clip-digest.txt").write_text(CLIP_DIGEST + "\n", encoding="utf-8")
    (args.out / "rigging-reconstruction-head.txt").write_text(RIGGING_HEAD + "\n", encoding="utf-8")
    (args.out / "rigging-artifact-sha256.txt").write_text(RIGGING_ARTIFACT_SHA256 + "\n", encoding="utf-8")

    fields = [
        "sample_index",
        "time_seconds",
        "angle_deg_from_transport_quaternion",
        "maximum_position_residual_m",
        "maximum_normal_angle_deg",
        "maximum_tangent_angle_deg",
        "maximum_normal_tangent_dot_abs",
        "split_position_residual_m",
        "handedness_mismatch_count",
    ]
    with (args.out / "rigging-reconstruction-all-41-samples.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in receipt["all_41_key_samples"]:
            writer.writerow({field: row[field] for field in fields})

    print(report["gate"])
    print(f"rigging_head={RIGGING_HEAD}")
    print(f"clip_digest={CLIP_DIGEST}")
    print(f"max_time_mirror_residual_s={report['timing']['maximum_time_mirror_residual_seconds']}")
    print(f"max_angle_mirror_residual_deg={report['motion_identity']['maximum_angle_mirror_residual_deg']}")
    print(
        "normal_error_mirror_residual_deg="
        f"{report['reconstruction_error_temporal']['maximum_mirror_residual_by_field']['maximum_normal_angle_deg']}"
    )
    print(
        "normal_error_max_adjacent_delta_deg="
        f"{report['reconstruction_error_temporal']['maximum_adjacent_delta_by_field']['maximum_normal_angle_deg']}"
    )
    print(f"negative_control={negative['gate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
