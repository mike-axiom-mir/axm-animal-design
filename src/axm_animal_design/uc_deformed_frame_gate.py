"""Technical-Art capability gate for deformed normal/tangent transport.

Rigging owns the deformation observation. Technical Art owns whether a transport
path may truthfully claim that the observed deformed direction frame survives the
boundary. This module consumes only the retained Rigging receipt and generic UC
receiver identity; it does not recompute Animal topology, normals, tangents,
weights, poses, animation, or visual quality.
"""
from __future__ import annotations

from typing import Any

GATE_SCHEMA = "axm.deformed-direction-frame-transport-gate/v0.1"
RIGGING_SCHEMA = "axm.animal-transported-tangent-deformation-audit/v0.1"
RIGGING_HOLD_STATE = (
    "PASS_TRANSPORTED_SKINNED_POSITION_EQUIVALENCE__"
    "HOLD_DEFORMED_NORMAL_TANGENT_EQUIVALENCE"
)
RIGGING_PASS_STATE = "PASS_TRANSPORTED_SKINNED_TANGENT_FRAME_EQUIVALENCE"
BASE_TRANSPORT_STATUS = (
    "PASS_ANIMAL_GEOMETRY_UV_TANGENT_RENDER_DOMAIN_WITH_SKIN_KEYS_TO_CURRENT_UC_CODEC"
)
HOLD_STATE = "PASS_STATIC_SKIN_TRANSPORT__HOLD_DEFORMED_DIRECTION_FRAME"
PASS_STATE = "PASS_DEFORMED_DIRECTION_FRAME_TRANSPORT_GATE"
FAIL_STATE = "FAIL_DEFORMED_DIRECTION_FRAME_TRANSPORT_GATE"
POSITION_TOLERANCE_M = 1e-6
DIRECTION_EXCESS_TOLERANCE_DEG = 1e-6
ORTHOGONALITY_TOLERANCE = 1e-9


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    output = float(value)
    if output != output or output in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite")
    return output


def evaluate_deformed_direction_frame_gate(
    rigging_receipt: dict[str, Any],
    *,
    expected_technical_art_head: str,
    expected_glb_sha256: str,
    exact_rigging_head: str,
    current_uc_head: str,
    current_uc_codec_blob: str,
) -> dict[str, Any]:
    """Project Rigging's exact observation into a fail-closed transport decision.

    A green generic GLB/UC path is not enough to claim tangent-space readiness.
    Position/UV/handedness and deformed direction-frame equivalence are separate
    capabilities. A direction HOLD therefore remains a HOLD until an owning lane
    supplies new evidence for a correction/reconstruction path.
    """
    if rigging_receipt.get("schema") != RIGGING_SCHEMA:
        raise ValueError("Rigging deformation receipt schema drift")
    state = rigging_receipt.get("state")
    if state not in {RIGGING_HOLD_STATE, RIGGING_PASS_STATE}:
        raise ValueError("Rigging deformation receipt is neither the bounded PASS nor HOLD state")

    technical_art = _mapping(rigging_receipt.get("technical_art"), "technical_art")
    if technical_art.get("head") != expected_technical_art_head:
        raise ValueError("Rigging receipt Technical Art head drift")
    if technical_art.get("glb_sha256") != expected_glb_sha256:
        raise ValueError("Rigging receipt GLB identity drift")

    position = _mapping(rigging_receipt.get("position_uv_handedness"), "position_uv_handedness")
    directions = _mapping(rigging_receipt.get("direction_frames"), "direction_frames")
    truth = _mapping(rigging_receipt.get("truth_boundary"), "truth_boundary")

    max_position = _number(position.get("maximum_position_residual_m"), "maximum_position_residual_m")
    max_uv = _number(position.get("maximum_uv_residual"), "maximum_uv_residual")
    handedness_mismatches = position.get("tangent_handedness_mismatch_count")
    if type(handedness_mismatches) is not int or handedness_mismatches < 0:
        raise ValueError("tangent handedness mismatch count must be a non-negative integer")

    normal_excess = _number(directions.get("normal_deformation_excess_deg"), "normal_deformation_excess_deg")
    tangent_excess = _number(
        directions.get("corrected_tangent_deformation_excess_deg"),
        "corrected_tangent_deformation_excess_deg",
    )
    corrected_dot = _number(
        directions.get("maximum_corrected_normal_tangent_dot_abs"),
        "maximum_corrected_normal_tangent_dot_abs",
    )

    position_pass = (
        position.get("gate") == "PASS"
        and max_position <= POSITION_TOLERANCE_M
        and handedness_mismatches == 0
    )
    orthogonality_pass = (
        directions.get("post_skin_gram_schmidt_orthogonality_gate") == "PASS"
        and corrected_dot <= ORTHOGONALITY_TOLERANCE
    )
    direction_pass = (
        state == RIGGING_PASS_STATE
        and normal_excess <= DIRECTION_EXCESS_TOLERANCE_DEG
        and tangent_excess <= DIRECTION_EXCESS_TOLERANCE_DEG
    )

    if not position_pass:
        gate_state = FAIL_STATE
    elif direction_pass:
        gate_state = PASS_STATE
    else:
        gate_state = HOLD_STATE

    # Do not allow the transport lane to promote a direction-frame PASS that the
    # Rigging owner has not actually established.
    if truth.get("deformed_direction_frame_equivalence_established") is True and not direction_pass:
        raise ValueError("Rigging truth boundary contradicts measured direction-frame gate")
    if truth.get("position_equivalence_established") is not True and position_pass:
        raise ValueError("Rigging truth boundary does not establish the measured position PASS")

    return {
        "schema": GATE_SCHEMA,
        "state": gate_state,
        "source_observation": {
            "rigging_head": str(exact_rigging_head),
            "rigging_schema": RIGGING_SCHEMA,
            "rigging_state": state,
            "technical_art_head": str(expected_technical_art_head),
            "glb_sha256": str(expected_glb_sha256),
        },
        "receiver": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "head": str(current_uc_head),
            "codec": "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js",
            "codec_blob": str(current_uc_codec_blob),
            "product_modified": False,
        },
        "capabilities": {
            "base_static_skin_transport": BASE_TRANSPORT_STATUS,
            "position_uv_handedness": "PASS" if position_pass else "FAIL",
            "post_skin_gram_schmidt_orthogonality": "PASS" if orthogonality_pass else "HOLD",
            "deformed_direction_frame": "PASS" if direction_pass else "HOLD",
            "tangent_space_runtime_ready": bool(direction_pass),
        },
        "measurements": {
            "maximum_position_residual_m": max_position,
            "maximum_uv_residual": max_uv,
            "tangent_handedness_mismatch_count": handedness_mismatches,
            "normal_deformation_excess_deg": normal_excess,
            "corrected_tangent_deformation_excess_deg": tangent_excess,
            "maximum_corrected_normal_tangent_dot_abs": corrected_dot,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "direction_excess_tolerance_deg": DIRECTION_EXCESS_TOLERANCE_DEG,
            "orthogonality_tolerance": ORTHOGONALITY_TOLERANCE,
        },
        "required_receiver_action": (
            None
            if direction_pass
            else "provide separately proven deformed normal/tangent reconstruction or correction before tangent-space runtime/visual acceptance"
        ),
        "truth_boundary": {
            "owner_observation_recomputed": False,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "position_transport_established": bool(position_pass),
            "deformed_direction_frame_equivalence_established": bool(direction_pass),
            "orthogonality_alone_counts_as_direction_equivalence": False,
            "target_engine_import_or_playback_accepted": False,
            "shaded_visual_quality_accepted": False,
            "runtime_or_controller_accepted": False,
            "canon_claimed": False,
        },
    }


def require_tangent_space_runtime_ready(decision: dict[str, Any]) -> None:
    """Fail closed when a caller attempts to promote a held frame transport."""
    if decision.get("schema") != GATE_SCHEMA:
        raise ValueError("direction-frame gate decision schema drift")
    capabilities = _mapping(decision.get("capabilities"), "capabilities")
    if capabilities.get("tangent_space_runtime_ready") is not True:
        raise ValueError("deformed direction-frame equivalence is HOLD; tangent-space runtime promotion refused")
