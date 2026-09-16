extends SceneTree

const PAYLOAD_PATH := "res://generated/tangent_motion_payload.json"
const RECEIPT_PATH := "res://generated/tangent_motion_godot_receipt.json"
const POSITION_TOLERANCE := 0.000001
const UV_TOLERANCE := 0.000001
const SCALAR_TOLERANCE := 0.000001
# Godot 4.7.2 ArrayMesh readback stores normals/tangents through its packed
# direction representation. The first exact-host attempt proved that requiring
# 1e-6 component/vector identity was false precision: positions/UVs/w remained
# exact while only direction vectors showed bounded ~1e-4 reconstruction error.
# Keep that failed receipt as evidence and use an explicit, tight host-storage
# envelope rather than silently calling the packed vectors exact.
const PACKED_DIRECTION_TOLERANCE := 0.00025
const PACKED_DIRECTION_ANGLE_TOLERANCE_DEG := 0.015

var receipt := {
    "schema": "axm.animal-animation-godot-tangent-motion-readback/v0.1",
    "proof_runtime": "Godot 4.7.2",
    "proof_mode": "DETERMINISTIC_AUTHORED_SAMPLE_ATTRIBUTE_APPLICATION_NOT_REALTIME_PACING",
    "promotion_effect": "NONE",
    "host_storage_boundary": {
        "position_tolerance_m": POSITION_TOLERANCE,
        "uv_tolerance": UV_TOLERANCE,
        "scalar_and_unit_length_tolerance": SCALAR_TOLERANCE,
        "packed_direction_vector_tolerance": PACKED_DIRECTION_TOLERANCE,
        "packed_direction_angle_tolerance_deg": PACKED_DIRECTION_ANGLE_TOLERANCE_DEG,
        "claim": "BOUNDED_GODOT_ARRAYMESH_DIRECTION_RECONSTRUCTION_NOT_EXACT_DIRECTION_FLOAT_IDENTITY"
    },
    "truth_boundary": "This proof creates Godot ArrayMesh surfaces from the exact Animation-bound Rigging position/normal/UV/tangent frames and reads those attributes back within an explicit host storage envelope. It does not establish shaded deformation quality, tangent-space normal-map appearance, production skin tangent transport, continuous interpolation, real-time pacing, exported animation/skeleton transport, controller/state-machine behavior, gameplay, target-device performance, CANON, or production readiness."
}

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func load_json(path: String):
    var text := FileAccess.get_file_as_string(path)
    if text.is_empty():
        return null
    return JSON.parse_string(text)

func vec3(row) -> Vector3:
    return Vector3(float(row[0]), float(row[1]), float(row[2]))

func vec2(row) -> Vector2:
    return Vector2(float(row[0]), float(row[1]))

func angular_error_deg(expected: Vector3, observed: Vector3) -> float:
    if expected.length_squared() == 0.0 or observed.length_squared() == 0.0:
        return 180.0
    var cosine := clampf(expected.normalized().dot(observed.normalized()), -1.0, 1.0)
    return rad_to_deg(acos(cosine))

func build_mesh(side_payload: Dictionary, frame: Dictionary) -> ArrayMesh:
    var vertices := PackedVector3Array()
    var normals := PackedVector3Array()
    var uvs := PackedVector2Array()
    var tangents := PackedFloat32Array()
    var indices := PackedInt32Array()
    for row in frame.get("positions", []):
        vertices.append(vec3(row))
    for row in frame.get("normals", []):
        normals.append(vec3(row))
    for row in frame.get("uvs", []):
        uvs.append(vec2(row))
    for row in frame.get("tangents", []):
        tangents.append(float(row[0]))
        tangents.append(float(row[1]))
        tangents.append(float(row[2]))
        tangents.append(float(row[3]))
    for value in side_payload.get("render_indices", []):
        indices.append(int(value))
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_TANGENT] = tangents
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    return mesh

func attribute_errors(mesh: ArrayMesh, side_payload: Dictionary, frame: Dictionary) -> Dictionary:
    if mesh.get_surface_count() != 1:
        return {"state": "FAIL", "reason": "surface-count"}
    var arrays := mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
    var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
    var tangents: PackedFloat32Array = arrays[Mesh.ARRAY_TANGENT]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    var expected_positions = frame.get("positions", [])
    var expected_normals = frame.get("normals", [])
    var expected_uvs = frame.get("uvs", [])
    var expected_tangents = frame.get("tangents", [])
    var expected_indices = side_payload.get("render_indices", [])
    if vertices.size() != expected_positions.size() or normals.size() != expected_normals.size() or uvs.size() != expected_uvs.size() or tangents.size() != expected_tangents.size() * 4 or indices.size() != expected_indices.size():
        return {"state": "FAIL", "reason": "attribute-count"}
    var max_position := 0.0
    var max_normal := 0.0
    var max_normal_angle_deg := 0.0
    var max_uv := 0.0
    var max_tangent_xyz := 0.0
    var max_tangent_angle_deg := 0.0
    var max_tangent_w := 0.0
    var max_tangent_normal_dot := 0.0
    var max_normal_unit_error := 0.0
    var max_tangent_unit_error := 0.0
    for index in range(vertices.size()):
        var expected_position := vec3(expected_positions[index])
        var expected_normal := vec3(expected_normals[index])
        var expected_uv := vec2(expected_uvs[index])
        var expected_tangent := vec3(expected_tangents[index])
        var observed_tangent := Vector3(tangents[index * 4], tangents[index * 4 + 1], tangents[index * 4 + 2])
        max_position = maxf(max_position, vertices[index].distance_to(expected_position))
        max_normal = maxf(max_normal, normals[index].distance_to(expected_normal))
        max_normal_angle_deg = maxf(max_normal_angle_deg, angular_error_deg(expected_normal, normals[index]))
        max_uv = maxf(max_uv, uvs[index].distance_to(expected_uv))
        max_tangent_xyz = maxf(max_tangent_xyz, observed_tangent.distance_to(expected_tangent))
        max_tangent_angle_deg = maxf(max_tangent_angle_deg, angular_error_deg(expected_tangent, observed_tangent))
        max_tangent_w = maxf(max_tangent_w, absf(tangents[index * 4 + 3] - float(expected_tangents[index][3])))
        max_tangent_normal_dot = maxf(max_tangent_normal_dot, absf(normals[index].dot(observed_tangent)))
        max_normal_unit_error = maxf(max_normal_unit_error, absf(normals[index].length() - 1.0))
        max_tangent_unit_error = maxf(max_tangent_unit_error, absf(observed_tangent.length() - 1.0))
    var index_mismatches := 0
    for index in range(indices.size()):
        if int(indices[index]) != int(expected_indices[index]):
            index_mismatches += 1
    return {
        "state": "PASS",
        "maximum_position_readback_error_m": max_position,
        "maximum_normal_readback_error": max_normal,
        "maximum_normal_angular_error_deg": max_normal_angle_deg,
        "maximum_uv_readback_error": max_uv,
        "maximum_tangent_xyz_readback_error": max_tangent_xyz,
        "maximum_tangent_angular_error_deg": max_tangent_angle_deg,
        "maximum_tangent_w_readback_error": max_tangent_w,
        "maximum_tangent_normal_dot_abs": max_tangent_normal_dot,
        "maximum_normal_unit_length_error": max_normal_unit_error,
        "maximum_tangent_unit_length_error": max_tangent_unit_error,
        "index_mismatch_count": index_mismatches
    }

func _initialize() -> void:
    if not FileAccess.file_exists(PAYLOAD_PATH):
        fail("tangent motion payload missing")
        return
    var payload = load_json(PAYLOAD_PATH)
    if payload == null or not (payload is Dictionary):
        fail("tangent motion payload is not valid JSON")
        return
    if str(payload.get("schema", "")) != "axm.animal-animation-godot-tangent-motion-payload/v0.1":
        fail("unexpected tangent motion payload schema")
        return
    if str(payload.get("gate", "")) != "PASS_BILATERAL_DEFORMED_TANGENT_GODOT_PAYLOAD_BUILD":
        fail("payload gate is not PASS")
        return
    var playback: Dictionary = payload.get("playback", {})
    if int(playback.get("endpoint_inclusive_sample_count", 0)) != 41:
        fail("authored sample count drift")
        return

    receipt["payload_sha256"] = FileAccess.get_sha256(PAYLOAD_PATH)
    receipt["source_identity"] = payload.get("source_identity", {})
    receipt["coordinate_bridge"] = payload.get("coordinate_bridge", {})
    receipt["source_gate"] = payload.get("source_gate", "")

    var maximum_position := 0.0
    var maximum_normal := 0.0
    var maximum_normal_angle_deg := 0.0
    var maximum_uv := 0.0
    var maximum_tangent_xyz := 0.0
    var maximum_tangent_angle_deg := 0.0
    var maximum_tangent_w := 0.0
    var maximum_tangent_normal_dot := 0.0
    var maximum_normal_unit_error := 0.0
    var maximum_tangent_unit_error := 0.0
    var index_mismatches := 0
    var applications := 0
    var side_summaries := {}

    for side in ["left", "right"]:
        var side_payload: Dictionary = payload.get(side, {})
        var frames = side_payload.get("frames", [])
        if frames.size() != 41:
            fail(side + " frame count drift")
            return
        var side_max_position := 0.0
        var side_max_normal := 0.0
        var side_max_normal_angle_deg := 0.0
        var side_max_uv := 0.0
        var side_max_tangent := 0.0
        var side_max_tangent_angle_deg := 0.0
        for sample_index in range(41):
            var frame: Dictionary = frames[sample_index]
            if int(frame.get("sample_index", -1)) != sample_index:
                fail(side + " sample ordering drift")
                return
            var mesh := build_mesh(side_payload, frame)
            var observed := attribute_errors(mesh, side_payload, frame)
            if observed.get("state") != "PASS":
                fail(side + " attribute readback failed at sample " + str(sample_index))
                return
            side_max_position = maxf(side_max_position, float(observed["maximum_position_readback_error_m"]))
            side_max_normal = maxf(side_max_normal, float(observed["maximum_normal_readback_error"]))
            side_max_normal_angle_deg = maxf(side_max_normal_angle_deg, float(observed["maximum_normal_angular_error_deg"]))
            side_max_uv = maxf(side_max_uv, float(observed["maximum_uv_readback_error"]))
            side_max_tangent = maxf(side_max_tangent, float(observed["maximum_tangent_xyz_readback_error"]))
            side_max_tangent_angle_deg = maxf(side_max_tangent_angle_deg, float(observed["maximum_tangent_angular_error_deg"]))
            maximum_position = maxf(maximum_position, float(observed["maximum_position_readback_error_m"]))
            maximum_normal = maxf(maximum_normal, float(observed["maximum_normal_readback_error"]))
            maximum_normal_angle_deg = maxf(maximum_normal_angle_deg, float(observed["maximum_normal_angular_error_deg"]))
            maximum_uv = maxf(maximum_uv, float(observed["maximum_uv_readback_error"]))
            maximum_tangent_xyz = maxf(maximum_tangent_xyz, float(observed["maximum_tangent_xyz_readback_error"]))
            maximum_tangent_angle_deg = maxf(maximum_tangent_angle_deg, float(observed["maximum_tangent_angular_error_deg"]))
            maximum_tangent_w = maxf(maximum_tangent_w, float(observed["maximum_tangent_w_readback_error"]))
            maximum_tangent_normal_dot = maxf(maximum_tangent_normal_dot, float(observed["maximum_tangent_normal_dot_abs"]))
            maximum_normal_unit_error = maxf(maximum_normal_unit_error, float(observed["maximum_normal_unit_length_error"]))
            maximum_tangent_unit_error = maxf(maximum_tangent_unit_error, float(observed["maximum_tangent_unit_length_error"]))
            index_mismatches += int(observed["index_mismatch_count"])
            applications += 1
        side_summaries[side] = {
            "sample_applications": 41,
            "maximum_position_readback_error_m": side_max_position,
            "maximum_normal_readback_error": side_max_normal,
            "maximum_normal_angular_error_deg": side_max_normal_angle_deg,
            "maximum_uv_readback_error": side_max_uv,
            "maximum_tangent_xyz_readback_error": side_max_tangent,
            "maximum_tangent_angular_error_deg": side_max_tangent_angle_deg
        }

    var boundary := {
        "applications": applications,
        "maximum_position_readback_error_m": maximum_position,
        "maximum_normal_readback_error": maximum_normal,
        "maximum_normal_angular_error_deg": maximum_normal_angle_deg,
        "maximum_uv_readback_error": maximum_uv,
        "maximum_tangent_xyz_readback_error": maximum_tangent_xyz,
        "maximum_tangent_angular_error_deg": maximum_tangent_angle_deg,
        "maximum_tangent_w_readback_error": maximum_tangent_w,
        "maximum_tangent_normal_dot_abs": maximum_tangent_normal_dot,
        "maximum_normal_unit_length_error": maximum_normal_unit_error,
        "maximum_tangent_unit_length_error": maximum_tangent_unit_error,
        "index_mismatch_count": index_mismatches,
        "sides": side_summaries
    }
    receipt["attribute_readback"] = boundary

    if maximum_position > POSITION_TOLERANCE or maximum_normal > PACKED_DIRECTION_TOLERANCE or maximum_normal_angle_deg > PACKED_DIRECTION_ANGLE_TOLERANCE_DEG or maximum_uv > UV_TOLERANCE or maximum_tangent_xyz > PACKED_DIRECTION_TOLERANCE or maximum_tangent_angle_deg > PACKED_DIRECTION_ANGLE_TOLERANCE_DEG or maximum_tangent_w > SCALAR_TOLERANCE or maximum_tangent_normal_dot > PACKED_DIRECTION_TOLERANCE or maximum_normal_unit_error > SCALAR_TOLERANCE or maximum_tangent_unit_error > SCALAR_TOLERANCE or index_mismatches != 0:
        fail("Godot attribute readback exceeded explicit host storage envelope")
        return

    receipt["state"] = "PASS_GODOT_BILATERAL_DEFORMED_TANGENT_MOTION_ATTRIBUTE_READBACK"
    boundary["real_time_frame_pacing_claimed"] = false
    boundary["interpolation_claimed"] = false
    boundary["shaded_visual_quality_claimed"] = false
    boundary["exact_direction_float_identity_claimed"] = false
    write_receipt()
    quit(0)
