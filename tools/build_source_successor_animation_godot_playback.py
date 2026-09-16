#!/usr/bin/env python3
"""Build the pinned Godot discrete-playback payload for the Animal source successor."""
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

EXPECTED_BASE_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_SOURCE_PROFILE_DIGEST = "8dbab7764819ebcbf825f6d0650053b108b8773df3644934738e3ec9f4712e66"
EXPECTED_CANDIDATE_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_SUCCESSOR_RIGGING_HEAD = "b48bb957622ed5c82a24ca4fcb471f7ee9b5147a"
EXPECTED_SOURCE_GATE = "PASS_SOURCE_SUCCESSOR_41_SAMPLE_MOTION_REBIND"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _godot_point(point: list[float]) -> list[float]:
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
    receipt = _load(evidence_dir / "source_successor_motion_receipt.json")
    frames_doc = _load(evidence_dir / "source_successor_motion_frames.json")
    if receipt.get("gate") != EXPECTED_SOURCE_GATE:
        raise ValueError("source-successor Animation prerequisite is not green")
    source = receipt.get("source_identity", {})
    donor = receipt.get("successor_rigging_donor", {})
    if source.get("base_source_digest") != EXPECTED_BASE_SOURCE_DIGEST:
        raise ValueError("base source identity drift")
    if source.get("source_successor_profile_digest") != EXPECTED_SOURCE_PROFILE_DIGEST:
        raise ValueError("source-successor profile identity drift")
    if source.get("source_successor_candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("source-successor candidate identity drift")
    if source.get("rig_plan_digest") != EXPECTED_RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if source.get("clip_digest") != EXPECTED_CLIP_DIGEST:
        raise ValueError("clip identity drift")
    if source.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("Animation weighting drift")
    if donor.get("git_head") != EXPECTED_SUCCESSOR_RIGGING_HEAD:
        raise ValueError("successor Rigging donor identity drift")
    if donor.get("refined_weighting_adopted_by_animation") is not False:
        raise ValueError("unreviewed refined weighting was silently adopted")
    if frames_doc.get("source_successor_candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("frame candidate identity drift")

    indices = [int(value) for value in frames_doc.get("indices", [])]
    source_frames = frames_doc.get("frames", [])
    if len(source_frames) != 41 or len(indices) != 240:
        raise ValueError("expected exact 41-sample / 80-triangle source-successor motion")
    if source_frames[0].get("positions") != source_frames[40].get("positions"):
        raise ValueError("endpoint neutral closure drift")

    frames: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(source_frames[:40]):
        positions = [_godot_point(point) for point in frame.get("positions", [])]
        if len(positions) != 42:
            raise ValueError("vertex-count drift")
        frames.append(
            {
                "frame_index": frame_index,
                "sample_index": int(frame.get("sample_index", -1)),
                "time_seconds": float(frame.get("time_seconds", -1.0)),
                "surface_digest": str(frame.get("positions_digest", "")),
                "angles_deg": {"front-elbow-L": float(frame.get("angle_deg", 0.0))},
                "positions": positions,
                "indices": indices,
            }
        )
    if any(frame["sample_index"] != index for index, frame in enumerate(frames)):
        raise ValueError("frame/sample ordering drift")
    unique_digests = len({frame["surface_digest"] for frame in frames})
    if unique_digests <= 2:
        raise ValueError("motion lacks materially distinct authored surfaces")

    receiving_repository = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "git_head": _git_head(),
    }
    source_identity = dict(source)
    source_identity.update(
        {
            "source_successor_rigging_head": EXPECTED_SUCCESSOR_RIGGING_HEAD,
            "connected_candidate_id": "front-left-connected-chain-elbow-source-successor-003",
            "connected_candidate_digest": EXPECTED_CANDIDATE_DIGEST,
        }
    )
    payload = {
        "schema": "axm.animal-animation-godot-discrete-playback-payload/v0.1",
        "proof_scope": "PINNED_GODOT_SOURCE_SUCCESSOR_AUTHORED_SAMPLE_APPLICATION_NOT_REALTIME_CONTROLLER",
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "source_playback": {
            "playback_schema": "axm.animal-animation-source-successor-motion-rebind/v0.1",
            "playback_mode": "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION",
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "display_frame_interval_seconds": 0.025,
            "endpoint_inclusive_source_sample_count": 41,
            "displayed_frame_count_per_cycle": 40,
            "source_gate": EXPECTED_SOURCE_GATE,
        },
        "coordinate_bridge": {
            "source": "+X forward, +Y left, +Z up",
            "godot": "+X right, +Y up, +Z forward-axis representation",
            "mapping": "[-source_y, source_z, source_x]",
            "purpose": "proof-host presentation only; no source geometry mutation",
        },
        "topology": {
            "candidate_id": "front-left-connected-chain-elbow-source-successor-003",
            "candidate_digest": EXPECTED_CANDIDATE_DIGEST,
            "vertex_count": 42,
            "index_count": 240,
            "triangle_count": 80,
            "primitive_partitions": [
                {
                    "id": "front-left-connected-chain-elbow-source-successor-003",
                    "vertex_offset": 0,
                    "vertex_count": 42,
                    "index_offset": 0,
                    "index_count": 240,
                }
            ],
        },
        "bounds_godot": _bounds(frames),
        "frames": frames,
        "truth": {
            "proves_if_green": [
                "the unchanged smoothstep-v0 41-sample Animation pulse rebound to the exact source-owned elbow successor can be applied as triangle geometry inside pinned Godot 4.7.2",
                "the proof host can step two complete exact 40-frame cycles and return to neutral without source-successor, rig, clip, weighting or sample-order substitution",
            ],
            "does_not_prove": [
                "continuous interpolation between authored samples",
                "real-time 40 Hz frame pacing",
                "exported skeleton or animation-clip transport",
                "runtime controller or state-machine integration",
                "gameplay acceptance",
                "ease-out-power-0p75-v1 adoption",
                "perceptual animation/deformation quality or biological gait",
                "target-device performance or production runtime acceptance",
            ],
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    PAYLOAD_PATH.write_bytes(payload_bytes)
    summary = {
        "schema": "axm.animal-animation-source-successor-godot-playback-build-summary/v0.1",
        "payload_sha256": _sha256(payload_bytes),
        "receiving_repository": receiving_repository,
        "source_identity": source_identity,
        "source_playback": payload["source_playback"],
        "topology": payload["topology"],
        "unique_authored_surface_digests": unique_digests,
        "bounds_godot": payload["bounds_godot"],
        "gate": "PASS_SOURCE_SUCCESSOR_GODOT_DISCRETE_PLAYBACK_PAYLOAD_BUILD",
        "truth": payload["truth"],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion-evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.motion_evidence_dir), sort_keys=True))


if __name__ == "__main__":
    main()
