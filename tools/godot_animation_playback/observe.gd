extends SceneTree

const PAYLOAD_PATH := "res://generated/quadruped_animation_payload.json"
const RECEIPT_PATH := "res://generated/quadruped_animation_godot_receipt.json"
const NEUTRAL_CAPTURE := "res://generated/godot-neutral.png"
const PEAK_CAPTURE := "res://generated/godot-peak.png"
const LAST_CAPTURE := "res://generated/godot-last-visible.png"
const WRAP_CAPTURE := "res://generated/godot-wrap-neutral.png"

var receipt := {
    "schema": "axm.animal-animation-godot-discrete-playback-proof/v0.1",
    "proof_runtime": "Godot 4.7.2",
    "proof_mode": "DETERMINISTIC_AUTHORED_SAMPLE_STEPPING_NOT_REALTIME_PACING",
    "promotion_effect": "NONE",
    "truth_boundary": "This proof applies the exact existing Animal authored sample surfaces as triangle geometry inside pinned Godot 4.7.2 and steps them through two deterministic cycles plus wrap. It does not prove interpolation, real-time 40 Hz pacing, exported skeleton/clip transport, runtime controller or state-machine integration, gameplay acceptance, perceptual animation quality, biological gait, target-device performance, or production runtime acceptance."
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

func vector_from_row(row) -> Vector3:
    return Vector3(float(row[0]), float(row[1]), float(row[2]))

func build_mesh(frame: Dictionary, material: StandardMaterial3D) -> ArrayMesh:
    var vertices := PackedVector3Array()
    for row in frame.get("positions", []):
        vertices.append(vector_from_row(row))
    var indices := PackedInt32Array()
    for value in frame.get("indices", []):
        indices.append(int(value))
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    mesh.surface_set_material(0, material)
    return mesh

func mesh_readback_error(mesh: ArrayMesh, frame: Dictionary) -> float:
    if mesh.get_surface_count() != 1:
        return INF
    var arrays := mesh.surface_get_arrays(0)
    var observed: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var expected = frame.get("positions", [])
    if observed.size() != expected.size():
        return INF
    var maximum := 0.0
    for index in range(observed.size()):
        maximum = maxf(maximum, observed[index].distance_to(vector_from_row(expected[index])))
    return maximum

func capture(viewport: SubViewport, path: String) -> Dictionary:
    for _index in range(6):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        return {"state": "FAIL"}
    var error := image.save_png(path)
    if error != OK:
        return {"state": "FAIL", "error": error}
    return {
        "state": "PASS",
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(path).size()
    }

func pixel_delta(path_a: String, path_b: String) -> Dictionary:
    var a := Image.load_from_file(path_a)
    var b := Image.load_from_file(path_b)
    if a == null or b == null or a.is_empty() or b.is_empty() or a.get_size() != b.get_size():
        return {"state": "FAIL"}
    var sampled := 0
    var changed := 0
    var sum_delta := 0.0
    var max_delta := 0.0
    for y in range(0, a.get_height(), 2):
        for x in range(0, a.get_width(), 2):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var delta := absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)
            sampled += 1
            sum_delta += delta
            max_delta = maxf(max_delta, delta)
            if delta > 0.04:
                changed += 1
    return {
        "state": "PASS",
        "sampled_pixels": sampled,
        "changed_pixels": changed,
        "changed_ratio": float(changed) / float(maxi(sampled, 1)),
        "max_rgb_delta": max_delta,
        "mean_rgb_delta": sum_delta / float(maxi(sampled, 1))
    }

func apply_frame(mesh_instance: MeshInstance3D, frame: Dictionary, material: StandardMaterial3D) -> float:
    var mesh := build_mesh(frame, material)
    mesh_instance.mesh = mesh
    await process_frame
    return mesh_readback_error(mesh, frame)

func _initialize() -> void:
    if not FileAccess.file_exists(PAYLOAD_PATH):
        fail("exact Animal playback payload missing")
        return
    var payload = load_json(PAYLOAD_PATH)
    if payload == null or not (payload is Dictionary):
        fail("Animal playback payload is not valid JSON")
        return
    if str(payload.get("schema", "")) != "axm.animal-animation-godot-discrete-playback-payload/v0.1":
        fail("unexpected Animal playback payload schema")
        return

    var source_playback: Dictionary = payload.get("source_playback", {})
    var frames = payload.get("frames", [])
    var frame_count := int(source_playback.get("displayed_frame_count_per_cycle", 0))
    if frame_count != 40 or frames.size() != frame_count:
        fail("exact 40-frame authored display cycle was not preserved")
        return
    if str(source_playback.get("playback_mode", "")) != "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION":
        fail("proof host received an unexpected playback mode")
        return
    for index in range(frame_count):
        if int(frames[index].get("frame_index", -1)) != index or int(frames[index].get("sample_index", -1)) != index:
            fail("authored frame/sample ordering drifted")
            return

    receipt["payload_sha256"] = FileAccess.get_sha256(PAYLOAD_PATH)
    receipt["source_identity"] = payload.get("source_identity", {})
    receipt["source_playback"] = source_playback
    receipt["coordinate_bridge"] = payload.get("coordinate_bridge", {})
    receipt["topology"] = payload.get("topology", {})

    var viewport := SubViewport.new()
    viewport.size = Vector2i(800, 600)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)

    var scene_root := Node3D.new()
    viewport.add_child(scene_root)

    var environment := Environment.new()
    environment.background_mode = Environment.BG_COLOR
    environment.background_color = Color(0.025, 0.03, 0.04, 1.0)
    var world_environment := WorldEnvironment.new()
    world_environment.environment = environment
    scene_root.add_child(world_environment)

    var material := StandardMaterial3D.new()
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    material.albedo_color = Color(0.78, 0.82, 0.88, 1.0)

    var mesh_instance := MeshInstance3D.new()
    mesh_instance.name = "ExactAuthoredAnimalSample"
    scene_root.add_child(mesh_instance)

    var bounds: Dictionary = payload.get("bounds_godot", {})
    var center := vector_from_row(bounds.get("center", [0.0, 0.0, 0.0]))
    var size := vector_from_row(bounds.get("size", [1.0, 1.0, 1.0]))
    var radius := maxf(size.length() * 0.5, 0.5)
    var camera := Camera3D.new()
    camera.fov = 40.0
    camera.near = 0.01
    camera.far = 100.0
    camera.look_at_from_position(
        center + Vector3(radius * 1.35, radius * 0.70, radius * 2.55),
        center + Vector3(0.0, radius * 0.05, 0.0),
        Vector3.UP
    )
    scene_root.add_child(camera)
    camera.make_current()

    # Retain fixed exact authored samples before the full sequence exercise.
    var neutral_error := await apply_frame(mesh_instance, frames[0], material)
    var neutral_capture := await capture(viewport, NEUTRAL_CAPTURE)
    var peak_error := await apply_frame(mesh_instance, frames[20], material)
    var peak_capture := await capture(viewport, PEAK_CAPTURE)
    var last_error := await apply_frame(mesh_instance, frames[39], material)
    var last_capture := await capture(viewport, LAST_CAPTURE)
    for result in [neutral_capture, peak_capture, last_capture]:
        if result.get("state") != "PASS":
            fail("Godot authored-sample capture failed")
            return

    # Exercise two complete exact discrete cycles in the real Godot process.
    # One process_frame is yielded per authored sample application only so this
    # proves engine sample application/readback, not wall-clock 40 Hz pacing.
    var applied_indices := []
    var maximum_readback_error := maxf(neutral_error, maxf(peak_error, last_error))
    var unique_surface_digests := {}
    for cycle_index in range(2):
        for frame_index in range(frame_count):
            var frame: Dictionary = frames[frame_index]
            maximum_readback_error = maxf(maximum_readback_error, await apply_frame(mesh_instance, frame, material))
            applied_indices.append(frame_index)
            unique_surface_digests[str(frame.get("surface_digest", ""))] = true

    # Exact wrap back to authored sample zero after both cycles.
    maximum_readback_error = maxf(maximum_readback_error, await apply_frame(mesh_instance, frames[0], material))
    applied_indices.append(0)
    var wrap_capture := await capture(viewport, WRAP_CAPTURE)
    if wrap_capture.get("state") != "PASS":
        fail("Godot neutral-wrap capture failed")
        return

    var neutral_to_peak := pixel_delta(NEUTRAL_CAPTURE, PEAK_CAPTURE)
    var neutral_to_wrap := pixel_delta(NEUTRAL_CAPTURE, WRAP_CAPTURE)
    var last_to_wrap := pixel_delta(LAST_CAPTURE, WRAP_CAPTURE)
    if neutral_to_peak.get("state") != "PASS" or neutral_to_wrap.get("state") != "PASS" or last_to_wrap.get("state") != "PASS":
        fail("Godot retained image comparison failed")
        return

    var peak_visible := float(neutral_to_peak.get("changed_ratio", 0.0)) >= 0.00005
    var neutral_roundtrip := float(neutral_to_wrap.get("changed_ratio", 1.0)) <= 0.00010
    var exact_sequence_length := applied_indices.size() == frame_count * 2 + 1
    var sequence_order_ok := exact_sequence_length
    if sequence_order_ok:
        for cycle_index in range(2):
            for frame_index in range(frame_count):
                if int(applied_indices[cycle_index * frame_count + frame_index]) != frame_index:
                    sequence_order_ok = false
        sequence_order_ok = sequence_order_ok and int(applied_indices[-1]) == 0

    receipt["engine_sample_application"] = {
        "applied_sample_steps": applied_indices.size(),
        "cycles_exercised": 2,
        "final_wrap_sample": int(applied_indices[-1]),
        "sequence_order_ok": sequence_order_ok,
        "unique_authored_surface_digests_seen": unique_surface_digests.size(),
        "maximum_vertex_readback_error_m": maximum_readback_error,
        "readback_matches_payload": maximum_readback_error <= 0.000001,
        "one_process_frame_yield_per_sample_application": true,
        "real_time_frame_pacing_claimed": false,
        "interpolation_claimed": false
    }
    receipt["visual_observation"] = {
        "neutral_to_peak": neutral_to_peak,
        "last_visible_to_wrap": last_to_wrap,
        "neutral_to_wrap": neutral_to_wrap,
        "peak_visible": peak_visible,
        "neutral_roundtrip_visually_clean": neutral_roundtrip,
        "captures": {
            "neutral": neutral_capture,
            "peak": peak_capture,
            "last_visible": last_capture,
            "wrap_neutral": wrap_capture
        },
        "visual_quality_acceptance": "NOT_CLAIMED"
    }

    if not sequence_order_ok:
        fail("Godot did not exercise the exact two-cycle authored sample order")
        return
    if maximum_readback_error > 0.000001:
        fail("Godot vertex readback drifted from exact authored sample payload")
        return
    if unique_surface_digests.size() <= 2:
        fail("Godot proof did not exercise materially distinct authored sample identities")
        return
    if not peak_visible or not neutral_roundtrip:
        fail("retained Godot renders did not satisfy bounded motion/roundtrip visibility gates")
        return

    receipt["state"] = "PASS_GODOT_DISCRETE_SAMPLE_PLAYBACK_PROOF_HOST"
    receipt["remaining_open"] = [
        "independent Art Director and Visual Observer review of cadence, silhouette, pinching, weight and personality",
        "continuous interpolation between authored samples",
        "real-time 40 Hz target-engine frame pacing",
        "exported skeleton or animation-clip transport",
        "runtime controller or state-machine integration",
        "gameplay acceptance",
        "target-device performance and production runtime acceptance"
    ]
    write_receipt()
    print("AXM ANIMAL GODOT DISCRETE PLAYBACK PASS ", JSON.stringify(receipt))
    quit(0)
