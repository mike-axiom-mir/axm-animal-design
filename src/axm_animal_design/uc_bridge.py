"""Explicit technical-art bridge from animal-design surface evidence into UC.

The animal form study authors in metres using +X forward, +Y left, +Z up.
Universal Creation's portable surface/GLB path is metres, Y-up, +Z forward.
This adapter performs the coordinate/handedness conversion explicitly, reverses
triangle winding after the reflection, converts the neutral material contract,
and records exact digests. It does not make animal-specific semantics part of UC.
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


def adapt_form_evidence_for_uc(form_evidence: dict[str, Any]) -> dict[str, Any]:
    """Return a strict UC-compatible surface without modifying source evidence."""
    if not isinstance(form_evidence, dict) or form_evidence.get("schema") != ANIMAL_EVIDENCE_SCHEMA:
        raise ValueError(f"form evidence must use {ANIMAL_EVIDENCE_SCHEMA}")
    if form_evidence.get("coordinate_system") != SOURCE_COORDINATES:
        raise ValueError("unsupported animal coordinate system; refusing implicit axis conversion")
    name = form_evidence.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("form evidence name is required")
    surface = form_evidence.get("surface")
    if not isinstance(surface, dict) or surface.get("schema") != UC_SURFACE_SCHEMA:
        raise ValueError(f"surface must declare {UC_SURFACE_SCHEMA}")
    if surface.get("units") != "m":
        raise ValueError("bridge requires animal surface units='m'")
    primitives = surface.get("primitives")
    if not isinstance(primitives, list) or not primitives:
        raise ValueError("surface primitives are required")

    output_primitives = []
    seen = set()
    for primitive_index, primitive in enumerate(primitives):
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
