"""Reusable Technical-Art proof for the executable UC receiver dependency closure.

This module does not define Animal semantics and does not modify Universal Creation.
It discovers local CommonJS dependencies from the exact receiver entry point, binds
that executable closure by Git-blob identity, and compares receiver observations.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "axm.technical-art-uc-receiver-dependency-continuity/v0.1"
STATE = "PASS_CURRENT_UC_RIGGED_RECEIVER_DEPENDENCY_CLOSURE_IDENTICAL_TO_TESTED_RECEIVER"
DEFAULT_ENTRY = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
_REQUIRE_RE = re.compile(r"require\(\s*['\"](\.{1,2}/[^'\"]+)['\"]\s*\)")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _normalize_relative_path(source_path: str, request: str) -> str:
    source = PurePosixPath(source_path)
    candidate = source.parent.joinpath(request)
    parts: list[str] = []
    for part in candidate.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError("CommonJS dependency escapes repository root")
            parts.pop()
        else:
            parts.append(part)
    resolved = PurePosixPath(*parts)
    if not resolved.suffix:
        resolved = resolved.with_suffix(".js")
    if resolved.suffix != ".js":
        raise ValueError(f"unsupported local CommonJS dependency type: {request}")
    return resolved.as_posix()


def commonjs_dependency_closure(root: Path, entry_path: str = DEFAULT_ENTRY) -> dict[str, str]:
    """Return the exact local CommonJS file closure as path -> Git blob SHA.

    Only relative ``require()`` edges are part of this executable source closure.
    Package/runtime dependencies stay outside this source-identity claim.
    """
    repository_root = Path(root).resolve()
    pending = [PurePosixPath(entry_path).as_posix()]
    observed: dict[str, str] = {}
    while pending:
        relative = pending.pop(0)
        if relative in observed:
            continue
        path = (repository_root / relative).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError as exc:
            raise ValueError("receiver dependency escapes repository root") from exc
        if not path.is_file():
            raise ValueError(f"receiver dependency missing: {relative}")
        data = path.read_bytes()
        observed[relative] = _git_blob_sha(data)
        text = data.decode("utf-8")
        for request in _REQUIRE_RE.findall(text):
            dependency = _normalize_relative_path(relative, request)
            if dependency not in observed and dependency not in pending:
                pending.append(dependency)
    return dict(sorted(observed.items()))


def require_exact_footprint(observed: dict[str, str], expected: dict[str, str], *, label: str) -> None:
    if not observed or not expected:
        raise ValueError(f"{label} receiver footprint must be non-empty")
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        added = sorted(set(observed) - set(expected))
        changed = sorted(
            path for path in set(observed).intersection(expected) if observed[path] != expected[path]
        )
        raise ValueError(
            f"{label} receiver dependency closure drift: missing={missing}, added={added}, changed={changed}"
        )


def build_continuity_receipt(
    *,
    technical_art_head: str,
    tested_uc_head: str,
    current_uc_head: str,
    source_glb_sha256: str,
    tested_footprint: dict[str, str],
    current_footprint: dict[str, str],
    expected_tested_footprint: dict[str, str],
    tested_inspection: dict[str, Any],
    current_inspection: dict[str, Any],
    tested_is_ancestor_of_current: bool,
) -> dict[str, Any]:
    for value, label in (
        (technical_art_head, "Technical Art head"),
        (tested_uc_head, "tested UC head"),
        (current_uc_head, "current UC head"),
        (source_glb_sha256, "source GLB SHA-256"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if tested_is_ancestor_of_current is not True:
        raise ValueError("tested UC receiver head is not an ancestor of current UC head")
    require_exact_footprint(tested_footprint, expected_tested_footprint, label="tested UC")
    require_exact_footprint(current_footprint, tested_footprint, label="current UC")
    if tested_inspection.get("pass") is not True or current_inspection.get("pass") is not True:
        raise ValueError("UC receiver inspection did not pass at both heads")
    if json.dumps(tested_inspection, sort_keys=True, separators=(",", ":")) != json.dumps(
        current_inspection, sort_keys=True, separators=(",", ":")
    ):
        raise ValueError("current UC receiver observation differs from tested receiver observation")

    return {
        "schema": SCHEMA,
        "state": STATE,
        "technical_art_head": technical_art_head,
        "universal_creation": {
            "tested_head": tested_uc_head,
            "current_head": current_uc_head,
            "tested_is_ancestor_of_current": True,
            "entry": DEFAULT_ENTRY,
            "tested_receiver_dependency_closure": tested_footprint,
            "current_receiver_dependency_closure": current_footprint,
            "product_modified": False,
        },
        "exact_source": {
            "glb_sha256": source_glb_sha256,
            "tested_receiver_inspection": tested_inspection,
            "current_receiver_inspection": current_inspection,
            "inspection_identical": True,
        },
        "truth_boundary": {
            "uc_receiver_executable_source_closure_identical": True,
            "exact_source_receiver_observation_identical": True,
            "animal_domain_policy_moved_into_uc": False,
            "uc_product_modified": False,
            "godot_target_host_rerun_at_current_uc_head": False,
            "bilateral_target_host_equivalence_established": False,
            "runtime_product_implementation_established": False,
            "target_device_performance_accepted": False,
            "canon_claimed": False,
            "production_ready": False,
        },
    }
