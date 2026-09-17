extends Node3D

const EXPECTED_SCHEMA := "axm.animal-materials-tangent-space-lookdev/v0.1"
const EXPECTED_RIGGING_TANGENT_HEAD := "63c65d57fda0595217f86d971ff8c67f256188be"
const EXPECTED_RIGGING_TANGENT_MODULE_BLOB := "fbade964b3305d70775d196232ad2cd4671d0eac"
const EXPECTED_GEOMETRY_HEAD := "ca4bb8a2f144231f8755eacc980785d1807b79db"
const EXPECTED_GEOMETRY_MODULE_BLOB := "ba0b4e620f132413606177358e47bd32ae4d4965"

var payload: Dictionary
var out_dir := ""
var mesh_instance: MeshInstance3D
var camera: Camera3D
var model_center := Vector3.ZERO
var model_radius := 1.0
var probe_shader: Shader

func _ready() -> void:
    var args := OS.get_cmdline_user_args()
    var payload_path := _arg(args, "--payload")
    out_dir = _arg(args, "--out-dir")
    var rigging_head := _arg(args, "--rigging-tangent-head")
    var rigging_blob := _arg(args, "--rigging-tangent-module-blob")
    var geometry_head := _arg(args, "--geometry-head")
    var geometry_blob := _arg(args, "--geometry-module-blob")
    if payload_path.is_empty() or out_dir.is_empty():
        push_error("missing --payload or --out-dir")
        get_tree().quit(2)
        return
    if rigging_head != EXPECTED_RIGGING_TANGENT_HEAD or rigging_blob != EXPECTED_RIGGING_TANGENT_MODULE_BLOB:
        push_error("unexpected Rigging tangent provenance")
        get_tree().quit(3)
        return
    if geometry_head != EXPECTED_GEOMETRY_HEAD or geometry_blob != EXPECTED_GEOMETRY_MODULE_BLOB:
        push_error("unexpected Geometry UV/tangent provenance")
        get_tree().quit(4)
        return

    payload = _load_json(payload_path)
    if payload.get("schema", "") != EXPECTED_SCHEMA:
        push_error("unexpected payload schema")
        get_tree().quit(5)
        return
    if payload.get("exact_rigging_tangent_head", "") != rigging_head:
        push_error("payload Rigging tangent head mismatch")
        get_tree().quit(6)
        return
    if payload.get("exact_rigging_tangent_module_blob", "") != rigging_blob:
        push_error("payload Rigging tangent module blob mismatch")
        get_tree().quit(7)
        return
    if payload.get("exact_geometry_uv_tangent_head", "") != geometry_head:
        push_error("payload Geometry head mismatch")
        get_tree().quit(8)
        return
    if payload.get("exact_geometry_uv_tangent_module_blob", "") != geometry_blob:
        push_error("payload Geometry module blob mismatch")
        get_tree().quit(9)
        return

    DirAccess.make_dir_recursive_absolute(out_dir)
    _build_probe_stage()
    _measure_all_bounds(payload["pose_sets"])
    await get_tree().process_frame
    await get_tree().process_frame

    var render_records: Array = []
    for raw_pose in payload["pose_sets"]:
        var pose: Dictionary = raw_pose
        var pose_file_id := _safe_id(str(pose["pose_id"]))
        for context in payload["camera_contexts"]:
            _place_camera(str(context), str(pose["side"]))
            for shader_mode in payload["shader_modes"]:
                _set_mesh(pose, str(shader_mode))
                await get_tree().process_frame
                await get_tree().process_frame
                var filename := "%s__%s__%s.png" % [pose_file_id, context, shader_mode]
                var path := out_dir.path_join(filename)
                var image := get_viewport().get_texture().get_image()
                var error := image.save_png(path)
                if error != OK:
                    push_error("failed to save %s: %s" % [path, error])
                    get_tree().quit(10)
                    return
                render_records.append({
                    "filename": filename,
                    "pose_id": pose["pose_id"],
                    "side": pose["side"],
                    "weighting": pose["weighting"],
                    "angle_deg": pose["angle_deg"],
                    "camera_context": context,
                    "shader_mode": shader_mode,
                    "camera_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
                })

    var telemetry := {
        "schema": "axm.animal-materials-tangent-space-lookdev-telemetry/v0.1",
        "godot_version": Engine.get_version_info(),
        "rendering_method": ProjectSettings.get_setting("rendering/renderer/rendering_method"),
        "rendering_device": RenderingServer.get_rendering_device() != null,
        "rigging_tangent_head": rigging_head,
        "rigging_tangent_module_blob": rigging_blob,
        "geometry_uv_tangent_head": geometry_head,
        "geometry_uv_tangent_module_blob": geometry_blob,
        "model_center_godot": [model_center.x, model_center.y, model_center.z],
        "model_radius": model_radius,
        "probe_material": payload["probe_material"],
        "render_count": render_records.size(),
        "renders": render_records,
        "truth_boundary": {
            "production_material_is_assigned": false,
            "external_normal_texture_is_used": false,
            "procedural_tangent_space_probe_is_rendered": true,
            "deliberate_handedness_mutation_is_rendered": true,
            "continuous_motion_visual_quality_is_proven": false,
            "production_skin_tangent_transport_is_tested": false,
            "target_engine_import_equivalence_is_tested": false,
            "target_device_performance_is_tested": false,
            "final_visual_acceptance_is_claimed": false,
            "canon_is_claimed": false,
        },
    }
    var telemetry_path := out_dir.get_base_dir().path_join("target-host-telemetry.json")
    var file := FileAccess.open(telemetry_path, FileAccess.WRITE)
    if file == null:
        push_error("failed to open telemetry output")
        get_tree().quit(11)
        return
    file.store_string(JSON.stringify(telemetry, "  ") + "\n")
    file.close()
    print("PASS_TARGET_HOST_TANGENT_SPACE_DIAGNOSTIC_CAPTURED")
    get_tree().quit(0)

func _arg(args: PackedStringArray, name: String) -> String:
    for i in range(args.size() - 1):
        if args[i] == name:
            return args[i + 1]
    return ""

func _safe_id(value: String) -> String:
    return value.replace("+", "p").replace("-", "m").replace(".", "p")

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

    probe_shader = Shader.new()
    probe_shader.code = """
shader_type spatial;
render_mode cull_back;
uniform bool tangent_probe = false;
uniform float u_cycles = 4.0;
uniform float v_cycles = 3.0;
uniform float tangent_amplitude = 0.28;
uniform float bitangent_amplitude = 0.20;
void fragment() {
    ALBEDO = vec3(0.46, 0.49, 0.53);
    METALLIC = 0.0;
    ROUGHNESS = 0.5;
    if (tangent_probe) {
        float tx = tangent_amplitude * sin(UV.x * 6.28318530718 * u_cycles);
        float ty = bitangent_amplitude * cos(UV.y * 6.28318530718 * v_cycles);
        vec3 tangent_normal = normalize(vec3(tx, ty, 1.0));
        NORMAL_MAP = tangent_normal * 0.5 + 0.5;
    } else {
        NORMAL_MAP = vec3(0.5, 0.5, 1.0);
    }
    NORMAL_MAP_DEPTH = 1.0;
}
"""

func _measure_all_bounds(pose_sets: Array) -> void:
    var min_v := Vector3(INF, INF, INF)
    var max_v := Vector3(-INF, -INF, -INF)
    for raw_pose in pose_sets:
        var pose: Dictionary = raw_pose
        for raw in pose["render_positions"]:
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

func _place_camera(context: String, side: String) -> void:
    var offset := Vector3.ZERO
    if context == "three_quarter":
        offset = Vector3(2.35, 1.05, 2.55) * model_radius
    elif context == "grazing":
        offset = Vector3(3.35, 0.28, 0.82) * model_radius
    else:
        push_error("unknown camera context: %s" % context)
        get_tree().quit(12)
        return
    # Mirror the depth component for the left side so bilateral corresponding
    # views observe the same semantic surface rather than opposite sides.
    if side == "left":
        offset.z = -offset.z
    camera.global_position = model_center + offset
    camera.look_at(model_center, Vector3.UP)

func _to_godot(raw: Array) -> Vector3:
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1]))

func _to_godot_direction(raw: Array) -> Vector3:
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1])).normalized()

func _set_mesh(pose: Dictionary, shader_mode: String) -> void:
    var positions: Array = pose["render_positions"]
    var normals: Array = pose["render_normals"]
    var uvs: Array = pose["render_uvs"]
    var tangents: Array = pose["render_tangents"]
    var indices: Array = pose["render_indices"]
    if positions.size() != 84 or normals.size() != 84 or uvs.size() != 84 or tangents.size() != 84:
        push_error("unexpected render-domain attribute count")
        get_tree().quit(13)
        return
    if indices.size() != 240:
        push_error("unexpected render-index count")
        get_tree().quit(14)
        return

    var mutate_handedness := shader_mode == "flipped_handedness_mutation"
    var tangent_probe := shader_mode != "flat_tangent_control"
    if shader_mode != "flat_tangent_control" and shader_mode != "periodic_tangent_probe" and not mutate_handedness:
        push_error("unknown shader mode: %s" % shader_mode)
        get_tree().quit(15)
        return

    var st := SurfaceTool.new()
    st.begin(Mesh.PRIMITIVE_TRIANGLES)
    for raw_index in indices:
        var idx := int(raw_index)
        var normal := _to_godot_direction(normals[idx])
        var tangent_xyz := _to_godot_direction(tangents[idx])
        var tangent_w := float(tangents[idx][3])
        if mutate_handedness:
            tangent_w = -tangent_w
        st.set_normal(normal)
        st.set_uv(Vector2(float(uvs[idx][0]), float(uvs[idx][1])))
        st.set_tangent(Plane(tangent_xyz.x, tangent_xyz.y, tangent_xyz.z, tangent_w))
        st.add_vertex(_to_godot(positions[idx]))
    var mesh := st.commit()

    var material := ShaderMaterial.new()
    material.shader = probe_shader
    material.set_shader_parameter("tangent_probe", tangent_probe)
    material.set_shader_parameter("u_cycles", float(payload["probe_material"]["u_cycles"]))
    material.set_shader_parameter("v_cycles", float(payload["probe_material"]["v_cycles"]))
    material.set_shader_parameter("tangent_amplitude", float(payload["probe_material"]["tangent_amplitude"]))
    material.set_shader_parameter("bitangent_amplitude", float(payload["probe_material"]["bitangent_amplitude"]))
    mesh.surface_set_material(0, material)
    mesh_instance.mesh = mesh
