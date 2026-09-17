#!/usr/bin/env python3
"""Build retained evidence for Rigging rebind to Technical Art JOINTS_0 width adoption."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from axm_animal_design.joint_index_width_rigging_rebind import (
    CONTROL_ARTIFACT_ID,
    CONTROL_ARTIFACT_SHA256,
    PASS_STATE,
    PRODUCER_ARTIFACT_ID,
    PRODUCER_ARTIFACT_SHA256,
    PRODUCER_MODULE_BLOB,
    PRODUCER_TECHNICAL_ART_HEAD,
    inspect_joint_index_width_rigging_rebind,
)


def _load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-glb", type=Path, required=True)
    parser.add_argument("--producer-glb", type=Path, required=True)
    parser.add_argument("--control-transport-receipt", type=Path, required=True)
    parser.add_argument("--producer-transport-receipt", type=Path, required=True)
    parser.add_argument("--adoption-receipt", type=Path, required=True)
    parser.add_argument("--owner-frames", type=Path, required=True)
    parser.add_argument("--geometry-basis", type=Path, required=True)
    parser.add_argument("--control-artifact-id", type=int, required=True)
    parser.add_argument("--control-artifact-sha256", required=True)
    parser.add_argument("--producer-artifact-id", type=int, required=True)
    parser.add_argument("--producer-artifact-sha256", required=True)
    parser.add_argument("--producer-technical-art-head", required=True)
    parser.add_argument("--producer-module-blob", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    expected = {
        "control_artifact_id": CONTROL_ARTIFACT_ID,
        "control_artifact_sha256": CONTROL_ARTIFACT_SHA256,
        "producer_artifact_id": PRODUCER_ARTIFACT_ID,
        "producer_artifact_sha256": PRODUCER_ARTIFACT_SHA256,
        "producer_technical_art_head": PRODUCER_TECHNICAL_ART_HEAD,
        "producer_module_blob": PRODUCER_MODULE_BLOB,
    }
    observed = {
        "control_artifact_id": args.control_artifact_id,
        "control_artifact_sha256": args.control_artifact_sha256,
        "producer_artifact_id": args.producer_artifact_id,
        "producer_artifact_sha256": args.producer_artifact_sha256,
        "producer_technical_art_head": args.producer_technical_art_head,
        "producer_module_blob": args.producer_module_blob,
    }
    if observed != expected:
        raise SystemExit(f"exact donor identity drift: {observed!r} != {expected!r}")

    receipt = inspect_joint_index_width_rigging_rebind(
        control_glb=args.control_glb.read_bytes(),
        producer_glb=args.producer_glb.read_bytes(),
        control_transport_receipt=_load(args.control_transport_receipt),
        producer_transport_receipt=_load(args.producer_transport_receipt),
        adoption_receipt=_load(args.adoption_receipt),
        owner_frames=_load(args.owner_frames),
        geometry_basis=_load(args.geometry_basis),
    )
    if receipt["state"] != PASS_STATE:
        raise SystemExit(f"joint-index width Rigging rebind did not pass: {receipt['state']}")

    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "joint-index-width-rigging-rebind-receipt.json", receipt)
    _write(
        args.out / "summary.json",
        {
            "state": receipt["state"],
            "exact_rigging_head": args.current_rigging_head,
            "exact_identities": receipt["exact_identities"],
            "storage_boundary": receipt["storage_boundary"],
            "motion_boundary": receipt["motion_boundary"],
            "negative_controls": receipt["negative_controls"],
            "preserved_hold": receipt["preserved_hold"],
            "truth_boundary": receipt["truth_boundary"],
        },
    )
    for source, name in (
        (args.control_glb, "retained-control.glb"),
        (args.producer_glb, "producer-byte-joints.glb"),
        (args.control_transport_receipt, "control-transport-receipt.json"),
        (args.producer_transport_receipt, "producer-transport-receipt.json"),
        (args.adoption_receipt, "producer-joint-index-width-adoption-receipt.json"),
        (args.owner_frames, "exact-animation-owner-frames.json"),
        (args.geometry_basis, "exact-geometry-right-basis.json"),
    ):
        shutil.copyfile(source, args.out / name)
    (args.out / "exact-rigging-head.txt").write_text(args.current_rigging_head + "\n", encoding="utf-8")

    boundary = receipt["motion_boundary"]
    mutation = receipt["negative_controls"]["rigid_child_joint_identity_mutation"]
    print(receipt["state"])
    print(f"max_control_producer_position_residual_m={boundary['maximum_control_vs_producer_position_residual_m']}")
    print(f"max_producer_owner_position_residual_m={boundary['maximum_producer_vs_owner_position_residual_m']}")
    print(f"mutation_position_signal_m={mutation['position_signal_m']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
