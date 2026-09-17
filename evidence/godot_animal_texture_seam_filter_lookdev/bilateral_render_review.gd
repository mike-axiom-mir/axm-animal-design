extends "res://render_review.gd"

const BILATERAL_EXPECTED_SCHEMA := "axm.animal-materials-tangent-space-lookdev/v0.1"
const BILATERAL_EXPECTED_RIGGING_TANGENT_HEAD := "63c65d57fda0595217f86d971ff8c67f256188be"
const BILATERAL_EXPECTED_GEOMETRY_HEAD := "ca4bb8a2f144231f8755eacc980785d1807b79db"

func _ready() -> void:
    var args := OS.get_cmdline_user_args()
    var payload_path := _arg(args, "--payload")
    out_dir = _arg(args, "--out-dir")
    if payload_path.is_empty() or out_dir.is_empty():
        push_error("missing --payload or --out-dir")
        get_tree().quit(2)
        return
    payload = _load_json(payload_path)
    if payload.get("schema", "") != BILATERAL_EXPECTED_SCHEMA:
        push_error("unexpected bilateral payload schema")
        get_tree().quit(3)
        return
    if payload.get("exact_rigging_tangent_head", "") != BILATERAL_EXPECTED_RIGGING_TANGENT_HEAD:
        push_error("unexpected Rigging tangent provenance")
        get_tree().quit(4)
        return
    if payload.get("exact_geometry_uv_tangent_head", "") != BILATERAL_EXPECTED_GEOMETRY_HEAD:
        push_error("unexpected Geometry UV/tangent provenance")
        get_tree().quit(5)
        return
    if int(payload.get("budget", {}).get("side_count", 0)) != 2:
        push_error("bilateral payload does not contain two sides")
        get_tree().quit(6)
        return

    DirAccess.make_dir_recursive_absolute(out_dir)
    _build_stage()
    _measure_all_bounds(payload["pose_sets"])
    await get_tree().process_frame
    await get_tree().process_frame

    var render_records: Array = []
    var modes := ["flat_control", "periodic_mipped", "periodic_no_mip", "edge_mutated_mipped_negative", "seam_locator"]
    for raw_pose in payload["pose_sets"]:
        var pose: Dictionary = raw_pose
        var pose_id := str(pose["pose_id"])
        for context in payload["camera_contexts"]:
            _place_camera(str(context))
            for mode in modes:
                _set_mesh(pose, str(mode))
                await get_tree().process_frame
                await get_tree().process_frame
                var filename := "%s__%s__%s.png" % [pose_id, context, mode]
                var path := out_dir.path_join(filename)
                var image := get_viewport().get_texture().get_image()
                var error := image.save_png(path)
                if error != OK:
                    push_error("failed to save %s: %s" % [path, error])
                    get_tree().quit(7)
                    return
                render_records.append({
                    "filename": filename,
                    "pose_id": pose_id,
                    "side": pose["side"],
                    "weighting": pose["weighting"],
                    "angle_deg": pose["angle_deg"],
                    "camera_context": context,
                    "texture_mode": mode,
                    "camera_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
                })

    var telemetry := {
        "schema": "axm.animal-materials-texture-seam-filter-bilateral-lookdev-telemetry/v0.1",
        "godot_version": Engine.get_version_info(),
        "rendering_method": ProjectSettings.get_setting("rendering/renderer/rendering_method"),
        "rendering_device": RenderingServer.get_rendering_device() != null,
        "rigging_tangent_head": payload["exact_rigging_tangent_head"],
        "geometry_uv_tangent_head": payload["exact_geometry_uv_tangent_head"],
        "texture_size": TEXTURE_SIZE,
        "edge_mutation_pixels": EDGE_MUTATION_PIXELS,
        "seam_locator_band_uv": SEAM_LOCATOR_BAND,
        "candidate_base_edge_max_rgb_delta_8bit": _base_edge_max_delta(candidate_image),
        "negative_base_edge_max_rgb_delta_8bit": _base_edge_max_delta(negative_image),
        "render_count": render_records.size(),
        "renders": render_records,
        "truth_boundary": {
            "bilateral_real_renderer_sampling_exercised": true,
            "production_normal_map_used": false,
            "all_mipmap_levels_wrap_perfect_claimed": false,
            "technical_art_transport_claimed": false,
            "runtime_adoption_claimed": false,
            "final_art_or_qa_acceptance_claimed": false,
            "canon_claimed": false,
        },
    }
    var telemetry_path := out_dir.get_base_dir().path_join("target-host-telemetry.json")
    var file := FileAccess.open(telemetry_path, FileAccess.WRITE)
    if file == null:
        push_error("failed to open telemetry output")
        get_tree().quit(8)
        return
    file.store_string(JSON.stringify(telemetry, "  ") + "\n")
    file.close()
    print("PASS_TARGET_HOST_ANIMAL_BILATERAL_TEXTURE_SEAM_FILTER_CAPTURED")
    get_tree().quit(0)

func _set_mesh(pose: Dictionary, mode: String) -> void:
    var positions: Array = pose["render_positions"]
    var normals: Array = pose["render_normals"]
    var uvs: Array = pose["render_uvs"]
    var tangents: Array = pose["render_tangents"]
    var indices: Array = pose["render_indices"]
    if positions.size() != 84 or normals.size() != 84 or uvs.size() != 84 or tangents.size() != 84:
        push_error("unexpected bilateral render-domain attribute count")
        get_tree().quit(9)
        return
    if indices.size() != 240:
        push_error("unexpected bilateral render-index count")
        get_tree().quit(10)
        return

    var st := SurfaceTool.new()
    st.begin(Mesh.PRIMITIVE_TRIANGLES)
    for raw_index in indices:
        var idx := int(raw_index)
        var normal := _to_godot_direction(normals[idx])
        var tangent_xyz := _to_godot_direction(tangents[idx])
        var tangent_w := float(tangents[idx][3])
        st.set_normal(normal)
        st.set_uv(Vector2(float(uvs[idx][0]), float(uvs[idx][1])))
        st.set_tangent(Plane(tangent_xyz.x, tangent_xyz.y, tangent_xyz.z, tangent_w))
        st.add_vertex(_to_godot(positions[idx]))
    var mesh := st.commit()
    var material := ShaderMaterial.new()
    if mode == "flat_control":
        material.shader = mipped_shader
        material.set_shader_parameter("normal_tex", flat_texture)
    elif mode == "periodic_mipped":
        material.shader = mipped_shader
        material.set_shader_parameter("normal_tex", candidate_mipped_texture)
    elif mode == "periodic_no_mip":
        material.shader = no_mip_shader
        material.set_shader_parameter("normal_tex", candidate_no_mip_texture)
    elif mode == "edge_mutated_mipped_negative":
        material.shader = mipped_shader
        material.set_shader_parameter("normal_tex", negative_mipped_texture)
    elif mode == "seam_locator":
        material.shader = locator_shader
        material.set_shader_parameter("seam_band", SEAM_LOCATOR_BAND)
    else:
        push_error("unknown bilateral texture mode: %s" % mode)
        get_tree().quit(11)
        return
    mesh.surface_set_material(0, material)
    mesh_instance.mesh = mesh
