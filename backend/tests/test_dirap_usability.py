"""Tests for DIRAP v3.0 Usability slice (read-only, policy v1).

Covers:
- Pure policy engine: every rule of the six query types, with at least one
  usable / partial_usable / unusable case per type as specified in the task.
- official_search & legal_review reject organizational / expert / derived.
- analysis_input accepts the four allowed authority values.
- memory_query is not blocked by authority or source when owner=accepted.
- none is accepted wherever the policy allows "any".
- API: 404 for foreign/missing records, 422 for an invalid query_type.
- API is read-only: record dimensions + lifecycle unchanged, no audit event,
  no new table (no migration) created by the policy computation.
"""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest
from httpx import AsyncClient

from app.services.usability_policy import (
    QUERY_TYPES,
    evaluate_usability,
    usable_for_query_types,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


async def _mk_draft(client: AsyncClient, tmp_path: Path, content: str = "fact\n") -> tuple[str, str]:
    """Create session + work item + source file + extract + draft; return (task_id, kr_id)."""
    resp = await client.post("/api/sessions", json={"title": "UB", "workspace_path": str(tmp_path)})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "UB WI"})
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    (tmp_path / "doc.txt").write_text(content, encoding="utf-8")
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files", json={"file_path": "doc.txt"}
    )
    assert resp.status_code == 201
    source_file_id = resp.json()["id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files/{source_file_id}/extract"
    )
    assert resp.status_code == 201
    r = resp.json()
    extraction_id, record_id = r["extraction"]["id"], r["records"][0]["id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_id},
    )
    assert resp.status_code == 201
    return task_id, resp.json()["id"]


async def _mk_active(
    client: AsyncClient,
    tmp_path: Path,
    authority: str,
    with_calc: bool = False,
) -> tuple[str, str]:
    """draft → review_pending → active with the given authority; return (task_id, kr_id)."""
    task_id, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})
    payload: dict = {
        "reviewer": "rv-ub",
        "source_evidence_reference": "doc.txt line 1",
        "authority_status": authority,
        "authority_reference": "ref/2026/1",
    }
    if with_calc:
        payload["calculation_evidence_reference"] = "calc.xlsx sheet1"
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json=payload,
    )
    assert resp.status_code == 200
    return task_id, kr_id


async def _record_dims(tmp_path: Path, kr_id: str) -> dict:
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, source_verification_state, calculation_verification_state, "
            "owner_acceptance_state, authority_status FROM dirap_knowledge_records WHERE id = ?",
            (kr_id,),
        ) as cur:
            row = await cur.fetchone()
    assert row is not None
    return dict(row)


async def _audit_rows_for(tmp_path: Path, kr_id: str) -> list[dict]:
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action, target, payload_json FROM audit_events WHERE target = ? ORDER BY id",
            (kr_id,),
        ) as cur:
            rows = await cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        raw = d.pop("payload_json", None)
        d["payload"] = json.loads(raw) if raw else None
        out.append(d)
    return out


async def _table_names(tmp_path: Path) -> set[str]:
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
        ) as cur:
            rows = await cur.fetchall()
    return {r[0] for r in rows}


# -----------------------------------------------------------------------------
# Pure policy engine — rule per query type (usable / partial / unusable)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_official_search_rules() -> None:
    """official_search: full-usable; partial when source+authority ok; else unusable."""
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="official_search",
    ).overall_usability_state == "usable"

    # Partial: missing calculation only
    partial_calc = evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="official_search",
    )
    assert partial_calc.overall_usability_state == "partial_usable"
    dims = {e.dimension for e in partial_calc.exclusions}
    assert dims == {"calculation_verification_state"}

    # Partial: missing owner only
    partial_owner = evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="pending",
        authority_status="regulatory",
        query_type="official_search",
    )
    assert partial_owner.overall_usability_state == "partial_usable"
    assert {e.dimension for e in partial_owner.exclusions} == {"owner_acceptance_state"}

    # Unusable: wrong authority
    unusable_auth = evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="organizational",
        query_type="official_search",
    )
    assert unusable_auth.overall_usability_state == "unusable"
    assert {e.dimension for e in unusable_auth.exclusions} == {"authority_status"}

    # Unusable: source unverified
    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="official_search",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_official_legal_reject_non_regulatory() -> None:
    """official_search & legal_review refuse organizational / expert / derived / none."""
    for qtype in ("official_search", "legal_review"):
        for authority in ("organizational", "expert", "derived", "none"):
            result = evaluate_usability(
                source_verification_state="verified",
                calculation_verification_state="verified",
                owner_acceptance_state="accepted",
                authority_status=authority,
                query_type=qtype,
            )
            assert result.overall_usability_state == "unusable", (qtype, authority)


@pytest.mark.asyncio
async def test_policy_exploratory_search_rules() -> None:
    """exploratory_search: partial when source verified (any other dimension), else unusable."""
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",
        owner_acceptance_state="pending",
        authority_status="none",
        query_type="exploratory_search",
    ).overall_usability_state == "partial_usable"

    unusable = evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="exploratory_search",
    )
    assert unusable.overall_usability_state == "unusable"
    assert {e.dimension for e in unusable.exclusions} == {"source_verification_state"}


@pytest.mark.asyncio
async def test_policy_analysis_input_accepts_four_values() -> None:
    """analysis_input: usable for regulatory|organizational|expert|derived (with sv+cv verified)."""
    for authority in ("regulatory", "organizational", "expert", "derived"):
        result = evaluate_usability(
            source_verification_state="verified",
            calculation_verification_state="verified",
            owner_acceptance_state="pending",  # owner is not a condition here
            authority_status=authority,
            query_type="analysis_input",
        )
        assert result.overall_usability_state == "usable", authority
        assert result.exclusions == []

    # none is refused where a specific set applies
    refused = evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="none",
        query_type="analysis_input",
    )
    assert refused.overall_usability_state == "partial_usable"
    assert {e.dimension for e in refused.exclusions} == {"authority_status"}

    # Partial: source ok but calculation missing
    partial = evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",
        owner_acceptance_state="accepted",
        authority_status="expert",
        query_type="analysis_input",
    )
    assert partial.overall_usability_state == "partial_usable"

    # Unusable: source unverified
    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="analysis_input",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_legal_review_rules() -> None:
    """legal_review: usable only full regulatory; every other case unusable (no partial)."""
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="legal_review",
    ).overall_usability_state == "usable"

    # Missing owner alone => unusable (no partial tier)
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="pending",
        authority_status="regulatory",
        query_type="legal_review",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_context_packaging_rules() -> None:
    """context_packaging: usable only when source verified + owner accepted."""
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",  # not a condition
        owner_acceptance_state="accepted",
        authority_status="none",  # not a condition
        query_type="context_packaging",
    ).overall_usability_state == "usable"

    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="pending",
        authority_status="regulatory",
        query_type="context_packaging",
    ).overall_usability_state == "unusable"

    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
        query_type="context_packaging",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_memory_query_owner_only() -> None:
    """memory_query: usable when owner accepted; never blocked by authority or source."""
    # owner accepted with everything else missing/unset
    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="unverified",
        owner_acceptance_state="accepted",
        authority_status="none",
        query_type="memory_query",
    ).overall_usability_state == "usable"

    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="unverified",
        owner_acceptance_state="pending",
        authority_status="none",
        query_type="memory_query",
    ).overall_usability_state == "unusable"

    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="rejected",
        authority_status="regulatory",
        query_type="memory_query",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_none_accepted_in_any_conditions() -> None:
    """none satisfies 'any' conditions but never a specific authority set."""
    # memory_query: owner accepted + authority none => usable
    assert evaluate_usability(
        source_verification_state="unverified",
        calculation_verification_state="unverified",
        owner_acceptance_state="accepted",
        authority_status="none",
        query_type="memory_query",
    ).overall_usability_state == "usable"
    # context_packaging: none authority fine
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",
        owner_acceptance_state="accepted",
        authority_status="none",
        query_type="context_packaging",
    ).overall_usability_state == "usable"
    # exploratory: none authority fine
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="unverified",
        owner_acceptance_state="pending",
        authority_status="none",
        query_type="exploratory_search",
    ).overall_usability_state == "partial_usable"
    # official_search: none authority is NOT accepted
    assert evaluate_usability(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="none",
        query_type="official_search",
    ).overall_usability_state == "unusable"


@pytest.mark.asyncio
async def test_policy_usable_for_query_types_only_usable() -> None:
    """usable_for_query_types lists only 'usable' purposes, never partial_usable."""
    usable = usable_for_query_types(
        source_verification_state="verified",
        calculation_verification_state="verified",
        owner_acceptance_state="accepted",
        authority_status="regulatory",
    )
    # official, analysis, legal, context, memory are usable; exploratory never is
    assert usable == [
        "official_search",
        "analysis_input",
        "legal_review",
        "context_packaging",
        "memory_query",
    ]

    none_usable = usable_for_query_types(
        source_verification_state="unverified",
        calculation_verification_state="unverified",
        owner_acceptance_state="pending",
        authority_status="none",
    )
    assert none_usable == []


@pytest.mark.asyncio
async def test_policy_unknown_query_type_raises() -> None:
    with pytest.raises(ValueError):
        evaluate_usability(
            source_verification_state="verified",
            calculation_verification_state="verified",
            owner_acceptance_state="accepted",
            authority_status="regulatory",
            query_type="not_a_query_type",
        )


@pytest.mark.asyncio
async def test_policy_query_types_exactly_six() -> None:
    """The engine exposes exactly the six canonical purposes, no extras."""
    assert QUERY_TYPES == (
        "official_search",
        "exploratory_search",
        "analysis_input",
        "legal_review",
        "context_packaging",
        "memory_query",
    )


# -----------------------------------------------------------------------------
# API — GET usability
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_usable_full_regulatory_record(client: AsyncClient, tmp_path: Path) -> None:
    """Active record (sv/cv verified, owner accepted, regulatory) is usable for official_search."""
    task_id, kr_id = await _mk_active(client, tmp_path, "regulatory", with_calc=True)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["record_id"] == kr_id
    assert body["lifecycle_state"] == "active"
    assert body["query_type"] == "official_search"
    assert body["source_verification_state"] == "verified"
    assert body["calculation_verification_state"] == "verified"
    assert body["owner_acceptance_state"] == "accepted"
    assert body["authority_status"] == "regulatory"
    assert body["overall_usability_state"] == "usable"
    assert body["policy_version"] == "v1"
    assert body["exclusions"] == []
    assert "official_search" in body["usable_for_query_types"]
    assert "exploratory_search" not in body["usable_for_query_types"]


@pytest.mark.asyncio
async def test_api_draft_record_official_search_unusable_with_exclusions(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A draft (default dimensions) is unusable for official_search with all reasons listed."""
    task_id, kr_id = await _mk_draft(client, tmp_path)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lifecycle_state"] == "draft"
    assert body["overall_usability_state"] == "unusable"
    dims = {e["dimension"] for e in body["exclusions"]}
    assert dims == {
        "source_verification_state",
        "calculation_verification_state",
        "owner_acceptance_state",
        "authority_status",
    }
    for exc in body["exclusions"]:
        assert exc["required_state"]
        assert exc["actual_state"]
        assert exc["reason"]


@pytest.mark.asyncio
async def test_api_analysis_input_accepts_non_regulatory(client: AsyncClient, tmp_path: Path) -> None:
    """organizational record usable for analysis_input (and not for legal_review)."""
    task_id, kr_id = await _mk_active(client, tmp_path, "organizational", with_calc=True)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "analysis_input"},
    )
    assert resp.status_code == 200
    assert resp.json()["overall_usability_state"] == "usable"

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "legal_review"},
    )
    assert resp.status_code == 200
    assert resp.json()["overall_usability_state"] == "unusable"


@pytest.mark.asyncio
async def test_api_official_search_rejects_organizational(client: AsyncClient, tmp_path: Path) -> None:
    """official_search refuses a non-regulatory authority over the API."""
    task_id, kr_id = await _mk_active(client, tmp_path, "expert", with_calc=True)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_usability_state"] == "unusable"
    assert {e["dimension"] for e in body["exclusions"]} == {"authority_status"}


@pytest.mark.asyncio
async def test_api_memory_query_not_blocked_by_authority(client: AsyncClient, tmp_path: Path) -> None:
    """memory_query stays usable for an accepted record even with non-regulatory authority."""
    task_id, kr_id = await _mk_active(client, tmp_path, "derived", with_calc=True)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "memory_query"},
    )
    assert resp.status_code == 200
    assert resp.json()["overall_usability_state"] == "usable"


@pytest.mark.asyncio
async def test_api_foreign_record_404(client: AsyncClient, tmp_path: Path) -> None:
    """A record from another work item is 404 (task scoping enforced)."""
    task_a, kr_a = await _mk_active(client, tmp_path, "regulatory", with_calc=True)
    task_b, _ = await _mk_draft(client, tmp_path)

    resp = await client.get(
        f"/api/dirap/work-items/{task_b}/knowledge-records/{kr_a}/usability",
        params={"query_type": "memory_query"},
    )
    assert resp.status_code == 404
    assert task_a != task_b


@pytest.mark.asyncio
async def test_api_missing_record_404(client: AsyncClient, tmp_path: Path) -> None:
    task_id, _ = await _mk_draft(client, tmp_path)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/does-not-exist/usability",
        params={"query_type": "memory_query"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_invalid_query_type_422(client: AsyncClient, tmp_path: Path) -> None:
    task_id, kr_id = await _mk_draft(client, tmp_path)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "not_a_query_type"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_readonly_no_db_change_no_audit_no_migration(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Computing usability must not mutate the record, add audit events or tables."""
    task_id, kr_id = await _mk_active(client, tmp_path, "regulatory", with_calc=True)

    before_dims = await _record_dims(tmp_path, kr_id)
    before_audit = await _audit_rows_for(tmp_path, kr_id)
    before_tables = await _table_names(tmp_path)
    assert "overall_usability_state" not in before_dims
    assert not any("usability" in t for t in before_tables)

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/usability",
        params={"query_type": "official_search"},
    )
    assert resp.status_code == 200
    assert resp.json()["overall_usability_state"] == "usable"

    after_dims = await _record_dims(tmp_path, kr_id)
    after_audit = await _audit_rows_for(tmp_path, kr_id)
    after_tables = await _table_names(tmp_path)

    assert after_dims == before_dims  # lifecycle + four dimensions untouched
    assert after_audit == before_audit  # no new audit event for a policy read
    assert after_tables == before_tables  # no new table (no migration)
