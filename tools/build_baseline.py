from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.organic_form import build_form_study, project_wire_svg

spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
evidence = build_form_study(spec)
out = ROOT / "evidence"
out.mkdir(exist_ok=True)
(out / "quadruped_neutral_001.evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True))
(out / "quadruped_neutral_001.side.svg").write_text(project_wire_svg(evidence, "side"))
(out / "quadruped_neutral_001.front.svg").write_text(project_wire_svg(evidence, "front"))
summary = {
    "schema": "axm.animal-organic-form-summary/v0.1",
    "source_digest": evidence["source_digest"],
    "surface_digest": evidence["surface_digest"],
    "counts": evidence["counts"],
    "gate": evidence["gates"]["declared-proportion-and-symmetry-intent"],
    "bend_zone_statuses": sorted({row["status"] for row in evidence["intent"]["bend_zones"]}),
    "truth": evidence["truth"],
}
(out / "quadruped_neutral_001.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
print(json.dumps(summary, sort_keys=True))
