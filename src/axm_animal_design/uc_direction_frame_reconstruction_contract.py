"""Technical-Art adoption contract for post-skin direction-frame reconstruction.

Rigging owns the proved reconstruction from transported skinned POSITION back to
the Geometry/Rigging owner normal+tangent frame. Technical Art owns only the
receiving contract: which exact evidence is sufficient to expose that option to
an importer/runtime without pretending the older static NORMAL/TANGENT skinning
path is correct.

This module deliberately does not copy the Animal frame-reconstruction algorithm
and does not add Animal semantics to Universal Creation. It binds owner evidence,
records the reusable receiver steps, and fails closed until a real target/runtime
implements and proves those steps separately.
"""
from __future__ import annotations

import math
from typing import Any

CONTRACT_SCHEMA = "axm.animal-uc-direction-frame-reconstruction-contract/v0.1"
RIGGING_SCHEMA = "axm.animal-post-skin-owner-frame-reconstruction/v0.1"
RIGGING_PASS_STATE = "PASS_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_41_KEYS"
PASS_STATE = (
    "PASS_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_CONTRACT_ADOPTED__"
    "HOLD_TARGET_RUNTIME_IMPLEMENTATION"
)
KEY_COUNT = 41
POSITION_TOLERANCE_M = 1e-6
DIRECTION_TOLERANCE_DEG = 1e-3
ORTHOGONALITY_TOLERANCE = 1e-9
MUTATION_MIN_SIGNAL_DEG = 5e-2


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{label} must be finite")
    return output


def _non_negative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def adopt_direction_frame_reconstruction_contract(
    rigging_receipt: dict[str, Any],
    *,
    exact_rigging_head: str,
    exact_rigging_artifact_id: int,
    exact_rigging_artifact_sha256: str,
    exact_source_technical_art_head: str,
    exact_source_glb_sha256: str,
    current_technical_art_head: str,
    current_uc_head: str,
    current_uc_codec_blob: str,
) -> dict[str, Any]:
    """Adopt a bounded receiver contract from exact Rigging-owned evidence.

    Adoption here means Technical Art can name and gate the receiver steps. It is
    intentionally *not* a claim that Godot, a runtime shader, UC, or another
    target already performs them.
    """
    if rigging_receipt.get("schema") != RIGGING_SCHEMA:
        raise ValueError("Rigging reconstruction receipt schema drift")
    if rigging_receipt.get("state") != RIGGING_PASS_STATE:
        raise ValueError("Rigging reconstruction owner state is not the exact bounded PASS")

    premise = _mapping(rigging_receipt.get("premise"), "premise")
    motion = _mapping(rigging_receipt.get("motion_boundary"), "motion_boundary")
    reconstruction = _mapping(rigging_receipt.get("reconstruction"), "reconstruction")
    negatives = _mapping(rigging_receipt.get("negative_controls"), "negative_controls")
    truth = _mapping(rigging_receipt.get("truth_boundary"), "truth_boundary")

    # The new contract must not erase the historical finding: blindly skinning
    # static NORMAL/TANGENT payloads remains the wrong direction-frame path.
    if premise.get("static_direction_transport_gate") != "HOLD":
        raise ValueError("static transported NORMAL/TANGENT premise is no longer the retained HOLD")
    if motion.get("authored_key_count") != KEY_COUNT:
        raise ValueError("Rigging reconstruction authored-key boundary drift")
    if reconstruction.get("gate") != "PASS":
        raise ValueError("Rigging owner reconstruction gate is not PASS")

    split_residual = _number(
        reconstruction.get("maximum_uv_split_position_residual_m"),
        "maximum_uv_split_position_residual_m",
    )
    position_residual = _number(
        reconstruction.get("maximum_owner_position_residual_m"),
        "maximum_owner_position_residual_m",
    )
    normal_angle = _number(
        reconstruction.get("maximum_owner_normal_angle_deg"),
        "maximum_owner_normal_angle_deg",
    )
    tangent_angle = _number(
        reconstruction.get("maximum_owner_tangent_angle_deg"),
        "maximum_owner_tangent_angle_deg",
    )
    orthogonality = _number(
        reconstruction.get("maximum_normal_tangent_dot_abs"),
        "maximum_normal_tangent_dot_abs",
    )
    handedness_mismatches = _non_negative_int(
        reconstruction.get("tangent_handedness_mismatch_count"),
        "tangent_handedness_mismatch_count",
    )

    if split_residual > POSITION_TOLERANCE_M:
        raise ValueError("UV-split position equivalence exceeds Technical Art contract bound")
    if position_residual > POSITION_TOLERANCE_M:
        raise ValueError("owner position reconstruction exceeds Technical Art contract bound")
    if normal_angle > DIRECTION_TOLERANCE_DEG:
        raise ValueError("owner normal reconstruction exceeds Technical Art contract bound")
    if tangent_angle > DIRECTION_TOLERANCE_DEG:
        raise ValueError("owner tangent reconstruction exceeds Technical Art contract bound")
    if orthogonality > ORTHOGONALITY_TOLERANCE:
        raise ValueError("reconstructed normal/tangent orthogonality exceeds contract bound")
    if handedness_mismatches != 0:
        raise ValueError("reconstructed tangent handedness mismatch is not zero")

    mutation = _mapping(negatives.get("coherent_posed_shape_mutation"), "coherent_posed_shape_mutation")
    if mutation.get("status") != "PASS_MUTATION_DETECTED":
        raise ValueError("Rigging reconstruction sensitivity control is not PASS_MUTATION_DETECTED")
    mutation_signal = _number(mutation.get("direction_signal_deg"), "direction_signal_deg")
    if mutation_signal < MUTATION_MIN_SIGNAL_DEG:
        raise ValueError("Rigging reconstruction sensitivity signal is below the retained bound")

    if truth.get("post_skin_owner_frame_reconstruction_established") is not True:
        raise ValueError("Rigging truth boundary does not establish the reconstruction")
    if truth.get("technical_art_adopted_reconstruction") is not False:
        raise ValueError("owner receipt must precede Technical Art adoption")
    for key in (
        "animation_accepted",
        "runtime_or_controller_accepted",
        "shaded_visual_quality_accepted",
        "canon_claimed",
    ):
        if truth.get(key) is True:
            raise ValueError(f"Rigging owner receipt overclaims {key}")

    if type(exact_rigging_artifact_id) is not int or exact_rigging_artifact_id <= 0:
        raise ValueError("exact Rigging artifact id must be a positive integer")
    for value, label in (
        (exact_rigging_head, "exact Rigging head"),
        (exact_rigging_artifact_sha256, "exact Rigging artifact SHA-256"),
        (exact_source_technical_art_head, "source Technical Art head"),
        (exact_source_glb_sha256, "source GLB SHA-256"),
        (current_technical_art_head, "current Technical Art head"),
        (current_uc_head, "current UC head"),
        (current_uc_codec_blob, "current UC codec blob"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be non-empty")

    return {
        "schema": CONTRACT_SCHEMA,
        "state": PASS_STATE,
        "owner_evidence": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "rigging_head": exact_rigging_head,
            "artifact_id": exact_rigging_artifact_id,
            "artifact_sha256": exact_rigging_artifact_sha256,
            "schema": RIGGING_SCHEMA,
            "state": RIGGING_PASS_STATE,
        },
        "source_transport": {
            "technical_art_head": exact_source_technical_art_head,
            "glb_sha256": exact_source_glb_sha256,
            "raw_static_normal_tangent_skinning": "HOLD",
        },
        "technical_art": {
            "head": current_technical_art_head,
            "contract_adopted": True,
            "owner_reconstruction_algorithm_copied": False,
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "head": current_uc_head,
            "codec": "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js",
            "codec_blob": current_uc_codec_blob,
            "product_modified": False,
            "role": "generic rigged GLB transport/receiver only",
        },
        "receiver_contract": {
            "id": "POST_SKIN_POSITION_TO_OWNER_DIRECTION_FRAME_RECONSTRUCTION",
            "portable_contract_adopted": True,
            "target_runtime_implemented": False,
            "required_inputs": [
                "transported skinned POSITION field",
                "fixed render_source_indices mapping",
                "source topology identity",
                "fixed TEXCOORD_0 identity",
                "tangent handedness identity",
            ],
            "steps": [
                "skin transported POSITION using the receiver skin palette",
                "collapse UV-split render positions by fixed render_source_indices with split-equivalence gate",
                "map target positions back through the explicit Animal-to-UC coordinate boundary",
                "invoke the owner-provided posed normal/tangent reconstruction over source positions + topology + UV identity",
                "expand the reconstructed owner frame through the fixed render_source_indices mapping while preserving tangent W",
            ],
            "owner_algorithm_location": "Rigging/Geometry domain owner; not Technical Art and not Universal Creation",
        },
        "measurements": {
            "authored_key_count": KEY_COUNT,
            "maximum_uv_split_position_residual_m": split_residual,
            "maximum_owner_position_residual_m": position_residual,
            "maximum_owner_normal_angle_deg": normal_angle,
            "maximum_owner_tangent_angle_deg": tangent_angle,
            "maximum_normal_tangent_dot_abs": orthogonality,
            "tangent_handedness_mismatch_count": handedness_mismatches,
            "mutation_direction_signal_deg": mutation_signal,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "direction_tolerance_deg": DIRECTION_TOLERANCE_DEG,
            "orthogonality_tolerance": ORTHOGONALITY_TOLERANCE,
        },
        "truth_boundary": {
            "raw_static_normal_tangent_direction_equivalence_established": False,
            "post_skin_reconstruction_contract_adopted_by_technical_art": True,
            "owner_reconstruction_algorithm_copied_into_technical_art": False,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "target_engine_reconstruction_implemented": False,
            "runtime_or_controller_accepted": False,
            "shaded_visual_quality_accepted": False,
            "canon_claimed": False,
            "production_ready": False,
        },
    }


def require_target_runtime_ready(contract: dict[str, Any]) -> None:
    """Refuse runtime promotion until a real target proves this adopted contract."""
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("direction-frame reconstruction contract schema drift")
    receiver = _mapping(contract.get("receiver_contract"), "receiver_contract")
    if receiver.get("target_runtime_implemented") is not True:
        raise ValueError("direction-frame reconstruction contract is adopted but target runtime implementation is HOLD")
