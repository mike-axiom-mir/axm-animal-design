from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_motion import build_animation_frame, frame_as_form_evidence, inspect_animation_motion
from axm_animal_design.organic_form import project_wire_svg

spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
plan = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
clip = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())
report = inspect_animation_motion(spec, plan, clip)
if report["gate"] != "PASS":
    raise SystemExit("animation motion evidence gate failed")

out = ROOT / "evidence"
frames_out = out / "quadruped_articulation_loop_001_frames"
frames_out.mkdir(parents=True, exist_ok=True)
(out / "quadruped_articulation_loop_001.evidence.json").write_text(json.dumps(report, indent=2, sort_keys=True))

retained = []
for time_seconds in report["retained_keyframe_times_seconds"]:
    frame = build_animation_frame(spec, plan, clip, time_seconds)
    tag = f"t{int(round(time_seconds * 1000)):04d}ms"
    (frames_out / f"{tag}.frame.json").write_text(json.dumps(frame, indent=2, sort_keys=True))
    render_evidence = frame_as_form_evidence(frame, f"{clip['name']} {time_seconds:.2f}s")
    side_name = f"{tag}.side.svg"
    front_name = f"{tag}.front.svg"
    (frames_out / side_name).write_text(project_wire_svg(render_evidence, view="side"))
    (frames_out / front_name).write_text(project_wire_svg(render_evidence, view="front"))
    retained.append({
        "time_seconds": time_seconds,
        "sample_index": frame["sample_index"],
        "angles_deg": frame["angles_deg"],
        "surface_digest": frame["surface_digest"],
        "frame_file": f"quadruped_articulation_loop_001_frames/{tag}.frame.json",
        "side_view": f"quadruped_articulation_loop_001_frames/{side_name}",
        "front_view": f"quadruped_articulation_loop_001_frames/{front_name}",
    })

summary = {
    "schema": "axm.animal-animation-motion-summary/v0.1",
    "source_name": report["source_name"],
    "source_digest": report["source_digest"],
    "neutral_surface_digest": report["neutral_surface_digest"],
    "rig_plan_digest": report["rig_plan_digest"],
    "rig_weighting_profile": report["rig_weighting_profile"],
    "clip_name": report["clip_name"],
    "clip_digest": report["clip_digest"],
    "motion_semantics": report["motion_semantics"],
    "duration_seconds": report["duration_seconds"],
    "sample_rate_hz": report["sample_rate_hz"],
    "sample_count": report["sample_count"],
    "track_count": report["track_count"],
    "metrics": report["metrics"],
    "retained_frames": retained,
    "gate": report["gate"],
    "truth": report["truth"],
}
(out / "quadruped_articulation_loop_001.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
print(json.dumps(summary, sort_keys=True))
