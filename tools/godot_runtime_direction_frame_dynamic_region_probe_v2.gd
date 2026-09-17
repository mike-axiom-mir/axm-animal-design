extends SceneTree

const PACKET_SCHEMA := "axm.animal-direction-frame-target-host-adapter/v0.1"
const RESULT_SCHEMA := "axm.animal-runtime-direction-frame-dynamic-region/v0.2"
const PASS_STATE := "PASS_ANIMAL_GODOT_ENGINE_PACKED_VERTEX_REGION_UPDATE__SURFACE_REBUILDS_41_TO_0__HOLD_SHADED_DEVICE"
const HOLD_STATE := "HOLD_ANIMAL_GODOT_ENGINE_PACKED_VERTEX_REGION_UPDATE"
const EXPECTED_KEYS := 41
const EXPECTED_VERTICES := 84
const EXPECTED_INDICES := 240
const POSITION_TOLERANCE := 0.000001
const DIRECTION_VECTOR_TOLERANCE := 0.00025
const DIRECTION_ANGLE_TOLERANCE_DEG := 0.015
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
		return Vector3.ZERO
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _as_vec2(value: Variant) -> Vector2:
	if typeof(value) != TYPE_ARRAY or value.size() != 2:
		_fatal("expected vec2 array")
		return Vector2.ZERO
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


func _write_json(path: String, value: Dictionary) -> void:
	var handle := FileAccess.open(path, FileAccess.WRITE)
	if handle == null:
		_fatal("failed to open output receipt")
		return
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


func _assert_static_topology_attributes(packed_frames: Array) -> bool:
	var reference: Dictionary = packed_frames[0]
	var reference_uvs: PackedVector2Array = reference["uvs"]
	var reference_indices: PackedInt32Array = reference["indices"]
	for frame_index in range(1, packed_frames.size()):
		var current: Dictionary = packed_frames[frame_index]
		var current_uvs: PackedVector2Array = current["uvs"]
		var current_indices: PackedInt32Array = current["indices"]
		for vertex_index in range(EXPECTED_VERTICES):
			if current_uvs[vertex_index] != reference_uvs[vertex_index]:
				return false
		for index_offset in range(EXPECTED_INDICES):
			if current_indices[index_offset] != reference_indices[index_offset]:
				return false
	return true


func _add_surface(mesh: ArrayMesh, packed: Dictionary, dynamic: bool = false) -> void:
	var flags := 0
	if dynamic:
		flags = Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, packed["arrays"], [], {}, flags)


func _capture_readback(mesh: ArrayMesh) -> Dictionary:
	var observed: Array = mesh.surface_get_arrays(0)
	return {
		"vertices": observed[Mesh.ARRAY_VERTEX],
		"normals": observed[Mesh.ARRAY_NORMAL],
		"tangents": observed[Mesh.ARRAY_TANGENT],
		"uvs": observed[Mesh.ARRAY_TEX_UV],
		"indices": observed[Mesh.ARRAY_INDEX],
	}


func _capture_engine_vertex_data(mesh: ArrayMesh) -> PackedByteArray:
	var surface: Dictionary = RenderingServer.mesh_get_surface(mesh.get_rid(), 0)
	var data: PackedByteArray = surface.get("vertex_data", PackedByteArray())
	return data


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
	if observed_vertices.size() != EXPECTED_VERTICES or observed_normals.size() != EXPECTED_VERTICES or observed_uvs.size() != EXPECTED_VERTICES or observed_tangents.size() != EXPECTED_VERTICES * 4 or observed_indices.size() != EXPECTED_INDICES:
		metrics["frames"] = int(metrics["frames"]) + 1
		metrics["maximum_position_vector_delta"] = INF
		return

	for vertex_index in range(EXPECTED_VERTICES):
		var expected_tangent := Vector3(expected_tangents[vertex_index * 4], expected_tangents[vertex_index * 4 + 1], expected_tangents[vertex_index * 4 + 2])
		var observed_tangent := Vector3(observed_tangents[vertex_index * 4], observed_tangents[vertex_index * 4 + 1], observed_tangents[vertex_index * 4 + 2])
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


func _metrics_exact(metrics: Dictionary) -> bool:
	return (
		int(metrics["frames"]) == EXPECTED_KEYS
		and float(metrics["maximum_position_vector_delta"]) == 0.0
		and float(metrics["maximum_normal_vector_delta"]) == 0.0
		and float(metrics["maximum_normal_angle_deg"]) == 0.0
		and float(metrics["maximum_tangent_vector_delta"]) == 0.0
		and float(metrics["maximum_tangent_angle_deg"]) == 0.0
		and float(metrics["maximum_uv_delta"]) == 0.0
		and int(metrics["tangent_w_mismatch_count"]) == 0
		and int(metrics["index_mismatch_count"]) == 0
	)


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
	if ordered.is_empty():
		return 0.0
	var middle := int(ordered.size() / 2)
	if ordered.size() % 2 == 1:
		return float(ordered[middle])
	return (float(ordered[middle - 1]) + float(ordered[middle])) * 0.5


func _percentile(values: Array, fraction: float) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	if ordered.is_empty():
		return 0.0
	var index := clampi(int(ceil(float(ordered.size()) * fraction)) - 1, 0, ordered.size() - 1)
	return float(ordered[index])


func _baseline_surface_rebuild_sweep(mesh: ArrayMesh, packed_frames: Array) -> int:
	var started := Time.get_ticks_usec()
	for packed in packed_frames:
		if mesh.get_surface_count() > 0:
			mesh.clear_surfaces()
		_add_surface(mesh, packed)
	return Time.get_ticks_usec() - started


func _candidate_vertex_region_sweep(mesh: ArrayMesh, vertex_payloads: Array) -> int:
	var started := Time.get_ticks_usec()
	for payload in vertex_payloads:
		mesh.surface_update_vertex_region(0, 0, payload)
	return Time.get_ticks_usec() - started


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var payload_path := _arg_value(args, "--payload")
	var out_path := _arg_value(args, "--out")
	if payload_path.is_empty() or out_path.is_empty():
		_fatal("usage: --payload <json> --out <json>")
		return

	var payload: Variant = JSON.parse_string(FileAccess.get_file_as_string(payload_path))
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema") != PACKET_SCHEMA:
		_fatal("runtime probe payload/schema drift")
		return
	var frames: Variant = payload.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("runtime probe requires all 41 authored keys")
		return

	var packed_frames: Array = []
	for frame_index in range(frames.size()):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("runtime probe sample ordering drift")
			return
		packed_frames.append(_pack_frame(frame))
	var static_topology_attributes := _assert_static_topology_attributes(packed_frames)
	if not static_topology_attributes:
		_fatal("candidate requires UV/index stability across all 41 keys")
		return

	# Baseline doubles as the engine-owned byte packer. We retain the exact raw
	# vertex_data produced by Godot for each pass-40 surface instead of manually
	# reproducing private target-host normal/tangent packing.
	var baseline_mesh := ArrayMesh.new()
	var baseline_metrics := _new_metrics()
	var baseline_observations: Array = []
	var engine_vertex_payloads: Array = []
	var raw_vertex_bytes_per_key := -1
	for packed in packed_frames:
		if baseline_mesh.get_surface_count() > 0:
			baseline_mesh.clear_surfaces()
		_add_surface(baseline_mesh, packed)
		var observed := _capture_readback(baseline_mesh)
		baseline_observations.append(observed)
		_accumulate_readback(observed, packed, baseline_metrics)
		var raw_vertex_data := _capture_engine_vertex_data(baseline_mesh)
		if raw_vertex_data.is_empty():
			_fatal("Godot did not expose engine-packed vertex_data")
			return
		if raw_vertex_bytes_per_key < 0:
			raw_vertex_bytes_per_key = raw_vertex_data.size()
		elif raw_vertex_data.size() != raw_vertex_bytes_per_key:
			_fatal("engine-packed vertex_data size changed across fixed-topology keys")
			return
		engine_vertex_payloads.append(raw_vertex_data)

	var candidate_mesh := ArrayMesh.new()
	_add_surface(candidate_mesh, packed_frames[0], true)
	var candidate_mesh_instance_id := candidate_mesh.get_instance_id()
	var candidate_surface_count := candidate_mesh.get_surface_count()
	var candidate_format := candidate_mesh.surface_get_format(0)
	var candidate_initial_vertex_data := _capture_engine_vertex_data(candidate_mesh)
	var engine_payload_size_matches_candidate := candidate_initial_vertex_data.size() == raw_vertex_bytes_per_key
	var dynamic_flag_retained := (candidate_format & Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE) != 0
	var envelope := _motion_envelope(packed_frames)
	candidate_mesh.custom_aabb = envelope

	var candidate_metrics := _new_metrics()
	var cross_metrics := _new_metrics()
	var identity_stable := true
	for frame_index in range(EXPECTED_KEYS):
		candidate_mesh.surface_update_vertex_region(0, 0, engine_vertex_payloads[frame_index])
		if candidate_mesh.get_instance_id() != candidate_mesh_instance_id or candidate_mesh.get_surface_count() != candidate_surface_count:
			identity_stable = false
		var observed := _capture_readback(candidate_mesh)
		_accumulate_readback(observed, packed_frames[frame_index], candidate_metrics)
		_accumulate_readback(observed, baseline_observations[frame_index], cross_metrics)

	var frame_volumes: Array = []
	for packed in packed_frames:
		frame_volumes.append(_aabb_volume(_frame_aabb(packed)))
	var envelope_volume := _aabb_volume(envelope)
	var median_frame_volume := _median(frame_volumes)
	var envelope_vs_median_ratio := envelope_volume / median_frame_volume if median_frame_volume > 0.0 else INF

	for _warmup in range(WARMUP_ROUNDS):
		_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames)
		_candidate_vertex_region_sweep(candidate_mesh, engine_vertex_payloads)

	var baseline_samples: Array = []
	var candidate_samples: Array = []
	for round_index in range(MEASURED_ROUNDS):
		if round_index % 2 == 0:
			baseline_samples.append(_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames))
			candidate_samples.append(_candidate_vertex_region_sweep(candidate_mesh, engine_vertex_payloads))
		else:
			candidate_samples.append(_candidate_vertex_region_sweep(candidate_mesh, engine_vertex_payloads))
			baseline_samples.append(_baseline_surface_rebuild_sweep(baseline_mesh, packed_frames))

	var baseline_median_us := _median(baseline_samples)
	var candidate_median_us := _median(candidate_samples)
	var baseline_p95_us := _percentile(baseline_samples, 0.95)
	var candidate_p95_us := _percentile(candidate_samples, 0.95)
	var median_delta_percent := (candidate_median_us - baseline_median_us) / baseline_median_us * 100.0 if baseline_median_us > 0.0 else INF
	var p95_delta_percent := (candidate_p95_us - baseline_p95_us) / baseline_p95_us * 100.0 if baseline_p95_us > 0.0 else INF
	var timing_gate := baseline_median_us > 0.0 and candidate_median_us <= baseline_median_us * MAX_MEDIAN_RATIO
	var pass_gate := (
		_metrics_pass(baseline_metrics)
		and _metrics_pass(candidate_metrics)
		and _metrics_exact(cross_metrics)
		and identity_stable
		and candidate_surface_count == 1
		and dynamic_flag_retained
		and engine_payload_size_matches_candidate
		and static_topology_attributes
		and timing_gate
	)

	var version := Engine.get_version_info()
	var result := {
		"schema": RESULT_SCHEMA,
		"state": PASS_STATE if pass_gate else HOLD_STATE,
		"target_host": {
			"engine": "Godot",
			"version": version.get("string", "unknown"),
			"mode": "ArrayMesh persistent engine-packed vertex_data region receiving proof",
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
			"arraymesh_resource_constructions_per_41_key_playback": 1,
			"surface_rebuilds_per_41_key_playback": EXPECTED_KEYS,
			"surface_constructions_per_41_key_playback": EXPECTED_KEYS,
			"vertex_region_updates_per_41_key_playback": 0,
		},
		"after": {
			"arraymesh_resource_constructions_per_41_key_playback": 1,
			"surface_rebuilds_per_41_key_playback": 0,
			"surface_constructions_to_establish_receiver": 1,
			"surface_rebuild_reduction_percent": 100.0,
			"surface_construction_reduction_percent": float(EXPECTED_KEYS - 1) / float(EXPECTED_KEYS) * 100.0,
			"vertex_region_updates_per_key": 1,
			"vertex_region_updates_per_41_key_playback": EXPECTED_KEYS,
			"persistent_arraymesh_identity": identity_stable,
			"persistent_surface_identity": identity_stable and candidate_surface_count == 1,
			"dynamic_update_flag_retained": dynamic_flag_retained,
			"uv_and_index_buffers_untouched": true,
		},
		"engine_packed_vertex_cache": {
			"packing_source": "RenderingServer.mesh_get_surface(...).vertex_data captured from the pass-40 surface-rebuild baseline",
			"manual_private_vertex_encoding_reimplemented": false,
			"raw_vertex_bytes_per_key": raw_vertex_bytes_per_key,
			"cached_raw_vertex_bytes_all_41_keys": raw_vertex_bytes_per_key * EXPECTED_KEYS,
			"candidate_initial_vertex_bytes": candidate_initial_vertex_data.size(),
			"payload_size_matches_candidate": engine_payload_size_matches_candidate,
			"preparation_cost_in_timed_playback_sweeps": false,
		},
		"motion_envelope": {
			"custom_aabb_used": true,
			"all_41_keys_included": true,
			"envelope_volume": envelope_volume,
			"minimum_frame_aabb_volume": frame_volumes.min(),
			"median_frame_aabb_volume": median_frame_volume,
			"maximum_frame_aabb_volume": frame_volumes.max(),
			"envelope_vs_median_frame_volume_ratio": envelope_vs_median_ratio,
			"tradeoff": "conservative full-motion AABB prevents stale-culling clips but can reduce per-frame culling tightness",
		},
		"readback": {
			"surface_rebuild_baseline": baseline_metrics,
			"engine_packed_region_candidate": candidate_metrics,
			"candidate_vs_baseline": cross_metrics,
			"candidate_vs_baseline_exact": _metrics_exact(cross_metrics),
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
			"receiver_array_result": "EXACT_ARRAY_IDENTITY_ALL_41_KEYS" if _metrics_exact(cross_metrics) else "RECEIVER_ARRAY_DIFFERENCE_DETECTED",
			"fresh_shaded_render_run": false,
			"art_review_state": "HOLD_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW",
			"note": "Receiver arrays are compared against the pass-40 surface-rebuild path. The persistent full-motion AABB is deliberately conservative; fresh shaded A/B remains separate.",
		},
		"failed_predecessor_preserved": {
			"runtime_head": "fbc9c8a86daa299c6a3bf2b9aa421cf30b01df41",
			"workflow_run": 35267861278,
			"artifact_id": 10516719596,
			"artifact_sha256": "a00a9af5192bc7c923e1f4a1891faa7880a3c47eec263d82c1e04e664eaf7413",
			"failure": "manual vertex-buffer packing diverged from Godot readback; gate remained closed",
		},
		"truth_boundary": {
			"technical_art_packet_changed": false,
			"owner_reconstructed_positions_normals_tangents_changed": false,
			"universal_creation_modified": false,
			"persistent_arraymesh_resource_proved": true,
			"persistent_surface_buffer_update_proved": pass_gate,
			"engine_packed_vertex_region_update_proved": pass_gate,
			"static_uv_index_proved": static_topology_attributes,
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
