"""Evidence verifier — every cited raw_ref must exist in stored data (E6, NF3, T8)."""

from __future__ import annotations

from collections.abc import Callable

from common.schema import Candidate, Evidence

Resolver = Callable[[str], bool]


def verify_evidence(
    candidates: list[Candidate],
    evidence_by_id: dict[str, Evidence],
    *,
    exists: Resolver,
) -> tuple[list[Candidate], list[str]]:
    """Drop or flag evidence whose raw_ref does not resolve.

    Returns (cleaned candidates, rejected evidence ids).
    """
    rejected: list[str] = []
    cleaned: list[Candidate] = []
    for cand in candidates:
        keep: list[str] = []
        for eid in cand.evidence:
            ev = evidence_by_id.get(eid)
            if ev is None or not exists(ev.raw_ref):
                rejected.append(eid)
                continue
            keep.append(eid)
        cleaned.append(cand.model_copy(update={"evidence": keep}))
    return cleaned, rejected
