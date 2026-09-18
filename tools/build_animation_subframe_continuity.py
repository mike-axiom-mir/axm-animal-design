from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_subframe_continuity import (
    inspect_hidden_between_key_negative_control,
    inspect_subframe_continuity,
)

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-animation-head", required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "evidence" / "animation-subframe-continuity",
    )
    args = parser.parse_args()

    positive = inspect_subframe_continuity(SPEC, PLAN, CLIP)
    negative = inspect_hidden_between_key_negative_control(SPEC, PLAN, CLIP)

    if positive["gate"] != "PASS_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY_WITNESS":
        raise SystemExit("exact-source dense subframe gate failed")
    if negative["gate"] != "HOLD_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY":
        raise SystemExit("hidden-between-key negative control did not fail closed")
    if not negative["negative_control"]["authored_samples_preserved"]:
        raise SystemExit("negative control changed an authored sample and is not a valid between-key control")

    args.out.mkdir(parents=True, exist_ok=True)
    positive_path = args.out / "quadruped_articulation_loop_001.subframe_continuity.json"
    negative_path = args.out / "quadruped_articulation_loop_001.hidden_between_key_negative_control.json"
    positive_path.write_text(json.dumps(positive, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    negative_path.write_text(json.dumps(negative, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "schema": "axm.animal-animation-subframe-continuity-summary/v0.1",
        "animation_head": args.current_animation_head,
        "source_digest": positive["source_digest"],
        "neutral_surface_digest": positive["neutral_surface_digest"],
        "rig_plan_digest": positive["rig_plan_digest"],
        "rig_weighting_profile": positive["rig_weighting_profile"],
        "clip_digest": positive["clip_digest"],
        "motion_semantics": positive["motion_semantics"],
        "authored_sample_rate_hz": positive["authored_sample_rate_hz"],
        "authored_sample_count": positive["authored_sample_count"],
        "subframes_per_authored_interval": positive["subframes_per_authored_interval"],
        "dense_sample_rate_hz": positive["dense_sample_rate_hz"],
        "dense_sample_count": positive["dense_sample_count"],
        "positive_gate": positive["gate"],
        "positive_metrics": positive["metrics"],
        "negative_control_gate": negative["gate"],
        "negative_control": negative["negative_control"],
        "negative_control_metrics": {
            "maximum_authored_sample_position_rebind_residual_m": negative["metrics"]["maximum_authored_sample_position_rebind_residual_m"],
            "maximum_authored_sample_angle_rebind_residual_deg": negative["metrics"]["maximum_authored_sample_angle_rebind_residual_deg"],
            "maximum_time_mirror_position_residual_m": negative["metrics"]["maximum_time_mirror_position_residual_m"],
            "maximum_time_mirror_angle_residual_deg": negative["metrics"]["maximum_time_mirror_angle_residual_deg"],
            "maximum_dense_bilateral_angle_residual_deg": negative["metrics"]["maximum_dense_bilateral_angle_residual_deg"],
        },
        "truth": positive["truth"],
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
