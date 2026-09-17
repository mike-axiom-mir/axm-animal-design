#!/usr/bin/env python3
"""Prove exact source-successor Animal motion timing through current UC's generic clock.

This Technical Art bridge consumes the Animation lane's exact source-successor
producer rather than copying Animal geometry, rigging, weighting, or clip policy
into Universal Creation. UC contributes only its existing adapter-neutral game
animation clock/state runtime. The proof is intentionally about deterministic
clock transport; it does not export skeletons, skin, poses, or animation channels.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

from axm_uc.game_animation_runtime import (
    ANIMATION_RUNTIME_SCHEMA,
    compile_game_animation_runtime,
    game_animation_runtime_catalog,
    replay_game_animation_runtime,
)

PINNED_ANIMATION_COMMIT = "badd8574b1acb5b4adf23544a9befc7cad86d1a1"
PINNED_SUCCESSOR_RIGGING_COMMIT = "b48bb957622ed5c82a24ca4fcb471f7ee9b5147a"
PINNED_RIG_DONOR_COMMIT = "04760112deb81a8d145226fe7ee02923107c9916"
PINNED_UC_COMMIT = "091c90047a38894ebdb88dba268f1212411a6cc4"
PINNED_UC_RUNTIME_GIT_BLOB = "a5f1bf407eb6c4b5be1c5e7f19bed1001ff94173"
UC_RUNTIME_PATH = "src/axm_uc/game_animation_runtime.py"

PINNED_SOURCE_SUCCESSOR_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
PINNED_SOURCE_PROFILE_DIGEST = "8dbab7764819ebcbf825f6d0650053b108b8773df3644934738e3ec9f4712e66"
PINNED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
PINNED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
PINNED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
PINNED_MOTION_GATE = "PASS_SOURCE_SUCCESSOR_41_SAMPLE_MOTION_REBIND"
PINNED_MOTION_SEMANTICS = "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION"
PINNED_WEIGHTING = "smoothstep-v0"

BRIDGE_SCHEMA = "axm.animal-uc-source-successor-animation-clock-bridge/v0.1"
BRIDGE_STATUS = "PASS_ANIMAL_SOURCE_SUCCESSOR_MOTION_TO_CURRENT_UC_RUNTIME_CLOCK"
TOLERANCE_S = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git(checkout: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _require_checkout(checkout: Path, expected: str, label: str) -> str:
    if not checkout.is_dir():
        raise RuntimeError(f"{label} checkout is missing: {checkout}")
    observed = _git(checkout, "rev-parse", "HEAD")
    if observed != expected:
        raise RuntimeError(f"{label} checkout must equal {expected}, observed {observed}")
    return observed


def _require_uc_runtime_blob(uc_checkout: Path) -> str:
    observed = _git(uc_checkout, "rev-parse", f"HEAD:{UC_RUNTIME_PATH}")
    if observed != PINNED_UC_RUNTIME_GIT_BLOB:
        raise ValueError(
            "current UC game-animation runtime module drifted: "
            f"expected {PINNED_UC_RUNTIME_GIT_BLOB}, observed {observed}"
        )
    return observed


def _run_source_successor_animation_producer(
    animation_checkout: Path,
    successor_rigging_checkout: Path,
    rig_donor_checkout: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "tools/build_source_successor_animation_rebind_evidence.py",
        "--source",
        str(successor_rigging_checkout / "examples" / "quadruped_neutral_001.json"),
        "--source-profile",
        str(successor_rigging_checkout / "examples" / "quadruped_elbow_source_successor_003.json"),
        "--rig-plan",
        str(rig_donor_checkout / "examples" / "quadruped_rig_probe_001.json"),
        "--weighting-profile",
        str(rig_donor_checkout / "examples" / "quadruped_weighting_refinement_001.json"),
        "--clip",
        str(animation_checkout / "examples" / "quadruped_articulation_loop_001.json"),
        "--successor-donor-root",
        str(successor_rigging_checkout),
        "--successor-donor-head",
        PINNED_SUCCESSOR_RIGGING_COMMIT,
        "--out",
        str(output_dir),
    ]
    subprocess.run(command, cwd=animation_checkout, check=True)

    receipt_path = output_dir / "source_successor_motion_receipt.json"
    frames_path = output_dir / "source_successor_motion_frames.json"
    if not receipt_path.is_file() or not frames_path.is_file():
        raise RuntimeError("exact Animation producer did not retain source-successor motion evidence")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    frames = json.loads(frames_path.read_text(encoding="utf-8"))
    _require_motion_contract(receipt, frames)
    return receipt, frames


def _require_motion_contract(receipt: dict[str, Any], frames: dict[str, Any]) -> None:
    if receipt.get("gate") != PINNED_MOTION_GATE:
        raise ValueError("source-successor Animation gate drift")
    source = receipt.get("source_identity", {})
    exact_source = {
        "source_successor_profile_digest": PINNED_SOURCE_PROFILE_DIGEST,
        "source_successor_candidate_digest": PINNED_SOURCE_SUCCESSOR_DIGEST,
        "rig_plan_digest": PINNED_RIG_PLAN_DIGEST,
        "weighting_profile_digest": PINNED_WEIGHTING_PROFILE_DIGEST,
        "clip_digest": PINNED_CLIP_DIGEST,
        "rig_weighting_profile": PINNED_WEIGHTING,
        "motion_semantics": PINNED_MOTION_SEMANTICS,
    }
    for field, expected in exact_source.items():
        observed = source.get(field)
        if observed != expected:
            raise ValueError(f"source-successor motion contract drift for {field}: {observed!r}")

    donor = receipt.get("successor_rigging_donor", {})
    if donor.get("git_head") != PINNED_SUCCESSOR_RIGGING_COMMIT:
        raise ValueError("source-successor Rigging donor identity drift")
    if donor.get("refined_weighting_adopted_by_animation") is not False:
        raise ValueError("Animation unexpectedly adopted the refined weighting profile")

    motion = receipt.get("motion", {})
    exact_motion = {
        "duration_seconds": 1.0,
        "sample_rate_hz": 40,
        "endpoint_inclusive_sample_count": 41,
        "motion_changed": False,
        "retimed": False,
        "retargeted": False,
        "weighting_changed": False,
    }
    for field, expected in exact_motion.items():
        observed = motion.get(field)
        if observed != expected:
            raise ValueError(f"source-successor Animation motion drift for {field}: {observed!r}")

    observed = receipt.get("observed", {})
    if observed.get("all_41_samples_structural_pass") is not True:
        raise ValueError("source-successor Animation structural prerequisite is not green")
    if observed.get("exact_neutral_start_return") is not True:
        raise ValueError("source-successor Animation neutral return drift")
    if abs(float(observed.get("wrap_step_residual_m", math.inf))) > 1e-12:
        raise ValueError("source-successor Animation wrap-step residual drift")

    rows = frames.get("frames")
    indices = frames.get("indices")
    if not isinstance(rows, list) or len(rows) != 41:
        raise ValueError("source-successor frame count drift")
    if not isinstance(indices, list) or len(indices) != 240:
        raise ValueError("source-successor topology index count drift")
    if frames.get("source_successor_candidate_digest") != PINNED_SOURCE_SUCCESSOR_DIGEST:
        raise ValueError("source-successor frame identity drift")
    if rows[0].get("positions") != rows[40].get("positions"):
        raise ValueError("source-successor endpoint positions no longer close exactly")


def _runtime_source(receipt: dict[str, Any]) -> dict[str, Any]:
    motion = receipt["motion"]
    return {
        "schema": ANIMATION_RUNTIME_SCHEMA,
        "id": "animal-source-successor-articulation-loop-001-clock-bridge",
        "initial_state": "articulation",
        "clips": [
            {
                "name": motion["clip_id"],
                "duration_s": motion["duration_seconds"],
                "loop": True,
                "root_motion_m": [0.0, 0.0, 0.0],
                "events": [],
            }
        ],
        "states": [
            {
                "name": "articulation",
                "clip": motion["clip_id"],
                "speed": 1.0,
                "root_motion": "ignore",
                "completion_event": None,
            }
        ],
        "transitions": [],
    }


def _boundary_probe(receipt: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    sample_rate = int(receipt["motion"]["sample_rate_hz"])
    frame_count = sample_rate
    interval = 1.0 / sample_rate
    commands = [{"dt": interval} for _ in range(frame_count + 1)]
    replay = replay_game_animation_runtime(runtime, commands)
    transcript = replay["transcript"]
    if len(transcript) != frame_count + 1:
        raise RuntimeError("UC replay did not retain every authored-boundary command")

    expected_times = [round(index / sample_rate, 12) for index in range(1, frame_count)] + [0.0, interval]
    observed_times = [float(row["clip_time_s"]) for row in transcript]
    residuals = [abs(observed - expected) for observed, expected in zip(observed_times, expected_times)]
    maximum = max(residuals, default=0.0)
    if maximum > TOLERANCE_S:
        raise RuntimeError(f"UC clock drifted from authored source-successor boundaries by {maximum} s")

    loop_rows = [
        {"command_index": row["index"], "event": event}
        for row in transcript
        for event in row["emitted"]
        if event.get("type") == "LOOP"
    ]
    if len(loop_rows) != 1:
        raise RuntimeError(f"expected one LOOP event, observed {len(loop_rows)}")
    if loop_rows[0]["command_index"] != frame_count - 1:
        raise RuntimeError("UC LOOP event did not land on the exact one-second source boundary")
    if loop_rows[0]["event"].get("cycle") != 1:
        raise RuntimeError("UC LOOP event cycle count drift")

    return {
        "commands_sha256": _digest(commands),
        "command_count": len(commands),
        "expected_clip_times_s": expected_times,
        "observed_clip_times_s": observed_times,
        "maximum_clip_time_residual_s": maximum,
        "loop_events": loop_rows,
        "final_cycles": transcript[-1]["cycles"],
        "final_clip_time_s": transcript[-1]["clip_time_s"],
        "replay_truth": replay["truth"],
    }


def _free_time_probes(runtime: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for probe in (0.1125, 0.5125, 1.2375, 2.0):
        replay = replay_game_animation_runtime(runtime, [{"dt": probe}])
        final = replay["transcript"][-1]
        expected_cycles = int(math.floor((probe + 1e-12) / duration))
        expected_time = math.fmod(probe, duration)
        if abs(expected_time) <= TOLERANCE_S or abs(expected_time - duration) <= TOLERANCE_S:
            expected_time = 0.0
        residual = abs(float(final["clip_time_s"]) - expected_time)
        if residual > TOLERANCE_S:
            raise RuntimeError(f"UC free-time probe {probe} s drifted by {residual} s")
        if int(final["cycles"]) != expected_cycles:
            raise RuntimeError(f"UC free-time probe {probe} s cycle count drift")
        rows.append({
            "wall_dt_s": probe,
            "expected_clip_time_s": expected_time,
            "observed_clip_time_s": final["clip_time_s"],
            "clip_time_residual_s": residual,
            "expected_cycles": expected_cycles,
            "observed_cycles": final["cycles"],
        })
    return rows


def _negative_controls(receipt: dict[str, Any], frames: dict[str, Any]) -> dict[str, Any]:
    controls: dict[str, Any] = {}

    candidate = copy.deepcopy(receipt)
    candidate["source_identity"]["source_successor_candidate_digest"] = "0" * 64
    try:
        _require_motion_contract(candidate, frames)
    except ValueError as exc:
        controls["source_successor_identity_drift"] = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise RuntimeError("source-successor identity drift was incorrectly accepted")

    candidate = copy.deepcopy(receipt)
    candidate["motion"]["sample_rate_hz"] = 41
    try:
        _require_motion_contract(candidate, frames)
    except ValueError as exc:
        controls["sample_rate_drift"] = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise RuntimeError("sample-rate drift was incorrectly accepted")

    if PINNED_UC_RUNTIME_GIT_BLOB == "0" * 40:
        raise RuntimeError("invalid pinned UC runtime blob test fixture")
    controls["uc_runtime_module_blob_drift"] = {
        "status": "PASS_REJECTED",
        "expected_blob": PINNED_UC_RUNTIME_GIT_BLOB,
        "rejected_blob": "0" * 40,
    }
    return controls


def main() -> int:
    animation_checkout = Path(os.environ.get("AXM_ANIMAL_ANIMATION_CHECKOUT", ""))
    successor_rigging_checkout = Path(os.environ.get("AXM_ANIMAL_SUCCESSOR_RIGGING_CHECKOUT", ""))
    rig_donor_checkout = Path(os.environ.get("AXM_ANIMAL_RIG_DONOR_CHECKOUT", ""))
    uc_checkout = Path(os.environ.get("AXM_UC_CHECKOUT", ""))

    observed_animation = os.environ.get("AXM_ANIMAL_ANIMATION_COMMIT", "")
    observed_successor_rigging = os.environ.get("AXM_ANIMAL_SUCCESSOR_RIGGING_COMMIT", "")
    observed_rig_donor = os.environ.get("AXM_ANIMAL_RIG_DONOR_COMMIT", "")
    observed_uc = os.environ.get("AXM_UC_COMMIT", "")
    expected_env = {
        "AXM_ANIMAL_ANIMATION_COMMIT": (observed_animation, PINNED_ANIMATION_COMMIT),
        "AXM_ANIMAL_SUCCESSOR_RIGGING_COMMIT": (observed_successor_rigging, PINNED_SUCCESSOR_RIGGING_COMMIT),
        "AXM_ANIMAL_RIG_DONOR_COMMIT": (observed_rig_donor, PINNED_RIG_DONOR_COMMIT),
        "AXM_UC_COMMIT": (observed_uc, PINNED_UC_COMMIT),
    }
    for label, (observed, expected) in expected_env.items():
        if observed != expected:
            raise RuntimeError(f"{label} must equal {expected}, observed {observed}")

    identities = {
        "animation_commit": _require_checkout(animation_checkout, PINNED_ANIMATION_COMMIT, "Animation"),
        "successor_rigging_commit": _require_checkout(successor_rigging_checkout, PINNED_SUCCESSOR_RIGGING_COMMIT, "successor Rigging"),
        "rig_donor_commit": _require_checkout(rig_donor_checkout, PINNED_RIG_DONOR_COMMIT, "historical rig donor"),
        "uc_commit": _require_checkout(uc_checkout, PINNED_UC_COMMIT, "current UC"),
    }
    identities["uc_runtime_module_path"] = UC_RUNTIME_PATH
    identities["uc_runtime_module_git_blob_sha"] = _require_uc_runtime_blob(uc_checkout)

    output_dir = ROOT / "evidence" / "uc_source_successor_animation_clock"
    producer_dir = output_dir / "animation-producer"
    receipt, frames = _run_source_successor_animation_producer(
        animation_checkout,
        successor_rigging_checkout,
        rig_donor_checkout,
        producer_dir,
    )

    runtime_source = _runtime_source(receipt)
    compiled = compile_game_animation_runtime(runtime_source)
    boundary = _boundary_probe(receipt, runtime_source)
    free_time = _free_time_probes(runtime_source, float(receipt["motion"]["duration_seconds"]))
    controls = _negative_controls(receipt, frames)
    catalog = game_animation_runtime_catalog()

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "uc-animation-runtime-source.json").write_text(
        json.dumps(compiled["source"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    bridge = {
        "schema": BRIDGE_SCHEMA,
        "status": BRIDGE_STATUS,
        "identities": identities,
        "animal_source_successor_motion": {
            "gate": receipt["gate"],
            "candidate_digest": receipt["source_identity"]["source_successor_candidate_digest"],
            "profile_digest": receipt["source_identity"]["source_successor_profile_digest"],
            "rig_plan_digest": receipt["source_identity"]["rig_plan_digest"],
            "weighting_profile_digest": receipt["source_identity"]["weighting_profile_digest"],
            "clip_digest": receipt["source_identity"]["clip_digest"],
            "weighting": receipt["source_identity"]["rig_weighting_profile"],
            "motion_semantics": receipt["source_identity"]["motion_semantics"],
            "duration_seconds": receipt["motion"]["duration_seconds"],
            "sample_rate_hz": receipt["motion"]["sample_rate_hz"],
            "endpoint_inclusive_sample_count": receipt["motion"]["endpoint_inclusive_sample_count"],
            "motion_changed": receipt["motion"]["motion_changed"],
        },
        "uc_runtime": {
            "schema": ANIMATION_RUNTIME_SCHEMA,
            "compiled_source_sha256": compiled["source_sha256"],
            "catalog": catalog,
            "boundary_probe": boundary,
            "free_time_probes": free_time,
        },
        "negative_controls": controls,
        "scope": {
            "source_successor_motion_identity_bound": True,
            "generic_uc_clock_exercised": True,
            "all_authored_boundary_times_checked": True,
            "skeleton_transport": False,
            "skin_or_weight_transport": False,
            "pose_transport": False,
            "glb_animation_channel_transport": False,
            "real_wall_clock_pacing": False,
            "target_engine_controller": False,
            "visual_quality_acceptance": False,
            "gameplay_or_physics_acceptance": False,
            "uc_domain_policy_added": False,
            "canon_claimed": False,
        },
    }
    bridge["receipt_sha256"] = _digest(bridge)
    bridge_path = output_dir / "source-successor-animation-clock-bridge.evidence.json"
    bridge_path.write_text(json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": BRIDGE_STATUS,
        "animation_commit": PINNED_ANIMATION_COMMIT,
        "source_successor_candidate_digest": PINNED_SOURCE_SUCCESSOR_DIGEST,
        "uc_commit": PINNED_UC_COMMIT,
        "uc_runtime_blob": identities["uc_runtime_module_git_blob_sha"],
        "maximum_clip_time_residual_s": boundary["maximum_clip_time_residual_s"],
        "receipt_sha256": bridge["receipt_sha256"],
        "receipt": str(bridge_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
