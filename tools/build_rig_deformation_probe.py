from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.rig_deformation import inspect_rig_deformation

spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
plan = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
evidence = inspect_rig_deformation(spec, plan)
out = ROOT / "evidence"
out.mkdir(exist_ok=True)
(out / "quadruped_rig_probe_001.evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True))
summary = {
    "schema": "axm.animal-rig-deformation-summary/v0.2",
    "source_name": evidence["source_name"],
    "source_digest": evidence["source_digest"],
    "surface_digest": evidence["surface_digest"],
    "plan_digest": evidence["plan_digest"],
    "joint_count": evidence["joint_count"],
    "pose_count": evidence["pose_count"],
    "declared_downstream_region_count": evidence["declared_downstream_region_count"],
    "gate": evidence["gate"],
    "joint_statuses": {row["id"]: row["status"] for row in evidence["joints"]},
    "truth": evidence["truth"],
}
(out / "quadruped_rig_probe_001.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
print(json.dumps(summary, sort_keys=True))
