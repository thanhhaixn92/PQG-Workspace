"""Tests for DIRAP v3.0 Controlled Knowledge Search slice (read-only).

Covers:
- Task scoping: never leaks records of another work item
- Deterministic matching: content + provenance, casefold, multi-space phrases
- Route /search never treated as {knowledge_record_id}
- Validation: empty/blank/too-long q, bad query_type, bad limit/offset -> 422
- Policy filtering (v1) BEFORE pagination:
  * official_search / legal_review return only authority=regulatory
  * analysis_input accepts all four allowed authorities
  * exploratory_search may return partial_usable; other purposes never do
- Pagination happens after policy filtering
- Search is strictly read-only: no DB change, no audit, no migration
"""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest
from httpx import AsyncClient


async def _mk_wi(client: AsyncClient, tmp_path: Path, title: str) -> tuple[str, str]:
    """Create a session + work item; return (session_id, task_id)."""
    resp = await client.post(
        "/api/sessions", json={"title": title, "workspace_path": str(tmp_path)}
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]
    resp = await client.post(
        "/api/dirap/work-items", json={"session_id": session_id, "title": f"{title} WI"}
    )
    assert resp.status_code == 201
    return session_id, resp.json()["task_id"]


async def _mk_record(
    client: AsyncClient,
    tmp_path: Path,
    task_id: str,
    content: str,
    *,
    authority: str = "regulatory",
    with_calculation: bool = True,
    approve: bool = True,
    filename: str = "rec.txt",
) -> dict:
    """Create one knowledge record inside an existing task.

    Returns the record dict (with status + four dimensions) after optional
    submit+approve (mimics the accepted Knowledge Review slice).
    """
    (tmp_path / filename).write_text(content, encoding="utf-8")
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": filename},
    )
    assert resp.status_code == 201
    source_file_id = resp.json()["id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files/{source_file_id}/extract"
    )
    assert resp.status_code == 201
    r = resp.json()
    extraction_id = r["extraction"]["id"]
    record_id = r["records"][0]["id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_id},
    )
    assert resp.status_code == 201
    kr = resp.json()

    if approve:
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/knowledge-records/{kr['id']}/submit",
            json={},
        )
        assert resp.status_code == 200
        payload: dict = {
            "reviewer": "reviewer-1",
            "source_evidence_reference": f"{filename} {kr['provenance'] or 'line 1'}",
            "authority_status": authority,
            "authority_reference": "ket-luan/2026/2.1",
        }
        if with_calculation:
            payload["calculation_evidence_reference"] = "calc-report.xlsx sheet2"
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/knowledge-records/{kr['id']}/review/approve",
            json=payload,
        )
        assert resp.status_code == 200
        kr = resp.json()

    return kr


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_app.db"


async def _snapshot(tmp_path: Path) -> dict:
    """Snapshot records + audit + tables for read-only assertions."""
    async with aiosqlite.connect(str(_db_path(tmp_path))) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, status, source_verification_state, calculation_verification_state, "
            "owner_acceptance_state, authority_status, content FROM dirap_knowledge_records "
            "ORDER BY id"
        ) as cur:
            records = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT COUNT(*) AS n FROM audit_events") as cur:
            audit_count = (await cur.fetchone())["n"]
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cur:
            tables = [r["name"] for r in await cur.fetchall()]
    return {"records": records, "audit_count": audit_count, "tables": tables}


# ---------------------------------------------------------------- matching


@pytest.mark.asyncio
async def test_match_content_casefold_and_multispace(
    client: AsyncClient, tmp_path: Path
) -> None:
    """casefold + collapsed whitespace: 'vùng   BIỂN abc' matches content."""
    _, task_id = await _mk_wi(client, tmp_path, "S1")
    await _mk_record(
        client, tmp_path, task_id, "Hải đồ vùng biển ABC 2026\n",
        filename="a1.txt",
    )
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "vùng   BIỂN abc", "query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["matched_field"] == "content"
    assert body["results"][0]["usability_state"] == "usable"


@pytest.mark.asyncio
async def test_match_provenance(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Casefold match in provenance ('LINE 1' matches 'line 1')."""
    _, task_id = await _mk_wi(client, tmp_path, "S2")
    await _mk_record(client, tmp_path, task_id, "Hải đồ vùng biển ABC 2026\n", filename="b1.txt")
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "LINE 1", "query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["matched_field"] == "provenance"


@pytest.mark.asyncio
async def test_no_match_returns_empty(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id = await _mk_wi(client, tmp_path, "S3")
    await _mk_record(client, tmp_path, task_id, "Hải đồ vùng biển ABC 2026\n", filename="c1.txt")
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "không có trong kho", "query_type": "official_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


# ---------------------------------------------------------------- scoping


@pytest.mark.asyncio
async def test_task_scoping_never_leaks_other_task(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Same phrase in both tasks: each task sees only its own record."""
    _, task_a = await _mk_wi(client, tmp_path, "SA")
    _, task_b = await _mk_wi(client, tmp_path, "SB")
    ra = await _mk_record(client, tmp_path, task_a, "CẦU CẢNG HẢI PHÒNG 2026\n", filename="d1.txt")
    rb = await _mk_record(client, tmp_path, task_b, "CẦU CẢNG HẢI PHÒNG 2026\n", filename="e1.txt")

    resp_a = await client.get(
        f"/api/dirap/work-items/{task_a}/knowledge-records/search",
        params={"q": "cầu cảng", "query_type": "official_search"},
    )
    assert resp_a.status_code == 200
    ids_a = [r["record_id"] for r in resp_a.json()["results"]]
    assert ids_a == [ra["id"]]
    assert rb["id"] not in ids_a

    resp_b = await client.get(
        f"/api/dirap/work-items/{task_b}/knowledge-records/search",
        params={"q": "cầu cảng", "query_type": "official_search"},
    )
    ids_b = [r["record_id"] for r in resp_b.json()["results"]]
    assert ids_b == [rb["id"]]


@pytest.mark.asyncio
async def test_unknown_task_returns_404(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.get(
        "/api/dirap/work-items/no-such-task/knowledge-records/search",
        params={"q": "abc", "query_type": "official_search"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------- policy filters


@pytest.mark.asyncio
async def test_official_and_legal_only_regulatory(
    client: AsyncClient, tmp_path: Path
) -> None:
    _, task_id = await _mk_wi(client, tmp_path, "S4")
    await _mk_record(client, tmp_path, task_id, "Bản tin hàng hải R1\n", authority="regulatory", filename="f1.txt")
    await _mk_record(client, tmp_path, task_id, "Bản tin hàng hải R2\n", authority="organizational", filename="f2.txt")
    await _mk_record(client, tmp_path, task_id, "Bản tin hàng hải R3\n", authority="expert", filename="f3.txt")
    await _mk_record(client, tmp_path, task_id, "Bản tin hàng hải R4\n", authority="derived", filename="f4.txt")

    for purpose in ("official_search", "legal_review"):
        resp = await client.get(
            f"/api/dirap/work-items/{task_id}/knowledge-records/search",
            params={"q": "bản tin", "query_type": purpose},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1, purpose
        assert body["results"][0]["authority_status"] == "regulatory"


@pytest.mark.asyncio
async def test_analysis_input_accepts_four_authorities(
    client: AsyncClient, tmp_path: Path
) -> None:
    _, task_id = await _mk_wi(client, tmp_path, "S5")
    for i, authority in enumerate(("regulatory", "organizational", "expert", "derived")):
        await _mk_record(
            client, tmp_path, task_id, f"Phân tích dữ liệu {authority}\n",
            authority=authority, filename=f"g{i}.txt",
        )
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "phân tích", "query_type": "analysis_input"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    authorities = sorted(r["authority_status"] for r in body["results"])
    assert authorities == ["derived", "expert", "organizational", "regulatory"]


@pytest.mark.asyncio
async def test_exploratory_allows_partial_and_others_do_not(
    client: AsyncClient, tmp_path: Path
) -> None:
    """verified source + unverified calculation => partial_usable:
    allowed for exploratory_search only; strict purposes must drop it."""
    _, task_id = await _mk_wi(client, tmp_path, "S6")
    kr = await _mk_record(
        client, tmp_path, task_id, "Nghiên cứu luồng hàng hải X\n",
        authority="regulatory", with_calculation=False, filename="h1.txt",
    )
    assert kr["source_verification_state"] == "verified"
    assert kr["calculation_verification_state"] == "unverified"

    # exploratory: partial_usable is returned with the level shown
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "nghiên cứu", "query_type": "exploratory_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["usability_state"] == "partial_usable"

    # strict purposes: never return partial_usable. This record is only
    # partial for analysis_input; for official_search / legal_review it is
    # unusable (authority alone is not enough). It is genuinely usable for
    # context_packaging (sv verified + owner accepted) and memory_query
    # (owner accepted), so those two goals DO return it — as usable.
    expected_totals = {
        "official_search": 0,
        "analysis_input": 0,
        "legal_review": 0,
        "context_packaging": 1,
        "memory_query": 1,
    }
    for purpose, expected in expected_totals.items():
        resp = await client.get(
            f"/api/dirap/work-items/{task_id}/knowledge-records/search",
            params={"q": "nghiên cứu", "query_type": purpose},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == expected, purpose
        if expected:
            assert body["results"][0]["usability_state"] == "usable"


@pytest.mark.asyncio
async def test_rejected_record_is_excluded_from_every_query_type(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Terminal lifecycle always wins over otherwise-valid evidence dimensions."""
    _, task_id = await _mk_wi(client, tmp_path, "Rejected Matrix")
    kr = await _mk_record(
        client, tmp_path, task_id, "controlled lifecycle evidence\n",
        filename="rejected-matrix.txt",
    )
    async with aiosqlite.connect(str(_db_path(tmp_path))) as db:
        await db.execute(
            """UPDATE dirap_knowledge_records
               SET status = 'rejected', owner_acceptance_state = 'rejected'
               WHERE id = ?""",
            (kr["id"],),
        )
        await db.commit()

    for query_type in (
        "official_search", "analysis_input", "legal_review",
        "exploratory_search", "context_packaging", "memory_query",
    ):
        response = await client.get(
            f"/api/dirap/work-items/{task_id}/knowledge-records/search",
            params={"q": "controlled lifecycle", "query_type": query_type},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0, query_type
        assert response.json()["results"] == [], query_type


# ---------------------------------------------------------------- pagination


@pytest.mark.asyncio
async def test_pagination_happens_after_policy_filter(
    client: AsyncClient, tmp_path: Path
) -> None:
    """3 usable records + 1 draft (unusable): total reflects only allowed ones;
    pages slice the already-filtered list."""
    _, task_id = await _mk_wi(client, tmp_path, "S7")
    for i in range(3):
        await _mk_record(client, tmp_path, task_id, f"Điều lệ cảng biển {i}\n", filename=f"i{i}.txt")
    # one matching draft stays unusable (defaults unverified/pending/none)
    await _mk_record(
        client, tmp_path, task_id, "Điều lệ cảng biển draft\n",
        approve=False, filename="draft.txt",
    )

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "điều lệ", "query_type": "official_search", "limit": 2, "offset": 0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3, "draft must not count after policy filtering"
    assert len(body["results"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "điều lệ", "query_type": "official_search", "limit": 2, "offset": 2},
    )
    body = resp.json()
    assert body["total"] == 3
    assert len(body["results"]) == 1

    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "điều lệ", "query_type": "official_search", "limit": 2, "offset": 3},
    )
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_default_limit_and_offset(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id = await _mk_wi(client, tmp_path, "S8")
    await _mk_record(client, tmp_path, task_id, "Chỉ thị an toàn hàng hải\n", filename="j1.txt")
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "an toàn", "query_type": "context_packaging"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 1


# ---------------------------------------------------------------- validation


@pytest.mark.asyncio
async def test_validation_errors(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id = await _mk_wi(client, tmp_path, "S9")
    base = f"/api/dirap/work-items/{task_id}/knowledge-records/search"

    # empty q
    resp = await client.get(base, params={"q": "", "query_type": "official_search"})
    assert resp.status_code == 422
    # whitespace-only q (empty after normalization)
    resp = await client.get(base, params={"q": "     ", "query_type": "official_search"})
    assert resp.status_code == 422
    # q longer than 200 chars
    resp = await client.get(
        base, params={"q": "x" * 201, "query_type": "official_search"}
    )
    assert resp.status_code == 422
    # bad query_type
    resp = await client.get(base, params={"q": "abc", "query_type": "bogus"})
    assert resp.status_code == 422
    # bad limit / offset
    resp = await client.get(base, params={"q": "abc", "query_type": "official_search", "limit": 0})
    assert resp.status_code == 422
    resp = await client.get(base, params={"q": "abc", "query_type": "official_search", "limit": 101})
    assert resp.status_code == 422
    resp = await client.get(base, params={"q": "abc", "query_type": "official_search", "offset": -1})
    assert resp.status_code == 422
    # limit is capped at 100 max on success
    resp = await client.get(base, params={"q": "x", "query_type": "official_search", "limit": 100})
    assert resp.status_code == 200


# ---------------------------------------------------------------- read-only


@pytest.mark.asyncio
async def test_search_is_read_only_no_audit_no_db_change(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Search never mutates records, never adds audit, never creates tables."""
    _, task_id = await _mk_wi(client, tmp_path, "S10")
    await _mk_record(client, tmp_path, task_id, "Quy chế hoạt động hoa tiêu\n", filename="k1.txt")

    before = await _snapshot(tmp_path)

    for purpose in ("official_search", "exploratory_search", "analysis_input"):
        resp = await client.get(
            f"/api/dirap/work-items/{task_id}/knowledge-records/search",
            params={"q": "hoa tiêu", "query_type": purpose},
        )
        assert resp.status_code == 200

    after = await _snapshot(tmp_path)
    assert after["records"] == before["records"]
    assert after["audit_count"] == before["audit_count"]
    assert after["tables"] == before["tables"]
    assert not any("search" in t for t in after["tables"])


@pytest.mark.asyncio
async def test_search_result_contract_fields(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Response carries the minimal contract: id, excerpt, provenance,
    lifecycle, four dimensions, matched field, usability level, total/limit/offset."""
    _, task_id = await _mk_wi(client, tmp_path, "S11")
    await _mk_record(client, tmp_path, task_id, "Công ước quốc tế SOLAS\n", filename="l1.txt")
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/knowledge-records/search",
        params={"q": "solas", "query_type": "memory_query"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"query_type", "total", "limit", "offset", "results"}
    r = body["results"][0]
    assert set(r.keys()) == {
        "record_id",
        "content_excerpt",
        "provenance",
        "lifecycle_state",
        "source_verification_state",
        "calculation_verification_state",
        "owner_acceptance_state",
        "authority_status",
        "matched_field",
        "usability_state",
    }
    assert r["lifecycle_state"] == "active"
    assert r["usability_state"] == "usable"
    assert r["content_excerpt"]
    assert r["provenance"]
