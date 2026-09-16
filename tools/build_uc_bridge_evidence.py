#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.organic_form import build_form_study
from axm_animal_design.uc_bridge import adapt_form_evidence_for_uc, build_bridge_evidence
from axm_uc.procedural_3d import publish_glb, verify_glb

PINNED_UC_COMMIT = "640bd7dc177b90e023aad879b4c00051df7f4ee3"


def main() -> int:
    observed_commit = os.environ.get("AXM_UC_COMMIT", "")
    if observed_commit != PINNED_UC_COMMIT:
        raise RuntimeError(f"AXM_UC_COMMIT must equal pinned UC commit {PINNED_UC_COMMIT}")

    spec_path = ROOT / "examples" / "quadruped_neutral_001.json"
    form_spec = json.loads(spec_path.read_text())
    form_evidence = build_form_study(form_spec)
    uc_surface = adapt_form_evidence_for_uc(form_evidence)

    evidence_dir = ROOT / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    surface_path = evidence_dir / "quadruped_uc_surface_001.json"
    surface_path.write_text(json.dumps(uc_surface, indent=2, sort_keys=True) + "\n")

    glb_path = evidence_dir / "quadruped_uc_bridge_001.glb"
    publish = publish_glb(glb_path, uc_surface, replace=True)
    glb_bytes = glb_path.read_bytes()
    glb_sha256 = hashlib.sha256(glb_bytes).hexdigest()
    if glb_sha256 != publish["sha256"]:
        raise RuntimeError("published GLB digest differs from on-disk bytes")

    verification = verify_glb(glb_bytes, expected_spec_digest=publish["specification_sha256"])
    receipt = build_bridge_evidence(
        form_evidence,
        uc_surface,
        uc_commit=PINNED_UC_COMMIT,
        glb_sha256=glb_sha256,
        uc_specification_sha256=publish["specification_sha256"],
        uc_verification=verification,
    )
    receipt["paths"] = {
        "source": str(spec_path.relative_to(ROOT)),
        "uc_surface": str(surface_path.relative_to(ROOT)),
        "glb": str(glb_path.relative_to(ROOT)),
    }
    receipt["counts"] = {
        "source_vertices": form_evidence["counts"]["vertices"],
        "source_triangles": form_evidence["counts"]["triangles"],
        "verified_glb_triangles": verification["triangles"],
    }
    if receipt["counts"]["source_triangles"] != receipt["counts"]["verified_glb_triangles"]:
        raise RuntimeError("triangle count changed across the UC bridge")

    receipt_path = evidence_dir / "quadruped_uc_bridge_001.evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": receipt["status"],
        "uc_commit": PINNED_UC_COMMIT,
        "glb_sha256": glb_sha256,
        "source_triangles": receipt["counts"]["source_triangles"],
        "verified_glb_triangles": receipt["counts"]["verified_glb_triangles"],
        "receipt": str(receipt_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
