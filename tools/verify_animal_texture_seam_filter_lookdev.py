#!/usr/bin/env python3
"""Verify Animal UV seam / texture-filter real-render evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageFilter

EXPECTED_PAYLOAD_SCHEMA = "axm.animal-materials-transported-frame-lookdev/v0.1"
EXPECTED_TELEMETRY_SCHEMA = "axm.animal-materials-texture-seam-filter-lookdev-telemetry/v0.1"
PASS_STATE = "PASS_ANIMAL_PERIODIC_NORMAL_TEXTURE_BASE_EDGE_CLOSED__MIPPED_SEAM_MUTATION_LOCALIZED"
HOLD_STATE = "HOLD_ANIMAL_TEXTURE_SEAM_FILTER_LOOKDEV"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _filename(pose_id: str, context: str, mode: str) -> str:
    return f"{pose_id}__{context}__{mode}.png"


def _rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def _compare(left: Image.Image, right: Image.Image):
    if left.size != right.size:
        raise SystemExit("image size mismatch")
    changed = []
    max_delta = 0
    delta_sum = 0
    for a, b in zip(left.getdata(), right.getdata()):
        deltas = (abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
        maximum = max(deltas)
        changed.append(255 if maximum > 1 else 0)
        max_delta = max(max_delta, maximum)
        delta_sum += sum(deltas)
    count = sum(1 for value in changed if value)
    pixels = left.width * left.height
    mask = Image.new("L", left.size)
    mask.putdata(changed)
    return {
        "pixel_count": pixels,
        "changed_pixels_gt_1_lsb": count,
        "changed_fraction_gt_1_lsb": count / pixels,
        "maximum_channel_delta_8bit": max_delta,
        "mean_normalized_rgb_channel_delta": delta_sum / (pixels * 3 * 255.0),
        "mask": mask,
    }


def _locator_mask(image: Image.Image) -> Image.Image:
    values = []
    for r, g, b in image.getdata():
        values.append(255 if (r >= 180 and r >= g * 2 and r >= b * 2) else 0)
    mask = Image.new("L", image.size)
    mask.putdata(values)
    return mask


def _mask_count(mask: Image.Image) -> int:
    return sum(1 for value in mask.getdata() if value)


def _overlap_fraction(diff_mask: Image.Image, locator: Image.Image) -> float:
    # Allow a small raster/filter halo around the UV-edge locator rather than
    # pretending projected texture filtering is pixel-perfect to the locator.
    dilated = locator.filter(ImageFilter.MaxFilter(21))
    diff_values = list(diff_mask.getdata())
    loc_values = list(dilated.getdata())
    changed = sum(1 for value in diff_values if value)
    if changed == 0:
        return 0.0
    overlap = sum(1 for a, b in zip(diff_values, loc_values) if a and b)
    return overlap / changed


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
    if payload.get("schema") != EXPECTED_PAYLOAD_SCHEMA:
        raise SystemExit("payload schema drift")
    if telemetry.get("schema") != EXPECTED_TELEMETRY_SCHEMA:
        raise SystemExit("telemetry schema drift")
    if telemetry.get("render_count") != 50:
        raise SystemExit(f"expected 50 real renders, got {telemetry.get('render_count')}")
    if telemetry.get("rigging_reconstruction_head") != payload.get("exact_rigging_reconstruction_head"):
        raise SystemExit("Rigging reconstruction telemetry drift")
    if telemetry.get("technical_art_glb_sha256") != payload.get("exact_technical_art_glb_sha256"):
        raise SystemExit("Technical Art GLB telemetry drift")

    candidate_edge_closed = telemetry.get("candidate_base_edge_max_rgb_delta_8bit") == 0
    negative_edge_broken = int(telemetry.get("negative_base_edge_max_rgb_delta_8bit", 0)) >= 8
    rows = []
    candidate_response_visible = True
    visible_seam_contexts = 0
    negative_visible_contexts = 0
    localized_contexts = 0
    mip_filter_visible_contexts = 0

    for pose in payload["pose_sets"]:
        pose_id = str(pose["pose_id"])
        for context in payload["camera_contexts"]:
            paths = {
                mode: args.renders / _filename(pose_id, str(context), mode)
                for mode in (
                    "flat_control",
                    "periodic_mipped",
                    "periodic_no_mip",
                    "edge_mutated_mipped_negative",
                    "seam_locator",
                )
            }
            for path in paths.values():
                if not path.is_file():
                    raise SystemExit(f"missing real render: {path}")
            flat = _rgb(paths["flat_control"])
            candidate = _rgb(paths["periodic_mipped"])
            no_mip = _rgb(paths["periodic_no_mip"])
            negative = _rgb(paths["edge_mutated_mipped_negative"])
            locator_image = _rgb(paths["seam_locator"])

            candidate_vs_flat = _compare(candidate, flat)
            candidate_vs_negative = _compare(candidate, negative)
            candidate_vs_no_mip = _compare(candidate, no_mip)
            locator = _locator_mask(locator_image)
            locator_pixels = _mask_count(locator)
            overlap = _overlap_fraction(candidate_vs_negative["mask"], locator)

            if candidate_vs_flat["changed_pixels_gt_1_lsb"] < 100:
                candidate_response_visible = False
            if candidate_vs_no_mip["changed_pixels_gt_1_lsb"] > 0:
                mip_filter_visible_contexts += 1
            if locator_pixels >= 20:
                visible_seam_contexts += 1
                if candidate_vs_negative["changed_pixels_gt_1_lsb"] > 0:
                    negative_visible_contexts += 1
                    if overlap >= 0.50:
                        localized_contexts += 1

            rows.append({
                "pose_id": pose_id,
                "sample_index": int(pose["sample_index"]),
                "angle_deg": float(pose["angle_deg"]),
                "camera_context": str(context),
                "locator_pixels": locator_pixels,
                "candidate_vs_flat": {k: v for k, v in candidate_vs_flat.items() if k != "mask"},
                "candidate_vs_no_mip": {k: v for k, v in candidate_vs_no_mip.items() if k != "mask"},
                "candidate_vs_edge_mutated_negative": {k: v for k, v in candidate_vs_negative.items() if k != "mask"},
                "negative_diff_overlap_with_dilated_seam_locator": overlap,
            })

    localized_negative_valid = (
        visible_seam_contexts > 0
        and negative_visible_contexts == visible_seam_contexts
        and localized_contexts == visible_seam_contexts
    )
    state = PASS_STATE if (
        candidate_edge_closed
        and negative_edge_broken
        and candidate_response_visible
        and localized_negative_valid
    ) else HOLD_STATE

    summary = {
        "state": state,
        "materials_head": args.materials_head,
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "rendering_device": telemetry.get("rendering_device"),
        },
        "texture_probe": {
            "size_px": telemetry.get("texture_size"),
            "edge_mutation_pixels": telemetry.get("edge_mutation_pixels"),
            "seam_locator_band_uv": telemetry.get("seam_locator_band_uv"),
            "candidate_base_edge_max_rgb_delta_8bit": telemetry.get("candidate_base_edge_max_rgb_delta_8bit"),
            "negative_base_edge_max_rgb_delta_8bit": telemetry.get("negative_base_edge_max_rgb_delta_8bit"),
        },
        "gates": {
            "candidate_base_edge_closed": candidate_edge_closed,
            "negative_base_edge_broken": negative_edge_broken,
            "candidate_normal_response_visible_all_contexts": candidate_response_visible,
            "visible_seam_contexts": visible_seam_contexts,
            "negative_visible_contexts": negative_visible_contexts,
            "localized_negative_contexts": localized_contexts,
            "localized_negative_valid": localized_negative_valid,
            "mip_filter_difference_visible_contexts": mip_filter_visible_contexts,
        },
        "comparisons": rows,
        "provenance": {
            "rigging_reconstruction_head": payload.get("exact_rigging_reconstruction_head"),
            "technical_art_head": payload.get("exact_technical_art_head"),
            "technical_art_glb_sha256": payload.get("exact_technical_art_glb_sha256"),
            "art_direction_owner_frame_baseline_commit": payload.get("art_direction_owner_frame_baseline_commit"),
        },
        "truth_boundary": {
            "base_level_periodic_texture_edge_closure_proven": candidate_edge_closed,
            "real_mipped_sampling_exercised": True,
            "all_mipmap_levels_wrap_perfect_claimed": False,
            "production_normal_map_claimed": False,
            "final_uv_packing_or_texel_density_claimed": False,
            "technical_art_or_runtime_adoption_claimed": False,
            "final_art_or_qa_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(state)
    if not localized_negative_valid:
        raise SystemExit("edge-mutated seam negative was not visible and localized in every visible-seam context")
    if not candidate_edge_closed or not negative_edge_broken:
        raise SystemExit("texture-edge structural controls failed")
    if not candidate_response_visible:
        raise SystemExit("periodic normal texture did not produce visible target-host response in every context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
