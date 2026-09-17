extends SceneTree

const PAYLOAD_PATH := "res://generated/payload.json"
const RECEIPT_PATH := "res://generated/godot_receipt.json"
const RESIDUAL_LIMIT_DEG := 0.001
const NEGATIVE_MIN_SIGNAL_DEG := 0.10

var receipt := {
    "schema": "axm.animal-animation-godot-quaternion-interpolation-equivalence/v0.1",
    "proof_runtime": "Godot 4.7.2",
    "proof_mode": "DETERMINISTIC_ANIMATIONPLAYER_SEEK_READBACK_NOT_WALLCLOCK_PACING",
    "promotion_effect": "NONE"
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

func quat_error_deg(observed: Quaternion, expected: Quaternion) -> float:
    var a := observed.normalized()
    var b := expected.normalized()
    var d := absf(a.dot(b))
    d = clampf(d, -1.0, 1.0)
    return rad_to_deg(2.0 * acos(d))

func _initialize() -> void:
    if not FileAccess.file_exists(PAYLOAD_PATH):
        fail("quaternion interpolation payload missing")
        return
    var payload = JSON.parse_string(FileAccess.get_file_as_string(PAYLOAD_PATH))
    if payload == null or not (payload is Dictionary):
        fail("payload is not valid JSON")
        return
    if str(payload.get("schema", "")) != "axm.animal-animation-godot-quaternion-interpolation-payload/v0.1":
        fail("unexpected payload schema")
        return

    var keys = payload.get("authored_keys", [])
    var dense: Dictionary = payload.get("dense_reference", {})
    var samples = dense.get("samples", [])
    if keys.size() != 41 or samples.size() != 321:
        fail("exact authored/dense sample counts drift")
        return
    if int(dense.get("samples_per_authored_interval", 0)) != 8:
        fail("dense subdivision drift")
        return

    var host := Node3D.new()
    host.name = "Host"
    get_root().add_child(host)

    var probe := Node3D.new()
    probe.name = "Probe"
    host.add_child(probe)

    var player := AnimationPlayer.new()
    player.name = "AnimationPlayer"
    player.root_node = NodePath("..")
    host.add_child(player)

    var animation := Animation.new()
    animation.length = 1.0
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_ROTATION_3D)
    animation.track_set_path(track, NodePath("Probe"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
    for key in keys:
        animation.track_insert_key(track, float(key.get("time_s", 0.0)), quat_from_row(key.get("quaternion_xyzw", [0, 0, 0, 1])))

    var library := AnimationLibrary.new()
    library.add_animation("probe", animation)
    player.add_animation_library("", library)
    player.play("probe")
    player.pause()

    var max_error_deg := 0.0
    var max_error_sample := -1
    var authored_boundary_max_deg := 0.0
    var observed_count := 0
    for sample in samples:
        var time_s := float(sample.get("time_s", 0.0))
        player.seek(time_s, true)
        await process_frame
        var expected := quat_from_row(sample.get("expected_quaternion_xyzw", [0, 0, 0, 1]))
        var error_deg := quat_error_deg(probe.quaternion, expected)
        if error_deg > max_error_deg:
            max_error_deg = error_deg
            max_error_sample = int(sample.get("sample_index", -1))
        if bool(sample.get("authored_boundary", false)):
            authored_boundary_max_deg = maxf(authored_boundary_max_deg, error_deg)
        observed_count += 1

    if observed_count != 321:
        fail("dense observation count drift")
        return
    if max_error_deg > RESIDUAL_LIMIT_DEG:
        receipt["maximum_quaternion_residual_deg"] = max_error_deg
        receipt["maximum_residual_sample_index"] = max_error_sample
        fail("Godot AnimationPlayer quaternion interpolation exceeds bounded residual")
        return

    # Fail-closed verifier-only mutation. The source payload and retained GLB remain unchanged.
    var original_peak: Quaternion = animation.track_get_key_value(track, 20)
    var mutated_peak := (Quaternion(Vector3.RIGHT, deg_to_rad(0.25)) * original_peak).normalized()
    animation.track_set_key_value(track, 20, mutated_peak)
    player.seek(0.5, true)
    await process_frame
    var expected_peak := quat_from_row(samples[160].get("expected_quaternion_xyzw", [0, 0, 0, 1]))
    var negative_signal_deg := quat_error_deg(probe.quaternion, expected_peak)
    animation.track_set_key_value(track, 20, original_peak)
    if negative_signal_deg < NEGATIVE_MIN_SIGNAL_DEG:
        receipt["negative_control_signal_deg"] = negative_signal_deg
        fail("verifier-only quaternion key mutation did not fail closed")
        return

    receipt["state"] = "PASS_GODOT_ANIMATIONPLAYER_GLTF_LINEAR_QUATERNION_INTERPOLATION_EQUIVALENCE"
    receipt["payload_sha256"] = FileAccess.get_sha256(PAYLOAD_PATH)
    receipt["source_identity"] = payload.get("source_identity", {})
    receipt["dense_observation"] = {
        "sample_count": observed_count,
        "diagnostic_rate_hz": int(dense.get("diagnostic_rate_hz", 0)),
        "maximum_quaternion_residual_deg": max_error_deg,
        "maximum_residual_sample_index": max_error_sample,
        "authored_boundary_maximum_residual_deg": authored_boundary_max_deg,
        "residual_limit_deg": RESIDUAL_LIMIT_DEG,
        "animation_track_type": "TYPE_ROTATION_3D",
        "animation_interpolation": "INTERPOLATION_LINEAR",
        "wallclock_pacing_claimed": false,
        "renderer_delivery_claimed": false
    }
    receipt["negative_control"] = {
        "mutation": "+0.25 degree verifier-only peak-key rotation about Godot +X",
        "signal_deg": negative_signal_deg,
        "minimum_required_signal_deg": NEGATIVE_MIN_SIGNAL_DEG,
        "failed_closed": true,
        "source_changed": false
    }
    receipt["truth_boundary"] = "This PASS proves deterministic Godot 4.7.2 AnimationPlayer TYPE_ROTATION_3D LINEAR seek/readback agreement with the exact retained glTF LINEAR quaternion channel at 321 diagnostic samples. It does not prove wall-clock 40 Hz delivery, renderer/display cadence, production Runtime controller/state-machine behavior, gameplay/input/collision/physics, target-device performance, final motion naturalness, Art/QA acceptance, CANON or production readiness."
    write_receipt()
    print("AXM ANIMAL GODOT QUATERNION INTERPOLATION PASS ", JSON.stringify(receipt))
    quit(0)
