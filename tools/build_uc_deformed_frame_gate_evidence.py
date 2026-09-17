#!/usr/bin/env python3
"""Build Technical-Art evidence from Rigging's retained deformation receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from axm_animal_design.uc_deformed_frame_gate import (
    HOLD_STATE,
    PASS_STATE,
    evaluate_deformed_direction_frame_gate,
    require_tangent_space_runtime_ready,
)


def load_object(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rigging-receipt", type=Path, required=True)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--rigging-artifact-id", type=int, required=True)
    parser.add_argument("--rigging-artifact-sha256", required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--transport-head", required=True)
    parser.add_argument("--glb-sha256", required=True)
    parser.add_argument("--uc-head", required=True)
    parser.add_argument("--uc-codec-blob", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = args.rigging_receipt.read_bytes()
    receipt_sha256 = hashlib.sha256(payload).hexdigest()
    receipt = json.loads(payload.decode("utf-8"))
    if not isinstance(receipt, dict):
        raise SystemExit("Rigging receipt must contain a JSON object")

    decision = evaluate_deformed_direction_frame_gate(
        receipt,
        expected_technical_art_head=args.transport_head,
        expected_glb_sha256=args.glb_sha256,
        exact_rigging_head=args.rigging_head,
        current_uc_head=args.uc_head,
        current_uc_codec_blob=args.uc_codec_blob,
    )
    if decision["state"] not in {HOLD_STATE, PASS_STATE}:
        raise SystemExit(f"direction-frame transport gate failed: {decision['state']}")

    # Deliberate negative promotion control: the currently observed Rigging HOLD
    # must refuse tangent-space runtime promotion rather than being treated as
    # ready merely because the generic GLB/UC path is otherwise green.
    negative_promotion = "NOT_APPLICABLE_OWNER_PASS"
    if decision["state"] == HOLD_STATE:
        try:
            require_tangent_space_runtime_ready(decision)
        except ValueError as exc:
            negative_promotion = f"PASS_REJECTED: {exc}"
        else:
            raise SystemExit("held direction frame was incorrectly promoted")

    args.out.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": "axm.animal-current-uc-deformed-direction-frame-gate-evidence/v0.1",
        "status": decision["state"],
        "technical_art_gate_head": args.technical_art_head,
        "rigging": {
            "head": args.rigging_head,
            "artifact_id": args.rigging_artifact_id,
            "artifact_sha256": args.rigging_artifact_sha256,
            "receipt_sha256": receipt_sha256,
        },
        "source_transport": {
            "technical_art_head": args.transport_head,
            "glb_sha256": args.glb_sha256,
        },
        "universal_creation": {
            "head": args.uc_head,
            "codec_blob": args.uc_codec_blob,
            "product_modified": False,
        },
        "decision": decision,
        "negative_controls": {
            "held_frame_runtime_promotion": negative_promotion,
        },
        "truth_boundary": {
            "rigging_observation_recomputed": False,
            "technical_art_transport_rewritten": False,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "engine_import_or_playback_proven": False,
            "visual_quality_accepted": False,
            "runtime_tangent_reconstruction_proven": False,
            "canon_or_production_ready": False,
        },
    }
    write_json(args.out / "uc_deformed_direction_frame_gate_evidence.json", evidence)
    (args.out / "technical-art-gate-head.txt").write_text(args.technical_art_head + "\n", encoding="utf-8")
    (args.out / "transport-head.txt").write_text(args.transport_head + "\n", encoding="utf-8")
    (args.out / "rigging-head.txt").write_text(args.rigging_head + "\n", encoding="utf-8")
    (args.out / "rigging-artifact-sha256.txt").write_text(args.rigging_artifact_sha256 + "\n", encoding="utf-8")
    (args.out / "rigging-receipt-sha256.txt").write_text(receipt_sha256 + "\n", encoding="utf-8")
    (args.out / "uc-head.txt").write_text(args.uc_head + "\n", encoding="utf-8")
    (args.out / "uc-codec-blob.txt").write_text(args.uc_codec_blob + "\n", encoding="utf-8")
    print(decision["state"])
    print(f"max_position_residual_m={decision['measurements']['maximum_position_residual_m']}")
    print(f"normal_excess_deg={decision['measurements']['normal_deformation_excess_deg']}")
    print(f"corrected_tangent_excess_deg={decision['measurements']['corrected_tangent_deformation_excess_deg']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
