extends "res://tools/godot_runtime_direction_frame_dynamic_render_probe.gd"

# Harness-only repair: the predecessor tried to orient the Camera3D before it
# entered the SceneTree. Keep the Runtime candidate and all acceptance gates
# unchanged; only establish the camera node before look_at().
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
	_viewport.add_child(camera)
	camera.look_at(center, Vector3.UP)
	camera.current = true

	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.material_override = _build_debug_material()
	_viewport.add_child(_mesh_instance)
