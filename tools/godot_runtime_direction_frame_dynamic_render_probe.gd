extends SceneTree

const PACKET_SCHEMA := "axm.animal-direction-frame-target-host-adapter/v0.1"
const RESULT_SCHEMA := "axm.animal-runtime-direction-frame-dynamic-render/v0.1"
const PASS_STATE := "PASS_ANIMAL_GODOT_PERSISTENT_VERTEX_BUFFER_UPDATE__41_TO_0_SURFACE_REBUILDS__41_RENDER_PAIRS_IDENTICAL__HOLD_DEVICE_ART"
const HOLD_STATE := "HOLD_ANIMAL_GODOT_PERSISTENT_VERTEX_BUFFER_UPDATE_RENDER_PROOF"
const EXPECTED_KEYS := 41
const EXPECTED_VERTICES := 84
const EXPECTED_INDICES := 240
const POSITION_TOLERANCE := 0.000001
const DIRECTION_VECTOR_TOLERANCE := 0.00025
const DIRECTION_ANGLE_TOLERANCE_DEG := 0.015
const UV_TOLERANCE := 0.000001
const WARMUP_ROUNDS := 5
const MEASURED_ROUNDS := 31
const VIEW_SIZE := 320
const RETAINED_RENDER_KEYS := [0, 10, 20, 30, 40]

var _viewport: SubViewport
var _mesh_instance: MeshInstance3D


func _fatal(message: String) -> void:
	push_error(message)
	quit(1)


func _arg_value(args: PackedStringArray, name: String) -> String:
	for index in range(args.size() - 1):
		if args[index] == name:
			return args[index + 1]
	return ""


func _as_vec3(value: Variant) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _as_vec2(value: Variant) -> Vector2:
	return Vector2(float(value[0]), float(value[1]))


func _direction_angle_deg(left: Vector3, right: Vector3) -> float:
	var length_product := left.length() * right.length()
	if length_product <= 0.0:
		return INF
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
	if position_rows.size() != EXPECTED_VERTICES or normal_rows.size() != EXPECTED_VERTICES or tangent_rows.size() != EXPECTED_VERTICES or uv_rows.size() != EXPECTED_VERTICES or index_rows.size() != EXPECTED_INDICES:
		_fatal("render probe domain drift")
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


func _static_uv_indices(packed_frames: Array) -> bool:
	var reference_uvs: PackedVector2Array = packed_frames[0]["uvs"]
	var reference_indices: PackedInt32Array = packed_frames[0]["indices"]
	for frame_index in range(1, packed_frames.size()):
		var uvs: PackedVector2Array = packed_frames[frame_index]["uvs"]
		var indices: PackedInt32Array = packed_frames[frame_index]["indices"]
		for i in range(EXPECTED_VERTICES):
			if uvs[i] != reference_uvs[i]:
				return false
		for i in range(EXPECTED_INDICES):
			if indices[i] != reference_indices[i]:
				return false
	return true


func _add_surface(mesh: ArrayMesh, packed: Dictionary, dynamic: bool = false) -> void:
	var flags := Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE if dynamic else 0
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, packed["arrays"], [], {}, flags)


func _capture_arrays(mesh: ArrayMesh) -> Dictionary:
	var arrays: Array = mesh.surface_get_arrays(0)
	return {
		"vertices": arrays[Mesh.ARRAY_VERTEX],
		"normals": arrays[Mesh.ARRAY_NORMAL],
		"tangents": arrays[Mesh.ARRAY_TANGENT],
		"uvs": arrays[Mesh.ARRAY_TEX_UV],
		"indices": arrays[Mesh.ARRAY_INDEX],
	}


func _capture_vertex_data(mesh: ArrayMesh) -> PackedByteArray:
	var surface: Dictionary = RenderingServer.mesh_get_surface(mesh.get_rid(), 0)
	return surface.get("vertex_data", PackedByteArray())


func _accumulate(observed: Dictionary, expected: Dictionary, metrics: Dictionary) -> void:
	var ov: PackedVector3Array = observed["vertices"]
	var on: PackedVector3Array = observed["normals"]
	var ot: PackedFloat32Array = observed["tangents"]
	var ou: PackedVector2Array = observed["uvs"]
	var oi: PackedInt32Array = observed["indices"]
	var ev: PackedVector3Array = expected["vertices"]
	var en: PackedVector3Array = expected["normals"]
	var et: PackedFloat32Array = expected["tangents"]
	var eu: PackedVector2Array = expected["uvs"]
	var ei: PackedInt32Array = expected["indices"]
	for vertex_index in range(EXPECTED_VERTICES):
		var observed_tangent := Vector3(ot[vertex_index * 4], ot[vertex_index * 4 + 1], ot[vertex_index * 4 + 2])
		var expected_tangent := Vector3(et[vertex_index * 4], et[vertex_index * 4 + 1], et[vertex_index * 4 + 2])
		metrics["maximum_position_vector_delta"] = max(float(metrics["maximum_position_vector_delta"]), ov[vertex_index].distance_to(ev[vertex_index]))
		metrics["maximum_normal_vector_delta"] = max(float(metrics["maximum_normal_vector_delta"]), on[vertex_index].distance_to(en[vertex_index]))
		metrics["maximum_normal_angle_deg"] = max(float(metrics["maximum_normal_angle_deg"]), _direction_angle_deg(on[vertex_index], en[vertex_index]))
		metrics["maximum_tangent_vector_delta"] = max(float(metrics["maximum_tangent_vector_delta"]), observed_tangent.distance_to(expected_tangent))
		metrics["maximum_tangent_angle_deg"] = max(float(metrics["maximum_tangent_angle_deg"]), _direction_angle_deg(observed_tangent, expected_tangent))
		metrics["maximum_uv_delta"] = max(float(metrics["maximum_uv_delta"]), ou[vertex_index].distance_to(eu[vertex_index]))
		if ot[vertex_index * 4 + 3] != et[vertex_index * 4 + 3]:
			metrics["tangent_w_mismatch_count"] = int(metrics["tangent_w_mismatch_count"]) + 1
	for index_offset in range(EXPECTED_INDICES):
		if oi[index_offset] != ei[index_offset]:
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


func _frame_aabb(packed: Dictionary) -> AABB:
	var vertices: PackedVector3Array = packed["vertices"]
	var minimum := vertices[0]
	var maximum := vertices[0]
	for i in range(1, vertices.size()):
		minimum = minimum.min(vertices[i])
		maximum = maximum.max(vertices[i])
	return AABB(minimum, maximum - minimum)


func _motion_envelope(packed_frames: Array) -> AABB:
	var envelope := _frame_aabb(packed_frames[0])
	for i in range(1, packed_frames.size()):
		envelope = envelope.merge(_frame_aabb(packed_frames[i]))
	return envelope


func _aabb_volume(box: AABB) -> float:
	return box.size.x * box.size.y * box.size.z


func _median(values: Array) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	if ordered.is_empty():
		return 0.0
	var middle := int(ordered.size() / 2)
	return float(ordered[middle]) if ordered.size() % 2 == 1 else (float(ordered[middle - 1]) + float(ordered[middle])) * 0.5


func _percentile(values: Array, fraction: float) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	if ordered.is_empty():
		return 0.0
	var index := clampi(int(ceil(float(ordered.size()) * fraction)) - 1, 0, ordered.size() - 1)
	return float(ordered[index])


func _baseline_sweep(mesh: ArrayMesh, packed_frames: Array) -> int:
	var started := Time.get_ticks_usec()
	for packed in packed_frames:
		if mesh.get_surface_count() > 0:
			mesh.clear_surfaces()
		_add_surface(mesh, packed)
	return Time.get_ticks_usec() - started


func _candidate_sweep(mesh: ArrayMesh, raw_payloads: Array) -> int:
	var started := Time.get_ticks_usec()
	for raw in raw_payloads:
		mesh.surface_update_vertex_region(0, 0, raw)
	return Time.get_ticks_usec() - started


func _build_debug_material() -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;
varying vec3 frame_signal;
void vertex() {
    vec3 n = normalize(NORMAL);
    vec3 t = normalize(TANGENT);
    frame_signal = n * 0.65 + t * 0.35;
}
void fragment() {
    ALBEDO = clamp(frame_signal * 0.5 + vec3(0.5), vec3(0.0), vec3(1.0));
    ALPHA = 1.0;
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	return material


func _setup_viewport(envelope: AABB) -> void:
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(VIEW_SIZE, VIEW_SIZE)
	_viewport.transparent_bg = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_viewport.world_3d = World3D.new()
	get_root().add_child(_viewport)

	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.025, 0.03, 0.04, 1.0)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.1, 0.1, 0.1, 1.0)
	environment.ambient_light_energy = 0.0
	_viewport.world_3d.environment = environment

	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = max(envelope.size.y, max(envelope.size.x, envelope.size.z)) * 1.55
	var center := envelope.get_center()
	camera.position = center + Vector3(1.15, 0.45, 1.35)
	camera.look_at(center, Vector3.UP)
	camera.current = true
	_viewport.add_child(camera)

	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.material_override = _build_debug_material()
	_viewport.add_child(_mesh_instance)


func _render_mesh(mesh: ArrayMesh) -> Image:
	_mesh_instance.mesh = mesh
	await process_frame
	await RenderingServer.frame_post_draw
	var image := _viewport.get_texture().get_image()
	image.convert(Image.FORMAT_RGBA8)
	return image


func _compare_images(left: Image, right: Image) -> Dictionary:
	if left.get_size() != right.get_size() or left.get_format() != right.get_format():
		return {"changed_pixels": VIEW_SIZE * VIEW_SIZE, "maximum_channel_delta": 255, "byte_identical": false}
	var a := left.get_data()
	var b := right.get_data()
	var changed_pixels := 0
	var maximum_channel_delta := 0
	for pixel in range(VIEW_SIZE * VIEW_SIZE):
		var changed := false
		for channel in range(4):
			var offset := pixel * 4 + channel
			var delta := absi(int(a[offset]) - int(b[offset]))
			maximum_channel_delta = maxi(maximum_channel_delta, delta)
			if delta != 0:
				changed = true
		if changed:
			changed_pixels += 1
	return {
		"changed_pixels": changed_pixels,
		"maximum_channel_delta": maximum_channel_delta,
		"byte_identical": changed_pixels == 0,
	}


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var payload_path := _arg_value(args, "--payload")
	var out_path := _arg_value(args, "--out")
	var image_dir := _arg_value(args, "--image-dir")
	if payload_path.is_empty() or out_path.is_empty() or image_dir.is_empty():
		_fatal("usage: --payload <json> --out <json> --image-dir <dir>")
		return
	DirAccess.make_dir_recursive_absolute(image_dir)

	var packet: Variant = JSON.parse_string(FileAccess.get_file_as_string(payload_path))
	if typeof(packet) != TYPE_DICTIONARY or packet.get("schema") != PACKET_SCHEMA:
		_fatal("render probe packet/schema drift")
		return
	var frames: Variant = packet.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("render probe requires all 41 keys")
		return

	var packed_frames: Array = []
	for frame_index in range(EXPECTED_KEYS):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("render probe key ordering drift")
			return
		packed_frames.append(_pack_frame(frame))
	var static_uv_index := _static_uv_indices(packed_frames)
	if not static_uv_index:
		_fatal("persistent vertex buffer candidate requires static UV/index data")
		return

	var baseline_mesh := ArrayMesh.new()
	var baseline_metrics := _new_metrics()
	var baseline_arrays: Array = []
	var raw_payloads: Array = []
	var raw_bytes_per_key := -1
	for packed in packed_frames:
		if baseline_mesh.get_surface_count() > 0:
			baseline_mesh.clear_surfaces()
		_add_surface(baseline_mesh, packed)
		var observed := _capture_arrays(baseline_mesh)
		baseline_arrays.append(observed)
		_accumulate(observed, packed, baseline_metrics)
		var raw := _capture_vertex_data(baseline_mesh)
		if raw_bytes_per_key < 0:
			raw_bytes_per_key = raw.size()
		if raw.size() != raw_bytes_per_key:
			_fatal("engine vertex_data size drift")
			return
		raw_payloads.append(raw)
	if not _metrics_pass(baseline_metrics):
		_fatal("pass-40 baseline no longer satisfies Technical Art tolerances")
		return

	var candidate_mesh := ArrayMesh.new()
	_add_surface(candidate_mesh, packed_frames[0], true)
	var candidate_id := candidate_mesh.get_instance_id()
	var dynamic_flag_retained := (candidate_mesh.surface_get_format(0) & Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE) != 0
	var envelope := _motion_envelope(packed_frames)
	candidate_mesh.custom_aabb = envelope
	var payload_size_match := _capture_vertex_data(candidate_mesh).size() == raw_bytes_per_key

	# Diagnostic only: ArrayMesh.surface_get_arrays() reflects CPU-side surface metadata,
	# not region-updated GPU vertex bytes. Peak-key stale readback is retained as evidence
	# of why v1/v2 fail-closed readback gates could not validate this API.
	candidate_mesh.surface_update_vertex_region(0, 0, raw_payloads[20])
	var stale_peak_metrics := _new_metrics()
	_accumulate(_capture_arrays(candidate_mesh), baseline_arrays[20], stale_peak_metrics)

	_setup_viewport(envelope)
	await process_frame
	await RenderingServer.frame_post_draw

	var render_pairs := 0
	var identical_pairs := 0
	var total_changed_pixels := 0
	var max_channel_delta := 0
	var baseline_key0_image: Image = null
	var baseline_key20_image: Image = null
	for key_index in range(EXPECTED_KEYS):
		if baseline_mesh.get_surface_count() > 0:
			baseline_mesh.clear_surfaces()
		_add_surface(baseline_mesh, packed_frames[key_index])
		var baseline_image := await _render_mesh(baseline_mesh)
		candidate_mesh.surface_update_vertex_region(0, 0, raw_payloads[key_index])
		var candidate_image := await _render_mesh(candidate_mesh)
		var comparison := _compare_images(baseline_image, candidate_image)
		render_pairs += 1
		if comparison["byte_identical"]:
			identical_pairs += 1
		total_changed_pixels += int(comparison["changed_pixels"])
		max_channel_delta = maxi(max_channel_delta, int(comparison["maximum_channel_delta"]))
		if key_index == 0:
			baseline_key0_image = baseline_image.duplicate()
		if key_index == 20:
			baseline_key20_image = baseline_image.duplicate()
		if RETAINED_RENDER_KEYS.has(key_index):
			baseline_image.save_png(image_dir.path_join("key_%02d_baseline.png" % key_index))
			candidate_image.save_png(image_dir.path_join("key_%02d_candidate.png" % key_index))

	var observer_sensitivity := _compare_images(baseline_key0_image, baseline_key20_image)
	var observer_sensitive := int(observer_sensitivity["changed_pixels"]) > 0
	var identity_stable := candidate_mesh.get_instance_id() == candidate_id and candidate_mesh.get_surface_count() == 1

	for _warmup in range(WARMUP_ROUNDS):
		_baseline_sweep(baseline_mesh, packed_frames)
		_candidate_sweep(candidate_mesh, raw_payloads)
	var baseline_samples: Array = []
	var candidate_samples: Array = []
	for round_index in range(MEASURED_ROUNDS):
		if round_index % 2 == 0:
			baseline_samples.append(_baseline_sweep(baseline_mesh, packed_frames))
			candidate_samples.append(_candidate_sweep(candidate_mesh, raw_payloads))
		else:
			candidate_samples.append(_candidate_sweep(candidate_mesh, raw_payloads))
			baseline_samples.append(_baseline_sweep(baseline_mesh, packed_frames))
	var baseline_median := _median(baseline_samples)
	var candidate_median := _median(candidate_samples)
	var baseline_p95 := _percentile(baseline_samples, 0.95)
	var candidate_p95 := _percentile(candidate_samples, 0.95)
	var median_delta_percent := (candidate_median - baseline_median) / baseline_median * 100.0 if baseline_median > 0.0 else INF
	var p95_delta_percent := (candidate_p95 - baseline_p95) / baseline_p95 * 100.0 if baseline_p95 > 0.0 else INF
	var timing_gate := baseline_median > 0.0 and candidate_median <= baseline_median

	var frame_volumes: Array = []
	for packed in packed_frames:
		frame_volumes.append(_aabb_volume(_frame_aabb(packed)))
	var envelope_volume := _aabb_volume(envelope)
	var median_frame_volume := _median(frame_volumes)
	var pass_gate := (
		_metrics_pass(baseline_metrics)
		and static_uv_index
		and payload_size_match
		and dynamic_flag_retained
		and identity_stable
		and render_pairs == EXPECTED_KEYS
		and identical_pairs == EXPECTED_KEYS
		and total_changed_pixels == 0
		and max_channel_delta == 0
		and observer_sensitive
		and timing_gate
	)

	var version := Engine.get_version_info()
	var result := {
		"schema": RESULT_SCHEMA,
		"state": PASS_STATE if pass_gate else HOLD_STATE,
		"target_host": {
			"engine": "Godot",
			"version": version.get("string", "unknown"),
			"rendering_method": RenderingServer.get_current_rendering_method(),
			"rendering_device": RenderingServer.get_video_adapter_name(),
		},
		"scope": {
			"side": "right",
			"authored_keys": EXPECTED_KEYS,
			"vertices_per_frame": EXPECTED_VERTICES,
			"indices_per_frame": EXPECTED_INDICES,
			"static_uv_and_indices": static_uv_index,
		},
		"before": {
			"arraymesh_resources_per_playback": 1,
			"surface_rebuilds_per_41_key_playback": EXPECTED_KEYS,
			"surface_constructions_per_41_key_playback": EXPECTED_KEYS,
			"vertex_region_updates_per_playback": 0,
		},
		"after": {
			"arraymesh_resources_per_playback": 1,
			"surface_rebuilds_per_41_key_playback": 0,
			"surface_constructions_to_establish_receiver": 1,
			"surface_rebuild_reduction_percent": 100.0,
			"surface_construction_reduction_percent": float(EXPECTED_KEYS - 1) / float(EXPECTED_KEYS) * 100.0,
			"vertex_region_updates_per_key": 1,
			"vertex_region_updates_per_playback": EXPECTED_KEYS,
			"persistent_arraymesh_identity": identity_stable,
			"persistent_surface_identity": identity_stable,
			"dynamic_update_flag_retained": dynamic_flag_retained,
			"uv_and_index_buffers_untouched": true,
		},
		"engine_packed_vertex_cache": {
			"source": "Godot RenderingServer.mesh_get_surface(...).vertex_data from verified pass-40 surface rebuilds",
			"raw_vertex_bytes_per_key": raw_bytes_per_key,
			"cached_raw_vertex_bytes_all_41_keys": raw_bytes_per_key * EXPECTED_KEYS,
			"manual_private_encoding_used": false,
			"payload_size_matches_candidate": payload_size_match,
			"preparation_in_timed_sweeps": false,
		},
		"baseline_target_host_readback": baseline_metrics,
		"region_update_cpu_readback_diagnostic": {
			"surface_get_arrays_after_peak_update": stale_peak_metrics,
			"used_as_acceptance_gate": false,
			"reason": "ArrayMesh.surface_update_vertex_region updates RenderingServer vertex storage while ArrayMesh surface_get_arrays retains original CPU-side surface metadata; correctness is therefore gated by rendered output, not stale metadata readback.",
		},
		"render_equivalence": {
			"render_pairs": render_pairs,
			"byte_identical_pairs": identical_pairs,
			"total_changed_pixels": total_changed_pixels,
			"maximum_channel_delta": max_channel_delta,
			"debug_shader_exercises_position_normal_and_tangent": true,
			"retained_keys": RETAINED_RENDER_KEYS,
			"observer_sensitivity_key0_vs_key20_changed_pixels": observer_sensitivity["changed_pixels"],
			"observer_sensitivity_key0_vs_key20_max_channel_delta": observer_sensitivity["maximum_channel_delta"],
			"observer_sensitive": observer_sensitive,
		},
		"proof_host_timing": {
			"warmup_rounds": WARMUP_ROUNDS,
			"measured_rounds": MEASURED_ROUNDS,
			"keys_per_round": EXPECTED_KEYS,
			"baseline_median_sweep_us": baseline_median,
			"candidate_median_sweep_us": candidate_median,
			"median_delta_percent": median_delta_percent,
			"baseline_p95_sweep_us": baseline_p95,
			"candidate_p95_sweep_us": candidate_p95,
			"p95_delta_percent": p95_delta_percent,
			"target_device_claimed": false,
		},
		"motion_envelope": {
			"custom_aabb_used": true,
			"all_41_keys_included": true,
			"envelope_volume": envelope_volume,
			"minimum_frame_aabb_volume": frame_volumes.min(),
			"median_frame_aabb_volume": median_frame_volume,
			"maximum_frame_aabb_volume": frame_volumes.max(),
			"envelope_vs_median_frame_volume_ratio": envelope_volume / median_frame_volume,
			"tradeoff": "full-motion AABB prevents stale-culling disappearance but is looser than the median per-key bound",
		},
		"visual_tradeoff": {
			"measured": "NONE_OBSERVED_41_OF_41_POSITION_NORMAL_TANGENT_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL" if identical_pairs == EXPECTED_KEYS else "RENDER_DELTA_DETECTED",
			"fresh_production_shaded_render_run": false,
			"art_review_state": "HOLD_PRODUCTION_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW",
		},
		"failed_predecessors_preserved": [
			{"head": "fbc9c8a86daa299c6a3bf2b9aa421cf30b01df41", "run": 35267861278, "artifact": 10516719596, "reason": "manual packing plus stale CPU readback gate failed closed"},
			{"head": "79c3fead177996e7b825885701c877c81a1f46c7", "run": 35268361181, "artifact": 10518260489, "reason": "engine-packed GPU update still used stale CPU surface_get_arrays as acceptance evidence and therefore held"},
		],
		"truth_boundary": {
			"technical_art_packet_changed": false,
			"universal_creation_modified": false,
			"persistent_surface_vertex_buffer_update_proved_by_render": pass_gate,
			"production_shaded_equivalence_proved": false,
			"bilateral_runtime_proved": false,
			"continuous_interpolated_playback_proved": false,
			"target_device_cpu_gpu_fps_vram_proved": false,
			"art_direction_acceptance_claimed": false,
			"visual_qa_acceptance_claimed": false,
			"canon_claimed": false,
			"production_ready": false,
		},
	}
	_write_json(out_path, result)
	quit(0 if pass_gate else 1)
