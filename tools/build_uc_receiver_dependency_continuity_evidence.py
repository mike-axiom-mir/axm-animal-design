#!/usr/bin/env python3
"""Prove the exact executable UC rigged-receiver closure stayed unchanged.

This is Technical-Art integration evidence only. It compares a previously tested UC
receiver head with the currently inspected UC head, discovers local CommonJS source
dependencies from the receiver entry point, then runs the exact same source GLB
through both receivers. No Animal semantics are copied into UC.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.uc_receiver_dependency_continuity import (
    DEFAULT_ENTRY,
    STATE,
    build_continuity_receipt,
    commonjs_dependency_closure,
)

TESTED_UC_HEAD = "aa53ee8aa803c19524b7edbef6250bf6ed9336c0"
CURRENT_UC_HEAD = "452b179cccff8acdde8930f7bde8662e52f86949"
SOURCE_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
EXPECTED_TESTED_FOOTPRINT = {
    "capabilities/platform-hands/shared/asset-hands/gltf-codec.js": "31d3145bc337214fc77da0b8955acf91da3f2253",
    "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js": "02b69b6c7368ba6e34f226ca545293d26d208922",
}


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def inspect(root: Path, glb: Path) -> dict[str, Any]:
    script = r"""
const fs = require('fs');
const codec = require(process.argv[1]);
const bytes = new Uint8Array(fs.readFileSync(process.argv[2]));
process.stdout.write(JSON.stringify(codec.inspect(bytes)));
"""
    output = subprocess.check_output(
        ["node", "-e", script, str((root / DEFAULT_ENTRY).resolve()), str(glb.resolve())],
        text=True,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("UC receiver inspection must return an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tested-uc-root", type=Path, required=True)
    parser.add_argument("--current-uc-root", type=Path, required=True)
    parser.add_argument("--source-glb", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if git_head(args.tested_uc_root) != TESTED_UC_HEAD:
        raise ValueError("tested UC checkout drift")
    if git_head(args.current_uc_root) != CURRENT_UC_HEAD:
        raise ValueError("current UC checkout drift")
    ancestor = subprocess.run(
        ["git", "-C", str(args.current_uc_root), "merge-base", "--is-ancestor", TESTED_UC_HEAD, CURRENT_UC_HEAD],
        check=False,
    ).returncode == 0
    if not ancestor:
        raise ValueError("tested UC receiver head is not an ancestor of current UC head")

    source_bytes = args.source_glb.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != SOURCE_GLB_SHA256:
        raise ValueError("exact Animal source GLB identity drift")

    tested_footprint = commonjs_dependency_closure(args.tested_uc_root)
    current_footprint = commonjs_dependency_closure(args.current_uc_root)
    tested_inspection = inspect(args.tested_uc_root, args.source_glb)
    current_inspection = inspect(args.current_uc_root, args.source_glb)

    receipt = build_continuity_receipt(
        technical_art_head=args.technical_art_head,
        tested_uc_head=TESTED_UC_HEAD,
        current_uc_head=CURRENT_UC_HEAD,
        source_glb_sha256=source_sha,
        tested_footprint=tested_footprint,
        current_footprint=current_footprint,
        expected_tested_footprint=EXPECTED_TESTED_FOOTPRINT,
        tested_inspection=tested_inspection,
        current_inspection=current_inspection,
        tested_is_ancestor_of_current=ancestor,
    )
    if receipt.get("state") != STATE:
        raise ValueError("receiver continuity receipt did not reach exact PASS state")

    corrupted = copy.deepcopy(current_footprint)
    corrupted["capabilities/platform-hands/shared/asset-hands/gltf-codec.js"] = "0" * 40
    try:
        build_continuity_receipt(
            technical_art_head=args.technical_art_head,
            tested_uc_head=TESTED_UC_HEAD,
            current_uc_head=CURRENT_UC_HEAD,
            source_glb_sha256=source_sha,
            tested_footprint=tested_footprint,
            current_footprint=corrupted,
            expected_tested_footprint=EXPECTED_TESTED_FOOTPRINT,
            tested_inspection=tested_inspection,
            current_inspection=current_inspection,
            tested_is_ancestor_of_current=True,
        )
    except ValueError as exc:
        negative = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("deliberate base-codec dependency mutation unexpectedly passed")

    receipt["negative_control"] = {
        "mutation": "replace only gltf-codec.js dependency blob identity while retaining rigged wrapper identity",
        **negative,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "uc-rigged-receiver-dependency-continuity.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.out / "technical-art-head.txt").write_text(args.technical_art_head + "\n", encoding="utf-8")
    (args.out / "tested-uc-head.txt").write_text(TESTED_UC_HEAD + "\n", encoding="utf-8")
    (args.out / "current-uc-head.txt").write_text(CURRENT_UC_HEAD + "\n", encoding="utf-8")
    (args.out / "source-glb-sha256.txt").write_text(source_sha + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
