#!/usr/bin/env python3
"""Build retained Technical-Art evidence for the adopted reconstruction contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from axm_animal_design.uc_direction_frame_reconstruction_contract import (
    PASS_STATE,
    adopt_direction_frame_reconstruction_contract,
    require_target_runtime_ready,
)


def _load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rigging-receipt", type=Path, required=True)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--rigging-artifact-id", type=int, required=True)
    parser.add_argument("--rigging-artifact-sha256", required=True)
    parser.add_argument("--source-technical-art-head", required=True)
    parser.add_argument("--source-glb", type=Path, required=True)
    parser.add_argument("--source-glb-sha256", required=True)
    parser.add_argument("--current-technical-art-head", required=True)
    parser.add_argument("--uc-head", required=True)
    parser.add_argument("--uc-codec-blob", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    receipt_payload = args.rigging_receipt.read_bytes()
    receipt_sha256 = hashlib.sha256(receipt_payload).hexdigest()
    receipt = _load(args.rigging_receipt)
    glb_payload = args.source_glb.read_bytes()
    observed_glb_sha256 = hashlib.sha256(glb_payload).hexdigest()
    if observed_glb_sha256 != args.source_glb_sha256:
        raise SystemExit(
            f"source Technical Art GLB digest drift: {observed_glb_sha256} != {args.source_glb_sha256}"
        )

    contract = adopt_direction_frame_reconstruction_contract(
        receipt,
        exact_rigging_head=args.rigging_head,
        exact_rigging_artifact_id=args.rigging_artifact_id,
        exact_rigging_artifact_sha256=args.rigging_artifact_sha256,
        exact_source_technical_art_head=args.source_technical_art_head,
        exact_source_glb_sha256=args.source_glb_sha256,
        current_technical_art_head=args.current_technical_art_head,
        current_uc_head=args.uc_head,
        current_uc_codec_blob=args.uc_codec_blob,
    )
    if contract["state"] != PASS_STATE:
        raise SystemExit(f"unexpected Technical Art contract state: {contract['state']}")

    # Deliberate promotion negative: contract adoption must not be mislabelled as
    # a target-runtime implementation merely because owner reconstruction is green.
    try:
        require_target_runtime_ready(contract)
    except ValueError as exc:
        runtime_promotion = f"PASS_REJECTED: {exc}"
    else:
        raise SystemExit("unimplemented target runtime was incorrectly promoted")

    args.out.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": "axm.animal-current-uc-direction-frame-reconstruction-contract-evidence/v0.1",
        "state": contract["state"],
        "exact_dependencies": {
            "rigging_head": args.rigging_head,
            "rigging_artifact_id": args.rigging_artifact_id,
            "rigging_artifact_sha256": args.rigging_artifact_sha256,
            "rigging_receipt_sha256": receipt_sha256,
            "source_technical_art_head": args.source_technical_art_head,
            "source_glb_sha256": observed_glb_sha256,
            "current_technical_art_head": args.current_technical_art_head,
            "uc_head": args.uc_head,
            "uc_codec_blob": args.uc_codec_blob,
        },
        "contract": contract,
        "negative_controls": {
            "unimplemented_target_runtime_promotion": runtime_promotion,
        },
        "truth_boundary": {
            "rigging_owner_receipt_recomputed": False,
            "owner_reconstruction_algorithm_copied": False,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "target_runtime_implemented": False,
            "visual_quality_accepted": False,
            "canon_or_production_ready": False,
        },
    }
    _write(args.out / "uc_direction_frame_reconstruction_contract_evidence.json", evidence)
    _write(args.out / "exact-rigging-owner-receipt.json", receipt)
    (args.out / "rigging-receipt-sha256.txt").write_text(receipt_sha256 + "\n", encoding="utf-8")
    (args.out / "rigging-head.txt").write_text(args.rigging_head + "\n", encoding="utf-8")
    (args.out / "rigging-artifact-sha256.txt").write_text(args.rigging_artifact_sha256 + "\n", encoding="utf-8")
    (args.out / "source-technical-art-head.txt").write_text(args.source_technical_art_head + "\n", encoding="utf-8")
    (args.out / "source-glb-sha256.txt").write_text(observed_glb_sha256 + "\n", encoding="utf-8")
    (args.out / "technical-art-head.txt").write_text(args.current_technical_art_head + "\n", encoding="utf-8")
    (args.out / "uc-head.txt").write_text(args.uc_head + "\n", encoding="utf-8")
    (args.out / "uc-codec-blob.txt").write_text(args.uc_codec_blob + "\n", encoding="utf-8")

    measurements = contract["measurements"]
    print(contract["state"])
    print(f"max_owner_position_residual_m={measurements['maximum_owner_position_residual_m']}")
    print(f"max_owner_normal_angle_deg={measurements['maximum_owner_normal_angle_deg']}")
    print(f"max_owner_tangent_angle_deg={measurements['maximum_owner_tangent_angle_deg']}")
    print(f"max_nt_dot={measurements['maximum_normal_tangent_dot_abs']}")
    print(runtime_promotion)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
