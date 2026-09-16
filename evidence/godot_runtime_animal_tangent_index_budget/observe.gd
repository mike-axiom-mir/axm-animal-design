extends SceneTree

const EXPECTED_SCHEMA := "axm.runtime-animal-tangent-index-budget-payload/v0.1"
const CONTROL_MODE := "UNINDEXED_TANGENT_READY_CONTROL"
const CANDIDATE_MODE := "INDEXED_TANGENT_READY_CANDIDATE"
const CONTEXTS := ["three_quarter", "grazing"]
const SETTLE_FRAMES := 4

var receipt: Dictionary = {}

func _arg(args: PackedStringArray, name: String) -> String:
    for i in range(args.size() - 1):
        if args[i] == name:
            return args[i + 1]
    return ""

func _load_json(path: String) -> Dictionary:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        return {}
    var parsed = JSON.parse_string(file.get_as_text())
    file.close()
    return parsed as Dictionary if parsed is Dictionary else {}

func _write_json(path: String, data: Dictionary) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        push_error("cannot write %s" % path)
        quit(90)
        return
    file.store_string(JSON.stringify(data, "  ") + "\n")
    file.close()

func _fail(message: String, out_dir: String) -> void:
    receipt["state"] = "FAIL_RUNTIME_ANIMAL_TANGENT_INDEX_BUDGET"
    receipt["failure"] = message
    receipt["godot_version"] = Engine.get_version_info()
    if not out_dir.is_empty():
        _write_json(out_dir.path_join("runtime.json"), receipt)
    push_error(message)
    quit(1)

func _gvec(raw: Array) -> Vector3:
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1]))

func _gnormal(raw: Array) -> Vector3:
    return _gvec(raw).normalized()

func _guv(raw: Array) -> Vector2:
    return Vector2(float(raw[0]), float(raw[1]))

func _gtangent(raw: Array) -> Plane:
    var xyz := Vector3(float(raw[0]), float(raw[2]), -float(raw[1])).normalized()
    return Plane(xyz, float(raw[3]))

func _runtime_stats() -> Dictionary:
    return {
        "objects_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "primitives_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "draw_calls_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "texture_mem_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
        "buffer_mem_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED),
    }

func _settle(frames: int = SETTLE_FRAMES) -> void:
    for _i in range(frames):
        await process_frame

func _emit_vertex(st: SurfaceTool, positions: Array, normals: Array, uvs: Array, tangents: Array, idx: int) -> void:
    st.set_normal(_gnormal(normals[idx] as Array))
    st.set_uv(_guv(uvs[idx] as Array))
    st.set_tangent(_gtangent(tangents[idx] as Array))
    st.add_vertex(_gvec(positions[idx] as Array))

func _build_mesh(payload: Dictionary, mode: String) -> Dictionary:
    var positions := payload["render_positions"] as Array
    var normals := payload["render_normals"] as Array
    var uvs := payload["render_uvs"] as Array
    var tangents := payload["render_tangents"] as Array
    var indices := payload["render_indices"] as Array
    var st := SurfaceTool.new()
    st.begin(Mesh.PRIMITIVE_TRIANGLES)
    var build_start := Time.get_ticks_usec()

    if mode == CONTROL_MODE:
        for raw_index in indices:
            _emit_vertex(st, positions, normals, uvs, tangents, int(raw_index))
    elif mode == CANDIDATE_MODE:
        for idx in range(positions.size()):
            _emit_vertex(st, positions, normals, uvs, tangents, idx)
        for raw_index in indices:
            st.add_index(int(raw_index))
    else:
        return {"state": "FAIL_UNKNOWN_MODE"}

    var mesh := st.commit() as ArrayMesh
    var build_end := Time.get_ticks_usec()
    if mesh == null or mesh.get_surface_count() != 1:
        return {"state": "FAIL_MESH_COMMIT"}

    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.56, 0.47, 0.38, 1.0)
    material.metallic = 0.0
    material.roughness = 0.63
    material.cull_mode = BaseMaterial3D.CULL_BACK
    mesh.surface_set_material(0, material)

    var vertex_count := mesh.surface_get_array_len(0)
    var index_count := mesh.surface_get_array_index_len(0)
    var primitive_count := index_count / 3 if index_count > 0 else vertex_count / 3
    return {
        "state": "PASS",
        "mesh": mesh,
        "material": material,
        "vertex_count": vertex_count,
        "index_count": index_count,
        "primitive_count": primitive_count,
        "build_usec": int(build_end - build_start),
        "logical_position_normal_uv_tangent_index_bytes": vertex_count * 48 + index_count * 4,
    }

func _bounds(raw_positions: Array) -> Dictionary:
    var min_v := Vector3(INF, INF, INF)
    var max_v := Vector3(-INF, -INF, -INF)
    for raw in raw_positions:
        var p := _gvec(raw as Array)
        min_v.x = minf(min_v.x, p.x)
        min_v.y = minf(min_v.y, p.y)
        min_v.z = minf(min_v.z, p.z)
        max_v.x = maxf(max_v.x, p.x)
        max_v.y = maxf(max_v.y, p.y)
        max_v.z = maxf(max_v.z, p.z)
    var size := max_v - min_v
    return {"center": (min_v + max_v) * 0.5, "radius": maxf(size.x, maxf(size.y, size.z))}

func _place_camera(camera: Camera3D, center: Vector3, radius: float, context: String) -> void:
    var offset := Vector3.ZERO
    if context == "three_quarter":
        offset = Vector3(2.35, 1.05, 2.55) * radius
    elif context == "grazing":
        offset = Vector3(3.35, 0.28, 0.82) * radius
    camera.look_at_from_position(center + offset, center, Vector3.UP)

func _capture(viewport: SubViewport, out_path: String) -> Dictionary:
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        return {"state": "FAIL_CAPTURE"}
    var err := image.save_png(out_path)
    if err != OK:
        return {"state": "FAIL_CAPTURE", "error": err}
    return {"state": "PASS", "width": image.get_width(), "height": image.get_height(), "bytes": FileAccess.get_file_as_bytes(out_path).size()}

func _initialize() -> void:
    var args := OS.get_cmdline_user_args()
    var payload_path := _arg(args, "--payload")
    var out_dir := _arg(args, "--out-dir")
    var mode := _arg(args, "--mode")
    if payload_path.is_empty() or out_dir.is_empty() or mode.is_empty():
        _fail("missing --payload / --out-dir / --mode", out_dir)
        return
    if mode != CONTROL_MODE and mode != CANDIDATE_MODE:
        _fail("unexpected mode", out_dir)
        return
    DirAccess.make_dir_recursive_absolute(out_dir)
    var payload := _load_json(payload_path)
    if payload.get("schema", "") != EXPECTED_SCHEMA:
        _fail("payload schema drift", out_dir)
        return
    if int(payload.get("source_vertex_count", -1)) != 42 or int(payload.get("render_vertex_count", -1)) != 84:
        _fail("source/render vertex count drift", out_dir)
        return
    if int(payload.get("render_index_count", -1)) != 240 or int(payload.get("triangle_count", -1)) != 80:
        _fail("index/triangle count drift", out_dir)
        return

    receipt = {
        "schema": "axm.runtime-animal-tangent-index-budget-observation/v0.1",
        "state": "RUNNING",
        "mode": mode,
        "runtime_head": payload.get("runtime_head", ""),
        "exact_rigging_parent_head": payload.get("exact_rigging_parent_head", ""),
        "exact_geometry_basis_head": payload.get("exact_geometry_basis_head", ""),
        "basis_id": payload.get("basis_id", ""),
        "source_candidate_id": payload.get("source_candidate_id", ""),
        "source_candidate_digest": payload.get("source_candidate_digest", ""),
        "truth_boundary": "Exact Animal Geometry #20 tangent-ready right render domain only. A/B changes storage indexing only: same 84 seam-aware render vertices/attributes, same 240 corner indices / 80 triangles, same material, lighting and cameras. No final UV/tangent appearance, deformed shading, transport, arbitrary-mesh, target-device or CANON claim.",
    }

    var viewport := SubViewport.new()
    viewport.size = Vector2i(960, 720)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)
    var root3d := Node3D.new()
    viewport.add_child(root3d)

    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.018, 0.021, 0.026, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.29, 0.31, 0.35, 1.0)
    env.ambient_light_energy = 0.38
    var world_env := WorldEnvironment.new()
    world_env.environment = env
    root3d.add_child(world_env)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.4
    key.light_color = Color(1.0, 0.94, 0.86, 1.0)
    key.rotation_degrees = Vector3(-48.0, -38.0, 0.0)
    root3d.add_child(key)
    var fill := DirectionalLight3D.new()
    fill.light_energy = 0.75
    fill.light_color = Color(0.72, 0.82, 1.0, 1.0)
    fill.rotation_degrees = Vector3(32.0, 142.0, 0.0)
    root3d.add_child(fill)

    var built := _build_mesh(payload, mode)
    if built.get("state") != "PASS":
        _fail("mesh build failed: %s" % built, out_dir)
        return
    var mesh_instance := MeshInstance3D.new()
    mesh_instance.mesh = built["mesh"]
    root3d.add_child(mesh_instance)

    var camera := Camera3D.new()
    camera.fov = 34.0
    camera.near = 0.01
    camera.far = 20.0
    root3d.add_child(camera)
    camera.make_current()
    await _settle()

    var b := _bounds(payload["render_positions"] as Array)
    var center: Vector3 = b["center"]
    var radius := maxf(float(b["radius"]), 0.001)
    var contexts: Dictionary = {}
    for context_value in CONTEXTS:
        var context := String(context_value)
        _place_camera(camera, center, radius, context)
        await _settle()
        var stats := _runtime_stats()
        if int(stats["objects_in_frame"]) != 1 or int(stats["primitives_in_frame"]) != 80 or int(stats["draw_calls_in_frame"]) != 1:
            _fail("proof camera did not present exact one-object / 80-primitive / one-draw surface in %s: %s" % [context, stats], out_dir)
            return
        var filename := "%s.png" % context
        var capture := _capture(viewport, out_dir.path_join(filename))
        if capture.get("state") != "PASS":
            _fail("capture failed for %s" % context, out_dir)
            return
        contexts[context] = {"runtime": stats, "capture": capture, "filename": filename}

    receipt["state"] = "PASS_RUNTIME_ANIMAL_TANGENT_INDEX_OBSERVATION"
    receipt["representation"] = {
        "surface_count": 1,
        "source_vertex_count": int(payload["source_vertex_count"]),
        "render_vertex_count": int(payload["render_vertex_count"]),
        "source_triangle_count": int(payload["triangle_count"]),
        "stored_vertex_count": int(built["vertex_count"]),
        "stored_index_count": int(built["index_count"]),
        "stored_primitive_count": int(built["primitive_count"]),
        "logical_position_normal_uv_tangent_index_bytes": int(built["logical_position_normal_uv_tangent_index_bytes"]),
        "mesh_build_usec": int(built["build_usec"]),
    }
    receipt["contexts"] = contexts
    receipt["godot_version"] = Engine.get_version_info()
    _write_json(out_dir.path_join("runtime.json"), receipt)
    print("PASS_RUNTIME_ANIMAL_TANGENT_INDEX_OBSERVATION")
    quit(0)
