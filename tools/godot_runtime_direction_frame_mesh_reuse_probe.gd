extends SceneTree

const PACKET_SCHEMA := "axm.animal-direction-frame-target-host-adapter/v0.1"
const RESULT_SCHEMA := "axm.animal-runtime-direction-frame-mesh-reuse/v0.1"
const PASS_STATE := "PASS_ANIMAL_GODOT_ARRAYMESH_RESOURCE_REUSE_41_TO_1__HOLD_DYNAMIC_REGION_SHADED_DEVICE"
const HOLD_STATE := "HOLD_ANIMAL_GODOT_ARRAYMESH_RESOURCE_REUSE"
const EXPECTED_KEYS := 41
const EXPECTED_VERTICES := 84
const EXPECTED_INDICES := 240
const POSITION_TOLERANCE := 0.000001
const DIRECTION_VECTOR_TOLERANCE := 0.00025
const DIRECTION_ANGLE_TOLERANCE_DEG := 0.015
const UV_TOLERANCE := 0.000001
const WARMUP_ROUNDS := 5
const MEASURED_ROUNDS := 31
const MAX_MEDIAN_REGRESSION_RATIO := 1.50


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
	if left.length_squared() <= 0.0 or right.length_squared() <= 0.0:
		return INF
	var dot_value: float = clamp(left.normalized().dot(right.normalized()), -1.0, 1.0)
	return rad_to_deg(acos(dot_value))


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
		_fatal("runtime probe render vertex count drift")
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


func _add_surface(mesh: ArrayMesh, packed: Dictionary) -> void:
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, packed["arrays"])
	if mesh.get_surface_count() != 1:
		_fatal("runtime probe ArrayMesh must contain exactly one surface")


func _validate_readback(mesh: ArrayMesh, packed: Dictionary, metrics: Dictionary) -> void:
	if mesh.get_surface_count() != 1:
		_fatal("runtime probe readback requires exactly one surface")
	var observed: Array = mesh.surface_get_arrays(0)
	var observed_vertices: PackedVector3Array = observed[Mesh.ARRAY_VERTEX]
	var observed_normals: PackedVector3Array = observed[Mesh.ARRAY_NORMAL]
	var observed_tangents: PackedFloat32Array = observed[Mesh.ARRAY_TANGENT]
	var observed_uvs: PackedVector2Array = observed[Mesh.ARRAY_TEX_UV]
	var observed_indices: PackedInt32Array = observed[Mesh.ARRAY_INDEX]
	var expected_vertices: PackedVector3Array = packed["vertices"]
	var expected_normals: PackedVector3Array = packed["normals"]
	var expected_tangents: PackedFloat32Array = packed["tangents"]
	var expected_uvs: PackedVector2Array = packed["uvs"]
	var expected_indices: PackedInt32Array = packed["indices"]
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
		metrics["maximum_position_vector_delta"] = max(
			float(metrics["maximum_position_vector_delta"]),
			expected_vertices[vertex_index].distance_to(observed_vertices[vertex_index])
		)
		metrics["maximum_normal_vector_delta"] = max(
			float(metrics["maximum_normal_vector_delta"]),
			expected_normals[vertex_index].distance_to(observed_normals[vertex_index])
		)
		metrics["maximum_normal_angle_deg"] = max(
			float(metrics["maximum_normal_angle_deg"]),
			_direction_angle_deg(expected_normals[vertex_index], observed_normals[vertex_index])
		)
		metrics["maximum_tangent_vector_delta"] = max(
			float(metrics["maximum_tangent_vector_delta"]),
			expected_tangent.distance_to(observed_tangent)
		)
		metrics["maximum_tangent_angle_deg"] = max(
			float(metrics["maximum_tangent_angle_deg"]),
			_direction_angle_deg(expected_tangent, observed_tangent)
		)
		metrics["maximum_uv_delta"] = max(
			float(metrics["maximum_uv_delta"]),
			expected_uvs[vertex_index].distance_to(observed_uvs[vertex_index])
		)
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


func _baseline_sweep(packed_frames: Array) -> int:
	var started := Time.get_ticks_usec()
	for packed in packed_frames:
		var mesh := ArrayMesh.new()
		_add_surface(mesh, packed)
	return Time.get_ticks_usec() - started


func _candidate_sweep(mesh: ArrayMesh, packed_frames: Array) -> int:
	var started := Time.get_ticks_usec()
	for packed in packed_frames:
		if mesh.get_surface_count() > 0:
			mesh.clear_surfaces()
		_add_surface(mesh, packed)
	return Time.get_ticks_usec() - started


func _median(values: Array) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	var count := ordered.size()
	if count == 0:
		return 0.0
	if count % 2 == 1:
		return float(ordered[count / 2])
	return (float(ordered[count / 2 - 1]) + float(ordered[count / 2])) * 0.5


func _percentile(values: Array, fraction: float) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	if ordered.is_empty():
		return 0.0
	var index := int(ceil(float(ordered.size()) * fraction)) - 1
	index = clamp(index, 0, ordered.size() - 1)
	return float(ordered[index])


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var payload_path := _arg_value(args, "--payload")
	var out_path := _arg_value(args, "--out")
	if payload_path.is_empty() or out_path.is_empty():
		_fatal("usage: --payload <json> --out <json>")

	var payload: Variant = JSON.parse_string(FileAccess.get_file_as_string(payload_path))
	if typeof(payload) != TYPE_DICTIONARY:
		_fatal("runtime probe payload must be a JSON object")
	if payload.get("schema") != PACKET_SCHEMA:
		_fatal("runtime probe payload schema drift")
	var frames: Variant = payload.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("runtime probe requires all 41 authored keys")

	# Conversion from retained JSON into Godot Packed arrays is intentionally
	# outside the timed region: a product receiver would not reparsed JSON every
	# frame, and this pass isolates ArrayMesh resource lifecycle only.
	var packed_frames: Array = []
	for frame_index in range(frames.size()):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("runtime probe sample ordering drift")
		packed_frames.append(_pack_frame(frame))

	var baseline_metrics := _new_metrics()
	for packed in packed_frames:
		var baseline_mesh := ArrayMesh.new()
		_add_surface(baseline_mesh, packed)
		_validate_readback(baseline_mesh, packed, baseline_metrics)

	var candidate_metrics := _new_metrics()
	var candidate_mesh := ArrayMesh.new()
	var candidate_mesh_instance_id := candidate_mesh.get_instance_id()
	for packed in packed_frames:
		if candidate_mesh.get_surface_count() > 0:
			candidate_mesh.clear_surfaces()
		_add_surface(candidate_mesh, packed)
		if candidate_mesh.get_instance_id() != candidate_mesh_instance_id:
			_fatal("candidate ArrayMesh resource identity changed")
		_validate_readback(candidate_mesh, packed, candidate_metrics)

	if not _metrics_pass(baseline_metrics):
		_fatal("current Technical Art per-frame ArrayMesh baseline failed readback")
	if not _metrics_pass(candidate_metrics):
		_fatal("stable ArrayMesh resource candidate failed readback")

	for _warmup in range(WARMUP_ROUNDS):
		_baseline_sweep(packed_frames)
		_candidate_sweep(candidate_mesh, packed_frames)

	var baseline_samples: Array = []
	var candidate_samples: Array = []
	for round_index in range(MEASURED_ROUNDS):
		if round_index % 2 == 0:
			baseline_samples.append(_baseline_sweep(packed_frames))
			candidate_samples.append(_candidate_sweep(candidate_mesh, packed_frames))
		else:
			candidate_samples.append(_candidate_sweep(candidate_mesh, packed_frames))
			baseline_samples.append(_baseline_sweep(packed_frames))

	var baseline_median_us := _median(baseline_samples)
	var candidate_median_us := _median(candidate_samples)
	var median_delta_percent := 0.0
	if baseline_median_us > 0.0:
		median_delta_percent = (candidate_median_us - baseline_median_us) / baseline_median_us * 100.0
	var median_within_guard := (
		baseline_median_us > 0.0
		and candidate_median_us <= baseline_median_us * MAX_MEDIAN_REGRESSION_RATIO
	)

	var per_playback_baseline_resources := EXPECTED_KEYS
	var per_playback_candidate_resources := 1
	var resource_reduction_percent := (
		float(per_playback_baseline_resources - per_playback_candidate_resources)
		/ float(per_playback_baseline_resources)
		* 100.0
	)
	var pass_gate := (
		_metrics_pass(baseline_metrics)
		and _metrics_pass(candidate_metrics)
		and candidate_mesh.get_instance_id() == candidate_mesh_instance_id
		and candidate_mesh.get_surface_count() == 1
		and per_playback_candidate_resources == 1
		and median_within_guard
	)

	var version := Engine.get_version_info()
	var result := {
		"schema": RESULT_SCHEMA,
		"state": PASS_STATE if pass_gate else HOLD_STATE,
		"target_host": {
			"engine": "Godot",
			"version": version.get("string", "unknown"),
			"mode": "ArrayMesh receiving proof",
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
			"source": "Technical Art target-host probe",
			"arraymesh_resource_constructions_per_41_key_playback": per_playback_baseline_resources,
			"surface_constructions_per_41_key_playback": EXPECTED_KEYS,
		},
		"after": {
			"arraymesh_resource_constructions_per_41_key_playback": per_playback_candidate_resources,
			"surface_constructions_per_41_key_playback": EXPECTED_KEYS,
			"persistent_arraymesh_identity": true,
			"resource_construction_reduction_percent": resource_reduction_percent,
			"surface_buffer_rebuild_eliminated": false,
		},
		"readback": {
			"baseline": baseline_metrics,
			"candidate": candidate_metrics,
			"visual_tradeoff": "NONE_OBSERVED_AT_RECEIVER_ARRAY_READBACK_ALL_41_KEYS__FRESH_SHADED_RENDER_NOT_RUN",
		},
		"proof_host_timing": {
			"clock": "Time.get_ticks_usec",
			"warmup_rounds": WARMUP_ROUNDS,
			"measured_rounds": MEASURED_ROUNDS,
			"keys_per_round": EXPECTED_KEYS,
			"baseline_median_sweep_us": baseline_median_us,
			"candidate_median_sweep_us": candidate_median_us,
			"candidate_minus_baseline_percent": median_delta_percent,
			"baseline_p95_sweep_us": _percentile(baseline_samples, 0.95),
			"candidate_p95_sweep_us": _percentile(candidate_samples, 0.95),
			"median_regression_guard_ratio": MAX_MEDIAN_REGRESSION_RATIO,
			"target_device_claimed": false,
		},
		"truth_boundary": {
			"technical_art_packet_changed": false,
			"owner_reconstructed_positions_normals_tangents_changed": false,
			"universal_creation_modified": false,
			"persistent_arraymesh_resource_proved": pass_gate,
			"persistent_surface_buffer_update_proved": false,
			"dynamic_region_update_proved": false,
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
	if not pass_gate:
		_fatal("stable ArrayMesh resource reuse gate failed")
	print(JSON.stringify(result))
	quit(0)
