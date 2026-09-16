extends Node3D

const EXPECTED_SCHEMA := "axm.animal-materials-bilateral-topology-shading-review/v0.1"
const EXPECTED_GEOMETRY_HEAD := "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
const EXPECTED_GEOMETRY_MODULE_BLOB := "9a0ebcc6169445996756bb446a87e3baf8b9cc33"

var payload: Dictionary
var out_dir := ""
var exact_head := ""
var geometry_module_blob := ""
var mesh_instance: MeshInstance3D
var camera: Camera3D
var model_center := Vector3.ZERO
var model_radius := 1.0

func _ready() -> void:
    var args := OS.get_cmdline_user_args()
    var payload_path := _arg(args, "--payload")
    out_dir = _arg(args, "--out-dir")
    exact_head = _arg(args, "--geometry-head")
    geometry_module_blob = _arg(args, "--geometry-module-blob")
    if payload_path.is_empty() or out_dir.is_empty():
        push_error("missing --payload or --out-dir")
        get_tree().quit(2)
        return
    if exact_head != EXPECTED_GEOMETRY_HEAD or geometry_module_blob != EXPECTED_GEOMETRY_MODULE_BLOB:
        push_error("unexpected exact Geometry provenance")
        get_tree().quit(3)
        return

    payload = _load_json(payload_path)
    if payload.get("schema", "") != EXPECTED_SCHEMA:
        push_error("unexpected payload schema")
        get_tree().quit(4)
        return
    if payload.get("exact_geometry_donor_head", "") != exact_head:
        push_error("payload Geometry donor head mismatch")
        get_tree().quit(5)
        return
    if payload.get("exact_geometry_module_blob", "") != geometry_module_blob:
        push_error("payload Geometry module blob mismatch")
        get_tree().quit(6)
        return

    DirAccess.make_dir_recursive_absolute(out_dir)
    _build_probe_stage()
    _measure_model_bounds(payload["variants"]["historical_right"]["positions"])
    await get_tree().process_frame
    await get_tree().process_frame

    var render_records: Array = []
    for normal_mode in payload["normal_modes"]:
        for context in payload["camera_contexts"]:
            _place_camera(context)
            for variant_name in ["historical_right", "exact_mirror_right"]:
                _set_mesh(payload["variants"][variant_name], normal_mode)
                await get_tree().process_frame
                await RenderingServer.frame_post_draw
                var filename := "%s-%s-%s.png" % [normal_mode, context, variant_name]
                var path := out_dir.path_join(filename)
                var image := get_viewport().get_texture().get_image()
                var error := image.save_png(path)
                if error != OK:
                    push_error("failed to save %s: %s" % [path, error])
                    get_tree().quit(7)
                    return
                render_records.append({
                    "filename": filename,
                    "normal_mode": normal_mode,
                    "camera_context": context,
                    "variant": variant_name,
                    "camera_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
                })

    var telemetry := {
        "schema": "axm.animal-materials-bilateral-topology-shading-review-telemetry/v0.1",
        "godot_version": Engine.get_version_info(),
        "rendering_method": ProjectSettings.get_setting("rendering/renderer/rendering_method"),
        "rendering_device": RenderingServer.get_rendering_device() != null,
        "geometry_donor_head": exact_head,
        "geometry_module_blob": geometry_module_blob,
        "model_center_godot": [model_center.x, model_center.y, model_center.z],
        "model_radius": model_radius,
        "probe_material": payload["neutral_probe_material"],
        "render_count": render_records.size(),
        "renders": render_records,
        "truth_boundary": {
            "probe_lighting_is_final_art_direction": false,
            "production_material_is_assigned": false,
            "authored_normals_or_tangents_are_tested": false,
            "target_device_performance_is_tested": false,
            "canon_is_claimed": false,
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
    print("PASS_TARGET_HOST_BILATERAL_TOPOLOGY_SHADING_REVIEW_CAPTURED")
    get_tree().quit(0)

func _arg(args: PackedStringArray, name: String) -> String:
    for i in range(args.size() - 1):
        if args[i] == name:
            return args[i + 1]
    return ""

func _load_json(path: String) -> Dictionary:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        push_error("unable to read payload: %s" % path)
        return {}
    var parsed = JSON.parse_string(file.get_as_text())
    file.close()
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("payload is not a JSON object")
        return {}
    return parsed

func _build_probe_stage() -> void:
    var world_env := WorldEnvironment.new()
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.018, 0.021, 0.026, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.29, 0.31, 0.35, 1.0)
    env.ambient_light_energy = 0.38
    world_env.environment = env
    add_child(world_env)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.4
    key.light_color = Color(1.0, 0.94, 0.86, 1.0)
    key.rotation_degrees = Vector3(-48.0, -38.0, 0.0)
    key.shadow_enabled = false
    add_child(key)

    var fill := DirectionalLight3D.new()
    fill.light_energy = 0.75
    fill.light_color = Color(0.72, 0.82, 1.0, 1.0)
    fill.rotation_degrees = Vector3(32.0, 142.0, 0.0)
    fill.shadow_enabled = false
    add_child(fill)

    camera = Camera3D.new()
    camera.fov = 34.0
    camera.near = 0.01
    camera.far = 20.0
    add_child(camera)
    camera.current = true

    mesh_instance = MeshInstance3D.new()
    add_child(mesh_instance)

func _measure_model_bounds(source_positions: Array) -> void:
    var min_v := Vector3(INF, INF, INF)
    var max_v := Vector3(-INF, -INF, -INF)
    for raw in source_positions:
        var p := _to_godot(raw)
        min_v.x = min(min_v.x, p.x)
        min_v.y = min(min_v.y, p.y)
        min_v.z = min(min_v.z, p.z)
        max_v.x = max(max_v.x, p.x)
        max_v.y = max(max_v.y, p.y)
        max_v.z = max(max_v.z, p.z)
    model_center = (min_v + max_v) * 0.5
    var size := max_v - min_v
    model_radius = max(size.x, max(size.y, size.z))
    if model_radius <= 0.0001:
        model_radius = 1.0

func _place_camera(context: String) -> void:
    var offset := Vector3.ZERO
    if context == "three_quarter":
        offset = Vector3(2.35, 1.05, 2.55) * model_radius
    elif context == "grazing":
        offset = Vector3(3.35, 0.28, 0.82) * model_radius
    else:
        push_error("unknown camera context: %s" % context)
        get_tree().quit(9)
        return
    camera.global_position = model_center + offset
    camera.look_at(model_center, Vector3.UP)

func _to_godot(raw: Array) -> Vector3:
    # Source data is Z-up. This is a proper rotation into Godot Y-up:
    # (x, y, z)_source -> (x, z, -y)_godot.
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1]))

func _set_mesh(variant: Dictionary, normal_mode: String) -> void:
    var raw_positions: Array = variant["positions"]
    var indices: Array = variant["indices"]
    var positions: Array[Vector3] = []
    for raw in raw_positions:
        positions.append(_to_godot(raw))

    var smooth_normals: Array[Vector3] = []
    if normal_mode == "vertex_smooth":
        smooth_normals.resize(positions.size())
        for i in range(smooth_normals.size()):
            smooth_normals[i] = Vector3.ZERO
        for offset in range(0, indices.size(), 3):
            var ia := int(indices[offset])
            var ib := int(indices[offset + 1])
            var ic := int(indices[offset + 2])
            var face_area_normal := (positions[ib] - positions[ia]).cross(positions[ic] - positions[ia])
            smooth_normals[ia] += face_area_normal
            smooth_normals[ib] += face_area_normal
            smooth_normals[ic] += face_area_normal
        for i in range(smooth_normals.size()):
            smooth_normals[i] = smooth_normals[i].normalized()
    elif normal_mode != "face_split":
        push_error("unknown normal mode: %s" % normal_mode)
        get_tree().quit(10)
        return

    var st := SurfaceTool.new()
    st.begin(Mesh.PRIMITIVE_TRIANGLES)
    for offset in range(0, indices.size(), 3):
        var ia := int(indices[offset])
        var ib := int(indices[offset + 1])
        var ic := int(indices[offset + 2])
        var face_normal := (positions[ib] - positions[ia]).cross(positions[ic] - positions[ia]).normalized()
        for idx in [ia, ib, ic]:
            if normal_mode == "vertex_smooth":
                st.set_normal(smooth_normals[idx])
            else:
                st.set_normal(face_normal)
            st.add_vertex(positions[idx])
    var mesh := st.commit()

    var material := StandardMaterial3D.new()
    var material_spec: Dictionary = payload["neutral_probe_material"]
    var albedo: Array = material_spec["albedo_srgb"]
    material.albedo_color = Color(float(albedo[0]), float(albedo[1]), float(albedo[2]), float(albedo[3]))
    material.metallic = float(material_spec["metallic"])
    material.roughness = float(material_spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    mesh.surface_set_material(0, material)
    mesh_instance.mesh = mesh
