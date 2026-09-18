extends SceneTree

const PAYLOAD_PATH := "res://generated/payload.json"
const RECEIPT_PATH := "res://generated/godot_receipt.json"
const HOST_REFERENCE_LIMIT_PHYSICAL_DEG := 0.0025
const PAIR_REFERENCE_LIMIT_PHYSICAL_DEG := 0.0025
const NEGATIVE_MIN_PHYSICAL_SIGNAL_DEG := 0.20
const NOMINAL_RUNTIME_TOLERANCE_DEG := 0.075

var receipt := {
    "schema": "axm.animal-animation-runtime-key-budget-rebind-godot/v0.1",
    "proof_runtime": "Godot 4.7.2",
    "proof_mode": "DETERMINISTIC_DUAL_ANIMATIONPLAYER_SEEK_READBACK_NOT_WALLCLOCK_PACING",
    "promotion_effect": "NONE",
    "runtime_representation_adopted": false,
    "runtime_controller_acceptance": false,
    "gameplay_acceptance": false
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

func quat_from_row(row) -> Quaternion:
    return Quaternion(float(row[0]), float(row[1]), float(row[2]), float(row[3])).normalized()

func shortest_quaternion_chord(a: Quaternion, b: Quaternion) -> float:
    var qa := a.normalized()
    var qb := b.normalized()
    var direct := Vector4(qa.x - qb.x, qa.y - qb.y, qa.z - qb.z, qa.w - qb.w).length()
    var negated := Vector4(qa.x + qb.x, qa.y + qb.y, qa.z + qb.z, qa.w + qb.w).length()
    return clampf(minf(direct, negated), 0.0, 2.0)

func runtime_half_angle_deg(a: Quaternion, b: Quaternion) -> float:
    # This deliberately reproduces Runtime PR #30's retained qerr semantics.
    # For unit rotation quaternions it is half of the shortest physical
    # relative-rotation angle, despite its historical "deg" name.
    return rad_to_deg(2.0 * asin(shortest_quaternion_chord(a, b) * 0.5))

func physical_rotation_deg(a: Quaternion, b: Quaternion) -> float:
    return 2.0 * runtime_half_angle_deg(a, b)

func build_player(host: Node3D, probe_name: String, player_name: String, keys) -> Dictionary:
    var probe := Node3D.new()
    probe.name = probe_name
    host.add_child(probe)

    var player := AnimationPlayer.new()
    player.name = player_name
    player.root_node = NodePath("..")
    host.add_child(player)

    var animation := Animation.new()
    animation.length = 1.0
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_ROTATION_3D)
    animation.track_set_path(track, NodePath(probe_name))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
    for key in keys:
        animation.track_insert_key(track, float(key.get("time_s", 0.0)), quat_from_row(key.get("quaternion_xyzw", [0, 0, 0, 1])))

    var library := AnimationLibrary.new()
    library.add_animation("probe", animation)
    player.add_animation_library("", library)
    player.play("probe")
    player.pause()
    return {"probe": probe, "player": player, "animation": animation, "track": track}

func _initialize() -> void:
    if not FileAccess.file_exists(PAYLOAD_PATH):
        fail("key-budget rebind payload missing")
        return
    var payload = JSON.parse_string(FileAccess.get_file_as_string(PAYLOAD_PATH))
    if payload == null or not (payload is Dictionary):
        fail("payload is not valid JSON")
        return
    if str(payload.get("schema", "")) != "axm.animal-animation-runtime-key-budget-rebind-payload/v0.1":
        fail("unexpected payload schema")
        return

    var control_keys = payload.get("control_keys", [])
    var candidate_keys = payload.get("candidate_keys", [])
    var dense: Dictionary = payload.get("dense_reference", {})
    var samples = dense.get("samples", [])
    if control_keys.size() != 41 or candidate_keys.size() != 19 or samples.size() != 321:
        fail("exact key/sample counts drift")
        return
    if int(dense.get("diagnostic_rate_hz", 0)) != 320:
        fail("diagnostic rate drift")
        return

    var semantics: Dictionary = payload.get("metric_semantics", {})
    if bool(semantics.get("animation_representation_adopted", true)):
        fail("payload silently adopted Runtime candidate")
        return
    if bool(semantics.get("owner_angle_semantics_resolved", true)):
        fail("payload silently resolved owner-angle policy")
        return
    if not bool(semantics.get("runtime_metric_below_declared_tolerance", false)):
        fail("Runtime half-angle condition no longer reproduced")
        return
    if not bool(semantics.get("physical_rotation_above_same_numeric_tolerance", false)):
        fail("physical-angle HOLD no longer reproduced")
        return

    var host := Node3D.new()
    host.name = "Host"
    get_root().add_child(host)
    var control = build_player(host, "ControlProbe", "ControlPlayer", control_keys)
    var candidate = build_player(host, "CandidateProbe", "CandidatePlayer", candidate_keys)
    var control_probe: Node3D = control["probe"]
    var candidate_probe: Node3D = candidate["probe"]
    var control_player: AnimationPlayer = control["player"]
    var candidate_player: AnimationPlayer = candidate["player"]

    var max_control_reference_physical := 0.0
    var max_candidate_reference_physical := 0.0
    var max_pair_reference_residual_physical := 0.0
    var max_observed_pair_half := 0.0
    var max_observed_pair_physical := 0.0
    var observed_worst_index := -1
    var peak_observed_pair_physical := 0.0
    var observed_count := 0

    for sample in samples:
        var sample_index := int(sample.get("sample_index", -1))
        var time_s := float(sample.get("time_s", 0.0))
        control_player.seek(time_s, true)
        candidate_player.seek(time_s, true)
        await process_frame

        var expected_control := quat_from_row(sample.get("control_quaternion_xyzw", [0, 0, 0, 1]))
        var expected_candidate := quat_from_row(sample.get("candidate_quaternion_xyzw", [0, 0, 0, 1]))
        var expected_pair_physical := float(sample.get("physical_relative_rotation_deg", -1.0))

        var control_reference_physical := physical_rotation_deg(control_probe.quaternion, expected_control)
        var candidate_reference_physical := physical_rotation_deg(candidate_probe.quaternion, expected_candidate)
        var observed_pair_half := runtime_half_angle_deg(control_probe.quaternion, candidate_probe.quaternion)
        var observed_pair_physical := physical_rotation_deg(control_probe.quaternion, candidate_probe.quaternion)
        var pair_reference_residual := absf(observed_pair_physical - expected_pair_physical)

        max_control_reference_physical = maxf(max_control_reference_physical, control_reference_physical)
        max_candidate_reference_physical = maxf(max_candidate_reference_physical, candidate_reference_physical)
        max_pair_reference_residual_physical = maxf(max_pair_reference_residual_physical, pair_reference_residual)
        if observed_pair_physical > max_observed_pair_physical:
            max_observed_pair_physical = observed_pair_physical
            max_observed_pair_half = observed_pair_half
            observed_worst_index = sample_index
        if sample_index == 160:
            peak_observed_pair_physical = observed_pair_physical
        observed_count += 1

    if observed_count != 321:
        fail("dense observation count drift")
        return
    if max_control_reference_physical > HOST_REFERENCE_LIMIT_PHYSICAL_DEG:
        fail("control AnimationPlayer exceeds physical host/reference residual")
        return
    if max_candidate_reference_physical > HOST_REFERENCE_LIMIT_PHYSICAL_DEG:
        fail("candidate AnimationPlayer exceeds physical host/reference residual")
        return
    if max_pair_reference_residual_physical > PAIR_REFERENCE_LIMIT_PHYSICAL_DEG:
        fail("observed control/candidate physical delta diverges from independent reference")
        return
    if observed_worst_index != 152:
        fail("observed worst sample index drift")
        return
    if not max_observed_pair_half < NOMINAL_RUNTIME_TOLERANCE_DEG:
        fail("observed Runtime half-angle metric no longer stays below nominal threshold")
        return
    if not max_observed_pair_physical > NOMINAL_RUNTIME_TOLERANCE_DEG:
        fail("observed physical relative rotation no longer exceeds same numeric threshold")
        return
    if peak_observed_pair_physical > HOST_REFERENCE_LIMIT_PHYSICAL_DEG:
        fail("retained 0.5 s peak key no longer closes within host tolerance")
        return

    # Verifier-only sensitivity check: modify only the in-memory candidate
    # AnimationPlayer peak key. The payload and exact Runtime GLB remain unchanged.
    var candidate_animation: Animation = candidate["animation"]
    var candidate_track: int = candidate["track"]
    var peak_key_index := -1
    for i in range(candidate_animation.track_get_key_count(candidate_track)):
        if absf(candidate_animation.track_get_key_time(candidate_track, i) - 0.5) <= 0.000001:
            peak_key_index = i
            break
    if peak_key_index < 0:
        fail("candidate retained peak key missing in Godot track")
        return
    var original_peak: Quaternion = candidate_animation.track_get_key_value(candidate_track, peak_key_index)
    var mutated_peak := (Quaternion(Vector3.RIGHT, deg_to_rad(0.25)) * original_peak).normalized()
    candidate_animation.track_set_key_value(candidate_track, peak_key_index, mutated_peak)
    candidate_player.seek(0.5, true)
    control_player.seek(0.5, true)
    await process_frame
    var negative_physical_signal := physical_rotation_deg(control_probe.quaternion, candidate_probe.quaternion)
    candidate_animation.track_set_key_value(candidate_track, peak_key_index, original_peak)
    if negative_physical_signal < NEGATIVE_MIN_PHYSICAL_SIGNAL_DEG:
        receipt["negative_control_signal_physical_deg"] = negative_physical_signal
        fail("verifier-only candidate mutation did not fail closed")
        return

    receipt["state"] = "HOLD_RUNTIME_19_KEY_ANIMATION_REBIND__GODOT_LINEAR_PLAYBACK_EQUIVALENCE_PASS__OWNER_ANGLE_SEMANTICS_UNRESOLVED"
    receipt["payload_sha256"] = FileAccess.get_sha256(PAYLOAD_PATH)
    receipt["source_identity"] = payload.get("source_identity", {})
    receipt["dense_observation"] = {
        "sample_count": observed_count,
        "diagnostic_rate_hz": int(dense.get("diagnostic_rate_hz", 0)),
        "maximum_control_host_reference_physical_deg": max_control_reference_physical,
        "maximum_candidate_host_reference_physical_deg": max_candidate_reference_physical,
        "maximum_pair_reference_residual_physical_deg": max_pair_reference_residual_physical,
        "maximum_observed_runtime_half_angle_metric_deg": max_observed_pair_half,
        "maximum_observed_physical_relative_rotation_deg": max_observed_pair_physical,
        "observed_worst_sample_index": observed_worst_index,
        "observed_worst_time_s": observed_worst_index / 320.0,
        "peak_0p5s_observed_physical_relative_rotation_deg": peak_observed_pair_physical,
        "runtime_nominal_tolerance_deg": NOMINAL_RUNTIME_TOLERANCE_DEG,
        "runtime_half_angle_below_nominal_tolerance": max_observed_pair_half < NOMINAL_RUNTIME_TOLERANCE_DEG,
        "physical_rotation_above_same_numeric_tolerance": max_observed_pair_physical > NOMINAL_RUNTIME_TOLERANCE_DEG,
        "metric_relation": "PHYSICAL_RELATIVE_ROTATION_DEG_EQUALS_2X_RUNTIME_HALF_ANGLE_METRIC_DEG_FOR_UNIT_QUATERNIONS",
        "animation_track_type": "TYPE_ROTATION_3D",
        "animation_interpolation": "INTERPOLATION_LINEAR",
        "wallclock_pacing_claimed": false,
        "renderer_delivery_claimed": false
    }
    receipt["negative_control"] = {
        "mutation": "+0.25 degree verifier-only retained candidate peak-key rotation about Godot +X",
        "physical_signal_deg": negative_physical_signal,
        "minimum_required_physical_signal_deg": NEGATIVE_MIN_PHYSICAL_SIGNAL_DEG,
        "failed_closed": true,
        "source_changed": false,
        "runtime_candidate_file_changed": false
    }
    receipt["decision"] = {
        "animation_source_clip_changed": false,
        "animation_source_clip_retimed": false,
        "runtime_19_key_representation_adopted_by_animation": false,
        "owner_angle_semantics_resolved": false,
        "reason": "Godot reproduces the exact candidate, but the same numeric 0.075 degree threshold means different things under Runtime's half-angle metric and Rigging/Animation physical owner-angle reading."
    }
    receipt["truth_boundary"] = "This scoped result proves deterministic Godot 4.7.2 AnimationPlayer LINEAR seek/readback for both exact 41-key control and exact 19-key Runtime candidate, and preserves the measured half-angle versus physical-rotation semantic split. It does not adopt the Runtime representation, resolve the 0.075 degree owner policy, prove wall-clock 40 Hz delivery, Runtime controller/state-machine/input behavior, gameplay/collision/physics, target-device performance, final motion quality, Art/QA acceptance, CANON or production readiness."
    write_receipt()
    print("AXM ANIMAL ANIMATION RUNTIME KEY-BUDGET REBIND HOLD/PASS ", JSON.stringify(receipt))
    quit(0)
