#!/usr/bin/env python3
"""Run the exact-mirror bridge with an explicit source-ID -> UC-ID projection.

Geometry candidate IDs remain untouched and digest-authoritative. Only the UC
transport copy receives a short portable group ID required by the generic UC
surface contract. The resulting mapping is appended to retained evidence.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.uc_transport_identity import project_candidate_transport_id

BUILDER_PATH = ROOT / "tools" / "build_uc_bilateral_mirror_surface_bridge_evidence.py"
OUTPUT_DIR = ROOT / "evidence" / "uc_bilateral_mirror_surface"
RECEIPT_PATH = OUTPUT_DIR / "quadruped_bilateral_mirror_surface_uc_bridge.evidence.json"
PORTABLE_IDS = {
    "left": "animal-selected003-left",
    "right": "animal-selected003-right-mirror",
}


def load_builder():
    spec = importlib.util.spec_from_file_location("axm_exact_mirror_uc_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load exact-mirror UC evidence builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def side_for_source_id(source_id: str) -> str:
    left = "-left-" in source_id
    right = "-right-" in source_id
    if left == right:
        raise RuntimeError(f"cannot resolve one transport side from source candidate id: {source_id}")
    return "left" if left else "right"


def main() -> int:
    builder = load_builder()
    base_adapter = builder.adapt_geometry_candidate_for_uc
    mappings: dict[str, dict] = {}

    def projected_adapter(candidate: dict, *, name: str, material: dict) -> dict:
        source_id = candidate.get("id")
        if not isinstance(source_id, str):
            raise RuntimeError("source candidate id is required before transport projection")
        side = side_for_source_id(source_id)
        projected, mapping = project_candidate_transport_id(candidate, portable_group_id=PORTABLE_IDS[side])
        if side in mappings and mappings[side] != mapping:
            raise RuntimeError(f"multiple conflicting {side} transport identity projections")
        mappings[side] = mapping
        return base_adapter(projected, name=name, material=material)

    builder.adapt_geometry_candidate_for_uc = projected_adapter
    result = builder.main()
    if result != 0:
        return int(result)
    if set(mappings) != {"left", "right"}:
        raise RuntimeError("both explicit transport identity projections were not exercised")
    if not RECEIPT_PATH.is_file():
        raise RuntimeError("exact-mirror bridge receipt is missing after successful builder run")

    left_surface = json.loads((OUTPUT_DIR / "quadruped_selected003_mirror_left_uc_surface.json").read_text(encoding="utf-8"))
    right_surface = json.loads((OUTPUT_DIR / "quadruped_selected003_mirror_right_uc_surface.json").read_text(encoding="utf-8"))
    observed = {
        "left": left_surface.get("primitives", [{}])[0].get("id"),
        "right": right_surface.get("primitives", [{}])[0].get("id"),
    }
    if observed != PORTABLE_IDS:
        raise RuntimeError(f"retained UC group IDs differ from explicit projection contract: {observed}")

    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    receipt["transport_identifier_projection"] = {
        "contract": (
            "Geometry-owned source candidate IDs and hashes remain authoritative; Technical Art projects only "
            "a receiver-local UC portable group ID on a deep copy after exact source identity verification."
        ),
        "left": mappings["left"],
        "right": mappings["right"],
        "retained_uc_group_ids": observed,
        "uc_receiver_constraint": "^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$",
        "source_identity_rewritten": False,
        "geometry_rewritten": False,
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt.get("status"),
        "transport_identifier_projection": observed,
        "source_identity_rewritten": False,
        "geometry_rewritten": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
