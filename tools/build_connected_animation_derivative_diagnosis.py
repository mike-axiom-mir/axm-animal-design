#!/usr/bin/env python3
"""Diagnose velocity discontinuities in the exact connected Animal motion.

This observer does not change the authored clip or interpolation. It consumes the
exact retained 41-sample connected Animation evidence and measures the one-sided
velocities implied by the already-proven piecewise-linear C0 interpolation.
The result is a bounded C1 diagnosis for timing/spacing review, not a smoothing
proposal, visual acceptance, real-time pacing, controller, or gameplay evidence.
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
EXPECTED_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
EXPECTED_CONNECTED_DONOR_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"
DT = 0.025


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _vec_sub(a: list[float], b: list[float]) -> tuple[float, float, float]:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _vec_scale(a: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _vec_norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _velocity(start: list[float], end: list[float]) -> tuple[float, float, float]:
    return _vec_scale(_vec_sub(end, start), 1.0 / DT)


def _velocity_jump(incoming: tuple[float, float, float], outgoing: tuple[float, float, float]) -> float:
    return _vec_norm((outgoing[0] - incoming[0], outgoing[1] - incoming[1], outgoing[2] - incoming[2]))


def _synthetic_controls() -> dict[str, Any]:
    # Straight constant-speed motion has no interior C1 jump.
    line = [[0.0, 0.0, 0.0], [0.025, 0.0, 0.0], [0.050, 0.0, 0.0]]
    v0 = _velocity(line[0], line[1])
    v1 = _velocity(line[1], line[2])
    straight_jump = _velocity_jump(v0, v1)

    # Same step length with a 90-degree turn must produce a non-zero jump.
    kink = [[0.0, 0.0, 0.0], [0.025, 0.0, 0.0], [0.025, 0.025, 0.0]]
    k0 = _velocity(kink[0], kink[1])
    k1 = _velocity(kink[1], kink[2])
    kink_jump = _velocity_jump(k0, k1)

    if straight_jump > 1e-12:
        raise ValueError("derivative observer false-positive on constant-velocity control")
    if kink_jump <= 1.0:
        raise ValueError("derivative observer failed deliberate direction-change control")
    return {
        "constant_velocity_control_jump_m_per_s": straight_jump,
        "direction_change_control_jump_m_per_s": kink_jump,
        "constant_velocity_control": "PASS_ZERO_JUMP",
        "direction_change_control": "PASS_NONZERO_JUMP_DETECTED",
    }


def _write_svg(boundaries: list[dict[str, Any]], output: Path) -> None:
    width, height = 1120, 420
    left, right, top, bottom = 60.0, 24.0, 36.0, 58.0
    plot_w, plot_h = width - left - right, height - top - bottom
    max_jump = max(float(row["max_vertex_velocity_jump_m_per_s"]) for row in boundaries)
    max_speed = max(float(row["max_incident_vertex_speed_m_per_s"]) for row in boundaries)
    scale_max = max(max_jump, max_speed, 1e-9)

    def sx(index: int) -> float:
        return left + (index / max(1, len(boundaries) - 1)) * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value / scale_max) * plot_h

    jump_points = " ".join(f"{sx(i):.2f},{sy(float(row['max_vertex_velocity_jump_m_per_s'])):.2f}" for i, row in enumerate(boundaries))
    speed_points = " ".join(f"{sx(i):.2f},{sy(float(row['max_incident_vertex_speed_m_per_s'])):.2f}" for i, row in enumerate(boundaries))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#111"/>',
        '<style>text{font-family:monospace;fill:#ddd;font-size:12px}.axis{stroke:#666;stroke-width:1}.jump{stroke:#f0f0f0;stroke-width:2;fill:none}.speed{stroke:#999;stroke-width:1.5;fill:none;stroke-dasharray:5 4}.mark{fill:#f0f0f0}</style>',
        f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>',
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>',
        f'<polyline class="jump" points="{jump_points}"/>',
        f'<polyline class="speed" points="{speed_points}"/>',
        '<text x="60" y="20">Exact connected clip: piecewise-linear one-sided velocity diagnosis</text>',
        f'<text x="790" y="20">scale max={scale_max:.6f} m/s</text>',
        '<text x="60" y="405">boundary sample index (0 = loop seam, 20 = authored peak)</text>',
        '<text x="74" y="54">solid: max velocity jump / dashed: max incident speed</text>',
    ]
    for index in (0, 10, 20, 30, 40):
        i = 0 if index == 40 else index
        x = sx(i)
        parts.append(f'<line class="axis" x1="{x:.2f}" y1="{top + plot_h}" x2="{x:.2f}" y2="{top + plot_h + 5}"/>')
        parts.append(f'<text x="{x - 7:.2f}" y="{top + plot_h + 21}">{index}</text>')
    peak_row = max(boundaries, key=lambda row: float(row["max_vertex_velocity_jump_m_per_s"]))
    peak_i = int(peak_row["boundary_sample_index"])
    peak_x = sx(peak_i)
    peak_y = sy(float(peak_row["max_vertex_velocity_jump_m_per_s"]))
    parts.append(f'<circle class="mark" cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="4"/>')
    parts.append(f'<text x="{min(peak_x + 8, width - 330):.2f}" y="{max(peak_y - 10, 74):.2f}">worst boundary={peak_i} jump={float(peak_row["max_vertex_velocity_jump_m_per_s"]):.6f} m/s</text>')
    parts.append('</svg>')
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def build(evidence_dir: Path, out_dir: Path) -> dict[str, Any]:
    receipt = _load(evidence_dir / "connected_forelimb_motion_receipt.json")
    frames_doc = _load(evidence_dir / "connected_forelimb_motion_frames.json")
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
        raise ValueError("weighting drift; diagnosis preserves smoothstep-v0")
    if source.get("motion_semantics") != "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION":
        raise ValueError("motion truth-label drift")
    if donor.get("git_head") != EXPECTED_CONNECTED_DONOR_HEAD:
        raise ValueError("connected Rigging donor head drift")
    if donor.get("candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("connected candidate identity drift")
    if frames_doc.get("candidate_digest") != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError("connected frame candidate identity drift")

    frames = frames_doc.get("frames", [])
    if len(frames) != 41:
        raise ValueError("expected exact endpoint-inclusive 41 connected frames")
    if frames[0].get("positions") != frames[40].get("positions"):
        raise ValueError("connected loop no longer closes exactly")
    if [int(frame.get("sample_index", -1)) for frame in frames] != list(range(41)):
        raise ValueError("authored sample ordering drift")
    if any(abs(float(frame.get("time_seconds", -1.0)) - index * DT) > 1e-12 for index, frame in enumerate(frames)):
        raise ValueError("authored sample timing drift")
    if any(len(frame.get("positions", [])) != 42 for frame in frames):
        raise ValueError("connected vertex-count drift")

    positions = [frame["positions"] for frame in frames]
    interval_velocities: list[list[tuple[float, float, float]]] = []
    interval_max_speed: list[float] = []
    for interval in range(40):
        velocities = [_velocity(a, b) for a, b in zip(positions[interval], positions[interval + 1])]
        interval_velocities.append(velocities)
        interval_max_speed.append(max(_vec_norm(v) for v in velocities))

    boundaries: list[dict[str, Any]] = []
    all_vertex_jumps: list[float] = []
    for boundary in range(40):
        incoming_interval = 39 if boundary == 0 else boundary - 1
        outgoing_interval = boundary
        jumps = [
            _velocity_jump(v_in, v_out)
            for v_in, v_out in zip(interval_velocities[incoming_interval], interval_velocities[outgoing_interval])
        ]
        all_vertex_jumps.extend(jumps)
        incoming_angle = (float(frames[boundary]["angle_deg"]) - float(frames[incoming_interval]["angle_deg"])) / DT
        if boundary == 0:
            incoming_angle = (float(frames[40]["angle_deg"]) - float(frames[39]["angle_deg"])) / DT
        outgoing_angle = (float(frames[boundary + 1]["angle_deg"]) - float(frames[boundary]["angle_deg"])) / DT
        angle_jump = abs(outgoing_angle - incoming_angle)
        boundaries.append(
            {
                "boundary_sample_index": boundary,
                "time_seconds": boundary * DT,
                "incoming_interval_index": incoming_interval,
                "outgoing_interval_index": outgoing_interval,
                "max_vertex_velocity_jump_m_per_s": max(jumps),
                "rms_vertex_velocity_jump_m_per_s": math.sqrt(sum(value * value for value in jumps) / len(jumps)),
                "mean_vertex_velocity_jump_m_per_s": sum(jumps) / len(jumps),
                "vertices_with_nonzero_jump": sum(value > 1e-12 for value in jumps),
                "max_incident_vertex_speed_m_per_s": max(interval_max_speed[incoming_interval], interval_max_speed[outgoing_interval]),
                "incoming_elbow_angular_velocity_deg_per_s": incoming_angle,
                "outgoing_elbow_angular_velocity_deg_per_s": outgoing_angle,
                "elbow_angular_velocity_jump_deg_per_s": angle_jump,
            }
        )

    controls = _synthetic_controls()
    worst = max(boundaries, key=lambda row: float(row["max_vertex_velocity_jump_m_per_s"]))
    peak = boundaries[20]
    seam = boundaries[0]
    zero_jump_boundaries = sum(float(row["max_vertex_velocity_jump_m_per_s"]) <= 1e-12 for row in boundaries)
    nonzero_boundaries = len(boundaries) - zero_jump_boundaries
    maximum_interval_speed = max(interval_max_speed)
    maximum_velocity_jump = float(worst["max_vertex_velocity_jump_m_per_s"])
    mean_velocity_jump = sum(all_vertex_jumps) / len(all_vertex_jumps)
    rms_velocity_jump = math.sqrt(sum(value * value for value in all_vertex_jumps) / len(all_vertex_jumps))

    if nonzero_boundaries == 0:
        raise ValueError("expected the current piecewise-linear motion to expose at least one C1 discontinuity")
    if int(worst["boundary_sample_index"]) not in range(40):
        raise ValueError("invalid worst-boundary identity")

    out_dir.mkdir(parents=True, exist_ok=True)
    receiving = {"repository": "mike-axiom-mir/axm-animal-design", "git_head": _git_head()}
    result = {
        "schema": "axm.animal-animation-connected-derivative-diagnosis/v0.1",
        "gate": "PASS_CONNECTED_C1_DISCONTINUITY_DIAGNOSIS_C0_INTERPOLANT_UNCHANGED",
        "receiving_repository": receiving,
        "source_identity": {
            **source,
            "connected_candidate_id": donor.get("candidate_id"),
            "connected_candidate_digest": EXPECTED_CANDIDATE_DIGEST,
            "connected_rigging_donor_head": EXPECTED_CONNECTED_DONOR_HEAD,
        },
        "diagnosed_motion": {
            "interpolation_method": "existing piecewise-linear per-vertex interpolation",
            "authored_duration_seconds": 1.0,
            "authored_sample_rate_hz": 40,
            "authored_interval_seconds": DT,
            "endpoint_inclusive_authored_sample_count": 41,
            "loop_boundaries_diagnosed": 40,
            "vertex_count": 42,
            "motion_changed": False,
            "smoothing_candidate_authored": False,
        },
        "summary": {
            "boundaries_with_nonzero_vertex_velocity_jump": nonzero_boundaries,
            "boundaries_with_zero_vertex_velocity_jump": zero_jump_boundaries,
            "maximum_interval_vertex_speed_m_per_s": maximum_interval_speed,
            "maximum_vertex_velocity_jump_m_per_s": maximum_velocity_jump,
            "mean_vertex_velocity_jump_m_per_s_all_vertices_boundaries": mean_velocity_jump,
            "rms_vertex_velocity_jump_m_per_s_all_vertices_boundaries": rms_velocity_jump,
            "worst_boundary_sample_index": int(worst["boundary_sample_index"]),
            "worst_boundary_time_seconds": float(worst["time_seconds"]),
            "peak_boundary_max_vertex_velocity_jump_m_per_s": float(peak["max_vertex_velocity_jump_m_per_s"]),
            "peak_boundary_elbow_angular_velocity_jump_deg_per_s": float(peak["elbow_angular_velocity_jump_deg_per_s"]),
            "loop_seam_max_vertex_velocity_jump_m_per_s": float(seam["max_vertex_velocity_jump_m_per_s"]),
            "loop_seam_elbow_angular_velocity_jump_deg_per_s": float(seam["elbow_angular_velocity_jump_deg_per_s"]),
        },
        "boundaries": boundaries,
        "negative_and_sanity_controls": controls,
        "truth": {
            "proves_if_green": [
                "the exact existing connected smoothstep-v0 clip has been measured for one-sided per-vertex velocity continuity at every authored boundary of its already-proven piecewise-linear C0 interpolation, including the loop seam",
                "the observer distinguishes a constant-velocity control from a deliberate direction-change control",
                "the authored clip, source, connected geometry, weighting, timing, amplitudes and C0 interpolation remain unchanged",
            ],
            "does_not_prove": [
                "that any measured derivative jump is visually unacceptable",
                "that a particular C1 smoothing or retiming method should be adopted",
                "acceleration continuity, jerk quality, volume preservation or continuous self-intersection freedom",
                "wall-clock pacing, AnimationPlayer, skeleton/skin/exported clip playback",
                "runtime controller, state machine, physics, collision or gameplay acceptance",
                "final motion quality, gait, locomotion, CANON or production readiness",
            ],
        },
    }
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    (out_dir / "quadruped_connected_derivative_diagnosis.json").write_bytes(payload)
    _write_svg(boundaries, out_dir / "quadruped_connected_derivative_diagnosis.svg")
    summary = {
        "schema": "axm.animal-animation-connected-derivative-diagnosis-summary/v0.1",
        "gate": result["gate"],
        "receiving_repository": receiving,
        "payload_sha256": _digest_bytes(payload),
        "summary": result["summary"],
        "negative_and_sanity_controls": controls,
        "truth": result["truth"],
    }
    (out_dir / "quadruped_connected_derivative_diagnosis_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--connected-evidence-dir",
        type=Path,
        default=ROOT / "evidence" / "animation-connected-forelimb-motion-001",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "evidence" / "animation-connected-derivative-diagnosis-001",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.connected_evidence_dir, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
