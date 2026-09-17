"""Technical-Art target-host contract for Animal post-skin owner-frame reconstruction.

Rigging/Geometry own the actual reconstruction algorithm. This module owns only
an integration packet: exact reconstructed frame values are handed to a real
receiver without copying Animal reconstruction semantics into Universal Creation
or claiming Runtime/product acceptance.
"""
from __future__ import annotations

import math
from typing import Any

ADOPTION_SCHEMA = "axm.animal-uc-direction-frame-reconstruction-contract/v0.1"
ADOPTION_STATE = (
    "PASS_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_CONTRACT_ADOPTED__"
    "HOLD_TARGET_RUNTIME_IMPLEMENTATION"
)
PACKET_SCHEMA = "axm.animal-direction-frame-target-host-adapter/v0.1"
PACKET_STATE = (
    "READY_TECHNICAL_ART_TARGET_HOST_REFERENCE_IMPLEMENTATION__"
    "HOLD_RUNTIME_PRODUCT_IMPLEMENTATION"
)
KEY_COUNT = 41
RENDER_VERTEX_COUNT = 84
TRIANGLE_COUNT = 80


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _vector(value: Any, width: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != width:
        raise ValueError(f"{label} must contain {width} values")
    output: list[float] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise ValueError(f"{label} must contain numeric values")
        number = float(component)
        if not math.isfinite(number):
            raise ValueError(f"{label} must contain finite values")
        output.append(number)
    return output


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty")
    return value.strip()


def validate_adoption_contract(contract: dict[str, Any]) -> None:
    """Require the exact bounded predecessor without rewriting its HOLDs."""
    if contract.get("schema") != ADOPTION_SCHEMA:
        raise ValueError("direction-frame adoption schema drift")
    if contract.get("state") != ADOPTION_STATE:
        raise ValueError("direction-frame adoption state drift")

    receiver = _mapping(contract.get("receiver_contract"), "receiver_contract")
    truth = _mapping(contract.get("truth_boundary"), "truth_boundary")
    technical_art = _mapping(contract.get("technical_art"), "technical_art")
    uc = _mapping(contract.get("universal_creation"), "universal_creation")

    if receiver.get("portable_contract_adopted") is not True:
        raise ValueError("Technical Art predecessor contract is not adopted")
    if receiver.get("target_runtime_implemented") is not False:
        raise ValueError("predecessor target-runtime HOLD was silently rewritten")
    if technical_art.get("owner_reconstruction_algorithm_copied") is not False:
        raise ValueError("owner reconstruction algorithm was copied into Technical Art")
    if truth.get("animal_domain_policy_moved_into_uc") is not False:
        raise ValueError("Animal domain policy moved into UC")
    if truth.get("raw_static_normal_tangent_direction_equivalence_established") is not False:
        raise ValueError("historical static direction-frame HOLD was silently erased")
    if uc.get("product_modified") is not False:
        raise ValueError("predecessor unexpectedly modified UC product code")


def build_target_host_packet(
    contract: dict[str, Any],
    *,
    frames: list[dict[str, Any]],
    exact_technical_art_head: str,
    exact_source_glb_sha256: str,
    exact_rigging_head: str,
    exact_rigging_reconstruction_module_blob: str,
    current_uc_head: str,
    current_uc_codec_blob: str,
    current_uc_inspection: dict[str, Any],
) -> dict[str, Any]:
    """Build a fail-closed packet for a real Technical-Art target-host probe.

    ``frames`` must already have been reconstructed by the exact owner checkout.
    This function validates/serializes the receiving boundary only.
    """
    validate_adoption_contract(contract)
    if not isinstance(frames, list) or len(frames) != KEY_COUNT:
        raise ValueError("target-host adapter requires all 41 authored keys")

    required_strings = (
        (exact_technical_art_head, "Technical Art head"),
        (exact_source_glb_sha256, "source GLB SHA-256"),
        (exact_rigging_head, "Rigging head"),
        (exact_rigging_reconstruction_module_blob, "Rigging reconstruction module blob"),
        (current_uc_head, "current UC head"),
        (current_uc_codec_blob, "current UC codec blob"),
    )
    for value, label in required_strings:
        _nonempty(value, label)

    if current_uc_inspection.get("pass") is not True:
        raise ValueError("current UC generic receiver did not accept the exact source GLB")
    if current_uc_inspection.get("vertices") != RENDER_VERTEX_COUNT:
        raise ValueError("current UC receiver vertex count drift")
    if current_uc_inspection.get("triangles") != TRIANGLE_COUNT:
        raise ValueError("current UC receiver triangle count drift")
    if current_uc_inspection.get("weightSumsPass") is not True:
        raise ValueError("current UC receiver weight-sum gate failed")
    if current_uc_inspection.get("jointIndicesPass") is not True:
        raise ValueError("current UC receiver joint-index gate failed")
    if _mapping(current_uc_inspection.get("deformation"), "UC deformation").get("pass") is not True:
        raise ValueError("current UC receiver deformation observer failed")

    normalized_frames: list[dict[str, Any]] = []
    last_time = -math.inf
    for expected_index, frame in enumerate(frames):
        row = _mapping(frame, f"frames[{expected_index}]")
        if row.get("sample_index") != expected_index:
            raise ValueError("target-host frame ordering drift")
        time_seconds = float(row.get("time_seconds"))
        if not math.isfinite(time_seconds) or time_seconds <= last_time:
            raise ValueError("target-host frame times must be finite and strictly increasing")
        last_time = time_seconds

        positions = row.get("positions")
        normals = row.get("normals")
        tangents = row.get("tangents")
        texcoords = row.get("texcoords")
        indices = row.get("indices")
        if not all(isinstance(value, list) for value in (positions, normals, tangents, texcoords, indices)):
            raise ValueError("target-host frame arrays must be lists")
        if not (
            len(positions) == len(normals) == len(tangents) == len(texcoords) == RENDER_VERTEX_COUNT
        ):
            raise ValueError("target-host render-domain count drift")
        if len(indices) != TRIANGLE_COUNT * 3:
            raise ValueError("target-host index count drift")
        if any(type(index) is not int or not 0 <= index < RENDER_VERTEX_COUNT for index in indices):
            raise ValueError("target-host index domain drift")

        clean_positions = [_vector(value, 3, "position") for value in positions]
        clean_normals = [_vector(value, 3, "normal") for value in normals]
        clean_tangents = [_vector(value, 4, "tangent") for value in tangents]
        clean_texcoords = [_vector(value, 2, "texcoord") for value in texcoords]
        for tangent in clean_tangents:
            if abs(abs(tangent[3]) - 1.0) > 1e-9:
                raise ValueError("target-host tangent handedness must stay exactly +/-1")

        split_residual = float(row.get("uv_split_position_residual_m"))
        if not math.isfinite(split_residual) or split_residual > 1e-6:
            raise ValueError("target-host UV-split position gate failed")

        normalized_frames.append(
            {
                "sample_index": expected_index,
                "time_seconds": time_seconds,
                "angle_deg": float(row.get("angle_deg")),
                "positions": clean_positions,
                "normals": clean_normals,
                "tangents": clean_tangents,
                "texcoords": clean_texcoords,
                "indices": [int(value) for value in indices],
                "uv_split_position_residual_m": split_residual,
            }
        )

    source = _mapping(contract.get("source_transport"), "source_transport")
    if source.get("glb_sha256") != exact_source_glb_sha256:
        raise ValueError("source GLB identity no longer matches adopted contract")
    owner = _mapping(contract.get("owner_evidence"), "owner_evidence")
    if owner.get("rigging_head") != exact_rigging_head:
        raise ValueError("Rigging owner head no longer matches adopted contract")

    return {
        "schema": PACKET_SCHEMA,
        "state": PACKET_STATE,
        "technical_art": {
            "head": exact_technical_art_head,
            "reference_target_host_adapter_implemented": True,
            "owner_reconstruction_algorithm_copied": False,
        },
        "owner": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "rigging_head": exact_rigging_head,
            "reconstruction_module_blob": exact_rigging_reconstruction_module_blob,
            "algorithm_invocation": "exact owner checkout at evidence build time",
        },
        "source_transport": {
            "glb_sha256": exact_source_glb_sha256,
            "raw_static_normal_tangent_skinning": "HOLD",
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "head": current_uc_head,
            "codec_blob": current_uc_codec_blob,
            "product_modified": False,
            "role": "generic rigged GLB validation/deformation receiver only",
            "inspection": current_uc_inspection,
        },
        "receiver_scope": {
            "side": "right",
            "authored_key_count": KEY_COUNT,
            "render_vertices": RENDER_VERTEX_COUNT,
            "triangles": TRIANGLE_COUNT,
            "target_host": "Godot ArrayMesh reference probe",
            "target_host_computes_owner_reconstruction": False,
            "target_host_receives_owner_reconstructed_frame": True,
        },
        "frames": normalized_frames,
        "truth_boundary": {
            "technical_art_target_host_reference_implemented": True,
            "owner_reconstruction_algorithm_copied_into_technical_art": False,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "runtime_product_implementation_established": False,
            "target_device_performance_accepted": False,
            "bilateral_target_host_equivalence_established": False,
            "continuous_interpolated_shaded_playback_established": False,
            "production_tangent_space_quality_accepted": False,
            "canon_claimed": False,
            "production_ready": False,
        },
    }


def require_runtime_product_ready(packet: dict[str, Any]) -> None:
    """Reference target-host evidence must never silently become Runtime acceptance."""
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("target-host adapter packet schema drift")
    truth = _mapping(packet.get("truth_boundary"), "truth_boundary")
    if truth.get("runtime_product_implementation_established") is not True:
        raise ValueError("Technical Art target-host adapter is green but Runtime product implementation is HOLD")
