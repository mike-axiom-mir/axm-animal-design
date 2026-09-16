#!/usr/bin/env python3
"""Build a Godot playback payload from the exact connected Animation evidence.

This bridge intentionally consumes the already-proven 41-sample connected motion
artifact produced by build_connected_animation_rebind_evidence.py. It does not
recompute or replace Rigging deformation semantics. It only translates the exact
retained positions into the existing bounded Godot proof-host coordinate system
and omits the duplicate endpoint from the displayed 40-frame cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tools" / "godot_animation_playback" / "generated"
PAYLOAD_PATH = OUT_DIR / "quadruped_animation_payload.json"
SUMMARY_PATH = OUT_DIR / "quadruped_animation_payload_summary.json"

EXPECTED_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
EXPECTED_CONNECTED_DONOR_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"


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
    # Preserve the already-used Animal proof-host bridge: source +X forward,
    # +Y left, +Z up -> Godot [-Y, Z, X]. This is presentation only.
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    return [-y, z, x]


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
        raise ValueError("weighting drift; connected playback must preserve smoothstep-v0")
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

    frames: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(source_frames[:40]):
        positions = [_godot_point(point) for point in frame.get("positions", [])]
        if len(positions) != 42:
            raise ValueError("connected vertex-count drift")
        frames.append({
            "frame_index": frame_index,
            "sample_index": int(frame.get("sample_index", -1)),
            "time_seconds": float(frame.get("time_seconds", -1.0)),
            "surface_digest": str(frame.get("positions_digest", "")),
            "angles_deg": {"front-elbow-L": float(frame.get("angle_deg", 0.0))},
            "positions": positions,
            "indices": indices,
        })
    if any(frame["sample_index"] != index for index, frame in enumerate(frames)):
        raise ValueError("connected frame/sample ordering drift")
    unique_digests = len({frame["surface_digest"] for frame in frames})
    if unique_digests <= 2:
        raise ValueError("connected playback lacks materially distinct posed surfaces")

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
        "schema": "axm.animal-animation-godot-discrete-playback-payload/v0.1",
        "proof_scope": "PINNED_GODOT_CONNECTED_AUTHORED_SAMPLE_APPLICATION_NOT_REALTIME_CONTROLLER",
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "source_playback": {
            "playback_schema": "axm.animal-animation-connected-forelimb-motion-rebind/v0.1",
            "playback_mode": "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION",
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "display_frame_interval_seconds": 0.025,
            "endpoint_inclusive_source_sample_count": 41,
            "displayed_frame_count_per_cycle": 40,
            "source_gate": receipt["gate"],
        },
        "coordinate_bridge": {
            "source": "+X forward, +Y left, +Z up",
            "godot": "+X right, +Y up, +Z forward-axis representation",
            "mapping": "[-source_y, source_z, source_x]",
            "purpose": "proof-host presentation only; no source geometry mutation",
        },
        "topology": {
            "candidate_id": donor.get("candidate_id"),
            "candidate_digest": EXPECTED_CANDIDATE_DIGEST,
            "vertex_count": 42,
            "index_count": 240,
            "triangle_count": 80,
            "primitive_partitions": [{
                "id": str(donor.get("candidate_id")),
                "vertex_offset": 0,
                "vertex_count": 42,
                "index_offset": 0,
                "index_count": 240,
            }],
        },
        "bounds_godot": _bounds(frames),
        "frames": frames,
        "truth": {
            "proves_if_green": [
                "the exact smoothstep-v0 connected left-forelimb authored samples can be applied as triangle geometry inside pinned Godot 4.7.2",
                "the proof host can step two full exact 40-frame connected cycles and return to neutral without source, rig, clip, weighting or connected-candidate substitution",
            ],
            "does_not_prove": [
                "continuous interpolation between authored samples",
                "real-time 40 Hz frame pacing",
                "exported skeleton or animation-clip transport",
                "runtime controller or state-machine integration",
                "gameplay acceptance",
                "whole-body connected topology or source adoption",
                "perceptual animation/deformation quality or biological gait",
                "target-device performance or production runtime acceptance",
            ],
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    PAYLOAD_PATH.write_bytes(payload_bytes)
    summary = {
        "schema": "axm.animal-animation-connected-godot-discrete-playback-build-summary/v0.1",
        "payload_sha256": _sha256(payload_bytes),
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "source_playback": payload["source_playback"],
        "topology": payload["topology"],
        "unique_authored_surface_digests": unique_digests,
        "bounds_godot": payload["bounds_godot"],
        "gate": "PASS_CONNECTED_GODOT_DISCRETE_PLAYBACK_PAYLOAD_BUILD",
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
