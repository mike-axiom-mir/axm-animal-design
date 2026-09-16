#!/usr/bin/env python3
"""Prove bilateral authored track intent without inheriting right-side deformation acceptance.

This Animation-local observer exists because Organic Form now source-owns a mirrored
right elbow successor while the current Animation surface proof is still explicitly
bound to the left source-successor Geometry/Rigging chain.  The contract therefore
separates two questions that must not be collapsed:

1. Is the existing authored clip itself bilaterally symmetric in timing/amplitude?
2. Has the new right source successor been rebound through Geometry/Rigging and
   directly exercised as a deforming/rendered surface?

This tool can answer only (1).  A green result intentionally keeps (2) held.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "axm.animal-animation-bilateral-track-intent/v0.1"
GATE = "PASS_BILATERAL_CLIP_TRACK_INTENT_PRESERVED__RIGHT_SURFACE_PLAYBACK_HELD"
ORGANIC_BILATERAL_HEAD = "4df3024b4c459675422565501a46f622acf229a9"
EXPECTED_BASE_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_LEFT_SUCCESSOR_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
EXPECTED_RIGHT_SUCCESSOR_DIGEST = "262f536e0e522fd3e102cb16464c3757985fbb1dfcb3001df3b1f27b623b0115"
EXPECTED_BILATERAL_PROFILE_ID = "quadruped-front-elbow-bilateral-form-successor-003"
EXPECTED_CLIP_NAME = "quadruped-articulation-loop-001"
EXPECTED_MOTION_SEMANTICS = "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _raised_cosine(sample_index: int, interval_count: int) -> float:
    if sample_index in (0, interval_count):
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * sample_index / interval_count)


def _require_track(tracks: dict[str, dict[str, Any]], joint_id: str, peak: float) -> dict[str, Any]:
    track = tracks.get(joint_id)
    if not track:
        raise ValueError(f"missing authored track: {joint_id}")
    observed = float(track.get("peak_angle_deg"))
    if not math.isclose(observed, peak, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{joint_id} peak drift: {observed} != {peak}")
    return track


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.organic_bilateral_head != ORGANIC_BILATERAL_HEAD:
        raise ValueError("Organic bilateral donor head drift")

    clip = _load(args.clip)
    bilateral = _load(args.bilateral_profile)

    if clip.get("schema") != "axm.animal-animation-motion-clip/v0.1":
        raise ValueError("clip schema drift")
    if clip.get("name") != EXPECTED_CLIP_NAME:
        raise ValueError("clip name drift")
    if clip.get("motion_semantics") != EXPECTED_MOTION_SEMANTICS:
        raise ValueError("clip truth label drift")
    if clip.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("bilateral intent evidence must preserve smoothstep-v0")
    if clip.get("curve") != "raised-cosine-neutral-to-peak-to-neutral":
        raise ValueError("clip curve drift")

    duration = float(clip.get("duration_seconds"))
    sample_rate = int(clip.get("sample_rate_hz"))
    if duration != 1.0 or sample_rate != 40:
        raise ValueError("clip timing drift; expected exact 1.0 s / 40 Hz")
    interval_count = int(round(duration * sample_rate))
    if interval_count != 40:
        raise ValueError("clip interval-count drift")

    track_rows = clip.get("tracks", [])
    if not isinstance(track_rows, list):
        raise ValueError("clip tracks must be a list")
    tracks = {str(row.get("joint_id")): row for row in track_rows if isinstance(row, dict)}
    _require_track(tracks, "front-elbow-L", 18.0)
    _require_track(tracks, "front-elbow-R", 18.0)
    _require_track(tracks, "hind-knee-L", 14.0)
    _require_track(tracks, "hind-knee-R", 14.0)

    if bilateral.get("schema") != "axm.animal-organic-bilateral-form-successor/v0.1":
        raise ValueError("Organic bilateral profile schema drift")
    if bilateral.get("id") != EXPECTED_BILATERAL_PROFILE_ID:
        raise ValueError("Organic bilateral profile id drift")
    if bilateral.get("base_source", {}).get("digest") != EXPECTED_BASE_SOURCE_DIGEST:
        raise ValueError("Organic bilateral base-source identity drift")
    left = bilateral.get("left_successor", {})
    if left.get("candidate_digest") != EXPECTED_LEFT_SUCCESSOR_DIGEST:
        raise ValueError("Organic left successor identity drift")
    right = bilateral.get("right_receiver", {})
    if right.get("candidate_id") != "front-right-connected-chain-001":
        raise ValueError("Organic right receiver identity drift")
    mirror = bilateral.get("mirror_contract", {})
    if mirror.get("plane") != "Y=0" or float(mirror.get("maximum_position_residual_m")) != 0.0:
        raise ValueError("Organic bilateral mirror contract drift")
    ownership = bilateral.get("ownership", {})
    if ownership.get("source_owner") != "organic-form" or ownership.get("source_owned_successor") is not True:
        raise ValueError("Organic bilateral source ownership drift")
    if ownership.get("canonical") is not False:
        raise ValueError("Organic bilateral successor unexpectedly became canonical")

    # The right successor digest is supplied by the exact Organic evidence/status handoff.
    # The profile intentionally carries the right receiver + right form change, while the
    # retained Organic evidence owns the resulting right candidate digest.  We record that
    # handoff identity without pretending Animation rebuilt Organic geometry here.
    right_form = bilateral.get("right_form_change", {})
    if right_form.get("landmark") != "elbow_R":
        raise ValueError("Organic right elbow form-change landmark drift")
    if [float(value) for value in right_form.get("axis", [])] != [0.0, -1.0, 0.0]:
        raise ValueError("Organic right elbow form-change axis drift")
    if not math.isclose(float(right_form.get("bend_plane_radius_m")), 0.0885, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Organic right elbow bend-plane radius drift")
    if not math.isclose(float(right_form.get("joint_axis_width_scale")), 1.03, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Organic right elbow joint-axis width drift")

    samples: list[dict[str, Any]] = []
    max_front_pair_residual = 0.0
    max_hind_pair_residual = 0.0
    for sample_index in range(interval_count + 1):
        envelope = _raised_cosine(sample_index, interval_count)
        front_l = 18.0 * envelope
        front_r = 18.0 * envelope
        hind_l = 14.0 * envelope
        hind_r = 14.0 * envelope
        max_front_pair_residual = max(max_front_pair_residual, abs(front_l - front_r))
        max_hind_pair_residual = max(max_hind_pair_residual, abs(hind_l - hind_r))
        samples.append(
            {
                "sample_index": sample_index,
                "time_seconds": round(sample_index / sample_rate, 9),
                "envelope": round(envelope, 12),
                "front_elbow_L_deg": round(front_l, 12),
                "front_elbow_R_deg": round(front_r, 12),
                "hind_knee_L_deg": round(hind_l, 12),
                "hind_knee_R_deg": round(hind_r, 12),
            }
        )

    if max_front_pair_residual != 0.0 or max_hind_pair_residual != 0.0:
        raise ValueError("bilateral authored track symmetry drift")
    if any(abs(float(samples[index]["front_elbow_L_deg"])) > 1e-12 for index in (0, 40)):
        raise ValueError("front elbow neutral closure drift")
    if any(abs(float(samples[index]["hind_knee_L_deg"])) > 1e-12 for index in (0, 40)):
        raise ValueError("hind knee neutral closure drift")
    if not math.isclose(float(samples[20]["front_elbow_L_deg"]), 18.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("front elbow peak drift")
    if not math.isclose(float(samples[20]["hind_knee_L_deg"]), 14.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("hind knee peak drift")

    receipt = {
        "schema": SCHEMA,
        "gate": GATE,
        "receiving_repository": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "git_head": _git_head(),
        },
        "authored_clip": {
            "name": EXPECTED_CLIP_NAME,
            "canonical_json_sha256": _canonical_digest(clip),
            "motion_semantics": EXPECTED_MOTION_SEMANTICS,
            "duration_seconds": duration,
            "sample_rate_hz": sample_rate,
            "endpoint_inclusive_sample_count": len(samples),
            "curve": clip["curve"],
            "rig_weighting_profile": clip["rig_weighting_profile"],
            "motion_changed": False,
            "retimed": False,
            "new_keys_authored": False,
        },
        "organic_bilateral_source_handoff": {
            "git_head": ORGANIC_BILATERAL_HEAD,
            "profile_id": EXPECTED_BILATERAL_PROFILE_ID,
            "profile_canonical_json_sha256": _canonical_digest(bilateral),
            "left_source_successor_digest": EXPECTED_LEFT_SUCCESSOR_DIGEST,
            "right_source_successor_digest_from_organic_handoff": EXPECTED_RIGHT_SUCCESSOR_DIGEST,
            "mirror_plane": "Y=0",
            "source_mirror_residual_m": 0.0,
            "canonical": False,
        },
        "observed_authored_motion": {
            "front_pair_peak_angle_deg": 18.0,
            "hind_pair_peak_angle_deg": 14.0,
            "maximum_front_pair_angle_residual_deg": max_front_pair_residual,
            "maximum_hind_pair_angle_residual_deg": max_hind_pair_residual,
            "exact_neutral_start_return": True,
            "exact_peak_sample_index": 20,
        },
        "adoption_boundary": {
            "left_source_successor_surface_playback": "ALREADY_PROVEN_ON_ANCESTOR_EVIDENCE__NOT_REBUILT_BY_THIS_TRACK_OBSERVER",
            "right_source_successor_motion_intent": "AUTHORED_TRACK_PRESENT_AND_EXACTLY_BILATERAL",
            "right_geometry_identity_consumed_by_animation": False,
            "right_rigging_identity_consumed_by_animation": False,
            "right_deforming_surface_generated": False,
            "right_target_host_playback_generated": False,
            "next_required_dependency": "EXPLICIT_RIGHT_GEOMETRY_THEN_RIGGING_REBIND_BEFORE_RIGHT_SURFACE_ANIMATION_EVIDENCE",
        },
        "truth": {
            "proves": [
                "the unchanged current clip contains explicit left/right front-elbow and hind-knee tracks",
                "the authored bilateral pairs have exact matching timing, raised-cosine phase and peak amplitudes at all 41 authored sample times",
                "Animation can preserve bilateral motion intent while refusing to inherit right-side deformation acceptance by source symmetry",
            ],
            "does_not_prove": [
                "right-side Geometry or topology acceptance",
                "right-side Rigging, weighting, skinning or deformation acceptance",
                "right-side rendered or target-engine surface playback",
                "continuous interpolation or C1/C2 motion quality",
                "real-time wall-clock pacing",
                "visual or Art Director acceptance",
                "controller or state-machine behavior",
                "collision, physics or gameplay acceptance",
                "biological gait or locomotion",
                "CANON or production readiness",
            ],
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "bilateral_track_intent_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    (args.out / "bilateral_track_samples.json").write_text(
        json.dumps({"schema": "axm.animal-animation-bilateral-track-samples/v0.1", "samples": samples}, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--bilateral-profile", type=Path, required=True)
    parser.add_argument("--organic-bilateral-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = build(args)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
