#!/usr/bin/env python3
"""Build retained Rigging evidence for post-skin owner-frame reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from axm_animal_design.transported_frame_reconstruction_constraint import (
    PASS_STATE,
    inspect_post_skin_owner_frame_reconstruction,
)
from axm_animal_design.transported_tangent_deformation_audit import (
    TECHNICAL_ART_ARTIFACT_ID,
    TECHNICAL_ART_ARTIFACT_SHA256,
    TECHNICAL_ART_GLB_SHA256,
    TECHNICAL_ART_HEAD,
    TECHNICAL_ART_MODULE_BLOB,
)


def _load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--left-profile", type=Path, required=True)
    parser.add_argument("--bilateral-profile", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--weighting-profile", type=Path, required=True)
    parser.add_argument("--technical-art-receipt", type=Path, required=True)
    parser.add_argument("--technical-art-glb", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--technical-art-module-blob", required=True)
    parser.add_argument("--technical-art-artifact-id", type=int, required=True)
    parser.add_argument("--technical-art-artifact-sha256", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    expected = {
        "technical_art_head": TECHNICAL_ART_HEAD,
        "technical_art_module_blob": TECHNICAL_ART_MODULE_BLOB,
        "technical_art_artifact_id": TECHNICAL_ART_ARTIFACT_ID,
        "technical_art_artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
    }
    observed = {
        "technical_art_head": args.technical_art_head,
        "technical_art_module_blob": args.technical_art_module_blob,
        "technical_art_artifact_id": args.technical_artifact_id,
        "technical_art_artifact_sha256": args.technical_artifact_sha256,
    }
    if observed != expected:
        raise SystemExit(f"exact Technical Art dependency identity drift: {observed!r} != {expected!r}")

    glb = args.technical_art_glb.read_bytes()
    if hashlib.sha256(glb).hexdigest() != TECHNICAL_ART_GLB_SHA256:
        raise SystemExit("exact Technical Art GLB digest drift")

    receipt = inspect_post_skin_owner_frame_reconstruction(
        _load(args.source),
        _load(args.left_profile),
        _load(args.bilateral_profile),
        _load(args.rig_plan),
        _load(args.weighting_profile),
        _load(args.technical_art_receipt),
        glb,
    )
    if receipt["state"] != PASS_STATE:
        raise SystemExit(f"post-skin owner-frame reconstruction did not pass: {receipt['state']}")

    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "post-skin-owner-frame-reconstruction-receipt.json", receipt)
    _write(
        args.out / "summary.json",
        {
            "state": receipt["state"],
            "exact_rigging_head": args.current_rigging_head,
            "technical_art_head": TECHNICAL_ART_HEAD,
            "technical_art_artifact_id": TECHNICAL_ART_ARTIFACT_ID,
            "technical_art_artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
            "technical_art_glb_sha256": TECHNICAL_ART_GLB_SHA256,
            "premise": receipt["premise"],
            "motion_boundary": receipt["motion_boundary"],
            "reconstruction": receipt["reconstruction"],
            "negative_controls": receipt["negative_controls"],
            "truth_boundary": receipt["truth_boundary"],
        },
    )
    shutil.copyfile(args.rig_plan, args.out / "exact-rig-plan.json")
    shutil.copyfile(args.weighting_profile, args.out / "exact-weighting-profile.json")
    shutil.copyfile(args.technical_art_receipt, args.out / "exact-technical-art-transport-receipt.json")
    (args.out / "exact-rigging-head.txt").write_text(args.current_rigging_head + "\n", encoding="utf-8")
    (args.out / "technical-art-head.txt").write_text(TECHNICAL_ART_HEAD + "\n", encoding="utf-8")
    (args.out / "technical-art-module-blob.txt").write_text(TECHNICAL_ART_MODULE_BLOB + "\n", encoding="utf-8")
    (args.out / "technical-art-artifact-sha256.txt").write_text(TECHNICAL_ART_ARTIFACT_SHA256 + "\n", encoding="utf-8")
    (args.out / "technical-art-glb-sha256.txt").write_text(TECHNICAL_ART_GLB_SHA256 + "\n", encoding="utf-8")

    reconstruction = receipt["reconstruction"]
    mutation = receipt["negative_controls"]["coherent_posed_shape_mutation"]
    print(receipt["state"])
    print(f"max_split_residual_m={reconstruction['maximum_uv_split_position_residual_m']}")
    print(f"max_owner_position_residual_m={reconstruction['maximum_owner_position_residual_m']}")
    print(f"max_owner_normal_angle_deg={reconstruction['maximum_owner_normal_angle_deg']}")
    print(f"max_owner_tangent_angle_deg={reconstruction['maximum_owner_tangent_angle_deg']}")
    print(f"max_nt_dot={reconstruction['maximum_normal_tangent_dot_abs']}")
    print(f"mutation_direction_signal_deg={mutation['direction_signal_deg']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
