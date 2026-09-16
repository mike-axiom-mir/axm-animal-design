from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.weighting_refinement import compare_weighting_profiles

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CANDIDATE = json.loads((ROOT / "examples/quadruped_weighting_refinement_001.json").read_text())
OUT = ROOT / "evidence" / "weighting-refinement-001"
OUT.mkdir(parents=True, exist_ok=True)

report = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
(OUT / "quadruped_weighting_refinement_001.evidence.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n"
)
summary = {
    "gate": report["gate"],
    "source_digest": report["source_digest"],
    "surface_digest": report["surface_digest"],
    "baseline_plan_digest": report["baseline_plan_digest"],
    "candidate_contract_digest": report["candidate_contract_digest"],
    "baseline_profile": report["baseline_profile"],
    "candidate_profile": report["candidate_profile"],
    "candidate_exponent": report["candidate_exponent"],
    "joint_count": report["joint_count"],
    "sampled_pose_count": report["sampled_pose_count"],
    "nonzero_comparison_count": report["nonzero_comparison_count"],
    "worst_case": report["worst_case"],
    "truth": report["truth"],
}
(OUT / "quadruped_weighting_refinement_001.summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
if report["gate"] != "PASS_SCOPED_WEIGHTING_REFINEMENT":
    raise SystemExit(1)
print(json.dumps(summary, indent=2, sort_keys=True))
