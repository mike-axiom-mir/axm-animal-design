extends SceneTree

const PAYLOAD_PATH := "res://generated/quadruped_animation_interpolation_payload.json"
const RECEIPT_PATH := "res://generated/quadruped_animation_interpolation_godot_receipt.json"
const NEUTRAL_CAPTURE := "res://generated/godot-neutral.png"
const PRE_PEAK_CAPTURE := "res://generated/godot-authored-19.png"
const INTERIOR_CAPTURE := "res://generated/godot-interior-19p5.png"
const PEAK_CAPTURE := "res://generated/godot-peak-20.png"
const LAST_INTERIOR_CAPTURE := "res://generated/godot-last-interior.png"
const FINAL_CAPTURE := "res://generated/godot-final-neutral.png"

var receipt := {
    "schema": "axm.animal-animation-connected-linear-interpolation-godot-proof/v0.1",
    "proof_runtime": "Godot 4.7.2",
    "proof_mode": "DETERMINISTIC_BETWEEN_SAMPLE_VERTEX_LERP_PROBES_NOT_REALTIME_PACING",
    "promotion_effect": "NONE",
    "truth_boundary": "This proof applies exact C0 piecewise-linear connected-forelimb interpolation probe surfaces inside pinned Godot 4.7.2. It exercises alpha 0.25, 0.5 and 0.75 in every authored interval while preserving exact authored boundaries. It does not prove C1 continuity, wall-clock pacing, AnimationPlayer/skeleton/skin/clip transport, runtime controller or state-machine integration, continuous collision/self-intersection freedom, gameplay acceptance, final perceptual motion quality, biological gait, target-device performance, or production readiness."
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

func apply_frame(mesh_instance: MeshInstance3D, frame: Dictionary, material: StandardMaterial3D) -> float:
    var mesh := build_mesh(frame, material)
    mesh_instance.mesh = mesh
    await process_frame
    return mesh_readback_error(mesh, frame)

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
    var max_delta := 0.0
    for y in range(0, a.get_height(), 2):
        for x in range(0, a.get_width(), 2):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var delta := absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)
            sampled += 1
            max_delta = maxf(max_delta, delta)
            if delta > 0.04:
                changed += 1
    return {
        "state": "PASS",
        "sampled_pixels": sampled,
        "changed_pixels": changed,
        "changed_ratio": float(changed) / float(maxi(sampled, 1)),
        "max_rgb_delta": max_delta
    }

func _initialize() -> void:
    if not FileAccess.file_exists(PAYLOAD_PATH):
        fail("exact Animal interpolation payload missing")
        return
    var payload = load_json(PAYLOAD_PATH)
    if payload == null or not (payload is Dictionary):
        fail("Animal interpolation payload is not valid JSON")
        return
    if str(payload.get("schema", "")) != "axm.animal-animation-connected-linear-interpolation-payload/v0.1":
        fail("unexpected Animal interpolation payload schema")
        return

    var contract: Dictionary = payload.get("interpolation_contract", {})
    var frames = payload.get("frames", [])
    if str(contract.get("continuity_class_claimed", "")) != "C0_POSITION_ONLY":
        fail("unexpected continuity claim")
        return
    if int(contract.get("authored_interval_count", 0)) != 40:
        fail("authored interval count drift")
        return
    if int(contract.get("subdivisions_per_authored_interval", 0)) != 4:
        fail("interpolation subdivision drift")
        return
    if frames.size() != 161:
        fail("expected exact 161 endpoint-inclusive interpolation probes")
        return
    for index in range(frames.size()):
        if int(frames[index].get("frame_index", -1)) != index:
            fail("interpolation frame ordering drift")
            return
    for sample_index in range(41):
        var frame_index := sample_index * 4
        if frame_index > 160:
            fail("authored boundary index escaped payload")
            return
        var boundary: Dictionary = frames[frame_index]
        if not bool(boundary.get("authored_boundary", false)):
            fail("authored boundary marker missing")
            return
        if int(boundary.get("source_sample_index", -1)) != sample_index:
            fail("authored source sample identity drift")
            return

    receipt["payload_sha256"] = FileAccess.get_sha256(PAYLOAD_PATH)
    receipt["source_identity"] = payload.get("source_identity", {})
    receipt["interpolation_contract"] = contract
    receipt["continuity_metrics"] = payload.get("continuity_metrics", {})
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
    mesh_instance.name = "ExactInterpolatedAnimalProbe"
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

    var maximum_readback_error := 0.0
    var retained := {
        "neutral": {"index": 0, "path": NEUTRAL_CAPTURE},
        "authored_19": {"index": 76, "path": PRE_PEAK_CAPTURE},
        "interior_19p5": {"index": 78, "path": INTERIOR_CAPTURE},
        "peak_20": {"index": 80, "path": PEAK_CAPTURE},
        "last_interior": {"index": 159, "path": LAST_INTERIOR_CAPTURE},
        "final_neutral": {"index": 160, "path": FINAL_CAPTURE}
    }
    var capture_results := {}
    for key in retained.keys():
        var spec: Dictionary = retained[key]
        var index := int(spec["index"])
        maximum_readback_error = maxf(maximum_readback_error, await apply_frame(mesh_instance, frames[index], material))
        var result := await capture(viewport, str(spec["path"]))
        if result.get("state") != "PASS":
            fail("Godot interpolation retained capture failed: " + str(key))
            return
        capture_results[key] = result

    # Exercise every between-sample quarter probe in two exact cycles. The final
    # endpoint at frame 160 duplicates loop-neutral and is applied once after the
    # two 160-probe cycles. Yields prove engine application only, not wall-clock rate.
    var applied_indices := []
    for cycle_index in range(2):
        for frame_index in range(160):
            maximum_readback_error = maxf(
                maximum_readback_error,
                await apply_frame(mesh_instance, frames[frame_index], material)
            )
            applied_indices.append(frame_index)
    maximum_readback_error = maxf(maximum_readback_error, await apply_frame(mesh_instance, frames[160], material))
    applied_indices.append(160)

    var sequence_order_ok := applied_indices.size() == 321
    if sequence_order_ok:
        for cycle_index in range(2):
            for frame_index in range(160):
                if int(applied_indices[cycle_index * 160 + frame_index]) != frame_index:
                    sequence_order_ok = false
        sequence_order_ok = sequence_order_ok and int(applied_indices[-1]) == 160

    # Re-capture final neutral after the full exercise so the roundtrip image is
    # tied to the terminal state, not only the earlier retained probe.
    var final_capture := await capture(viewport, FINAL_CAPTURE)
    if final_capture.get("state") != "PASS":
        fail("Godot final interpolation neutral capture failed")
        return
    capture_results["final_neutral_after_full_sequence"] = final_capture

    var neutral_to_final := pixel_delta(NEUTRAL_CAPTURE, FINAL_CAPTURE)
    var authored19_to_interior := pixel_delta(PRE_PEAK_CAPTURE, INTERIOR_CAPTURE)
    var interior_to_peak := pixel_delta(INTERIOR_CAPTURE, PEAK_CAPTURE)
    if neutral_to_final.get("state") != "PASS" or authored19_to_interior.get("state") != "PASS" or interior_to_peak.get("state") != "PASS":
        fail("Godot interpolation retained image comparison failed")
        return

    var neutral_roundtrip := float(neutral_to_final.get("changed_ratio", 1.0)) <= 0.00010
    receipt["engine_interpolation_application"] = {
        "applied_probe_steps": applied_indices.size(),
        "display_cycle_probe_count": 160,
        "cycles_exercised": 2,
        "final_endpoint_probe": 160,
        "sequence_order_ok": sequence_order_ok,
        "interior_probe_steps_per_cycle": 120,
        "authored_boundary_steps_per_cycle": 40,
        "maximum_vertex_readback_error_m": maximum_readback_error,
        "readback_matches_payload": maximum_readback_error <= 0.000001,
        "one_process_frame_yield_per_probe_application": true,
        "godot_applied_between_sample_positions": true,
        "real_time_frame_pacing_claimed": false,
        "animation_player_or_skeleton_interpolation_claimed": false,
        "runtime_controller_claimed": false
    }
    receipt["retained_visual_probes"] = {
        "captures": capture_results,
        "neutral_to_final": neutral_to_final,
        "authored_19_to_midpoint_19p5": authored19_to_interior,
        "midpoint_19p5_to_peak_20": interior_to_peak,
        "neutral_roundtrip_visually_clean": neutral_roundtrip,
        "visual_quality_acceptance": "NOT_CLAIMED"
    }

    if not sequence_order_ok:
        fail("Godot did not exercise the exact two-cycle interpolation probe order")
        return
    if maximum_readback_error > 0.000001:
        fail("Godot vertex readback drifted from interpolation payload")
        return
    if not neutral_roundtrip:
        fail("Godot terminal neutral did not visually roundtrip to retained neutral")
        return

    receipt["state"] = "PASS_GODOT_CONNECTED_C0_INTERPOLATION_PROBE_HOST"
    receipt["remaining_open"] = [
        "independent Visual Observer and Art Director review of timing, silhouette, pinching, weight and personality",
        "C1 velocity/acceleration continuity and derivative behavior at authored boundaries",
        "real wall-clock target-engine pacing",
        "AnimationPlayer/skeleton/skin/exported clip transport",
        "runtime controller or state-machine integration",
        "continuous self-intersection/collision freedom and gameplay acceptance",
        "target-device performance and production runtime acceptance"
    ]
    write_receipt()
    print("AXM ANIMAL GODOT CONNECTED C0 INTERPOLATION PASS ", JSON.stringify(receipt))
    quit(0)
