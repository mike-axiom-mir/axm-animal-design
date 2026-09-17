extends "res://tools/godot_runtime_direction_frame_dynamic_render_probe_v2.gd"

const RESULT_SCHEMA_DEDUP := "axm.animal-runtime-direction-frame-payload-dedup/v0.1"
const PASS_STATE_DEDUP := "PASS_ANIMAL_EXACT_KEY_VERTEX_PAYLOAD_DEDUP__LOWER_CACHE__41_RENDER_PAIRS_IDENTICAL__HOLD_DEVICE_ART"
const HOLD_STATE_DEDUP := "HOLD_ANIMAL_EXACT_KEY_VERTEX_PAYLOAD_DEDUP"


func _deduplicate_payloads(raw_payloads: Array) -> Dictionary:
	var unique_payloads: Array = []
	var key_to_unique: Array = []
	for raw_value in raw_payloads:
		var raw: PackedByteArray = raw_value
		var found := -1
		for unique_index in range(unique_payloads.size()):
			var candidate: PackedByteArray = unique_payloads[unique_index]
			if raw == candidate:
				found = unique_index
				break
		if found < 0:
			unique_payloads.append(raw)
			found = unique_payloads.size() - 1
		key_to_unique.append(found)
	return {
		"unique_payloads": unique_payloads,
		"key_to_unique": key_to_unique,
	}


func _dedup_sweep(mesh: ArrayMesh, unique_payloads: Array, key_to_unique: Array) -> int:
	var started := Time.get_ticks_usec()
	for key_index in range(key_to_unique.size()):
		var raw: PackedByteArray = unique_payloads[int(key_to_unique[key_index])]
		mesh.surface_update_vertex_region(0, 0, raw)
	return Time.get_ticks_usec() - started


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
		_fatal("payload dedup packet/schema drift")
		return
	var frames: Variant = packet.get("frames")
	if typeof(frames) != TYPE_ARRAY or frames.size() != EXPECTED_KEYS:
		_fatal("payload dedup requires all 41 authored keys")
		return

	var packed_frames: Array = []
	for frame_index in range(EXPECTED_KEYS):
		var frame: Dictionary = frames[frame_index]
		if int(frame.get("sample_index", -1)) != frame_index:
			_fatal("payload dedup key ordering drift")
			return
		packed_frames.append(_pack_frame(frame))
	if not _static_uv_indices(packed_frames):
		_fatal("payload dedup requires static UV/index data")
		return

	# Reconstruct the exact pass-41 Godot-packed payloads from verified full surfaces.
	var packing_mesh := ArrayMesh.new()
	var raw_payloads: Array = []
	var raw_bytes_per_key := -1
	for packed in packed_frames:
		if packing_mesh.get_surface_count() > 0:
			packing_mesh.clear_surfaces()
		_add_surface(packing_mesh, packed)
		var raw := _capture_vertex_data(packing_mesh)
		if raw_bytes_per_key < 0:
			raw_bytes_per_key = raw.size()
		if raw.size() != raw_bytes_per_key:
			_fatal("engine vertex_data size drift")
			return
		raw_payloads.append(raw)

	var dedup := _deduplicate_payloads(raw_payloads)
	var unique_payloads: Array = dedup["unique_payloads"]
	var key_to_unique: Array = dedup["key_to_unique"]
	var reconstruction_exact := true
	for key_index in range(EXPECTED_KEYS):
		var reconstructed: PackedByteArray = unique_payloads[int(key_to_unique[key_index])]
		var control: PackedByteArray = raw_payloads[key_index]
		if reconstructed != control:
			reconstruction_exact = false
			break

	var full_cache_bytes := raw_bytes_per_key * EXPECTED_KEYS
	var dedup_cache_bytes := raw_bytes_per_key * unique_payloads.size()
	var saved_cache_bytes := full_cache_bytes - dedup_cache_bytes
	var saved_cache_percent := float(saved_cache_bytes) / float(full_cache_bytes) * 100.0 if full_cache_bytes > 0 else 0.0

	# Both A/B paths use pass-41's persistent dynamic surface. The only candidate
	# difference is cache representation: 41 payload objects vs exact-byte unique pool + key map.
	var control_mesh := ArrayMesh.new()
	var candidate_mesh := ArrayMesh.new()
	_add_surface(control_mesh, packed_frames[0], true)
	_add_surface(candidate_mesh, packed_frames[0], true)
	var envelope := _motion_envelope(packed_frames)
	control_mesh.custom_aabb = envelope
	candidate_mesh.custom_aabb = envelope
	var control_id := control_mesh.get_instance_id()
	var candidate_id := candidate_mesh.get_instance_id()

	_setup_viewport(envelope)
	await process_frame
	await RenderingServer.frame_post_draw

	var render_pairs := 0
	var identical_pairs := 0
	var total_changed_pixels := 0
	var max_channel_delta := 0
	var control_key0_image: Image = null
	var control_key20_image: Image = null
	for key_index in range(EXPECTED_KEYS):
		control_mesh.surface_update_vertex_region(0, 0, raw_payloads[key_index])
		var control_image := await _render_mesh(control_mesh)
		var candidate_raw: PackedByteArray = unique_payloads[int(key_to_unique[key_index])]
		candidate_mesh.surface_update_vertex_region(0, 0, candidate_raw)
		var candidate_image := await _render_mesh(candidate_mesh)
		var comparison := _compare_images(control_image, candidate_image)
		render_pairs += 1
		if comparison["byte_identical"]:
			identical_pairs += 1
		total_changed_pixels += int(comparison["changed_pixels"])
		max_channel_delta = maxi(max_channel_delta, int(comparison["maximum_channel_delta"]))
		if key_index == 0:
			control_key0_image = control_image.duplicate()
		if key_index == 20:
			control_key20_image = control_image.duplicate()
		if RETAINED_RENDER_KEYS.has(key_index):
			control_image.save_png(image_dir.path_join("key_%02d_full_cache.png" % key_index))
			candidate_image.save_png(image_dir.path_join("key_%02d_dedup_cache.png" % key_index))

	var observer_sensitivity := _compare_images(control_key0_image, control_key20_image)
	var observer_sensitive := int(observer_sensitivity["changed_pixels"]) > 0
	var persistent_identity := (
		control_mesh.get_instance_id() == control_id
		and candidate_mesh.get_instance_id() == candidate_id
		and control_mesh.get_surface_count() == 1
		and candidate_mesh.get_surface_count() == 1
	)

	for _warmup in range(WARMUP_ROUNDS):
		_candidate_sweep(control_mesh, raw_payloads)
		_dedup_sweep(candidate_mesh, unique_payloads, key_to_unique)
	var full_cache_samples: Array = []
	var dedup_cache_samples: Array = []
	for round_index in range(MEASURED_ROUNDS):
		if round_index % 2 == 0:
			full_cache_samples.append(_candidate_sweep(control_mesh, raw_payloads))
			dedup_cache_samples.append(_dedup_sweep(candidate_mesh, unique_payloads, key_to_unique))
		else:
			dedup_cache_samples.append(_dedup_sweep(candidate_mesh, unique_payloads, key_to_unique))
			full_cache_samples.append(_candidate_sweep(control_mesh, raw_payloads))
	var full_median := _median(full_cache_samples)
	var dedup_median := _median(dedup_cache_samples)
	var full_p95 := _percentile(full_cache_samples, 0.95)
	var dedup_p95 := _percentile(dedup_cache_samples, 0.95)
	var median_delta_percent := (dedup_median - full_median) / full_median * 100.0 if full_median > 0.0 else INF
	var p95_delta_percent := (dedup_p95 - full_p95) / full_p95 * 100.0 if full_p95 > 0.0 else INF

	var pass_gate := (
		raw_bytes_per_key > 0
		and unique_payloads.size() > 0
		and unique_payloads.size() < EXPECTED_KEYS
		and key_to_unique.size() == EXPECTED_KEYS
		and reconstruction_exact
		and saved_cache_bytes > 0
		and persistent_identity
		and render_pairs == EXPECTED_KEYS
		and identical_pairs == EXPECTED_KEYS
		and total_changed_pixels == 0
		and max_channel_delta == 0
		and observer_sensitive
	)

	var version := Engine.get_version_info()
	var result := {
		"schema": RESULT_SCHEMA_DEDUP,
		"state": PASS_STATE_DEDUP if pass_gate else HOLD_STATE_DEDUP,
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
			"representation_only": true,
		},
		"cache_budget": {
			"raw_vertex_bytes_per_key": raw_bytes_per_key,
			"full_cache_payload_count": EXPECTED_KEYS,
			"full_cache_bytes": full_cache_bytes,
			"unique_payload_count": unique_payloads.size(),
			"deduplicated_cache_bytes": dedup_cache_bytes,
			"saved_cache_bytes": saved_cache_bytes,
			"saved_cache_percent": saved_cache_percent,
			"key_to_unique": key_to_unique,
			"exact_byte_reconstruction_all_keys": reconstruction_exact,
			"map_storage_bytes_not_included": true,
		},
		"receiver": {
			"arraymesh_resources_control": 1,
			"arraymesh_resources_candidate": 1,
			"surface_constructions_control": 1,
			"surface_constructions_candidate": 1,
			"surface_rebuilds_per_playback_control": 0,
			"surface_rebuilds_per_playback_candidate": 0,
			"vertex_region_updates_per_playback_control": EXPECTED_KEYS,
			"vertex_region_updates_per_playback_candidate": EXPECTED_KEYS,
			"same_motion_envelope_aabb": true,
			"persistent_identity": persistent_identity,
		},
		"render_equivalence": {
			"render_pairs": render_pairs,
			"byte_identical_pairs": identical_pairs,
			"total_changed_pixels": total_changed_pixels,
			"maximum_channel_delta": max_channel_delta,
			"retained_keys": RETAINED_RENDER_KEYS,
			"observer_sensitivity_key0_vs_key20_changed_pixels": observer_sensitivity["changed_pixels"],
			"observer_sensitivity_key0_vs_key20_max_channel_delta": observer_sensitivity["maximum_channel_delta"],
			"observer_sensitive": observer_sensitive,
		},
		"proof_host_timing": {
			"warmup_rounds": WARMUP_ROUNDS,
			"measured_rounds": MEASURED_ROUNDS,
			"keys_per_round": EXPECTED_KEYS,
			"full_cache_median_sweep_us": full_median,
			"dedup_cache_median_sweep_us": dedup_median,
			"median_delta_percent": median_delta_percent,
			"full_cache_p95_sweep_us": full_p95,
			"dedup_cache_p95_sweep_us": dedup_p95,
			"p95_delta_percent": p95_delta_percent,
			"timing_is_observation_not_acceptance_gate": true,
			"target_device_claimed": false,
		},
		"visual_tradeoff": {
			"measured": "NONE_OBSERVED_41_OF_41_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL" if identical_pairs == EXPECTED_KEYS else "RENDER_DELTA_DETECTED",
			"fresh_production_shaded_render_run": false,
			"art_review_state": "HOLD_PRODUCTION_SHADED_AND_TARGET_DEVICE_REVIEW",
		},
		"truth_boundary": {
			"technical_art_packet_changed": false,
			"universal_creation_modified": false,
			"pass41_surface_update_representation_changed": false,
			"cache_representation_only": true,
			"continuous_interpolated_playback_proved": false,
			"bilateral_runtime_proved": false,
			"production_shaded_equivalence_proved": false,
			"target_device_cpu_gpu_fps_vram_proved": false,
			"art_direction_acceptance_claimed": false,
			"visual_qa_acceptance_claimed": false,
			"canon_claimed": false,
			"production_ready": false,
		},
	}
	_write_json(out_path, result)
	quit(0 if pass_gate else 1)
