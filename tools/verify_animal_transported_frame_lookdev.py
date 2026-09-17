#!/usr/bin/env python3
"""Verify bounded real-render appearance evidence for Animal direction frames."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

EXPECTED_SCHEMA = "axm.animal-materials-transported-frame-lookdev/v0.1"
EXPECTED_TELEMETRY_SCHEMA = "axm.animal-materials-transported-frame-lookdev-telemetry/v0.1"
PASS_VISIBLE = "PASS_RECONSTRUCTED_OWNER_FRAME_VISUALLY_RECOVERS_BASELINE__STATIC_TRANSPORT_DIVERGENCE_VISIBLE"
PASS_NOT_VISUALLY_RESOLVED = "PASS_RECONSTRUCTED_OWNER_FRAME_VISUALLY_EQUIVALENT__STATIC_TRANSPORT_DIVERGENCE_NOT_RESOLVED_VISUALLY"
HOLD_STATE = "HOLD_RECONSTRUCTED_OWNER_FRAME_VISUAL_RECOVERY"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _compare(left_path: Path, right_path: Path):
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != right.size:
        raise SystemExit(f"image size mismatch: {left_path.name} vs {right_path.name}")
    pixel_count = left.width * left.height
    changed_gt_1 = 0
    raw_changed = 0
    maximum_channel_delta = 0
    channel_delta_sum = 0
    for a, b in zip(left.getdata(), right.getdata()):
        deltas = (abs(a[0]-b[0]), abs(a[1]-b[1]), abs(a[2]-b[2]))
        m = max(deltas)
        if m > 0:
            raw_changed += 1
        if m > 1:
            changed_gt_1 += 1
        maximum_channel_delta = max(maximum_channel_delta, m)
        channel_delta_sum += sum(deltas)
    return {
        "pixel_count": pixel_count,
        "raw_changed_pixels": raw_changed,
        "changed_pixels_gt_1_lsb": changed_gt_1,
        "changed_fraction_gt_1_lsb": changed_gt_1 / pixel_count,
        "maximum_channel_delta_8bit": maximum_channel_delta,
        "mean_normalized_rgb_channel_delta": channel_delta_sum / (pixel_count * 3 * 255.0),
    }


def _filename(pose_id: str, context: str, frame_mode: str) -> str:
    return f"{pose_id}__{context}__{frame_mode}.png"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--renders", required=True, type=Path)
    parser.add_argument("--materials-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    payload = _load(args.payload)
    telemetry = _load(args.telemetry)
    if payload.get("schema") != EXPECTED_SCHEMA:
        raise SystemExit("payload schema drift")
    if telemetry.get("schema") != EXPECTED_TELEMETRY_SCHEMA:
        raise SystemExit("telemetry schema drift")
    if telemetry.get("render_count") != 40:
        raise SystemExit(f"expected 40 real renders, got {telemetry.get('render_count')}")
    if payload.get("exact_rigging_reconstruction_head") != telemetry.get("rigging_reconstruction_head"):
        raise SystemExit("Rigging reconstruction telemetry drift")
    if payload.get("exact_technical_art_glb_sha256") != telemetry.get("technical_art_glb_sha256"):
        raise SystemExit("Technical Art GLB telemetry drift")

    rows = []
    negative_rows = []
    deformed_transport_visible_count = 0
    reconstruction_recovery_count = 0
    neutral_transport_clean = True
    negative_control_valid = True

    for pose in payload["pose_sets"]:
        pose_id = str(pose["pose_id"])
        sample_index = int(pose["sample_index"])
        angle_deg = float(pose["angle_deg"])
        for context in payload["camera_contexts"]:
            owner = args.renders / _filename(pose_id, context, "owner_rederived")
            transported = args.renders / _filename(pose_id, context, "transported_static_skin")
            reconstructed = args.renders / _filename(pose_id, context, "position_reconstructed")
            negative = args.renders / _filename(pose_id, context, "position_reconstructed_flipped_w_negative")
            for path in (owner, transported, reconstructed, negative):
                if not path.is_file():
                    raise SystemExit(f"missing real render: {path}")

            owner_vs_transport = _compare(owner, transported)
            owner_vs_reconstruction = _compare(owner, reconstructed)
            reconstruction_vs_negative = _compare(reconstructed, negative)
            row = {
                "pose_id": pose_id,
                "sample_index": sample_index,
                "angle_deg": angle_deg,
                "camera_context": context,
                "owner_vs_transported_static_skin": owner_vs_transport,
                "owner_vs_position_reconstructed": owner_vs_reconstruction,
            }
            rows.append(row)
            negative_rows.append({
                "pose_id": pose_id,
                "sample_index": sample_index,
                "camera_context": context,
                "position_reconstructed_vs_flipped_w_negative": reconstruction_vs_negative,
            })

            # Samples 0/40 are neutral closure. Their static transported frame
            # should remain visually neutral relative to the owner frame.
            if sample_index in (0, 40):
                if owner_vs_transport["changed_pixels_gt_1_lsb"] > 50 or owner_vs_transport["mean_normalized_rgb_channel_delta"] > 1e-5:
                    neutral_transport_clean = False
            else:
                if owner_vs_transport["changed_pixels_gt_1_lsb"] > 0:
                    deformed_transport_visible_count += 1
                transport_mean = owner_vs_transport["mean_normalized_rgb_channel_delta"]
                recon_mean = owner_vs_reconstruction["mean_normalized_rgb_channel_delta"]
                if recon_mean <= max(1e-6, transport_mean * 0.10):
                    reconstruction_recovery_count += 1

            # Existing Materials #24 already proved W sensitivity broadly. This
            # new pack retains a bounded local witness in every exact context.
            if reconstruction_vs_negative["changed_fraction_gt_1_lsb"] < 0.005:
                negative_control_valid = False

    deformed_comparison_count = 6  # samples 10/20/30 x two cameras
    reconstruction_visual_recovery = (
        neutral_transport_clean
        and negative_control_valid
        and reconstruction_recovery_count == deformed_comparison_count
    )
    static_transport_renderer_visible = deformed_transport_visible_count > 0
    if reconstruction_visual_recovery and static_transport_renderer_visible:
        state = PASS_VISIBLE
    elif reconstruction_visual_recovery:
        state = PASS_NOT_VISUALLY_RESOLVED
    else:
        state = HOLD_STATE

    summary = {
        "state": state,
        "materials_head": args.materials_head,
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "rendering_device": telemetry.get("rendering_device"),
        },
        "provenance": {
            "rigging_reconstruction_head": payload["exact_rigging_reconstruction_head"],
            "rigging_reconstruction_module_blob": payload["exact_rigging_reconstruction_module_blob"],
            "rigging_transport_audit_module_blob": payload["exact_rigging_transport_audit_module_blob"],
            "rigging_reconstruction_artifact_id": payload["exact_rigging_reconstruction_artifact_id"],
            "rigging_reconstruction_artifact_sha256": payload["exact_rigging_reconstruction_artifact_sha256"],
            "technical_art_head": payload["exact_technical_art_head"],
            "technical_art_artifact_id": payload["exact_technical_art_artifact_id"],
            "technical_art_artifact_sha256": payload["exact_technical_art_artifact_sha256"],
            "technical_art_glb_sha256": payload["exact_technical_art_glb_sha256"],
            "art_direction_owner_frame_baseline_commit": payload["art_direction_owner_frame_baseline_commit"],
        },
        "gates": {
            "neutral_transport_clean": neutral_transport_clean,
            "negative_control_valid_all_contexts": negative_control_valid,
            "deformed_static_transport_visible_contexts": deformed_transport_visible_count,
            "deformed_comparison_count": deformed_comparison_count,
            "reconstruction_recovery_contexts": reconstruction_recovery_count,
            "reconstruction_visual_recovery": reconstruction_visual_recovery,
            "static_transport_renderer_visible": static_transport_renderer_visible,
        },
        "comparisons": rows,
        "negative_controls": negative_rows,
        "truth_boundary": {
            "this_is_materials_appearance_evidence_only": True,
            "owner_reconstruction_algorithm_copied_into_materials": False,
            "technical_art_adoption_claimed": False,
            "runtime_implementation_claimed": False,
            "production_tangent_space_adopted": False,
            "final_art_or_qa_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(state)
    if not negative_control_valid:
        raise SystemExit("flipped-handedness negative control was not renderer-visible in every context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
