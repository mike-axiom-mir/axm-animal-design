#!/usr/bin/env python3
"""Rigging-owned guard for the Runtime Animal animation-key budget candidate.

Consumes the exact 41-key normalized-u16 control and exact 19-key Runtime candidate,
then replays both through the existing Animal owner rig at 321 dense samples. This
proves a bounded command-envelope inclusion plus sampled deformation witnesses; it
does not adopt Runtime representation, Animation timing/playback, or target-host state.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _pose_metrics,
    _select_joint,
    _source_triangle_areas,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.connected_deformation import _sub, _vec3, _weights, digest
from axm_animal_design.transported_frame_reconstruction_constraint import _frame_residual

SCHEMA = "axm.animal-rigging-animation-key-budget-deformation-guard/v0.1"
PASS_STATE = "PASS_ANIMAL_RUNTIME_KEY_BUDGET_COMMAND_ENVELOPE_AND_321_DEFORMATION_WITNESSES"
RUNTIME_HEAD = "13ba20d198d2b7c5e428167745d59927b3084004"
RUNTIME_ARTIFACT_ID = 10525970648
RUNTIME_ARTIFACT_SHA256 = "ad071f58796b606d707168af9619d988a497ba1a745dda8ac62b42e7f814b996"
CONTROL_GLB_SHA256 = "81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb"
CANDIDATE_GLB_SHA256 = "a8a32b58ad3bad44176a676b00f5cf1c20d1a2ec6da275b683d8f73a69088d6b"
PREDECESSOR_RIGGING_HEAD = "d0c27db357b015a1ff270de294e39c1a44e3931d"
RUNTIME_TOLERANCE_DEG = 0.075
DENSE_RATE_HZ = 320
DENSE_SAMPLE_COUNT = 321
RIGGING_REVIEW_MIN_DEG = -60.0
RIGGING_REVIEW_MAX_DEG = 60.0
AXIS_RESIDUAL_TOLERANCE = 1e-7
EPS = 1e-10
REPRESENTATIVE_INDICES = [0, 80, 152, 160, 240, 320]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("GLB header drift")
    offset = 12
    doc = None
    binary = None
    while offset + 8 <= len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        payload = data[offset : offset + length]
        offset += length
        if kind == b"JSON":
            doc = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind in (b"BIN\x00", b"BIN "):
            binary = payload
    if not isinstance(doc, dict) or binary is None:
        raise ValueError("GLB chunks missing")
    return doc, binary


def _accessor_rows(doc: dict[str, Any], binary: bytes, index: int):
    accessor = doc["accessors"][index]
    view = doc["bufferViews"][accessor["bufferView"]]
    if accessor.get("sparse") is not None:
        raise ValueError("sparse animation accessor unsupported")
    if int(accessor["componentType"]) != 5126:
        raise ValueError("animation accessor must be FLOAT")
    width = {"SCALAR": 1, "VEC4": 4}.get(accessor["type"])
    if width is None:
        raise ValueError("unexpected animation accessor type")
    packed = 4 * width
    if int(view.get("byteStride", packed)) != packed:
        raise ValueError("interleaved animation accessor unsupported")
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    rows = []
    for row_index in range(int(accessor["count"])):
        values = list(struct.unpack_from("<" + "f" * width, binary, base + row_index * packed))
        rows.append(values[0] if width == 1 else values)
    return rows


def _unit(q):
    norm = math.sqrt(sum(float(value) * float(value) for value in q))
    if norm <= 1e-15:
        raise ValueError("zero quaternion")
    return [float(value) / norm for value in q]


def _dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _slerp(a, b, t: float):
    qa = _unit(a)
    qb = _unit(b)
    dot = _dot(qa, qb)
    if dot < 0.0:
        qb = [-value for value in qb]
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _unit([(1.0 - t) * qa[i] + t * qb[i] for i in range(4)])
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    return [
        math.sin((1.0 - t) * theta) / sin_theta * qa[i]
        + math.sin(t * theta) / sin_theta * qb[i]
        for i in range(4)
    ]


def _rotation_at(times, quaternions, time_s: float):
    if time_s <= times[0]:
        return _unit(quaternions[0])
    if time_s >= times[-1]:
        return _unit(quaternions[-1])
    index = bisect.bisect_right(times, time_s) - 1
    alpha = (time_s - times[index]) / (times[index + 1] - times[index])
    return _slerp(quaternions[index], quaternions[index + 1], alpha)


def _quaternion_error_deg(a, b) -> float:
    qa = _unit(a)
    qb = _unit(b)
    d1 = math.sqrt(sum((qa[i] - qb[i]) ** 2 for i in range(4)))
    d2 = math.sqrt(sum((qa[i] + qb[i]) ** 2 for i in range(4)))
    return math.degrees(2.0 * math.asin(min(1.0, min(d1, d2) / 2.0)))


def _extract_rotation_curve(data: bytes, expected_sha: str, expected_keys: int):
    if _sha(data) != expected_sha:
        raise ValueError("exact GLB identity drift")
    doc, binary = _parse_glb(data)
    animations = doc.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected exact one-channel animation")
    channel = animations[0]["channels"][0]
    sampler = animations[0]["samplers"][channel["sampler"]]
    if channel.get("target", {}).get("path") != "rotation":
        raise ValueError("rotation target drift")
    if sampler.get("interpolation") != "LINEAR":
        raise ValueError("animation interpolation drift")
    times = [float(value) for value in _accessor_rows(doc, binary, int(sampler["input"]))]
    rotations = [[float(value) for value in row] for row in _accessor_rows(doc, binary, int(sampler["output"]))]
    if len(times) != expected_keys or len(rotations) != expected_keys:
        raise ValueError("animation key-count drift")
    if abs(times[0]) > 1e-9 or abs(times[-1] - 1.0) > 1e-6:
        raise ValueError("animation duration drift")
    return times, rotations


def _axis_from_curve(rotations):
    for quaternion in rotations:
        q = _unit(quaternion)
        if q[3] < 0.0:
            q = [-value for value in q]
        vector_norm = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2)
        if vector_norm > 1e-8:
            return [q[0] / vector_norm, q[1] / vector_norm, q[2] / vector_norm]
    raise ValueError("rotation curve has no non-neutral axis witness")


def _signed_angle_and_axis_residual(quaternion, axis):
    q = _unit(quaternion)
    if q[3] < 0.0:
        q = [-value for value in q]
    projection = q[0] * axis[0] + q[1] * axis[1] + q[2] * axis[2]
    residual = math.sqrt(
        (q[0] - projection * axis[0]) ** 2
        + (q[1] - projection * axis[1]) ** 2
        + (q[2] - projection * axis[2]) ** 2
    )
    angle = math.degrees(2.0 * math.atan2(projection, q[3]))
    return angle, residual


def _quat_from_axis_angle(axis, angle_deg: float):
    half = math.radians(angle_deg) * 0.5
    sine = math.sin(half)
    return [axis[0] * sine, axis[1] * sine, axis[2] * sine, math.cos(half)]


def _prepare_owner(spec, left_profile, bilateral_profile, plan):
    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    joint = _select_joint(spec, plan, "right")
    positions = [tuple(float(value) for value in point) for point in right_candidate["positions"]]
    indices = [int(value) for value in right_candidate["indices"]]
    pivot = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, pivot)
    weights = _weights(positions, pivot, child_direction, float(joint["influence_radius"]))
    areas = _source_triangle_areas(positions, indices)
    return {
        "candidate": right_candidate,
        "basis": static_basis,
        "joint": joint,
        "positions": positions,
        "indices": indices,
        "pivot": pivot,
        "weights": weights,
        "areas": areas,
    }


def _distance(a, b) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _max_position_delta(a, b) -> float:
    if len(a) != len(b):
        raise ValueError("position-count drift")
    return max((_distance(pa, pb) for pa, pb in zip(a, b)), default=0.0)


def _within_review_envelope(angle_deg: float) -> bool:
    return RIGGING_REVIEW_MIN_DEG - EPS <= angle_deg <= RIGGING_REVIEW_MAX_DEG + EPS


def build_report(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
    control_glb: bytes,
    candidate_glb: bytes,
    runtime_report: dict[str, Any],
    current_rigging_head: str,
):
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")

    build = runtime_report.get("build", runtime_report)
    if runtime_report.get("exact_runtime_head", RUNTIME_HEAD) != RUNTIME_HEAD:
        raise ValueError("Runtime exact head drift")
    if build.get("runtime_source_head") != "e7874c4a8dca1db48bc66f3546c2134f7d724456":
        raise ValueError("Runtime source representation head drift")
    if int(build.get("control_keys", -1)) != 41 or int(build.get("candidate_keys", -1)) != 19:
        raise ValueError("Runtime key-budget shape drift")
    if build.get("control_sha256") != CONTROL_GLB_SHA256 or build.get("candidate_sha256") != CANDIDATE_GLB_SHA256:
        raise ValueError("Runtime GLB identity drift")
    if abs(float(build.get("tolerance_deg", -1.0)) - RUNTIME_TOLERANCE_DEG) > 1e-12:
        raise ValueError("Runtime angular tolerance drift")
    if build.get("motion_retimed") is not False or build.get("source_authored_keys_modified") is not False:
        raise ValueError("Runtime authority boundary drift")

    control_times, control_rotations = _extract_rotation_curve(control_glb, CONTROL_GLB_SHA256, 41)
    candidate_times, candidate_rotations = _extract_rotation_curve(candidate_glb, CANDIDATE_GLB_SHA256, 19)
    axis = _axis_from_curve(control_rotations)

    max_axis_residual = 0.0
    retained_candidate_angles = []
    for rotation in control_rotations + candidate_rotations:
        _, residual = _signed_angle_and_axis_residual(rotation, axis)
        max_axis_residual = max(max_axis_residual, residual)
    for rotation in candidate_rotations:
        angle, _ = _signed_angle_and_axis_residual(rotation, axis)
        retained_candidate_angles.append(angle)
    if max_axis_residual > AXIS_RESIDUAL_TOLERANCE:
        raise ValueError("rotation axis drift prevents same-axis continuous command proof")
    if any(abs(b - a) >= 180.0 for a, b in zip(retained_candidate_angles, retained_candidate_angles[1:])):
        raise ValueError("candidate segment exceeds shortest same-axis interpolation domain")
    if not all(_within_review_envelope(angle) for angle in retained_candidate_angles):
        raise ValueError("retained candidate key exits Rigging review envelope")

    owner = _prepare_owner(spec, left_profile, bilateral_profile, plan)
    joint_axis = _vec3(owner["joint"]["axis"], "joint axis")
    max_radius = max(_distance(position, owner["pivot"]) for position in owner["positions"])
    angular_position_bound_m = 2.0 * max_radius * math.sin(math.radians(RUNTIME_TOLERANCE_DEG) * 0.5)

    max_qerr_deg = 0.0
    worst_qerr_index = 0
    max_position_delta_m = 0.0
    max_normal_delta_deg = 0.0
    max_tangent_delta_deg = 0.0
    handedness_mismatches = 0
    control_min_angle = float("inf")
    control_max_angle = float("-inf")
    candidate_min_angle = float("inf")
    candidate_max_angle = float("-inf")
    rows = []

    for dense_index in range(DENSE_SAMPLE_COUNT):
        time_s = dense_index / DENSE_RATE_HZ
        control_rotation = _rotation_at(control_times, control_rotations, time_s)
        candidate_rotation = _rotation_at(candidate_times, candidate_rotations, time_s)
        control_angle, control_axis_residual = _signed_angle_and_axis_residual(control_rotation, axis)
        candidate_angle, candidate_axis_residual = _signed_angle_and_axis_residual(candidate_rotation, axis)
        if max(control_axis_residual, candidate_axis_residual) > AXIS_RESIDUAL_TOLERANCE:
            raise ValueError(f"dense rotation axis drift at sample {dense_index}")
        if not _within_review_envelope(candidate_angle):
            raise ValueError(f"candidate command exits Rigging review envelope at sample {dense_index}")

        qerr = _quaternion_error_deg(control_rotation, candidate_rotation)
        if qerr > max_qerr_deg:
            max_qerr_deg = qerr
            worst_qerr_index = dense_index

        control_pose = _pose_metrics(
            owner["positions"], owner["indices"], owner["areas"], owner["weights"],
            owner["pivot"], joint_axis, control_angle,
        )
        candidate_pose = _pose_metrics(
            owner["positions"], owner["indices"], owner["areas"], owner["weights"],
            owner["pivot"], joint_axis, candidate_angle,
        )
        if control_pose.get("status") != "PASS" or candidate_pose.get("status") != "PASS":
            raise ValueError(f"Rigging owner deformation failed at dense sample {dense_index}")

        position_delta = _max_position_delta(control_pose["positions"], candidate_pose["positions"])
        max_position_delta_m = max(max_position_delta_m, position_delta)
        control_frame = _derive_posed_tangent_frame(owner["candidate"], owner["basis"], control_pose["positions"])
        candidate_frame = _derive_posed_tangent_frame(owner["candidate"], owner["basis"], candidate_pose["positions"])
        frame_delta = _frame_residual(candidate_frame, control_frame)
        max_normal_delta_deg = max(max_normal_delta_deg, float(frame_delta["maximum_normal_angle_deg"]))
        max_tangent_delta_deg = max(max_tangent_delta_deg, float(frame_delta["maximum_tangent_angle_deg"]))
        handedness_mismatches += int(frame_delta["handedness_mismatch_count"])

        control_min_angle = min(control_min_angle, control_angle)
        control_max_angle = max(control_max_angle, control_angle)
        candidate_min_angle = min(candidate_min_angle, candidate_angle)
        candidate_max_angle = max(candidate_max_angle, candidate_angle)
        rows.append({
            "dense_index": dense_index,
            "time_s": time_s,
            "control_angle_deg": control_angle,
            "candidate_angle_deg": candidate_angle,
            "quaternion_residual_deg": qerr,
            "maximum_owner_position_delta_m": position_delta,
            "maximum_owner_normal_delta_deg": float(frame_delta["maximum_normal_angle_deg"]),
            "maximum_owner_tangent_delta_deg": float(frame_delta["maximum_tangent_angle_deg"]),
            "handedness_mismatch_count": int(frame_delta["handedness_mismatch_count"]),
            "control_pose_status": control_pose["status"],
            "candidate_pose_status": candidate_pose["status"],
        })

    if max_qerr_deg > RUNTIME_TOLERANCE_DEG + 1e-9:
        raise ValueError("Runtime candidate exceeds exact angular budget under Rigging replay")
    if max_position_delta_m > angular_position_bound_m + 1e-9:
        raise ValueError("owner-position delta exceeds angle-derived Rigging bound")
    if handedness_mismatches != 0:
        raise ValueError("key reduction changes owner tangent handedness")

    runtime_max_qerr = float(build.get("max_quaternion_residual_deg", -1.0))
    if abs(runtime_max_qerr - max_qerr_deg) > 1e-7:
        raise ValueError("Rigging replay does not reproduce Runtime angular residual")

    # Actual-curve fail-closed mutation: shift one retained candidate key by +1 degree
    # about the same exact axis. This must violate the unchanged Runtime angular budget.
    mutated_rotations = [list(rotation) for rotation in candidate_rotations]
    mutation_index = min(range(len(candidate_times)), key=lambda index: abs(candidate_times[index] - 0.5))
    mutation_angle, _ = _signed_angle_and_axis_residual(mutated_rotations[mutation_index], axis)
    mutated_rotations[mutation_index] = _quat_from_axis_angle(axis, mutation_angle + 1.0)
    mutated_max_qerr = max(
        _quaternion_error_deg(
            _rotation_at(control_times, control_rotations, dense_index / DENSE_RATE_HZ),
            _rotation_at(candidate_times, mutated_rotations, dense_index / DENSE_RATE_HZ),
        )
        for dense_index in range(DENSE_SAMPLE_COUNT)
    )
    if mutated_max_qerr <= RUNTIME_TOLERANCE_DEG:
        raise ValueError("fail-closed +1 degree candidate-key mutation unexpectedly accepted")
    if _within_review_envelope(RIGGING_REVIEW_MAX_DEG + 1.0):
        raise ValueError("fail-closed review-envelope widening unexpectedly accepted")

    representative_indices = sorted(set(REPRESENTATIVE_INDICES + [worst_qerr_index]))
    representatives = [rows[index] for index in representative_indices]
    continuous_command_min = min(retained_candidate_angles)
    continuous_command_max = max(retained_candidate_angles)

    return {
        "schema": SCHEMA,
        "state": PASS_STATE,
        "current_rigging_head": current_rigging_head,
        "predecessor_rigging_head": PREDECESSOR_RIGGING_HEAD,
        "runtime_dependency": {
            "head": RUNTIME_HEAD,
            "artifact_id": RUNTIME_ARTIFACT_ID,
            "artifact_sha256": RUNTIME_ARTIFACT_SHA256,
            "control_glb_sha256": CONTROL_GLB_SHA256,
            "candidate_glb_sha256": CANDIDATE_GLB_SHA256,
            "control_keys": 41,
            "candidate_keys": 19,
            "runtime_angular_budget_deg": RUNTIME_TOLERANCE_DEG,
        },
        "rig_identity": {
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
            "side": "right",
            "weighting": "smoothstep-v0",
            "review_envelope_deg": [RIGGING_REVIEW_MIN_DEG, RIGGING_REVIEW_MAX_DEG],
            "source_or_rig_changed": False,
        },
        "continuous_command_envelope": {
            "same_axis_slerp_proven": True,
            "maximum_axis_residual": max_axis_residual,
            "retained_candidate_key_angle_min_deg": continuous_command_min,
            "retained_candidate_key_angle_max_deg": continuous_command_max,
            "all_candidate_segments_shorter_than_180_deg": True,
            "entire_reduced_channel_inside_existing_rigging_review_envelope": True,
            "continuous_deformation_or_collision_safety_claimed": False,
        },
        "dense_deformation_witnesses": {
            "sample_rate_hz": DENSE_RATE_HZ,
            "sample_count": DENSE_SAMPLE_COUNT,
            "control_angle_min_deg": control_min_angle,
            "control_angle_max_deg": control_max_angle,
            "candidate_angle_min_deg": candidate_min_angle,
            "candidate_angle_max_deg": candidate_max_angle,
            "all_control_owner_poses_pass": True,
            "all_candidate_owner_poses_pass": True,
            "maximum_quaternion_residual_deg": max_qerr_deg,
            "worst_quaternion_residual_index": worst_qerr_index,
            "worst_quaternion_residual_time_s": worst_qerr_index / DENSE_RATE_HZ,
            "maximum_owner_position_delta_m": max_position_delta_m,
            "angle_derived_owner_position_bound_m": angular_position_bound_m,
            "maximum_owner_normal_delta_deg": max_normal_delta_deg,
            "maximum_owner_tangent_delta_deg": max_tangent_delta_deg,
            "tangent_handedness_mismatches": handedness_mismatches,
        },
        "representative_poses": representatives,
        "negative_controls": {
            "candidate_retained_key_plus_1deg_max_residual_deg": mutated_max_qerr,
            "candidate_retained_key_plus_1deg_rejected_by_angular_budget": True,
            "review_envelope_plus_1deg_rejected": True,
        },
        "authority_boundary": {
            "runtime_key_budget_adopted_by_rigging": False,
            "animation_timing_interpolation_playback_accepted_by_rigging": False,
            "technical_art_target_host_accepted_by_rigging": False,
            "runtime_controller_device_accepted_by_rigging": False,
            "materials_art_qa_accepted_by_rigging": False,
            "canon_or_production_ready": False,
        },
        "truth_boundary": (
            "PASS proves same-axis continuous command-envelope inclusion and 321 sampled owner-deformation "
            "witnesses for the exact 19-key Runtime candidate. It does not prove mathematical continuous "
            "deformation/collision safety, Animation playback, target-host behavior, device performance, "
            "visual acceptance, CANON, or production readiness."
        ),
    }


def _load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--control-glb", required=True)
    parser.add_argument("--candidate-glb", required=True)
    parser.add_argument("--runtime-report", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = build_report(
        _load(Path(args.source)),
        _load(Path(args.left_profile)),
        _load(Path(args.bilateral_profile)),
        _load(Path(args.rig_plan)),
        _load(Path(args.weighting_profile)),
        Path(args.control_glb).read_bytes(),
        Path(args.candidate_glb).read_bytes(),
        _load(Path(args.runtime_report)),
        args.current_rigging_head,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "representative-poses.json").write_text(
        json.dumps(report["representative_poses"], indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
