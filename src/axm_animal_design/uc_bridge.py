"""Explicit technical-art bridges from animal-design surfaces into UC.

Animal source geometry is authored in metres using +X forward, +Y left, +Z up.
Universal Creation's portable surface/GLB path is metres, Y-up, +Z forward.
These adapters perform the coordinate/handedness conversion explicitly, reverse
triangle winding after the reflection, convert the Animal-local material contract,
and retain exact source/donor identities. Animal semantics stay in animal-design.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

ANIMAL_EVIDENCE_SCHEMA = "axm.animal-organic-form-evidence/v0.1"
UC_SURFACE_SCHEMA = "axm.surface-3d/v0.1"
SOURCE_COORDINATES = "+X forward, +Y left, +Z up"
TARGET_COORDINATES = "+X right, +Y up, +Z forward"
BRIDGE_SCHEMA = "axm.animal-uc-surface-bridge-evidence/v0.1"
CONNECTED_BRIDGE_SCHEMA = "axm.animal-connected-candidate-uc-bridge-evidence/v0.1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _vec3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must contain three values")
    return [_finite(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _source_to_uc(vector: Any, label: str) -> list[float]:
    """Map animal source coordinates to UC/glTF Y-up,+Z-forward coordinates.

    Source physical basis is forward/left/up. Target is right/up/forward, so the
    exact component map is (-left, up, forward). This changes handedness; triangle
    winding must therefore be reversed separately.
    """
    x_forward, y_left, z_up = _vec3(vector, label)
    return [round(-y_left, 9), round(z_up, 9), round(x_forward, 9)]


def _linear_rgba_to_hex(value: Any) -> str:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("base_color must contain four linear RGBA values")
    channels = []
    for index, item in enumerate(value):
        number = _finite(item, f"base_color[{index}]")
        if not 0.0 <= number <= 1.0:
            raise ValueError("base_color channels must stay within 0..1")
        channels.append(max(0, min(255, int(math.floor(number * 255.0 + 0.5)))))
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _convert_surface_to_uc(name: str, surface: dict[str, Any], *, coordinate_system: str) -> dict[str, Any]:
    """Convert one Animal-local renderer-neutral surface into UC's portable surface contract."""
    if coordinate_system != SOURCE_COORDINATES:
        raise ValueError("unsupported animal coordinate system; refusing implicit axis conversion")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("surface name is required")
    if not isinstance(surface, dict) or surface.get("schema") != UC_SURFACE_SCHEMA:
        raise ValueError(f"surface must declare {UC_SURFACE_SCHEMA}")
    if surface.get("units") != "m":
        raise ValueError("bridge requires animal surface units='m'")
    primitives = surface.get("primitives")
    if not isinstance(primitives, list) or not primitives:
        raise ValueError("surface primitives are required")

    output_primitives = []
    seen = set()
    for primitive in primitives:
        if not isinstance(primitive, dict):
            raise ValueError("surface primitive must be an object")
        identifier = primitive.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("primitive IDs must be unique non-empty text")
        seen.add(identifier)
        positions = primitive.get("positions")
        normals = primitive.get("normals")
        indices = primitive.get("indices")
        if not isinstance(positions, list) or not isinstance(normals, list) or len(positions) != len(normals):
            raise ValueError(f"{identifier} positions/normals must be equally sized lists")
        if not isinstance(indices, list) or not indices or len(indices) % 3:
            raise ValueError(f"{identifier} indices must contain complete triangles")
        if any(type(index) is not int or not 0 <= index < len(positions) for index in indices):
            raise ValueError(f"{identifier} contains an out-of-range triangle index")

        converted_indices = []
        for offset in range(0, len(indices), 3):
            a, b, c = indices[offset:offset + 3]
            converted_indices.extend([a, c, b])

        material = primitive.get("material")
        if not isinstance(material, dict):
            raise ValueError(f"{identifier} material is required")
        metallic = _finite(material.get("metallic"), f"{identifier}.metallic")
        roughness = _finite(material.get("roughness"), f"{identifier}.roughness")
        if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
            raise ValueError(f"{identifier} metallic/roughness must stay within 0..1")
        converted = {
            "id": identifier,
            "positions": [_source_to_uc(row, f"{identifier}.position") for row in positions],
            "normals": [_source_to_uc(row, f"{identifier}.normal") for row in normals],
            "indices": converted_indices,
            "material": {
                "color": _linear_rgba_to_hex(material.get("base_color")),
                "metallic": metallic,
                "roughness": roughness,
            },
        }
        if "colors" in primitive:
            colors = primitive["colors"]
            if not isinstance(colors, list) or len(colors) != len(positions):
                raise ValueError(f"{identifier} colors must match vertex count")
            converted["colors"] = copy.deepcopy(colors)
        output_primitives.append(converted)

    return {
        "schema": UC_SURFACE_SCHEMA,
        "name": name.strip(),
        "primitives": output_primitives,
    }


def adapt_form_evidence_for_uc(form_evidence: dict[str, Any]) -> dict[str, Any]:
    """Return a strict UC-compatible surface without modifying source form evidence."""
    if not isinstance(form_evidence, dict) or form_evidence.get("schema") != ANIMAL_EVIDENCE_SCHEMA:
        raise ValueError(f"form evidence must use {ANIMAL_EVIDENCE_SCHEMA}")
    return _convert_surface_to_uc(
        form_evidence.get("name"),
        form_evidence.get("surface"),
        coordinate_system=form_evidence.get("coordinate_system"),
    )


def build_candidate_source_primitive(candidate: dict[str, Any], *, material: dict[str, Any]) -> dict[str, Any]:
    """Attach transport-only normals/material to an exact Animal geometry candidate.

    Geometry remains authoritative for positions/indices. The bridge computes only
    the vertex normals required by the existing portable UC surface contract and
    carries an explicit Animal source material. This is transport plumbing, not a
    claim that the computed normals are final authored shading normals.
    """
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    identifier = candidate.get("id")
    positions = candidate.get("positions")
    indices = candidate.get("indices")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("candidate id is required")
    if not isinstance(positions, list) or not positions:
        raise ValueError("candidate positions are required")
    checked_positions = [_vec3(row, f"{identifier}.position") for row in positions]
    if not isinstance(indices, list) or not indices or len(indices) % 3:
        raise ValueError("candidate indices must contain complete triangles")
    if any(type(index) is not int or not 0 <= index < len(checked_positions) for index in indices):
        raise ValueError("candidate contains an out-of-range triangle index")
    if not isinstance(material, dict):
        raise ValueError("explicit source material is required")
    base_color = material.get("base_color")
    _linear_rgba_to_hex(base_color)
    metallic = _finite(material.get("metallic"), "material.metallic")
    roughness = _finite(material.get("roughness"), "material.roughness")
    if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
        raise ValueError("material metallic/roughness must stay within 0..1")

    accum = [[0.0, 0.0, 0.0] for _ in checked_positions]
    for offset in range(0, len(indices), 3):
        ia, ib, ic = indices[offset:offset + 3]
        a, b, c = checked_positions[ia], checked_positions[ib], checked_positions[ic]
        ab = [b[axis] - a[axis] for axis in range(3)]
        ac = [c[axis] - a[axis] for axis in range(3)]
        face = [
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        ]
        length = math.sqrt(sum(value * value for value in face))
        if length <= 1e-12:
            raise ValueError(f"{identifier} contains a degenerate triangle")
        face = [value / length for value in face]
        for vertex in (ia, ib, ic):
            for axis in range(3):
                accum[vertex][axis] += face[axis]

    normals = []
    for vertex, normal in enumerate(accum):
        length = math.sqrt(sum(value * value for value in normal))
        if length <= 1e-12:
            raise ValueError(f"{identifier} contains unreferenced vertex {vertex}")
        normals.append([round(value / length, 9) for value in normal])

    return {
        "id": identifier,
        "positions": [[round(value, 9) for value in row] for row in checked_positions],
        "normals": normals,
        "colors": [copy.deepcopy(base_color) for _ in checked_positions],
        "indices": list(indices),
        "material": {
            "base_color": copy.deepcopy(base_color),
            "metallic": metallic,
            "roughness": roughness,
        },
    }


def adapt_geometry_candidate_for_uc(
    candidate: dict[str, Any],
    *,
    name: str,
    material: dict[str, Any],
) -> dict[str, Any]:
    """Bridge one exact Animal geometry candidate without absorbing its semantics into UC."""
    primitive = build_candidate_source_primitive(candidate, material=material)
    source_surface = {
        "schema": UC_SURFACE_SCHEMA,
        "units": "m",
        "primitives": [primitive],
    }
    return _convert_surface_to_uc(name, source_surface, coordinate_system=SOURCE_COORDINATES)


def require_candidate_identity(candidate: dict[str, Any], expected_sha256: str) -> str:
    """Fail closed if an externally owned geometry candidate drifts."""
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("expected candidate sha256 is required")
    observed = _digest(candidate)
    if observed != expected_sha256:
        raise ValueError(f"geometry candidate identity drift: expected {expected_sha256}, observed {observed}")
    return observed


def build_bridge_evidence(form_evidence: dict[str, Any], uc_surface: dict[str, Any], *, uc_commit: str,
                          glb_sha256: str, uc_specification_sha256: str, uc_verification: dict[str, Any]) -> dict[str, Any]:
    """Bind one exact animal source -> UC surface -> GLB proof without widening claims."""
    if not isinstance(uc_commit, str) or len(uc_commit) < 7:
        raise ValueError("exact UC commit identity is required")
    if not isinstance(glb_sha256, str) or len(glb_sha256) != 64:
        raise ValueError("exact GLB sha256 is required")
    if not isinstance(uc_specification_sha256, str) or len(uc_specification_sha256) != 64:
        raise ValueError("UC specification sha256 is required")
    if not isinstance(uc_verification, dict) or not uc_verification.get("passed"):
        raise ValueError("successful UC verification is required")
    return {
        "schema": BRIDGE_SCHEMA,
        "status": "PASS_EXACT_CROSS_REPO_SURFACE_TO_GLB",
        "source": {
            "schema": form_evidence.get("schema"),
            "source_digest": form_evidence.get("source_digest"),
            "surface_digest": form_evidence.get("surface_digest"),
            "coordinate_system": form_evidence.get("coordinate_system"),
            "surface_units": form_evidence.get("surface", {}).get("units"),
        },
        "bridge": {
            "source_coordinates": SOURCE_COORDINATES,
            "target_coordinates": TARGET_COORDINATES,
            "component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "handedness_change": True,
            "triangle_winding_reversed": True,
            "uc_surface_sha256": _digest(uc_surface),
            "primitive_count": len(uc_surface.get("primitives", [])),
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "commit": uc_commit,
            "specification_sha256": uc_specification_sha256,
            "verification": copy.deepcopy(uc_verification),
        },
        "glb": {"sha256": glb_sha256},
        "truth": (
            "PASS proves only that this exact animal form evidence was explicitly converted from its authored "
            "metre/+X-forward/+Y-left/+Z-up frame into UC's metre/Y-up/+Z-forward portable surface, accepted "
            "by the pinned UC generator, emitted as GLB, and re-verified. It does not prove visual quality, "
            "anatomy, rig/deformation quality, animation, topology manifoldness, engine import, gameplay, "
            "performance, materials beyond transported factors, or production readiness."
        ),
    }


def build_connected_candidate_bridge_evidence(
    *,
    source_digest: str,
    source_surface_digest: str,
    geometry_commit: str,
    candidate: dict[str, Any],
    expected_candidate_sha256: str,
    source_material_sha256: str,
    uc_surface: dict[str, Any],
    uc_commit: str,
    glb_sha256: str,
    uc_specification_sha256: str,
    uc_verification: dict[str, Any],
) -> dict[str, Any]:
    """Bind exact connected Geometry ownership to current UC GLB transport."""
    candidate_sha256 = require_candidate_identity(candidate, expected_candidate_sha256)
    for label, value in (
        ("source_digest", source_digest),
        ("source_surface_digest", source_surface_digest),
        ("source_material_sha256", source_material_sha256),
        ("glb_sha256", glb_sha256),
        ("uc_specification_sha256", uc_specification_sha256),
    ):
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{label} must be an exact sha256")
    if not isinstance(geometry_commit, str) or len(geometry_commit) < 40:
        raise ValueError("exact Geometry commit identity is required")
    if not isinstance(uc_commit, str) or len(uc_commit) < 40:
        raise ValueError("exact UC commit identity is required")
    if not isinstance(uc_verification, dict) or not uc_verification.get("passed"):
        raise ValueError("successful UC verification is required")
    return {
        "schema": CONNECTED_BRIDGE_SCHEMA,
        "status": "PASS_CONNECTED_GEOMETRY_CANDIDATE_TO_CURRENT_UC_GLB",
        "source": {
            "source_digest": source_digest,
            "source_surface_digest": source_surface_digest,
            "coordinate_system": SOURCE_COORDINATES,
            "surface_units": "m",
        },
        "geometry": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "commit": geometry_commit,
            "candidate_id": candidate.get("id"),
            "candidate_sha256": candidate_sha256,
            "vertices": len(candidate.get("positions", [])),
            "triangles": len(candidate.get("indices", [])) // 3,
        },
        "transport_adapter": {
            "source_material_sha256": source_material_sha256,
            "normal_method": "vertex-average-of-unit-face-normals-transport-only",
            "source_coordinates": SOURCE_COORDINATES,
            "target_coordinates": TARGET_COORDINATES,
            "component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "handedness_change": True,
            "triangle_winding_reversed": True,
            "uc_surface_sha256": _digest(uc_surface),
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "commit": uc_commit,
            "specification_sha256": uc_specification_sha256,
            "verification": copy.deepcopy(uc_verification),
        },
        "glb": {"sha256": glb_sha256},
        "truth": (
            "PASS proves only that the exact externally owned connected Animal Geometry candidate was rebuilt "
            "from its pinned Geometry revision, given transport-only normals plus the unchanged neutral Animal "
            "source material, converted through the explicit Animal->UC coordinate contract, accepted by the "
            "pinned current UC GLB generator, and re-verified. It does not make the candidate canonical, does "
            "not prove final authored normals/materials, deformation or skin transport, animation, engine import, "
            "visual quality, gameplay, performance, or production readiness."
        ),
    }
