#!/usr/bin/env python3
"""Prove exact Animal sampled-playback timing through current UC's generic runtime clock.

This Technical Art bridge deliberately executes the Animation producer's own retained
sampled-playback builder from an exact checkout. It does not copy Animal motion,
rigging or deformation semantics into Universal Creation. UC supplies only its
existing adapter-neutral clip clock/state runtime.
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

PINNED_ANIMATION_COMMIT = "b10ec5aeeb02b5df8d42e13df2772f4dcaae9a3a"
PINNED_UC_COMMIT = "a05f5fb083ad1454a0d92d001e0d3994a779826f"
PINNED_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
PINNED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
PINNED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
PINNED_PLAYBACK_SCHEMA = "axm.animal-animation-sampled-playback/v0.1"
PINNED_PLAYBACK_GATE = "PASS_DISCRETE_SAMPLED_PLAYBACK_SEAM"
PINNED_MOTION_SEMANTICS = "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION"
BRIDGE_SCHEMA = "axm.animal-uc-animation-clock-bridge/v0.1"
BRIDGE_STATUS = "PASS_ANIMAL_SAMPLED_PLAYBACK_TO_CURRENT_UC_RUNTIME_CLOCK"
TOLERANCE_S = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_playback_contract(report: dict[str, Any]) -> None:
    exact = {
        "schema": PINNED_PLAYBACK_SCHEMA,
        "gate": PINNED_PLAYBACK_GATE,
        "source_digest": PINNED_SOURCE_DIGEST,
        "rig_plan_digest": PINNED_RIG_PLAN_DIGEST,
        "clip_digest": PINNED_CLIP_DIGEST,
        "motion_semantics": PINNED_MOTION_SEMANTICS,
        "duration_seconds": 1.0,
        "sample_rate_hz": 40,
        "endpoint_inclusive_source_sample_count": 41,
        "displayed_frame_count_per_cycle": 40,
        "display_frame_interval_seconds": 0.025,
    }
    for field, expected in exact.items():
        observed = report.get(field)
        if observed != expected:
            raise ValueError(f"playback contract drift for {field}: expected {expected!r}, observed {observed!r}")
    schedule = report.get("display_schedule_seconds")
    expected_schedule = [round(index / 40.0, 9) for index in range(40)]
    if schedule != expected_schedule:
        raise ValueError("playback display schedule drifted from the exact 40 Hz authored schedule")
    metrics = report.get("metrics")
    if not isinstance(metrics, dict) or metrics.get("exact_endpoint_seam") is not True:
        raise ValueError("playback contract requires the exact endpoint seam prerequisite")
    if abs(float(metrics.get("wrap_step_residual_m", math.inf))) > 1e-12:
        raise ValueError("playback wrap-step residual exceeds the retained prerequisite tolerance")


def _run_exact_animation_producer(checkout: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(checkout / "src")
    subprocess.run(
        [sys.executable, "tools/build_animation_playback.py"],
        cwd=checkout,
        env=env,
        check=True,
    )
    report_path = checkout / "evidence" / "quadruped_articulation_loop_001.playback.json"
    if not report_path.is_file():
        raise RuntimeError("exact Animation producer did not retain its sampled-playback receipt")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _require_playback_contract(report)
    return report


def _runtime_source(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ANIMATION_RUNTIME_SCHEMA,
        "id": "animal-quadruped-articulation-loop-001-clock-bridge",
        "initial_state": "articulation",
        "clips": [
            {
                "name": report["clip_name"],
                "duration_s": report["duration_seconds"],
                "loop": True,
                "root_motion_m": [0.0, 0.0, 0.0],
                "events": [],
            }
        ],
        "states": [
            {
                "name": "articulation",
                "clip": report["clip_name"],
                "speed": 1.0,
                "root_motion": "ignore",
                "completion_event": None,
            }
        ],
        "transitions": [],
    }


def _boundary_probe(report: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    interval = float(report["display_frame_interval_seconds"])
    frame_count = int(report["displayed_frame_count_per_cycle"])
    commands = [{"dt": interval} for _ in range(frame_count + 1)]
    replay = replay_game_animation_runtime(runtime, commands)
    transcript = replay["transcript"]
    if len(transcript) != frame_count + 1:
        raise RuntimeError("UC replay did not retain every authored-boundary command")

    expected_times = list(report["display_schedule_seconds"])[1:] + [0.0, interval]
    observed_times = [float(row["clip_time_s"]) for row in transcript]
    residuals = [abs(observed - expected) for observed, expected in zip(observed_times, expected_times)]
    max_residual = max(residuals, default=0.0)
    if max_residual > TOLERANCE_S:
        raise RuntimeError(f"UC clip clock drifted from Animal authored boundaries by {max_residual} s")

    loop_rows = [
        {"command_index": row["index"], "event": event}
        for row in transcript
        for event in row["emitted"]
        if event.get("type") == "LOOP"
    ]
    if len(loop_rows) != 1:
        raise RuntimeError(f"expected exactly one loop event in the first 41 authored steps, observed {len(loop_rows)}")
    loop = loop_rows[0]
    if loop["command_index"] != frame_count - 1 or loop["event"].get("cycle") != 1:
        raise RuntimeError("UC loop event did not land on the exact Animal one-second boundary")
    if transcript[frame_count - 1]["clip_time_s"] != 0.0:
        raise RuntimeError("UC exact cycle boundary did not return to clip time zero")
    if transcript[frame_count]["clip_time_s"] != interval:
        raise RuntimeError("UC first post-wrap authored interval did not return to 0.025 s")

    return {
        "commands": commands,
        "commands_sha256": _digest(commands),
        "expected_clip_times_s": expected_times,
        "observed_clip_times_s": observed_times,
        "maximum_clip_time_residual_s": max_residual,
        "loop_events": loop_rows,
        "final_cycles": transcript[-1]["cycles"],
        "final_clip_time_s": transcript[-1]["clip_time_s"],
        "replay_truth": replay["truth"],
    }


def _free_time_probes(runtime: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    probes = [0.1125, 0.5125, 1.2375, 2.0]
    rows = []
    for probe in probes:
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
            raise RuntimeError(
                f"UC free-time probe {probe} s cycle count drifted: expected {expected_cycles}, observed {final['cycles']}"
            )
        rows.append(
            {
                "wall_dt_s": probe,
                "expected_clip_time_s": expected_time,
                "observed_clip_time_s": final["clip_time_s"],
                "clip_time_residual_s": residual,
                "expected_cycles": expected_cycles,
                "observed_cycles": final["cycles"],
            }
        )
    return rows


def _negative_controls(report: dict[str, Any]) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    mutations = {
        "clip_identity_drift": ("clip_digest", "0" * 64),
        "sample_rate_drift": ("sample_rate_hz", 41),
    }
    for name, (field, value) in mutations.items():
        candidate = copy.deepcopy(report)
        candidate[field] = value
        try:
            _require_playback_contract(candidate)
        except ValueError as exc:
            controls[name] = {"status": "PASS_REJECTED", "observed_error": str(exc)}
        else:
            raise RuntimeError(f"negative control {name} was incorrectly accepted")
    return controls


def main() -> int:
    animation_checkout = Path(os.environ.get("AXM_ANIMAL_ANIMATION_CHECKOUT", ""))
    observed_animation_commit = os.environ.get("AXM_ANIMAL_ANIMATION_COMMIT", "")
    observed_uc_commit = os.environ.get("AXM_UC_COMMIT", "")
    if observed_animation_commit != PINNED_ANIMATION_COMMIT:
        raise RuntimeError(
            f"AXM_ANIMAL_ANIMATION_COMMIT must equal pinned Animation commit {PINNED_ANIMATION_COMMIT}"
        )
    if observed_uc_commit != PINNED_UC_COMMIT:
        raise RuntimeError(f"AXM_UC_COMMIT must equal pinned UC commit {PINNED_UC_COMMIT}")
    if not animation_checkout.is_dir():
        raise RuntimeError("AXM_ANIMAL_ANIMATION_CHECKOUT must point to the exact Animation checkout")

    report = _run_exact_animation_producer(animation_checkout)
    runtime = _runtime_source(report)
    compiled = compile_game_animation_runtime(runtime)
    boundary = _boundary_probe(report, runtime)
    free_time = _free_time_probes(runtime, float(report["duration_seconds"]))
    controls = _negative_controls(report)
    catalog = game_animation_runtime_catalog()

    output_dir = ROOT / "evidence" / "uc_animation_clock"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_receipt = animation_checkout / "evidence" / "quadruped_articulation_loop_001.playback.json"
    shutil.copy2(source_receipt, output_dir / "animal-sampled-playback-source.json")
    (output_dir / "uc-animation-runtime-source.json").write_text(
        json.dumps(compiled["source"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    receipt = {
        "schema": BRIDGE_SCHEMA,
        "status": BRIDGE_STATUS,
        "animation": {
            "commit": PINNED_ANIMATION_COMMIT,
            "schema": report["schema"],
            "gate": report["gate"],
            "source_digest": report["source_digest"],
            "rig_plan_digest": report["rig_plan_digest"],
            "clip_name": report["clip_name"],
            "clip_digest": report["clip_digest"],
            "motion_semantics": report["motion_semantics"],
            "duration_seconds": report["duration_seconds"],
            "sample_rate_hz": report["sample_rate_hz"],
            "displayed_frame_count_per_cycle": report["displayed_frame_count_per_cycle"],
            "display_schedule_sha256": _digest(report["display_schedule_seconds"]),
        },
        "uc": {
            "commit": PINNED_UC_COMMIT,
            "runtime_schema": ANIMATION_RUNTIME_SCHEMA,
            "compiled_source_sha256": compiled["source_sha256"],
            "catalog_truth": catalog["truth"],
        },
        "adapter": {
            "root_motion_m": [0.0, 0.0, 0.0],
            "root_motion_mode": "ignore",
            "speed": 1.0,
            "loop": True,
            "motion_changed": False,
            "retimed": False,
            "pose_data_transported": False,
        },
        "boundary_probe": boundary,
        "free_time_probes": free_time,
        "negative_controls": controls,
        "truth": {
            "proves_if_green": [
                "the exact Animal sampled-playback producer can be rebuilt from its pinned Animation revision before Technical Art adapts it",
                "current UC's existing adapter-neutral runtime clock lands on every exact 40 Hz authored display boundary through one complete loop and the first post-wrap boundary without retiming",
                "current UC's existing runtime clock preserves exact loop-cycle timing for additional bounded non-sample time probes",
            ],
            "does_not_prove": [
                "skeleton, skin, weight, pose or deformation transport into UC",
                "GLB animation-channel export",
                "real wall-clock frame pacing",
                "Godot AnimationPlayer or another target-engine controller/state-machine integration",
                "continuous interpolation quality or C1 continuity",
                "visual or motion-quality acceptance",
                "gameplay, collision, physics or target-device performance",
            ],
        },
    }
    receipt["receipt_sha256"] = _digest(receipt)
    receipt_path = output_dir / "animal-uc-animation-clock-bridge.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": receipt["status"],
                "animation_commit": PINNED_ANIMATION_COMMIT,
                "uc_commit": PINNED_UC_COMMIT,
                "source_clip_digest": PINNED_CLIP_DIGEST,
                "runtime_source_sha256": compiled["source_sha256"],
                "maximum_boundary_clock_residual_s": boundary["maximum_clip_time_residual_s"],
                "loop_event_count": len(boundary["loop_events"]),
                "receipt": str(receipt_path.relative_to(ROOT)),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
