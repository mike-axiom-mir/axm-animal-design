"""Technical-art-only source-ID -> UC transport-ID projection.

Domain candidate identity remains owned by Animal Geometry. This helper creates a
copy with a bounded portable receiver identifier only after callers have already
verified the exact source candidate identity. It exists because UC's generic
surface contract deliberately restricts group IDs to portable identifiers.
"""
from __future__ import annotations

import copy
import re
from typing import Any

UC_PORTABLE_GROUP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def project_candidate_transport_id(candidate: dict[str, Any], *, portable_group_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a non-mutating candidate copy with one explicit UC transport ID.

    This function does not establish or alter Geometry identity. Callers must
    fail closed on the source candidate digest before invoking it. The returned
    mapping receipt makes the source/receiver naming boundary auditable.
    """
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    source_id = candidate.get("id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source candidate id is required")
    if not isinstance(portable_group_id, str) or not UC_PORTABLE_GROUP_ID_RE.fullmatch(portable_group_id):
        raise ValueError("portable_group_id must satisfy UC's 1..80 portable identifier contract")

    projected = copy.deepcopy(candidate)
    projected["id"] = portable_group_id
    mapping = {
        "source_candidate_id": source_id,
        "uc_portable_group_id": portable_group_id,
        "source_candidate_mutated": False,
        "positions_preserved": projected.get("positions") == candidate.get("positions"),
        "indices_preserved": projected.get("indices") == candidate.get("indices"),
        "scope": "transport-identifier-only",
    }
    if not mapping["positions_preserved"] or not mapping["indices_preserved"]:
        raise RuntimeError("transport identifier projection changed source geometry")
    return projected, mapping
