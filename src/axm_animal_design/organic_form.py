"""Deterministic organic form-study geometry for animal/creature design.

Turns an explicit landmark + region study into renderer-neutral
``axm.surface-3d/v0.1`` geometry plus a bounded measurement receipt.

PASS means the generated geometry matches the authored design intent inside
stated tolerances. It does not establish biological anatomy, rigging,
deformation quality, runtime readiness, topology acceptance, or aesthetics.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

FORM_SCHEMA = "axm.animal-organic-form-study/v0.1"
EVIDENCE_SCHEMA = "axm.animal-organic-form-evidence/v0.1"
SURFACE_SCHEMA = "axm.surface-3d/v0.1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _num(value: Any, label: str, low: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if low is not None and value < low:
        raise ValueError(f"{label} must be >= {low}")
    return value


def _vec3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    return tuple(_num(v, f"{label}[{i}]") for i, v in enumerate(value))


def _vadd(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _vsub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _vmul(a, s):
    return tuple(a[i] * s for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a, label="vector"):
    length = _length(a)
    if length <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return _vmul(a, 1 / length)


def _material():
    return {"base_color": [0.72, 0.72, 0.70, 1.0], "metallic": 0.0, "roughness": 0.78}


def _primitive(identifier, positions, indices):
    accum = [[0.0, 0.0, 0.0] for _ in positions]
    for offset in range(0, len(indices), 3):
        ia, ib, ic = indices[offset:offset + 3]
        a, b, c = positions[ia], positions[ib], positions[ic]
        normal = _cross(_vsub(b, a), _vsub(c, a))
        size = _length(normal)
        if size <= 1e-12:
            raise ValueError(f"{identifier} produced a degenerate triangle")
        normal = _vmul(normal, 1 / size)
        for index in (ia, ib, ic):
            for axis in range(3):
                accum[index][axis] += normal[axis]
    normals = []
    for normal in accum:
        size = math.sqrt(sum(value * value for value in normal))
        if size <= 1e-12:
            raise ValueError(f"{identifier} contains an unreferenced vertex")
        normals.append([round(value / size, 9) for value in normal])
    return {
        "id": identifier,
        "positions": [[round(value, 9) for value in point] for point in positions],
        "normals": normals,
        "colors": [[0.72, 0.72, 0.70, 1.0] for _ in positions],
        "indices": indices,
        "material": _material(),
    }


def _basis(axis):
    forward = _unit(axis, "segment axis")
    helper = (0.0, 0.0, 1.0) if abs(forward[2]) < 0.9 else (0.0, 1.0, 0.0)
    side = _unit(_cross(forward, helper))
    up = _unit(_cross(forward, side))
    return forward, side, up


def _ellipsoid(identifier, center, radii, rings=5, segments=10):
    cx, cy, cz = center
    rx, ry, rz = radii
    if min(radii) <= 0:
        raise ValueError(f"{identifier} radii must be > 0")
    positions = [(cx, cy, cz + rz)]
    for ring in range(1, rings):
        phi = math.pi * ring / rings
        sin_phi, cos_phi = math.sin(phi), math.cos(phi)
        for segment in range(segments):
            theta = 2 * math.pi * segment / segments
            positions.append((
                cx + rx * sin_phi * math.cos(theta),
                cy + ry * sin_phi * math.sin(theta),
                cz + rz * cos_phi,
            ))
    south = len(positions)
    positions.append((cx, cy, cz - rz))
    indices = []
    for segment in range(segments):
        indices += [0, 1 + segment, 1 + (segment + 1) % segments]
    for ring in range(rings - 2):
        start = 1 + ring * segments
        nxt = start + segments
        for segment in range(segments):
            a = start + segment
            b = start + (segment + 1) % segments
            c = nxt + segment
            d = nxt + (segment + 1) % segments
            indices += [a, c, b, b, c, d]
    last = 1 + (rings - 2) * segments
    for segment in range(segments):
        indices += [last + segment, south, last + (segment + 1) % segments]
    return _primitive(identifier, positions, indices)


def _segment(identifier, a, b, radius_a, radius_b, segments=10):
    if radius_a <= 0 or radius_b <= 0:
        raise ValueError(f"{identifier} radii must be > 0")
    axis = _vsub(b, a)
    length = _length(axis)
    if length <= 1e-8:
        raise ValueError(f"{identifier} segment endpoints coincide")
    forward, side, up = _basis(axis)
    pole_a = _vsub(a, _vmul(forward, min(radius_a, length * 0.18)))
    pole_b = _vadd(b, _vmul(forward, min(radius_b, length * 0.18)))
    positions = [pole_a]
    rings = [(0.05, radius_a * 0.72), (0.28, radius_a), (0.72, radius_b), (0.95, radius_b * 0.72)]
    for t, radius in rings:
        center = _vadd(a, _vmul(axis, t))
        for segment in range(segments):
            theta = 2 * math.pi * segment / segments
            radial = _vadd(_vmul(side, math.cos(theta) * radius), _vmul(up, math.sin(theta) * radius))
            positions.append(_vadd(center, radial))
    end = len(positions)
    positions.append(pole_b)
    indices = []
    for segment in range(segments):
        indices += [0, 1 + segment, 1 + (segment + 1) % segments]
    for ring in range(len(rings) - 1):
        start = 1 + ring * segments
        nxt = start + segments
        for segment in range(segments):
            a0 = start + segment
            a1 = start + (segment + 1) % segments
            b0 = nxt + segment
            b1 = nxt + (segment + 1) % segments
            indices += [a0, b0, a1, a1, b0, b1]
    start = 1 + (len(rings) - 1) * segments
    for segment in range(segments):
        indices += [start + segment, end, start + (segment + 1) % segments]
    return _primitive(identifier, positions, indices)


def _validate_spec(spec):
    if not isinstance(spec, dict) or spec.get("schema") != FORM_SCHEMA:
        raise ValueError(f"spec must use {FORM_SCHEMA}")
    if spec.get("units") != "m":
        raise ValueError("v0.1 requires units='m'")
    if not isinstance(spec.get("name"), str) or not spec["name"]:
        raise ValueError("name required")
    landmarks = spec.get("landmarks")
    if not isinstance(landmarks, dict) or len(landmarks) < 4:
        raise ValueError("landmarks must contain at least four named points")
    checked_landmarks = {}
    for name, value in landmarks.items():
        if not isinstance(name, str) or not name:
            raise ValueError("landmark names must be non-empty text")
        checked_landmarks[name] = _vec3(value, f"landmark {name}")
    regions = spec.get("regions")
    if not isinstance(regions, list) or not regions or len(regions) > 128:
        raise ValueError("regions must contain 1..128 entries")
    ids = set()
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("region must be an object")
        identifier = region.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("region ids must be unique non-empty text")
        ids.add(identifier)
        kind = region.get("kind")
        if kind == "ellipsoid":
            center = region.get("center")
            if isinstance(center, str):
                if center not in checked_landmarks:
                    raise ValueError(f"{identifier} unknown center landmark")
            else:
                _vec3(center, f"{identifier}.center")
            radii = _vec3(region.get("radii"), f"{identifier}.radii")
            if min(radii) <= 0:
                raise ValueError(f"{identifier}.radii must be > 0")
        elif kind == "segment":
            if region.get("a") not in checked_landmarks or region.get("b") not in checked_landmarks:
                raise ValueError(f"{identifier} references unknown segment landmark")
            _num(region.get("radius_a"), f"{identifier}.radius_a", 1e-6)
            _num(region.get("radius_b"), f"{identifier}.radius_b", 1e-6)
        else:
            raise ValueError(f"{identifier} kind must be ellipsoid or segment")
    return checked_landmarks


def _polyline_length(path, landmarks):
    if not isinstance(path, list) or len(path) < 2 or any(point not in landmarks for point in path):
        raise ValueError("polyline path must reference at least two known landmarks")
    return sum(math.dist(landmarks[a], landmarks[b]) for a, b in zip(path, path[1:]))


def inspect_intent(spec):
    """Measure authored proportions/symmetry without claiming biological correctness."""
    landmarks = _validate_spec(spec)
    checks = []
    all_pass = True
    for check in spec.get("proportion_checks", []):
        identifier = check.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("proportion check id required")
        kind = check.get("kind")
        if kind == "distance":
            a, b = check.get("a"), check.get("b")
            if a not in landmarks or b not in landmarks:
                raise ValueError(f"{identifier} references unknown landmarks")
            measured = math.dist(landmarks[a], landmarks[b])
        elif kind == "polyline":
            measured = _polyline_length(check.get("path"), landmarks)
        else:
            raise ValueError(f"{identifier} unknown check kind")
        expected = _num(check.get("expected"), f"{identifier}.expected", 0)
        tolerance = _num(check.get("tolerance"), f"{identifier}.tolerance", 0)
        residual = abs(measured - expected)
        passed = residual <= tolerance + 1e-12
        all_pass &= passed
        checks.append({
            "id": identifier,
            "kind": kind,
            "measured": round(measured, 9),
            "expected": expected,
            "tolerance": tolerance,
            "residual": round(residual, 9),
            "status": "PASS" if passed else "FAIL",
        })
    symmetry = []
    for pair in spec.get("bilateral_pairs", []):
        identifier = pair.get("id")
        left, right = pair.get("left"), pair.get("right")
        if left not in landmarks or right not in landmarks:
            raise ValueError(f"{identifier} references unknown landmarks")
        if pair.get("axis", "y") != "y":
            raise ValueError("v0.1 bilateral mirror axis is y")
        tolerance = _num(pair.get("tolerance", 0.001), f"{identifier}.tolerance", 0)
        mirrored = (landmarks[left][0], -landmarks[left][1], landmarks[left][2])
        residual = math.dist(mirrored, landmarks[right])
        passed = residual <= tolerance + 1e-12
        all_pass &= passed
        symmetry.append({
            "id": identifier,
            "left": left,
            "right": right,
            "residual": round(residual, 9),
            "tolerance": tolerance,
            "status": "PASS" if passed else "FAIL",
        })
    bend_zones = []
    for zone in spec.get("bend_zones", []):
        identifier, landmark = zone.get("id"), zone.get("landmark")
        if landmark not in landmarks:
            raise ValueError(f"{identifier} unknown bend-zone landmark")
        radius = _num(zone.get("reserve_radius"), f"{identifier}.reserve_radius", 1e-6)
        bend_zones.append({
            "id": identifier,
            "landmark": landmark,
            "position": list(landmarks[landmark]),
            "reserve_radius": radius,
            "status": "DECLARED_NOT_DEFORMATION_TESTED",
        })
    return {
        "proportion_checks": checks,
        "bilateral_pairs": symmetry,
        "bend_zones": bend_zones,
        "declared_intent_status": "PASS" if all_pass else "FAIL",
    }


def build_form_study(spec):
    """Generate neutral-material geometry and an exact bounded intent receipt."""
    landmarks = _validate_spec(spec)
    primitives = []
    for region in spec["regions"]:
        identifier = region["id"]
        if region["kind"] == "ellipsoid":
            center = landmarks[region["center"]] if isinstance(region["center"], str) else _vec3(region["center"], f"{identifier}.center")
            primitives.append(_ellipsoid(identifier, center, _vec3(region["radii"], f"{identifier}.radii")))
        else:
            primitives.append(_segment(
                identifier,
                landmarks[region["a"]],
                landmarks[region["b"]],
                float(region["radius_a"]),
                float(region["radius_b"]),
            ))
    surface = {"schema": SURFACE_SCHEMA, "units": "m", "primitives": primitives}
    intent = inspect_intent(spec)
    return {
        "schema": EVIDENCE_SCHEMA,
        "source_schema": FORM_SCHEMA,
        "source_digest": _digest(spec),
        "name": spec["name"],
        "coordinate_system": "+X forward, +Y left, +Z up",
        "surface": surface,
        "surface_digest": _digest(surface),
        "counts": {
            "landmarks": len(landmarks),
            "regions": len(primitives),
            "vertices": sum(len(p["positions"]) for p in primitives),
            "triangles": sum(len(p["indices"]) // 3 for p in primitives),
        },
        "intent": intent,
        "gates": {"declared-proportion-and-symmetry-intent": intent["declared_intent_status"]},
        "truth": (
            "Deterministic neutral-material organic form study from explicit authored landmarks, masses, "
            "proportion checks and bend-zone reserves. PASS means the geometry matches that declared design "
            "intent. It does not establish biological anatomy, deformation quality, rigging, animation, "
            "runtime/game readiness, topology acceptance, material quality or aesthetic approval."
        ),
    }


def project_wire_svg(evidence, view="side", width=900, height=600):
    """Orthographic wire projection of the actual generated triangle geometry."""
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError("evidence schema mismatch")
    if view not in ("side", "front", "top"):
        raise ValueError("view must be side/front/top")
    points = []
    edges = set()
    for primitive in evidence["surface"]["primitives"]:
        base = len(points)
        points.extend(primitive["positions"])
        for offset in range(0, len(primitive["indices"]), 3):
            tri = primitive["indices"][offset:offset + 3]
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                a, b = base + a, base + b
                edges.add((min(a, b), max(a, b)))

    def project(point):
        x, y, z = point
        if view == "side":
            return x, z
        if view == "front":
            return y, z
        return x, y

    projected = [project(point) for point in points]
    xs, ys = [p[0] for p in projected], [p[1] for p in projected]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_x, span_y = max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)
    margin = 30
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)

    def canvas(point):
        return (
            margin + (point[0] - min_x) * scale,
            height - (margin + (point[1] - min_y) * scale),
        )

    lines = []
    for a, b in sorted(edges):
        x1, y1 = canvas(projected[a])
        x2, y2 = canvas(projected[b])
        lines.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<g stroke="black" stroke-width="0.65" fill="none" opacity="0.65">{"".join(lines)}</g>'
        f'<text x="20" y="25" font-family="sans-serif" font-size="16">{evidence["name"]} — {view} wire projection</text>'
        '</svg>'
    )
