#!/usr/bin/env python3
"""Verify target-host tangent-space frames for the unchanged Animal Animation loop."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

EXPECTED_MATERIALS_HEAD = "e9d5c451b16bd05d2419248f58bef911f83dc1e8"
EXPECTED_RIGGING_HEAD = "63c65d57fda0595217f86d971ff8c67f256188be"
EXPECTED_GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_RENDERER_BLOB = "252537d1544aa4e4af20bc78e54a6f886c1b9af0"
STATE = "PASS_TARGET_HOST_TANGENT_SPACE_SHADED_AUTHORED_SAMPLE_LOOP_CAPTURED"
SCHEMA = "axm.animal-animation-tangent-space-motion-review-evidence/v0.1"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_name(side: str, sample: int, camera: str) -> str:
    return f"animation__{side}__sample_{sample:02d}__{camera}__periodic_tangent_probe.png"


def changed_fraction_gt_1lsb(a: Path, b: Path) -> dict[str, Any]:
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    if ia.size != ib.size:
        raise ValueError("image size mismatch")
    changed = 0
    total = ia.size[0] * ia.size[1]
    for pa, pb in zip(ia.getdata(), ib.getdata()):
        if max(abs(int(x) - int(y)) for x, y in zip(pa, pb)) > 1:
            changed += 1
    ia.close()
    ib.close()
    return {"changed_pixels_gt_1lsb": changed, "total_pixels": total, "changed_fraction_gt_1lsb": changed / total}


def byte_identical(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def build_gif(frame_paths: list[Path], out: Path) -> None:
    images = [Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for path in frame_paths]
    out.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out, save_all=True, append_images=images[1:], duration=25, loop=0, optimize=False, disposal=2)
    for image in images:
        image.close()


def build_montage(renders: Path, out: Path) -> None:
    samples = [0, 10, 20, 30, 40]
    rows = [("left", "three_quarter"), ("right", "three_quarter"), ("left", "grazing"), ("right", "grazing")]
    thumbs = []
    for side, camera in rows:
        row = []
        for sample in samples:
            image = Image.open(renders / image_name(side, sample, camera)).convert("RGB")
            image.thumbnail((320, 240))
            row.append(image.copy())
            image.close()
        thumbs.append(row)
    cell_w = max(i.width for row in thumbs for i in row)
    cell_h = max(i.height for row in thumbs for i in row)
    canvas = Image.new("RGB", (cell_w * len(samples), cell_h * len(rows) + 28), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), "samples 00 / 10 / 20 / 30 / 40 — exact Materials PR #24 periodic tangent probe", fill=(235, 235, 235))
    y0 = 28
    for r, row in enumerate(thumbs):
        for c, image in enumerate(row):
            canvas.paste(image, (c * cell_w, y0 + r * cell_h))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    canvas.close()
    for row in thumbs:
        for image in row:
            image.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--telemetry", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--montage", type=Path, required=True)
    parser.add_argument("--gif-dir", type=Path, required=True)
    args = parser.parse_args()

    payload = load(args.payload)
    build = load(args.build_receipt)
    telemetry = load(args.telemetry)
    if build.get("gate") != "PASS_TANGENT_SPACE_SHADED_MOTION_REVIEW_PAYLOAD_BUILD":
        raise ValueError("payload build gate is not PASS")
    if build.get("materials_head") != EXPECTED_MATERIALS_HEAD or build.get("materials_render_review_blob") != EXPECTED_RENDERER_BLOB:
        raise ValueError("Materials donor identity drift")
    if build.get("rigging_tangent_head") != EXPECTED_RIGGING_HEAD or build.get("geometry_uv_tangent_head") != EXPECTED_GEOMETRY_HEAD:
        raise ValueError("Geometry/Rigging donor identity drift")
    if build.get("clip_digest") != EXPECTED_CLIP_DIGEST:
        raise ValueError("Animation clip identity drift")
    if build.get("payload_sha256") != file_sha(args.payload):
        raise ValueError("review payload digest drift")
    if payload.get("exact_materials_tangent_space_head") != EXPECTED_MATERIALS_HEAD:
        raise ValueError("payload Materials identity drift")
    if telemetry.get("rigging_tangent_head") != EXPECTED_RIGGING_HEAD or telemetry.get("geometry_uv_tangent_head") != EXPECTED_GEOMETRY_HEAD:
        raise ValueError("target-host donor identity drift")
    if telemetry.get("rendering_method") != "gl_compatibility":
        raise ValueError("unexpected Godot rendering method")

    expected = []
    for side in ("left", "right"):
        for sample in range(41):
            for camera in ("three_quarter", "grazing"):
                expected.append(image_name(side, sample, camera))
    observed = {p.name for p in args.renders.glob("*.png")}
    if set(expected) != observed:
        missing = sorted(set(expected) - observed)
        extra = sorted(observed - set(expected))
        raise ValueError(f"render set drift: missing={missing[:5]} extra={extra[:5]}")
    if int(telemetry.get("render_count", -1)) != len(expected):
        raise ValueError("target-host render-count drift")

    contexts = []
    for side in ("left", "right"):
        for camera in ("three_quarter", "grazing"):
            p0 = args.renders / image_name(side, 0, camera)
            p10 = args.renders / image_name(side, 10, camera)
            p20 = args.renders / image_name(side, 20, camera)
            p30 = args.renders / image_name(side, 30, camera)
            p40 = args.renders / image_name(side, 40, camera)
            endpoint_identical = byte_identical(p0, p40)
            if not endpoint_identical:
                raise ValueError(f"{side}/{camera} shaded endpoint seam is not byte-identical")
            neutral_peak = changed_fraction_gt_1lsb(p0, p20)
            if int(neutral_peak["changed_pixels_gt_1lsb"]) <= 0:
                raise ValueError(f"{side}/{camera} neutral and peak are visually identical")
            quarter_symmetry = changed_fraction_gt_1lsb(p10, p30)
            contexts.append({
                "side": side,
                "camera_context": camera,
                "endpoint_neutral_byte_identical": endpoint_identical,
                "neutral_vs_peak": neutral_peak,
                "sample10_vs_sample30_symmetry_observation": quarter_symmetry,
            })
            build_gif([args.renders / image_name(side, i, camera) for i in range(40)], args.gif_dir / f"{side}__{camera}__40fps_authored_samples.gif")

    build_montage(args.renders, args.montage)
    receipt = {
        "schema": SCHEMA,
        "state": STATE,
        "materials_tangent_space_head": EXPECTED_MATERIALS_HEAD,
        "materials_render_review_blob": EXPECTED_RENDERER_BLOB,
        "rigging_tangent_head": EXPECTED_RIGGING_HEAD,
        "geometry_uv_tangent_head": EXPECTED_GEOMETRY_HEAD,
        "animation_clip_digest": EXPECTED_CLIP_DIGEST,
        "payload_sha256": file_sha(args.payload),
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "render_count": int(telemetry.get("render_count", 0)),
        },
        "motion_capture": {
            "sides": 2,
            "camera_contexts": 2,
            "endpoint_inclusive_samples_per_side": 41,
            "source_png_count": len(expected),
            "review_gif_count": 4,
            "review_gif_frame_count_each": 40,
            "review_gif_declared_frame_duration_ms": 25,
            "discrete_authored_sample_sequence_only": True,
            "contexts": contexts,
        },
        "decision_boundary": "SHADED_DISCRETE_MOTION_REVIEW_SURFACE_ONLY__CONTINUOUS_INTERPOLATION_TIMING_AND_AESTHETIC_ACCEPTANCE_HELD",
        "truth_boundary": {
            "exact_materials_shader_reused_unchanged": True,
            "motion_retimed": False,
            "new_animation_keys_authored": False,
            "weighting_changed": False,
            "discrete_authored_sample_shaded_sequence_captured": True,
            "continuous_interpolation_visual_quality_proven": False,
            "real_time_40hz_engine_pacing_proven": False,
            "gif_timing_is_engine_runtime_evidence": False,
            "final_tangent_space_visual_quality_accepted": False,
            "production_skin_tangent_transport_established": False,
            "runtime_controller_or_state_machine_accepted": False,
            "gameplay_accepted": False,
            "canon_claimed": False,
            "production_ready_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
