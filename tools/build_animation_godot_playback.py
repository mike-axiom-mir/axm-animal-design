from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_motion import build_animation_frame
from axm_animal_design.animation_playback import inspect_sampled_playback

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())

OUT_DIR = ROOT / "tools" / "godot_animation_playback" / "generated"
PAYLOAD_PATH = OUT_DIR / "quadruped_animation_payload.json"
SUMMARY_PATH = OUT_DIR / "quadruped_animation_payload_summary.json"


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _godot_point(point):
    # Animal source is +X forward, +Y left, +Z up. This is the same explicit
    # Y-up bridge already used by the Animal -> UC handoff: [-Y, Z, X].
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    return [-y, z, x]


def _flatten_surface(surface):
    positions = []
    indices = []
    primitive_rows = []
    for primitive in surface["primitives"]:
        offset = len(positions)
        local_positions = [_godot_point(point) for point in primitive["positions"]]
        local_indices = [int(value) for value in primitive["indices"]]
        positions.extend(local_positions)
        indices.extend(offset + value for value in local_indices)
        primitive_rows.append({
            "id": primitive["id"],
            "vertex_offset": offset,
            "vertex_count": len(local_positions),
            "index_offset": len(indices) - len(local_indices),
            "index_count": len(local_indices),
        })
    return positions, indices, primitive_rows


def _bounds(frames):
    all_points = [point for frame in frames for point in frame["positions"]]
    mins = [min(point[axis] for point in all_points) for axis in range(3)]
    maxs = [max(point[axis] for point in all_points) for axis in range(3)]
    center = [(mins[axis] + maxs[axis]) / 2.0 for axis in range(3)]
    size = [maxs[axis] - mins[axis] for axis in range(3)]
    return {"min": mins, "max": maxs, "center": center, "size": size}


def main():
    playback = inspect_sampled_playback(SPEC, PLAN, CLIP)
    if playback["gate"] != "PASS_DISCRETE_SAMPLED_PLAYBACK_SEAM":
        raise SystemExit("sampled playback prerequisite is not green")

    rendered_frames = []
    expected_vertex_count = None
    expected_index_count = None
    expected_primitives = None
    for frame_index, time_seconds in enumerate(playback["display_schedule_seconds"]):
        authored = build_animation_frame(SPEC, PLAN, CLIP, time_seconds)
        positions, indices, primitives = _flatten_surface(authored["surface"])
        if expected_vertex_count is None:
            expected_vertex_count = len(positions)
            expected_index_count = len(indices)
            expected_primitives = primitives
        if len(positions) != expected_vertex_count or len(indices) != expected_index_count:
            raise ValueError("topology count drift across authored animation frames")
        if primitives != expected_primitives:
            raise ValueError("primitive partition drift across authored animation frames")
        rendered_frames.append({
            "frame_index": frame_index,
            "sample_index": authored["sample_index"],
            "time_seconds": authored["time_seconds"],
            "surface_digest": authored["surface_digest"],
            "angles_deg": authored["angles_deg"],
            "positions": positions,
            "indices": indices,
        })

    unique_surface_digests = len({frame["surface_digest"] for frame in rendered_frames})
    if unique_surface_digests <= 2:
        raise ValueError("authored playback did not retain materially distinct posed surfaces")

    payload = {
        "schema": "axm.animal-animation-godot-discrete-playback-payload/v0.1",
        "proof_scope": "PINNED_GODOT_AUTHORED_SAMPLE_APPLICATION_NOT_REALTIME_CONTROLLER",
        "source_identity": {
            "source_name": playback["source_name"],
            "source_digest": playback["source_digest"],
            "neutral_surface_digest": playback["neutral_surface_digest"],
            "rig_plan_digest": playback["rig_plan_digest"],
            "rig_weighting_profile": playback["rig_weighting_profile"],
            "clip_name": playback["clip_name"],
            "clip_digest": playback["clip_digest"],
            "motion_semantics": playback["motion_semantics"],
        },
        "source_playback": {
            "playback_schema": playback["schema"],
            "playback_mode": playback["playback_mode"],
            "duration_seconds": playback["duration_seconds"],
            "sample_rate_hz": playback["sample_rate_hz"],
            "display_frame_interval_seconds": playback["display_frame_interval_seconds"],
            "endpoint_inclusive_source_sample_count": playback["endpoint_inclusive_source_sample_count"],
            "displayed_frame_count_per_cycle": playback["displayed_frame_count_per_cycle"],
            "source_gate": playback["gate"],
        },
        "coordinate_bridge": {
            "source": "+X forward, +Y left, +Z up",
            "godot": "+X right, +Y up, +Z forward-axis representation",
            "mapping": "[-source_y, source_z, source_x]",
            "purpose": "proof-host presentation only; no source geometry mutation",
        },
        "topology": {
            "vertex_count": expected_vertex_count,
            "index_count": expected_index_count,
            "triangle_count": expected_index_count // 3,
            "primitive_partitions": expected_primitives,
        },
        "bounds_godot": _bounds(rendered_frames),
        "frames": rendered_frames,
        "truth": {
            "proves_if_green": [
                "the exact already-authored discrete Animal samples can be applied as triangle geometry inside the pinned Godot proof host",
                "the proof host can step two full exact sample cycles and return to frame zero without source, rig, clip or weighting substitution",
                "retained Godot renders show a visible neutral-to-peak change and a visually clean neutral roundtrip within the bounded proof host",
            ],
            "does_not_prove": [
                "continuous interpolation between authored samples",
                "real-time 40 Hz frame pacing",
                "exported skeleton or animation-clip transport",
                "runtime controller or state-machine integration",
                "gameplay acceptance",
                "perceptual animation quality, locomotion or biological correctness",
                "target-device performance or production runtime acceptance",
            ],
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    PAYLOAD_PATH.write_bytes(payload_bytes)
    summary = {
        "schema": "axm.animal-animation-godot-discrete-playback-build-summary/v0.1",
        "payload_sha256": _sha256_bytes(payload_bytes),
        "source_identity": payload["source_identity"],
        "source_playback": payload["source_playback"],
        "topology": payload["topology"],
        "unique_authored_surface_digests": unique_surface_digests,
        "bounds_godot": payload["bounds_godot"],
        "gate": "PASS_GODOT_DISCRETE_PLAYBACK_PAYLOAD_BUILD",
        "truth": payload["truth"],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
