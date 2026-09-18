#!/usr/bin/env python3
"""Build a bounded piecewise-linear interpolation payload for connected Animal motion.

This consumes the exact retained 41-sample connected Animation evidence and defines
C0-continuous vertex interpolation between adjacent authored samples. The payload
retains quarter-interval probes for every authored interval so the target host can
exercise real between-sample positions without claiming wall-clock pacing,
AnimationPlayer/skeleton transport, controller behavior, or gameplay acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tools" / "godot_animation_interpolation" / "generated"
PAYLOAD_PATH = OUT_DIR / "quadruped_animation_interpolation_payload.json"
SUMMARY_PATH = OUT_DIR / "quadruped_animation_interpolation_summary.json"

EXPECTED_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
EXPECTED_CONNECTED_DONOR_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"
SUBDIVISIONS_PER_INTERVAL = 4
AUTHORED_INTERVAL_SECONDS = 0.025


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _godot_point(point: list[float]) -> list[float]:
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    return [-y, z, x]


def _lerp_point(a: list[float], b: list[float], alpha: float) -> list[float]:
    return [float(a[axis]) + (float(b[axis]) - float(a[axis])) * alpha for axis in range(3)]


def _max_vertex_distance(a: list[list[float]], b: list[list[float]]) -> float:
    if len(a) != len(b):
        raise ValueError("vertex-count mismatch")
    maximum = 0.0
    for pa, pb in zip(a, b):
        distance = math.sqrt(sum((float(pa[axis]) - float(pb[axis])) ** 2 for axis in range(3)))
        maximum = max(maximum, distance)
    return maximum


def _bounds(frames: list[dict[str, Any]]) -> dict[str, list[float]]:
    points = [point for frame in frames for point in frame["positions"]]
    mins = [min(float(point[axis]) for point in points) for axis in range(3)]
    maxs = [max(float(point[axis]) for point in points) for axis in range(3)]
    return {
        "min": mins,
        "max": maxs,
        "center": [(mins[axis] + maxs[axis]) / 2.0 for axis in range(3)],
        "size": [maxs[axis] - mins[axis] for axis in range(3)],
    }


def build(evidence_dir: Path) -> dict[str, Any]:
    frames_doc = _load(evidence_dir / "connected_forelimb_motion_frames.json")
    receipt = _load(evidence_dir / "connected_forelimb_motion_receipt.json")

    if receipt.get("gate") != "PASS_EXACT_CONNECTED_FORELIMB_41_SAMPLE_MOTION_REBIND":
        raise ValueError("connected Animation prerequisite is not green")
    source = receipt.get("source_identity", {})
    donor = receipt.get("connected_rigging_donor", {})
    if source.get("source_digest") != EXPECTED_SOURCE_DIGEST:
        raise ValueError("source identity drift")
    if source.get("rig_plan_digest") != EXPECTED_RIG_PLAN_DIGEST:
        raise ValueError("rig-plan identity drift")
    if source.get("clip_digest") != EXPECTED_CLIP_DIGEST:
        raise ValueError("clip identity drift")
    if source.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("weighting drift; interpolation proof preserves smoothstep-v0")
    if source.get("motion_semantics") != "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION":
        raise ValueError("motion truth-label drift")
    if donor.get("git_head") != EXPECTED_CONNECTED_DONOR_HEAD:
        raise ValueError("connected Rigging donor head drift")
    if donor.get("candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("connected candidate identity drift")
    if frames_doc.get("candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("connected frame candidate identity drift")

    indices = [int(value) for value in frames_doc.get("indices", [])]
    source_frames = frames_doc.get("frames", [])
    if len(source_frames) != 41:
        raise ValueError("expected exact endpoint-inclusive 41 connected frames")
    if len(indices) != 240:
        raise ValueError("expected exact connected 80-triangle index buffer")
    if source_frames[0].get("positions") != source_frames[40].get("positions"):
        raise ValueError("connected endpoint does not close exactly to neutral")

    mapped_source: list[list[list[float]]] = []
    for frame in source_frames:
        positions = [_godot_point(point) for point in frame.get("positions", [])]
        if len(positions) != 42:
            raise ValueError("connected vertex-count drift")
        mapped_source.append(positions)

    frames: list[dict[str, Any]] = []
    maximum_authored_step = 0.0
    maximum_interpolated_step = 0.0
    maximum_authored_boundary_residual = 0.0
    maximum_join_residual = 0.0
    interior_distinct_failures = 0

    for interval_index in range(40):
        start = mapped_source[interval_index]
        end = mapped_source[interval_index + 1]
        authored_step = _max_vertex_distance(start, end)
        maximum_authored_step = max(maximum_authored_step, authored_step)
        for substep_index in range(SUBDIVISIONS_PER_INTERVAL):
            alpha = substep_index / float(SUBDIVISIONS_PER_INTERVAL)
            positions = [_lerp_point(a, b, alpha) for a, b in zip(start, end)]
            frame_index = interval_index * SUBDIVISIONS_PER_INTERVAL + substep_index
            if substep_index == 0:
                maximum_authored_boundary_residual = max(
                    maximum_authored_boundary_residual,
                    _max_vertex_distance(positions, start),
                )
            else:
                if _max_vertex_distance(positions, start) <= 0.0 or _max_vertex_distance(positions, end) <= 0.0:
                    interior_distinct_failures += 1
            frames.append({
                "frame_index": frame_index,
                "interval_index": interval_index,
                "substep_index": substep_index,
                "alpha": alpha,
                "time_seconds": (interval_index + alpha) * AUTHORED_INTERVAL_SECONDS,
                "authored_boundary": substep_index == 0,
                "source_sample_index": interval_index if substep_index == 0 else None,
                "positions": positions,
                "indices": indices,
            })

    final_positions = mapped_source[40]
    frames.append({
        "frame_index": 160,
        "interval_index": 39,
        "substep_index": 4,
        "alpha": 1.0,
        "time_seconds": 1.0,
        "authored_boundary": True,
        "source_sample_index": 40,
        "positions": final_positions,
        "indices": indices,
    })
    maximum_authored_boundary_residual = max(
        maximum_authored_boundary_residual,
        _max_vertex_distance(final_positions, mapped_source[40]),
    )

    for index in range(len(frames) - 1):
        maximum_interpolated_step = max(
            maximum_interpolated_step,
            _max_vertex_distance(frames[index]["positions"], frames[index + 1]["positions"]),
        )

    # C0 join proof: each linear interval ends at the exact next authored sample,
    # and the next interval starts at that same exact authored sample. We compute
    # this explicitly for every internal join plus the loop closure 1.0 -> 0.0.
    for sample_index in range(1, 40):
        left_end = [_lerp_point(a, b, 1.0) for a, b in zip(mapped_source[sample_index - 1], mapped_source[sample_index])]
        right_start = mapped_source[sample_index]
        maximum_join_residual = max(maximum_join_residual, _max_vertex_distance(left_end, right_start))
    loop_end = [_lerp_point(a, b, 1.0) for a, b in zip(mapped_source[39], mapped_source[40])]
    maximum_join_residual = max(maximum_join_residual, _max_vertex_distance(loop_end, mapped_source[0]))

    if maximum_authored_boundary_residual > 1e-12:
        raise ValueError("interpolation moved an authored boundary")
    if maximum_join_residual > 1e-12:
        raise ValueError("piecewise-linear C0 join residual exceeded tolerance")
    if interior_distinct_failures != 0:
        raise ValueError("one or more interior interpolation probes collapsed onto an authored endpoint")
    if maximum_authored_step <= 0.0:
        raise ValueError("authored motion contains no displacement")
    if maximum_interpolated_step > maximum_authored_step / SUBDIVISIONS_PER_INTERVAL + 1e-12:
        raise ValueError("quarter-step interpolation exceeded authored-step envelope")

    receiving_repository = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "git_head": _git_head(),
    }
    source_identity = dict(source)
    source_identity.update({
        "connected_candidate_id": donor.get("candidate_id"),
        "connected_candidate_digest": EXPECTED_CANDIDATE_DIGEST,
        "connected_rigging_donor_head": EXPECTED_CONNECTED_DONOR_HEAD,
    })
    payload = {
        "schema": "axm.animal-animation-connected-linear-interpolation-payload/v0.1",
        "proof_scope": "PIECEWISE_LINEAR_C0_VERTEX_INTERPOLATION_WITH_ALL_INTERVAL_QUARTER_PROBES_NOT_REALTIME_CONTROLLER",
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "interpolation_contract": {
            "method": "piecewise-linear per-vertex lerp",
            "continuity_class_claimed": "C0_POSITION_ONLY",
            "authored_duration_seconds": 1.0,
            "authored_sample_rate_hz": 40,
            "authored_interval_seconds": AUTHORED_INTERVAL_SECONDS,
            "endpoint_inclusive_authored_sample_count": 41,
            "authored_interval_count": 40,
            "subdivisions_per_authored_interval": SUBDIVISIONS_PER_INTERVAL,
            "interior_probe_alphas": [0.25, 0.5, 0.75],
            "probe_frame_count_including_final_endpoint": len(frames),
            "display_cycle_probe_count_excluding_duplicate_endpoint": 160,
            "source_gate": receipt["gate"],
        },
        "coordinate_bridge": {
            "source": "+X forward, +Y left, +Z up",
            "mapping": "[-source_y, source_z, source_x]",
            "purpose": "proof-host presentation only; no source geometry mutation",
        },
        "topology": {
            "candidate_id": donor.get("candidate_id"),
            "candidate_digest": EXPECTED_CANDIDATE_DIGEST,
            "vertex_count": 42,
            "index_count": 240,
            "triangle_count": 80,
        },
        "bounds_godot": _bounds(frames),
        "continuity_metrics": {
            "maximum_authored_boundary_residual_m": maximum_authored_boundary_residual,
            "maximum_piecewise_join_residual_m": maximum_join_residual,
            "maximum_authored_adjacent_vertex_step_m": maximum_authored_step,
            "maximum_quarter_probe_adjacent_vertex_step_m": maximum_interpolated_step,
            "maximum_probe_to_authored_step_ratio": maximum_interpolated_step / maximum_authored_step,
            "interior_endpoint_collapse_failures": interior_distinct_failures,
        },
        "frames": frames,
        "truth": {
            "proves_if_green": [
                "the exact smoothstep-v0 connected authored samples define a C0-continuous piecewise-linear per-vertex interpolation function with zero positional join residual at all authored boundaries including loop closure",
                "quarter-interval probes at alpha 0.25, 0.5 and 0.75 exist for every authored interval without changing exact authored endpoints",
                "the pinned Godot proof host can apply the retained between-sample probe surfaces if the target-host gate is green",
            ],
            "does_not_prove": [
                "C1 velocity or acceleration continuity",
                "real-time 40 Hz or 160 Hz pacing",
                "AnimationPlayer, skeleton, skin or exported clip interpolation",
                "runtime controller or state-machine integration",
                "gameplay acceptance",
                "continuous self-intersection freedom, volume preservation or final deformation quality",
                "perceptual motion quality, gait or locomotion",
                "target-device performance or production runtime acceptance",
            ],
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    PAYLOAD_PATH.write_bytes(payload_bytes)
    summary = {
        "schema": "axm.animal-animation-connected-linear-interpolation-summary/v0.1",
        "payload_sha256": _sha256(payload_bytes),
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "interpolation_contract": payload["interpolation_contract"],
        "topology": payload["topology"],
        "continuity_metrics": payload["continuity_metrics"],
        "gate": "PASS_CONNECTED_PIECEWISE_LINEAR_C0_INTERPOLATION_PAYLOAD",
        "truth": payload["truth"],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--connected-evidence-dir",
        type=Path,
        default=ROOT / "evidence" / "animation-connected-forelimb-motion-001",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.connected_evidence_dir), sort_keys=True))


if __name__ == "__main__":
    main()
