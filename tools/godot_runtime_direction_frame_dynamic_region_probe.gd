extends SceneTree

const PACKET_SCHEMA := "axm.animal-direction-frame-target-host-adapter/v0.1"
const RESULT_SCHEMA := "axm.animal-runtime-direction-frame-dynamic-region/v0.1"
const PASS_STATE := "PASS_ANIMAL_GODOT_DYNAMIC_VERTEX_DIRECTION_REGION_UPDATE__SURFACE_REBUILDS_41_TO_0__HOLD_SHADED_DEVICE"
const HOLD_STATE := "HOLD_ANIMAL_GODOT_DYNAMIC_VERTEX_DIRECTION_REGION_UPDATE"
const EXPECTED_KEYS := 41
const EXPECTED_VERTICES := 84
const EXPECTED_INDICES := 240
const POSITION_TOLERANCE := 0.000001
const DIRECTION_VECTOR_TOLERANCE := 0.00025
const DIRECTION_ANGLE_TOLERANCE_DEG := 0.015
const DIRECTION_ANGLE_SELF_CHECK_DEG := 0.01
const UV_TOLERANCE := 0.000001
const WARMUP_ROUNDS := 5
const MEASURED_ROUNDS := 31
const MAX_MEDIAN_RATIO := 1.0


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
	var known_angle_rad := deg_to_rad(DIRECTION_ANGLE_SELF_CHECK_DEG)
	var near_parallel := Vector3(cos(known_angle_rad), sin(known_angle_rad), 0.0)
	var measured_angle_deg := _direction_angle_deg(Vector3.RIGHT, near_parallel)
	if abs(measured_angle_deg - DIRECTION_ANGLE_SELF_CHECK_DEG) > 0.0005:
		_fatal("runtime direction angle evidence metric lost near-parallel precision")


func _write_json(path: String, value: Dictionary) -> void:
	var handle := FileAccess.open(path, FileAccess.WRITE)
	if handle == null:
		_fatal("failed to open output receipt")
	handle.store_string(JSON.stringify(value, "  ", false) + "\n")
	handle.close()


func _new_metrics() -> Dictionary:
	return {
		"frames": 0,
		"maximum_position_vector_delta": 0.0,
		"maximum_normal_vector_delta": 0.0,
		"maximum_normal_angle_deg": 0.0,
		"maximum_tangent_vector_delta": 0.0,
		"maximum_tangent_angle_deg": 0.0,
		"maximum_uv_delta": 0.0,
		"tangent_w_mismatch_count": 0,
		"index_mismatch_count": 0,
	}


func _pack_frame(frame: Dictionary) -> Dictionary:
	var position_rows: Array = frame["positions"]
	var normal_rows: Array = frame["normals"]
	var tangent_rows: Array = frame["tangents"]
	var uv_rows: Array = frame["texcoords"]
	var index_rows: Array = frame["indices"]
	if position_rows.size() != EXPECTED_VERTICES or normal_rows.size() != EXPECTED_VERTICES or tangent_rows.size() != EXPECTED_VERTICES or uv_rows.size() != EXPECTED_VERTICES:
		_fatal("runtime probe vertex-domain count drift")
	if index_rows.size() != EXPECTED_INDICES:
		_fatal("runtime probe index count drift")

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
			_fatal("runtime probe tangent width drift")
		for component in tangent_row:
			tangents.append(float(component))
	for value in index_rows:
		indices.append(int(value))

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = tangents
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices
	return {
		"arrays": arrays,
		"vertices": vertices,
		"normals": normals,
		"tangents": tangents,
		"uvs": uvs,
		"indices": indices,
	}


func _assert_static_topology_attributes(packed_frames: Array) -> void:
	var reference: Dictionary = packed_frames[0]
	var reference_uvs: PackedVector2Array = reference["uvs"]
	var reference_indices: PackedInt32Array = reference["indices"]
	for frame_index in range(1, packed_frames.size()):
		var current: Dictionary = packed_frames[frame_index]
		var current_uvs: PackedVector2Array = current["uvs"]
		var current_indices: PackedInt32Array = current["indices"]
		for vertex_index in range(EXPECTED_VERTICES):
			if current_uvs[vertex_index] != reference_uvs[vertex_index]:
				_fatal("dynamic-region candidate requires UVs to remain byte-stable across all keys")
		for index_offset in range(EXPECTED_INDICES):
			if current_indices[index_offset] != reference_indices[index_offset]:
				_fatal("dynamic-region candidate requires index topology to remain stable across all keys")


func _add_surface(mesh: ArrayMesh, packed: Dictionary, dynamic: bool = false) -> void:
	var flags := 0
	if dynamic:
		flags = Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, packed["arrays"], [], {}, flags)
	if mesh.get_surface_count() != 1:
		_fatal("runtime probe ArrayMesh must contain exactly one surface")


func _capture_readback(mesh: ArrayMesh) -> Dictionary:
	if mesh.get_surface_count() != 1:
		_fatal("runtime probe readback requires exactly one surface")
	var observed: Array = mesh.surface_get_arrays(0)
	return {
		"vertices": observed[Mesh.ARRAY_VERTEX],
		"normals": observed[Mesh.ARRAY_NORMAL],
		"tangents": observed[Mesh.ARRAY_TANGENT],
		"uvs": observed[Mesh.ARRAY_TEX_UV],
		"indices": observed[Mesh.ARRAY_INDEX],
	}


func _accumulate_readback(observed: Dictionary, expected: Dictionary, metrics: Dictionary) -> void:
	var observed_vertices: PackedVector3Array = observed["vertices"]
	var observed_normals: PackedVector3Array = observed["normals"]
	var observed_tangents: PackedFloat32Array = observed["tangents"]
	var observed_uvs: PackedVector2Array = observed["uvs"]
	var observed_indices: PackedInt32Array = observed["indices"]
	var expected_vertices: PackedVector3Array = expected["vertices"]
	var expected_normals: PackedVector3Array = expected["normals"]
	var expected_tangents: PackedFloat32Array = expected["tangents"]
	var expected_uvs: PackedVector2Array = expected["uvs"]
	var expected_indices: PackedInt32Array = expected["indices"]
	if observed_vertices.size() != EXPECTED_VERTICES or observed_normals.size() != EXPECTED_VERTICES or observed_uvs.size() != EXPECTED_VERTICES:
		_fatal("runtime probe readback vertex-domain count drift")
	if observed_tangents.size() != EXPECTED_VERTICES * 4 or observed_indices.size() != EXPECTED_INDICES:
		_fatal("runtime probe readback tangent/index count drift")

	for vertex_index in range(EXPECTED_VERTICES):
		var expected_tangent := Vector3(
			expected_tangents[vertex_index * 4],
			expected_tangents[vertex_index * 4 + 1],
			expected_tangents[vertex_index * 4 + 2]
		)
		var observed_tangent := Vector3(
			observed_tangents[vertex_index * 4],
			observed_tangents[vertex_index * 4 + 1],
			observed_tangents[vertex_index * 4 + 2]
		)
		metrics["maximum_position_vector_delta"] = max(float(metrics["maximum_position_vector_delta"]), expected_vertices[vertex_index].distance_to(observed_vertices[vertex_index]))
		metrics["maximum_normal_vector_delta"] = max(float(metrics["maximum_normal_vector_delta"]), expected_normals[vertex_index].distance_to(observed_normals[vertex_index]))
		metrics["maximum_normal_angle_deg"] = max(float(metrics["maximum_normal_angle_deg"]), _direction_angle_deg(expected_normals[vertex_index], observed_normals[vertex_index]))
		metrics["maximum_tangent_vector_delta"] = max(float(metrics["maximum_tangent_vector_delta"]), expected_tangent.distance_to(observed_tangent))
		metrics["maximum_tangent_angle_deg"] = max(float(metrics["maximum_tangent_angle_deg"]), _direction_angle_deg(expected_tangent, observed_tangent))
		metrics["maximum_uv_delta"] = max(float(metrics["maximum_uv_delta"]), expected_uvs[vertex_index].distance_to(observed_uvs[vertex_index]))
		if expected_tangents[vertex_index * 4 + 3] != observed_tangents[vertex_index * 4 + 3]:
			metrics["tangent_w_mismatch_count"] = int(metrics["tangent_w_mismatch_count"]) + 1
	for index_offset in range(EXPECTED_INDICES):
		if expected_indices[index_offset] != observed_indices[index_offset]:
			metrics["index_mismatch_count"] = int(metrics["index_mismatch_count"]) + 1
	metrics["frames"] = int(metrics["frames"]) + 1


func _metrics_pass(metrics: Dictionary) -> bool:
	return (
		int(metrics["frames"]) == EXPECTED_KEYS
		and float(metrics["maximum_position_vector_delta"]) <= POSITION_TOLERANCE
		and float(metrics["maximum_normal_vector_delta"]) <= DIRECTION_VECTOR_TOLERANCE
		and float(metrics["maximum_normal_angle_deg"]) <= DIRECTION_ANGLE_TOLERANCE_DEG
		and float(metrics["maximum_tangent_vector_delta"]) <= DIRECTION_VECTOR_TOLERANCE
		and float(metrics["maximum_tangent_angle_deg"]) <= DIRECTION_ANGLE_TOLERANCE_DEG
		and float(metrics["maximum_uv_delta"]) <= UV_TOLERANCE
		and int(metrics["tangent_w_mismatch_count"]) == 0
		and int(metrics["index_mismatch_count"]) == 0
	)


func _octahedron_encode(value: Vector3) -> Vector2:
	var n := value
	var denominator: float = abs(n.x) + abs(n.y) + abs(n.z)
	if denominator <= 0.0:
		_fatal("cannot octahedrally encode a zero direction")
	n /= denominator
	var encoded := Vector2.ZERO
	if n.z >= 0.0:
		encoded = Vector2(n.x, n.y)
	else:
		encoded.x = (1.0 - abs(n.y)) * (1.0 if n.x >= 0.0 else -1.0)
		encoded.y = (1.0 - abs(n.x)) * (1.0 if n.y >= 0.0 else -1.0)
	encoded.x = encoded.x * 0.5 + 0.5
	encoded.y = encoded.y * 0.5 + 0.5
	return encoded


func _octahedron_tangent_encode(value: Vector3, sign_value: float) -> Vector2:
	var bias := 1.0 / 32767.0
	var encoded := _octahedron_encode(value)
	encoded.y = max(encoded.y, bias)
	encoded.y = encoded.y * 0.5 + 0.5
	encoded.y = encoded.y if sign_value >= 0.0 else 1.0 - encoded.y
	return encoded


func _quantize_u16(value: float) -> int:
	return int(clamp(value * 65535.0, 0.0, 65535.0))


func _write_u16_le(buffer: PackedByteArray, offset: int, value: int) -> void:
	buffer[offset] = value & 0xff
	buffer[offset + 1] = (value >> 8) & 0xff


func _build_dynamic_payload(mesh: ArrayMesh, packed: Dictionary) -> Dictionary:
	var format := mesh.surface_get_format(0)
	var vertex_stride := RenderingServer.mesh_surface_get_format_vertex_stride(format, EXPECTED_VERTICES)
	var direction_stride := RenderingServer.mesh_surface_get_format_normal_tangent_stride(format, EXPECTED_VERTICES)
	var position_offset := RenderingServer.mesh_surface_get_format_offset(format, EXPECTED_VERTICES, Mesh.ARRAY_VERTEX)
	var normal_offset := RenderingServer.mesh_surface_get_format_offset(format, EXPECTED_VERTICES, Mesh.ARRAY_NORMAL)
	var tangent_offset := RenderingServer.mesh_surface_get_format_offset(format, EXPECTED_VERTICES, Mesh.ARRAY_TANGENT)
	if vertex_stride <= 0 or direction_stride <= 0:
		_fatal("dynamic-region candidate requires non-zero vertex and normal/tangent strides")
	var position_bytes: PackedByteArray = packed["vertices"].to_byte_array()
	if position_bytes.size() != vertex_stride * EXPECTED_VERTICES:
		_fatal("position byte size does not match Godot vertex-buffer stride")

	var direction_base := mini(normal_offset, tangent_offset)
	var normal_relative := normal_offset - direction_base
	var tangent_relative := tangent_offset - direction_base
	if normal_relative < 0 or tangent_relative < 0 or normal_relative + 4 > direction_stride or tangent_relative + 4 > direction_stride:
		_fatal("normal/tangent offsets are not contained by Godot direction stride")
	var direction_bytes := PackedByteArray()
	direction_bytes.resize(direction_stride * EXPECTED_VERTICES)
	var normals: PackedVector3Array = packed["normals"]
	var tangents: PackedFloat32Array = packed["tangents"]
	for vertex_index in range(EXPECTED_VERTICES):
		var normal_encoded := _octahedron_encode(normals[vertex_index])
		var nx := _quantize_u16(normal_encoded.x)
		var ny := _quantize_u16(normal_encoded.y)
		var tangent_vector := Vector3(
			tangents[vertex_index * 4],
			tangents[vertex_index * 4 + 1],
			tangents[vertex_index * 4 + 2]
		)
		var tangent_encoded := _octahedron_tangent_encode(tangent_vector, tangents[vertex_index * 4 + 3])
		var tx := _quantize_u16(tangent_encoded.x)
		var ty := _quantize_u16(tangent_encoded.y)
		# Godot reserves this otherwise-equivalent tangent encoding so the byte stream
		# cannot be mistaken for a compression marker.
		if tx == 0 and ty == 65535:
			tx = 65535
		var base_offset := vertex_index * direction_stride
		_write_u16_le(direction_bytes, base_offset + normal_relative, nx)
		_write_u16_le(direction_bytes, base_offset + normal_relative + 2, ny)
		_write_u16_le(direction_bytes, base_offset + tangent_relative, tx)
		_write_u16_le(direction_bytes, base_offset + tangent_relative + 2, ty)
	return {
		"position_offset": position_offset,
		"direction_offset": direction_base,
		"position_bytes": position_bytes,
		"direction_bytes": direction_bytes,
		"vertex_stride": vertex_stride,
		"direction_stride": direction_stride,
	}


func _apply_dynamic_payload(mesh: ArrayMesh, payload: Dictionary) -> void:
	mesh.surface_update_vertex_region(0, int(payload["position_offset"]), payload["position_bytes"])
	mesh.surface_update_vertex_region(0, int(payload["direction_offset"]), payload["direction_bytes"])


func _frame_aabb(packed: Dictionary) -> AABB:
	var vertices: PackedVector3Array = packed["vertices"]
	var minimum := vertices[0]
	var maximum := vertices[0]
	for vertex_index in range(1, vertices.size()):
		minimum = minimum.min(vertices[vertex_index])
		maximum = maximum.max(vertices[vertex_index])
	return AABB(minimum, maximum - minimum)


func _motion_envelope(packed_frames: Array) -> AABB:
	var envelope := _frame_aabb(packed_frames[0])
	for frame_index in range(1, packed_frames.size()):
		envelope = envelope.merge(_frame_aabb(packed_frames[frame_index]))
	return envelope


func _aabb_volume(box: AABB) -> float:
	return box.size.x * box.size.y * box.size.z


func _median(values: Array) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	var count := ordered.size()
	if count == 0:
		return 0.0
	var upper := int(count / 2)
	if count % 2 == 1:
		return float(ordered[upper])
	return (float(ordered[upper - 1]) + float(ordered[upper])) * 0.5


func _percentile(values: Array, fraction: float) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	if ordered.is_empty():
		return 0.0
	var index := int(ceil(float(ordered.size()) * fraction)) - 1
	index = clampi(index, 0, ordered.size() - 1)
	return float(ordered[index])


func _baseline_surface_rebuild_sweep(mesh: ArrayMesh, packed_frames: Array) -> int:
	var started := Time.get_ticks_usec()
	for packed in packed_frames:
		if mesh.get_surface_count() > 0:
			mesh.clear_surfaces()
		_add_surface(mesh, packed)
	return Time.get_ticks_usec() - started


func _candidate_region_update_sweep(mesh: ArrayMesh, dynamic_payloads: Array) -> int:
	var started := Time.get_ticks_usec()
	for payload in dynamic_payloads:
		_apply_dynamic_payload(mesh, payload)
	return Time.get_ticks_usec() - started


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var payload_path := _arg_value(args, "--payload")
	var out_path := _arg_value(args, "--out")
	if payload_path.is_empty() or out_path.is_empty():
		_fatal("usage: --payload <json> --out <json>")

	_verify_direction_angle_metric()

	var payload: Variant = JSON.parse_string(FileAccess.get_file_as_string(payload_path))
	if typeof(payload) != TYPE_DICTIONARY:
		_fatal("runtime probe payload must be a JSON object")
	if payload.get("schema") != PACKET_SCHEMA:
		_fatal("runtime probe payload schema drift")
	var frames: Variant = payload.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("runtime probe requires all 41 authored keys")

	var packed_frames: Array = []
	for frame_index in range(frames.size()):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("runtime probe sample ordering drift")
		packed_frames.append(_pack_frame(frame))
	_assert_static_topology_attributes(packed_frames)

	var baseline_mesh := ArrayMesh.new()
	var baseline_metrics := _new_metrics()
	var baseline_observations: Array = []
	for packed in packed_frames:
		if baseline_mesh.get_surface_count() > 0:
			baseline_mesh.clear_surfaces()
		_add_surface(baseline_mesh, packed)
		var observed := _capture_readback(baseline_mesh)
		baseline_observations.append(observed)
		_accumulate_readback(observed, packed, baseline_metrics)
	if not _metrics_pass(baseline_metrics):
		_fatal("pass-40 stable-resource surface-rebuild baseline failed readback")

	var candidate_mesh := ArrayMesh.new()
	_add_surface(candidate_mesh, packed_frames[0], true)
	var candidate_mesh_instance_id := candidate_mesh.get_instance_id()
	var candidate_format := candidate_mesh.surface_get_format(0)
	if (candidate_format & Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE) == 0:
		_fatal("candidate surface did not retain ARRAY_FLAG_USE_DYNAMIC_UPDATE")
	var envelope := _motion_envelope(packed_frames)
	candidate_mesh.custom_aabb = envelope
	var dynamic_payloads: Array = []
	var cached_update_bytes := 0
	for packed in packed_frames:
		var dynamic_payload := _build_dynamic_payload(candidate_mesh, packed)
		cached_update_bytes += dynamic_payload["position_bytes"].size() + dynamic_payload["direction_bytes"].size()
		dynamic_payloads.append(dynamic_payload)

	var candidate_metrics := _new_metrics()
	var cross_metrics := _new_metrics()
	for frame_index in range(EXPECTED_KEYS):
		_apply_dynamic_payload(candidate_mesh, dynamic_payloads[frame_index])
		if candidate_mesh.get_instance_id() != candidate_mesh_instance_id or candidate_mesh.get_surface_count() != 1:
			_fatal("dynamic-region candidate changed mesh or surface identity")
		var observed := _capture_readback(candidate_mesh)
		_accumulate_readback(observed, packed_frames[frame_index], candidate_metrics)
		_accumulate_readback(observed, baseline_observations[frame_index], cross_metrics)
	if not _metrics_pass(candidate_metrics):
		_fatal("dynamic vertex/direction region candidate failed expected-frame readback")
	if not _metrics_pass(cross_metrics):
		_fatal("dynamic vertex/direction region candidate diverged from pass-40 baseline readback")
	if float(cross_metrics["maximum_position_vector_delta"]) != 0.0 or float(cross_metrics["maximum_normal_vector_delta"]) != 0.0 or float(cross_metrics["maximum_tangent_vector_delta"]) != 0.0 or float(cross_metrics["maximum_uv_delta"]) != 0.0 or int(cross_metrics["tangent_w_mismatch_count"]) != 0 or int(cross_metrics["index_mismatch_count"]) != 0:
		_fatal("dynamic-region candidate must be exact-array identical to the surface-rebuild readback")

	var frame_volumes: Array = []
	for packed in packed_frames:
		frame_volumes.append(_aabb_volume(_frame_aabb(packed)))
	var envelope_volume := _aabb_volume(envelope)
	var median_frame_volume := _median(frame_volumes)
	var envelope_vs_median_ratio := 0.0
	if median_frame_volume > 0.0:
		envelope_vs_median_ratio = envelope_volume / median_frame_volume

	for _warmup in range(WARMUP_ROUNDS):
		_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames)
		_candidate_region_update_sweep(candidate_mesh, dynamic_payloads)

	var baseline_samples: Array = []
	var candidate_samples: Array = []
	for round_index in range(MEASURED_ROUNDS):
		if round_index % 2 == 0:
			baseline_samples.append(_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames))
			candidate_samples.append(_candidate_region_update_sweep(candidate_mesh, dynamic_payloads))
		else:
			candidate_samples.append(_candidate_region_update_sweep(candidate_mesh, dynamic_payloads))
			baseline_samples.append(_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames))

	var baseline_median_us := _median(baseline_samples)
	var candidate_median_us := _median(candidate_samples)
	var baseline_p95_us := _percentile(baseline_samples, 0.95)
	var candidate_p95_us := _percentile(candidate_samples, 0.95)
	var median_delta_percent := 0.0
	var p95_delta_percent := 0.0
	if baseline_median_us > 0.0:
		median_delta_percent = (candidate_median_us - baseline_median_us) / baseline_median_us * 100.0
	if baseline_p95_us > 0.0:
		p95_delta_percent = (candidate_p95_us - baseline_p95_us) / baseline_p95_us * 100.0
	var meaningful_timing_win := baseline_median_us > 0.0 and candidate_median_us <= baseline_median_us * MAX_MEDIAN_RATIO

	var bytes_per_key := int(dynamic_payloads[0]["position_bytes"].size()) + int(dynamic_payloads[0]["direction_bytes"].size())
	var pass_gate := (
		_metrics_pass(baseline_metrics)
		and _metrics_pass(candidate_metrics)
		and _metrics_pass(cross_metrics)
		and candidate_mesh.get_instance_id() == candidate_mesh_instance_id
		and candidate_mesh.get_surface_count() == 1
		and (candidate_mesh.surface_get_format(0) & Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE) != 0
		and meaningful_timing_win
	)

	var version := Engine.get_version_info()
	var result := {
		"schema": RESULT_SCHEMA,
		"state": PASS_STATE if pass_gate else HOLD_STATE,
		"target_host": {
			"engine": "Godot",
			"version": version.get("string", "unknown"),
			"mode": "ArrayMesh persistent dynamic vertex/direction region receiving proof",
		},
		"scope": {
			"side": "right",
			"authored_keys": EXPECTED_KEYS,
			"vertices_per_frame": EXPECTED_VERTICES,
			"indices_per_frame": EXPECTED_INDICES,
			"topology_changes": false,
			"uv_or_index_changes": false,
		},
		"before": {
			"arraymesh_resource_constructions_to_establish_receiver": 1,
			"surface_constructions_to_establish_41_key_receiver": EXPECTED_KEYS,
			"surface_rebuilds_per_41_key_playback": EXPECTED_KEYS,
			"update_vertex_region_calls_per_41_key_playback": 0,
		},
		"after": {
			"arraymesh_resource_constructions_to_establish_receiver": 1,
			"surface_constructions_to_establish_41_key_receiver": 1,
			"surface_rebuilds_per_41_key_playback": 0,
			"surface_construction_reduction_percent": float(EXPECTED_KEYS - 1) / float(EXPECTED_KEYS) * 100.0,
			"update_vertex_region_calls_per_key": 2,
			"update_vertex_region_calls_per_41_key_playback": EXPECTED_KEYS * 2,
			"persistent_arraymesh_identity": true,
			"persistent_surface_identity": true,
			"dynamic_update_flag_retained": true,
			"position_and_direction_regions_only": true,
			"uv_and_index_regions_unchanged": true,
		},
		"buffer_layout": {
			"vertex_stride_bytes": int(dynamic_payloads[0]["vertex_stride"]),
			"normal_tangent_stride_bytes": int(dynamic_payloads[0]["direction_stride"]),
			"position_region_bytes_per_key": int(dynamic_payloads[0]["position_bytes"].size()),
			"direction_region_bytes_per_key": int(dynamic_payloads[0]["direction_bytes"].size()),
			"dynamic_region_bytes_per_key": bytes_per_key,
			"dynamic_region_bytes_per_41_key_playback": bytes_per_key * EXPECTED_KEYS,
			"cached_dynamic_payload_bytes": cached_update_bytes,
		},
		"motion_envelope": {
			"custom_aabb_used": true,
			"all_41_keys_included": true,
			"envelope_volume": envelope_volume,
			"minimum_frame_aabb_volume": frame_volumes.min(),
			"median_frame_aabb_volume": median_frame_volume,
			"maximum_frame_aabb_volume": frame_volumes.max(),
			"envelope_vs_median_frame_volume_ratio": envelope_vs_median_ratio,
			"tradeoff": "conservative full-motion AABB prevents stale-culling clips but may reduce per-frame culling tightness",
		},
		"readback": {
			"surface_rebuild_baseline": baseline_metrics,
			"dynamic_region_candidate": candidate_metrics,
			"candidate_vs_baseline": cross_metrics,
		},
		"proof_host_timing": {
			"warmup_rounds": WARMUP_ROUNDS,
			"measured_rounds": MEASURED_ROUNDS,
			"keys_per_round": EXPECTED_KEYS,
			"baseline_median_sweep_us": baseline_median_us,
			"candidate_median_sweep_us": candidate_median_us,
			"median_delta_percent": median_delta_percent,
			"baseline_p95_sweep_us": baseline_p95_us,
			"candidate_p95_sweep_us": candidate_p95_us,
			"p95_delta_percent": p95_delta_percent,
			"median_ratio_gate": MAX_MEDIAN_RATIO,
			"target_device_claimed": false,
		},
		"visual_tradeoff": {
			"receiver_array_result": "EXACT_ARRAY_IDENTITY_ALL_41_KEYS",
			"fresh_shaded_render_run": false,
			"art_review_state": "HOLD_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW",
			"note": "No receiving-array delta was observed; the persistent full-motion AABB is deliberately conservative and fresh shaded A/B remains separate.",
		},
		"truth_boundary": {
			"technical_art_packet_changed": false,
			"owner_reconstructed_positions_normals_tangents_changed": false,
			"universal_creation_modified": false,
			"persistent_arraymesh_resource_proved": true,
			"persistent_surface_buffer_update_proved": pass_gate,
			"dynamic_region_update_proved": pass_gate,
			"static_uv_index_proved": true,
			"bilateral_runtime_proved": false,
			"continuous_interpolated_playback_proved": false,
			"fresh_shaded_render_proved": false,
			"target_device_cpu_gpu_fps_vram_proved": false,
			"art_direction_acceptance_claimed": false,
			"visual_qa_acceptance_claimed": false,
			"canon_claimed": false,
			"production_ready": false,
		},
	}
	_write_json(out_path, result)
	quit(0 if pass_gate else 1)
