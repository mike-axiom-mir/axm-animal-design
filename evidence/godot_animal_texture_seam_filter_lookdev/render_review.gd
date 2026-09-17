extends Node3D

const EXPECTED_SCHEMA := "axm.animal-materials-transported-frame-lookdev/v0.1"
const EXPECTED_RIGGING_RECONSTRUCTION_HEAD := "81ab44eab2e13bed95187610a476be2b2c4667a7"
const EXPECTED_TECHNICAL_ART_GLB_SHA := "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
const TEXTURE_SIZE := 256
const EDGE_MUTATION_PIXELS := 8
const SEAM_LOCATOR_BAND := 0.08

var payload: Dictionary
var out_dir := ""
var mesh_instance: MeshInstance3D
var camera: Camera3D
var model_center := Vector3.ZERO
var model_radius := 1.0
var candidate_image: Image
var negative_image: Image
var flat_texture: ImageTexture
var candidate_mipped_texture: ImageTexture
var candidate_no_mip_texture: ImageTexture
var negative_mipped_texture: ImageTexture
var mipped_shader: Shader
var no_mip_shader: Shader
var locator_shader: Shader

func _ready() -> void:
    var args := OS.get_cmdline_user_args()
    var payload_path := _arg(args, "--payload")
    out_dir = _arg(args, "--out-dir")
    if payload_path.is_empty() or out_dir.is_empty():
        push_error("missing --payload or --out-dir")
        get_tree().quit(2)
        return
    payload = _load_json(payload_path)
    if payload.get("schema", "") != EXPECTED_SCHEMA:
        push_error("unexpected payload schema")
        get_tree().quit(3)
        return
    if payload.get("exact_rigging_reconstruction_head", "") != EXPECTED_RIGGING_RECONSTRUCTION_HEAD:
        push_error("unexpected Rigging reconstruction provenance")
        get_tree().quit(4)
        return
    if payload.get("exact_technical_art_glb_sha256", "") != EXPECTED_TECHNICAL_ART_GLB_SHA:
        push_error("unexpected Technical Art GLB identity")
        get_tree().quit(5)
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
                    get_tree().quit(6)
                    return
                render_records.append({
                    "filename": filename,
                    "pose_id": pose_id,
                    "sample_index": pose["sample_index"],
                    "time_seconds": pose["time_seconds"],
                    "angle_deg": pose["angle_deg"],
                    "camera_context": context,
                    "texture_mode": mode,
                    "camera_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
                })

    var telemetry := {
        "schema": "axm.animal-materials-texture-seam-filter-lookdev-telemetry/v0.1",
        "godot_version": Engine.get_version_info(),
        "rendering_method": ProjectSettings.get_setting("rendering/renderer/rendering_method"),
        "rendering_device": RenderingServer.get_rendering_device() != null,
        "rigging_reconstruction_head": payload["exact_rigging_reconstruction_head"],
        "technical_art_glb_sha256": payload["exact_technical_art_glb_sha256"],
        "texture_size": TEXTURE_SIZE,
        "edge_mutation_pixels": EDGE_MUTATION_PIXELS,
        "seam_locator_band_uv": SEAM_LOCATOR_BAND,
        "candidate_base_edge_max_rgb_delta_8bit": _base_edge_max_delta(candidate_image),
        "negative_base_edge_max_rgb_delta_8bit": _base_edge_max_delta(negative_image),
        "render_count": render_records.size(),
        "renders": render_records,
        "truth_boundary": {
            "production_normal_map_used": false,
            "all_mipmap_levels_wrap_perfect_claimed": false,
            "technical_art_adoption_claimed": false,
            "runtime_adoption_claimed": false,
            "final_art_or_qa_acceptance_claimed": false,
            "canon_claimed": false,
        },
    }
    var telemetry_path := out_dir.get_base_dir().path_join("target-host-telemetry.json")
    var file := FileAccess.open(telemetry_path, FileAccess.WRITE)
    if file == null:
        push_error("failed to open telemetry output")
        get_tree().quit(7)
        return
    file.store_string(JSON.stringify(telemetry, "  ") + "\n")
    file.close()
    print("PASS_TARGET_HOST_ANIMAL_TEXTURE_SEAM_FILTER_CAPTURED")
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

func _build_stage() -> void:
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

    candidate_image = _make_probe_image(false)
    negative_image = _make_probe_image(true)
    var flat_image := Image.create(TEXTURE_SIZE, TEXTURE_SIZE, false, Image.FORMAT_RGBA8)
    flat_image.fill(Color(0.5, 0.5, 1.0, 1.0))

    var flat_mipped := flat_image.duplicate()
    flat_mipped.generate_mipmaps()
    flat_texture = ImageTexture.create_from_image(flat_mipped)

    var candidate_mipped := candidate_image.duplicate()
    candidate_mipped.generate_mipmaps()
    candidate_mipped_texture = ImageTexture.create_from_image(candidate_mipped)
    candidate_no_mip_texture = ImageTexture.create_from_image(candidate_image)

    var negative_mipped := negative_image.duplicate()
    negative_mipped.generate_mipmaps()
    negative_mipped_texture = ImageTexture.create_from_image(negative_mipped)

    mipped_shader = Shader.new()
    mipped_shader.code = """
shader_type spatial;
render_mode cull_back;
uniform sampler2D normal_tex : filter_linear_mipmap, repeat_enable;
void fragment() {
    ALBEDO = vec3(0.46, 0.49, 0.53);
    METALLIC = 0.0;
    ROUGHNESS = 0.5;
    NORMAL_MAP = texture(normal_tex, UV).rgb;
    NORMAL_MAP_DEPTH = 1.0;
}
"""
    no_mip_shader = Shader.new()
    no_mip_shader.code = """
shader_type spatial;
render_mode cull_back;
uniform sampler2D normal_tex : filter_linear, repeat_enable;
void fragment() {
    ALBEDO = vec3(0.46, 0.49, 0.53);
    METALLIC = 0.0;
    ROUGHNESS = 0.5;
    NORMAL_MAP = texture(normal_tex, UV).rgb;
    NORMAL_MAP_DEPTH = 1.0;
}
"""
    locator_shader = Shader.new()
    locator_shader.code = """
shader_type spatial;
render_mode unshaded, cull_back;
uniform float seam_band = 0.08;
void fragment() {
    float wrapped_u = fract(UV.x);
    float edge_distance = min(wrapped_u, 1.0 - wrapped_u);
    float mask = 1.0 - step(seam_band, edge_distance);
    ALBEDO = mix(vec3(0.0), vec3(1.0, 0.0, 0.0), mask);
}
"""

func _make_probe_image(seam_mutated: bool) -> Image:
    var image := Image.create(TEXTURE_SIZE, TEXTURE_SIZE, false, Image.FORMAT_RGBA8)
    for y in range(TEXTURE_SIZE):
        var v := float(y) / float(TEXTURE_SIZE - 1)
        for x in range(TEXTURE_SIZE):
            var u := float(x) / float(TEXTURE_SIZE - 1)
            var tx := 0.28 * sin(u * TAU * 4.0)
            var ty := 0.20 * cos(v * TAU * 3.0)
            if seam_mutated:
                if x < EDGE_MUTATION_PIXELS:
                    var left_strength := 1.0 - float(x) / float(EDGE_MUTATION_PIXELS)
                    tx += 0.42 * left_strength
                elif x >= TEXTURE_SIZE - EDGE_MUTATION_PIXELS:
                    var right_distance := float(TEXTURE_SIZE - 1 - x)
                    var right_strength := 1.0 - right_distance / float(EDGE_MUTATION_PIXELS)
                    tx -= 0.42 * right_strength
            var tangent_normal := Vector3(tx, ty, 1.0).normalized()
            image.set_pixel(x, y, Color(tangent_normal.x * 0.5 + 0.5, tangent_normal.y * 0.5 + 0.5, tangent_normal.z * 0.5 + 0.5, 1.0))
    return image

func _base_edge_max_delta(image: Image) -> int:
    var maximum := 0
    for y in range(TEXTURE_SIZE):
        var a := image.get_pixel(0, y)
        var b := image.get_pixel(TEXTURE_SIZE - 1, y)
        maximum = maxi(maximum, absi(int(round(a.r * 255.0)) - int(round(b.r * 255.0))))
        maximum = maxi(maximum, absi(int(round(a.g * 255.0)) - int(round(b.g * 255.0))))
        maximum = maxi(maximum, absi(int(round(a.b * 255.0)) - int(round(b.b * 255.0))))
    return maximum

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

func _place_camera(context: String) -> void:
    var offset := Vector3.ZERO
    if context == "three_quarter":
        offset = Vector3(2.35, 1.05, 2.55) * model_radius
    elif context == "grazing":
        offset = Vector3(3.35, 0.28, 0.82) * model_radius
    else:
        push_error("unknown camera context: %s" % context)
        get_tree().quit(8)
        return
    camera.global_position = model_center + offset
    camera.look_at(model_center, Vector3.UP)

func _to_godot(raw: Array) -> Vector3:
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1]))

func _to_godot_direction(raw: Array) -> Vector3:
    return Vector3(float(raw[0]), float(raw[2]), -float(raw[1])).normalized()

func _set_mesh(pose: Dictionary, mode: String) -> void:
    var variants: Dictionary = pose["frame_variants"]
    if not variants.has("position_reconstructed"):
        push_error("position-reconstructed frame missing")
        get_tree().quit(9)
        return
    var variant: Dictionary = variants["position_reconstructed"]
    var positions: Array = pose["render_positions"]
    var normals: Array = variant["render_normals"]
    var uvs: Array = pose["render_uvs"]
    var tangents: Array = variant["render_tangents"]
    var indices: Array = pose["render_indices"]
    if positions.size() != 84 or normals.size() != 84 or uvs.size() != 84 or tangents.size() != 84:
        push_error("unexpected render-domain attribute count")
        get_tree().quit(10)
        return
    if indices.size() != 240:
        push_error("unexpected render-index count")
        get_tree().quit(11)
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
        push_error("unknown texture mode: %s" % mode)
        get_tree().quit(12)
        return
    mesh.surface_set_material(0, material)
    mesh_instance.mesh = mesh
