extends SceneTree

const PACKET_SCHEMA := "axm.animal-direction-frame-target-host-adapter/v0.1"
const PASS_STATE := "PASS_TECHNICAL_ART_GODOT_ARRAYMESH_OWNER_RECONSTRUCTED_FRAME_41_KEYS_RIGHT"
const HOLD_STATE := "HOLD_TECHNICAL_ART_GODOT_ARRAYMESH_OWNER_RECONSTRUCTED_FRAME"
const EXPECTED_KEYS := 41
const EXPECTED_VERTICES := 84
const EXPECTED_INDICES := 240
const POSITION_TOLERANCE := 0.000001
const DIRECTION_VECTOR_TOLERANCE := 0.00025
const DIRECTION_ANGLE_TOLERANCE_DEG := 0.015
const UV_TOLERANCE := 0.000001


func _fatal(message: String) -> void:
	push_error(message)
	quit(1)


func _arg_value(args: PackedStringArray, name: String) -> String:
	for index in range(args.size() - 1):
		if args[index] == name:
			return args[index + 1]
	return ""


func _as_vec3(value: Variant) -> Vector3:
	if typeof(value) != TYPE_ARRAY or value.size() != 3:
		_fatal("expected vec3 array")
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _as_vec2(value: Variant) -> Vector2:
	if typeof(value) != TYPE_ARRAY or value.size() != 2:
		_fatal("expected vec2 array")
	return Vector2(float(value[0]), float(value[1]))


func _direction_angle_deg(left: Vector3, right: Vector3) -> float:
	var left_length := left.length()
	var right_length := right.length()
	if left_length <= 0.0 or right_length <= 0.0:
		return INF
	var length_product := left_length * right_length
	var sine_value: float = clamp(left.cross(right).length() / length_product, 0.0, 1.0)
	var cosine_value: float = clamp(left.dot(right) / length_product, -1.0, 1.0)
	return rad_to_deg(atan2(sine_value, cosine_value))


func _verify_direction_angle_metric() -> void:
	# acos(dot) loses useful precision for nearly parallel float32 Vector3 values.
	# This check retains the original angular gate while proving that the evidence
	# metric can still resolve a known angle smaller than that gate.
	var known_angle_deg := 0.01
	var known_angle_rad := deg_to_rad(known_angle_deg)
	var near_parallel := Vector3(cos(known_angle_rad), sin(known_angle_rad), 0.0)
	var measured_angle_deg := _direction_angle_deg(Vector3.RIGHT, near_parallel)
	if abs(measured_angle_deg - known_angle_deg) > 0.0005:
		_fatal("direction angle evidence metric lost near-parallel precision")


func _write_json(path: String, value: Dictionary) -> void:
	var handle := FileAccess.open(path, FileAccess.WRITE)
	if handle == null:
		_fatal("failed to open output receipt")
	handle.store_string(JSON.stringify(value, "  ", false) + "\n")
	handle.close()


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var payload_path := _arg_value(args, "--payload")
	var out_path := _arg_value(args, "--out")
	if payload_path.is_empty() or out_path.is_empty():
		_fatal("usage: --payload <json> --out <json>")

	_verify_direction_angle_metric()

	var payload_text := FileAccess.get_file_as_string(payload_path)
	var payload: Variant = JSON.parse_string(payload_text)
	if typeof(payload) != TYPE_DICTIONARY:
		_fatal("target-host payload must be a JSON object")
	if payload.get("schema") != PACKET_SCHEMA:
		_fatal("target-host payload schema drift")
	var frames: Variant = payload.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("target-host payload must contain all 41 authored keys")

	var maximum_position_delta := 0.0
	var maximum_normal_vector_delta := 0.0
	var maximum_normal_angle_deg := 0.0
	var maximum_tangent_vector_delta := 0.0
	var maximum_tangent_angle_deg := 0.0
	var maximum_uv_delta := 0.0
	var tangent_w_mismatches := 0
	var index_mismatches := 0
	var surface_count := 0

	for frame_index in range(frames.size()):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("target-host sample ordering drift")
		var position_rows: Array = frame["positions"]
		var normal_rows: Array = frame["normals"]
		var tangent_rows: Array = frame["tangents"]
		var uv_rows: Array = frame["texcoords"]
		var index_rows: Array = frame["indices"]
		if position_rows.size() != EXPECTED_VERTICES or normal_rows.size() != EXPECTED_VERTICES or tangent_rows.size() != EXPECTED_VERTICES or uv_rows.size() != EXPECTED_VERTICES:
			_fatal("target-host render vertex count drift")
		if index_rows.size() != EXPECTED_INDICES:
			_fatal("target-host index count drift")

		var vertices := PackedVector3Array()
		var normals := PackedVector3Array()
		var tangents := PackedFloat32Array()
		var uvs := PackedVector2Array()
		var indices := PackedInt32Array()
		vertices.resize(EXPECTED_VERTICES)
		normals.resize(EXPECTED_VERTICES)
		uvs.resize(EXPECTED_VERTICES)
		for vertex_index in range(EXPECTED_VERTICES):
			vertices[vertex_index] = _as_vec3(position_rows[vertex_index])
			normals[vertex_index] = _as_vec3(normal_rows[vertex_index])
			uvs[vertex_index] = _as_vec2(uv_rows[vertex_index])
			var tangent_row: Array = tangent_rows[vertex_index]
			if tangent_row.size() != 4:
				_fatal("target-host tangent width drift")
			tangents.append(float(tangent_row[0]))
			tangents.append(float(tangent_row[1]))
			tangents.append(float(tangent_row[2]))
			tangents.append(float(tangent_row[3]))
		for value in index_rows:
			indices.append(int(value))

		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_TANGENT] = tangents
		arrays[Mesh.ARRAY_TEX_UV] = uvs
		arrays[Mesh.ARRAY_INDEX] = indices
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		if mesh.get_surface_count() != 1:
			_fatal("Godot ArrayMesh did not create exactly one surface")
		surface_count += 1
		var observed: Array = mesh.surface_get_arrays(0)
		var observed_vertices: PackedVector3Array = observed[Mesh.ARRAY_VERTEX]
		var observed_normals: PackedVector3Array = observed[Mesh.ARRAY_NORMAL]
		var observed_tangents: PackedFloat32Array = observed[Mesh.ARRAY_TANGENT]
		var observed_uvs: PackedVector2Array = observed[Mesh.ARRAY_TEX_UV]
		var observed_indices: PackedInt32Array = observed[Mesh.ARRAY_INDEX]
		if observed_vertices.size() != EXPECTED_VERTICES or observed_normals.size() != EXPECTED_VERTICES or observed_uvs.size() != EXPECTED_VERTICES:
			_fatal("Godot ArrayMesh readback vertex-domain count drift")
		if observed_tangents.size() != EXPECTED_VERTICES * 4 or observed_indices.size() != EXPECTED_INDICES:
			_fatal("Godot ArrayMesh readback tangent/index count drift")

		for vertex_index in range(EXPECTED_VERTICES):
			var expected_position := vertices[vertex_index]
			var expected_normal := normals[vertex_index]
			var expected_tangent := Vector3(
				tangents[vertex_index * 4],
				tangents[vertex_index * 4 + 1],
				tangents[vertex_index * 4 + 2]
			)
			var observed_tangent := Vector3(
				observed_tangents[vertex_index * 4],
				observed_tangents[vertex_index * 4 + 1],
				observed_tangents[vertex_index * 4 + 2]
			)
			maximum_position_delta = max(maximum_position_delta, expected_position.distance_to(observed_vertices[vertex_index]))
			maximum_normal_vector_delta = max(maximum_normal_vector_delta, expected_normal.distance_to(observed_normals[vertex_index]))
			maximum_normal_angle_deg = max(maximum_normal_angle_deg, _direction_angle_deg(expected_normal, observed_normals[vertex_index]))
			maximum_tangent_vector_delta = max(maximum_tangent_vector_delta, expected_tangent.distance_to(observed_tangent))
			maximum_tangent_angle_deg = max(maximum_tangent_angle_deg, _direction_angle_deg(expected_tangent, observed_tangent))
			maximum_uv_delta = max(maximum_uv_delta, uvs[vertex_index].distance_to(observed_uvs[vertex_index]))
			if tangents[vertex_index * 4 + 3] != observed_tangents[vertex_index * 4 + 3]:
				tangent_w_mismatches += 1
		for index_offset in range(EXPECTED_INDICES):
			if indices[index_offset] != observed_indices[index_offset]:
				index_mismatches += 1

	var pass_gate := (
		maximum_position_delta <= POSITION_TOLERANCE
		and maximum_normal_vector_delta <= DIRECTION_VECTOR_TOLERANCE
		and maximum_normal_angle_deg <= DIRECTION_ANGLE_TOLERANCE_DEG
		and maximum_tangent_vector_delta <= DIRECTION_VECTOR_TOLERANCE
		and maximum_tangent_angle_deg <= DIRECTION_ANGLE_TOLERANCE_DEG
		and maximum_uv_delta <= UV_TOLERANCE
		and tangent_w_mismatches == 0
		and index_mismatches == 0
		and surface_count == EXPECTED_KEYS
	)
	var version := Engine.get_version_info()
	var receipt := {
		"schema": "axm.animal-godot-arraymesh-direction-frame-target-host/v0.1",
		"state": PASS_STATE if pass_gate else HOLD_STATE,
		"target_host": {
			"engine": "Godot",
			"version": version.get("string", "unknown"),
			"reference_only": true,
			"runtime_product_acceptance": false,
		},
		"source_packet": {
			"schema": payload.get("schema"),
			"technical_art": payload.get("technical_art"),
			"owner": payload.get("owner"),
			"universal_creation": payload.get("universal_creation"),
		},
		"measurements": {
			"authored_keys": EXPECTED_KEYS,
			"arraymesh_surfaces_created": surface_count,
			"maximum_position_vector_delta": maximum_position_delta,
			"maximum_normal_vector_delta": maximum_normal_vector_delta,
			"maximum_normal_angle_deg": maximum_normal_angle_deg,
			"maximum_tangent_vector_delta": maximum_tangent_vector_delta,
			"maximum_tangent_angle_deg": maximum_tangent_angle_deg,
			"maximum_uv_delta": maximum_uv_delta,
			"tangent_w_mismatch_count": tangent_w_mismatches,
			"index_mismatch_count": index_mismatches,
		},
		"gates": {
			"position_tolerance": POSITION_TOLERANCE,
			"direction_vector_tolerance": DIRECTION_VECTOR_TOLERANCE,
			"direction_angle_tolerance_deg": DIRECTION_ANGLE_TOLERANCE_DEG,
			"direction_angle_metric": "atan2(cross_length/length_product,dot/length_product)",
			"direction_angle_metric_self_check_deg": 0.01,
			"uv_tolerance": UV_TOLERANCE,
		},
		"truth_boundary": {
			"technical_art_target_host_reference_implemented": pass_gate,
			"target_host_computes_owner_reconstruction": false,
			"owner_reconstruction_algorithm_copied_into_target_host": false,
			"runtime_product_implementation_established": false,
			"bilateral_target_host_equivalence_established": false,
			"continuous_interpolated_shaded_playback_established": false,
			"production_tangent_space_quality_accepted": false,
			"canon_claimed": false,
			"production_ready": false,
		},
	}
	_write_json(out_path, receipt)
	if not pass_gate:
		_fatal("Godot ArrayMesh target-host direction-frame gate failed")
	print(JSON.stringify(receipt))
	quit(0)
