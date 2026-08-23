"""Tests for DIRAP v3.0 Knowledge Review slice.

Covers the controlled lifecycle draft -> review_pending -> active|rejected:
- Allowed/forbidden transitions (409 for anything else)
- Approve: required evidence references, the four verification dimensions,
  calculation dimension only verified with a calculation-evidence reference
- Reject: required reviewer + reason, owner acceptance rejected, history kept
- Evidence records + audit events per transition (payload stored in payload_json)
- Work-item scoping and idempotency
- Regression: drafts keep unverified/unverified/pending/none defaults
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
import pytest
from httpx import AsyncClient


async def _mk_draft(client: AsyncClient, tmp_path: Path, content: str = "fact\n") -> tuple[str, str, str]:
    """Create session + work item + source file + extract + draft; return (task_id, source_file_id, kr_id)."""
    resp = await client.post("/api/sessions", json={"title": "RV", "workspace_path": str(tmp_path)})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "RV WI"})
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
    return task_id, source_file_id, resp.json()["id"]


async def _audit_rows(tmp_path: Path, record_id: str, action: str) -> list[dict]:
    """Query audit_events by action + target; payload parsed from payload_json."""
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT session_id, target, payload_json FROM audit_events "
            "WHERE action = ? AND target = ?",
            (action, record_id),
        ) as cur:
            rows = await cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        raw = d.pop("payload_json", None)
        d["payload"] = json.loads(raw) if raw else None
        out.append(d)
    return out


async def _evidence_rows(tmp_path: Path, record_id: str) -> list[dict]:
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, evidence_type, reference, note FROM dirap_knowledge_evidence "
            "WHERE knowledge_record_id = ? ORDER BY created_at, id",
            (record_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# -----------------------------------------------------------------------------
# Lifecycle happy path + four dimensions
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lifecycle_draft_submit_approve(client: AsyncClient, tmp_path: Path) -> None:
    """draft → review_pending → active with the four dimensions set correctly."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)

    # Draft defaults: 4 dimensions + empty evidence
    detail = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}")
    assert detail.status_code == 200
    d0 = detail.json()
    assert d0["status"] == "draft"
    assert d0["source_verification_state"] == "unverified"
    assert d0["calculation_verification_state"] == "unverified"
    assert d0["owner_acceptance_state"] == "pending"
    assert d0["authority_status"] == "none"
    assert d0["evidence"] == []

    # Submit: draft -> review_pending
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit",
        json={"note": "cần kiểm tra"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "review_pending"
    # Dimensions untouched by submit
    assert resp.json()["source_verification_state"] == "unverified"
    assert resp.json()["authority_status"] == "none"

    # Approve without calculation evidence
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={
            "reviewer": "rv-An",
            "source_evidence_reference": "doc.txt line 1",
            "authority_status": "regulatory",
            "authority_reference": "Ket luan 04/2026 muc 2.1",
            "note": "đủ nguồn",
        },
    )
    assert resp.status_code == 200
    kr = resp.json()
    assert kr["status"] == "active"
    assert kr["source_verification_state"] == "verified"
    assert kr["calculation_verification_state"] == "unverified"  # no calc reference
    assert kr["owner_acceptance_state"] == "accepted"
    assert kr["authority_status"] == "regulatory"

    # Evidence rows: reviewer + source_evidence + authority_evidence
    evidence = await _evidence_rows(tmp_path, kr_id)
    types = sorted(e["evidence_type"] for e in evidence)
    assert types == ["authority_evidence", "reviewer", "source_evidence"]
    src = next(e for e in evidence if e["evidence_type"] == "source_evidence")
    assert src["reference"] == "doc.txt line 1"
    auth = next(e for e in evidence if e["evidence_type"] == "authority_evidence")
    assert auth["reference"] == "Ket luan 04/2026 muc 2.1"

    # Audit trail: one submitted + one approved
    assert len(await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.submitted")) == 1
    approved = await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.accepted")
    assert len(approved) == 1
    assert approved[0]["payload"]["from"] == "review_pending"
    assert approved[0]["payload"]["to"] == "active"
    assert approved[0]["payload"]["authority_status"] == "regulatory"
    assert approved[0]["payload"]["calculation_verification_state"] == "unverified"
    assert approved[0]["payload"]["owner_acceptance_state"] == "accepted"


@pytest.mark.asyncio
async def test_approve_with_calculation_reference_sets_verified(
    client: AsyncClient, tmp_path: Path
) -> None:
    """calculation becomes verified only when a calculation reference is supplied."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={}
    )
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={
            "reviewer": "reviewer-1",
            "source_evidence_reference": "doc.txt line 1",
            "calculation_evidence_reference": "calc-report.xlsx sheet2",
            "authority_status": "expert",
            "authority_reference": "policy/2026/1",
        },
    )
    assert resp.status_code == 200
    kr = resp.json()
    assert kr["status"] == "active"
    assert kr["calculation_verification_state"] == "verified"

    evidence = await _evidence_rows(tmp_path, kr_id)
    calc = [e for e in evidence if e["evidence_type"] == "calculation_evidence"]
    assert len(calc) == 1
    assert calc[0]["reference"] == "calc-report.xlsx sheet2"


@pytest.mark.asyncio
async def test_approve_without_calculation_reference_keeps_unverified(
    client: AsyncClient, tmp_path: Path
) -> None:
    """No calculation reference => calculation dimension stays unverified."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={}
    )
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={
            "reviewer": "reviewer-1",
            "source_evidence_reference": "doc.txt line 1",
            "authority_status": "organizational",
            "authority_reference": "dec/2026/1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["calculation_verification_state"] == "unverified"
    evidence = await _evidence_rows(tmp_path, kr_id)
    assert all(e["evidence_type"] != "calculation_evidence" for e in evidence)


# -----------------------------------------------------------------------------
# Rejection paths: missing evidence / wrong lifecycle / scoping
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_missing_required_fields_rejected(client: AsyncClient, tmp_path: Path) -> None:
    """Approve without reviewer / source evidence / authority reference => 422/400."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})

    # Missing reviewer
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={"source_evidence_reference": "x", "authority_status": "derived", "authority_reference": "b"},
    )
    assert resp.status_code == 422

    # Missing source-evidence reference
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={"reviewer": "r", "authority_status": "derived", "authority_reference": "b"},
    )
    assert resp.status_code == 422

    # authority_status == 'none' is explicitly forbidden (400)
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={
            "reviewer": "r",
            "source_evidence_reference": "x",
            "authority_status": "none",
            "authority_reference": "b",
        },
    )
    assert resp.status_code == 400
    assert "authority" in resp.json()["detail"].lower()

    # Record unchanged after all failed attempts: no transition, no evidence
    detail = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}")
    assert detail.json()["status"] == "review_pending"
    assert await _evidence_rows(tmp_path, kr_id) == []


@pytest.mark.asyncio
async def test_reject_requires_reviewer_and_reason(client: AsyncClient, tmp_path: Path) -> None:
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json={"reviewer": "r"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json={"reason": "sai nguồn"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_transitions_all_rejected(client: AsyncClient, tmp_path: Path) -> None:
    """Only draft→review_pending, review_pending→active|rejected are allowed."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)

    approve_body = {
        "reviewer": "r",
        "source_evidence_reference": "x",
        "authority_status": "derived",
        "authority_reference": "b",
    }

    # approve/reject directly on a draft
    r = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve", json=approve_body
    )
    assert r.status_code == 409
    r = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json={"reviewer": "r", "reason": "no"},
    )
    assert r.status_code == 409

    # submit -> review_pending; second submit rejected
    r = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={}
    )
    assert r.status_code == 200
    r = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={}
    )
    assert r.status_code == 409

    # active is terminal: nothing else allowed afterwards
    r = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve", json=approve_body
    )
    assert r.status_code == 200
    for path, body in (
        ("/submit", {}),
        ("/review/approve", approve_body),
        ("/review/reject", {"reviewer": "r", "reason": "no"}),
    ):
        r = await client.post(
            f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}{path}", json=body
        )
        assert r.status_code == 409, path


@pytest.mark.asyncio
async def test_review_scoped_to_work_item(client: AsyncClient, tmp_path: Path) -> None:
    """submit/approve/reject on another work item's record => 404."""
    task_a, _, kr_id = await _mk_draft(client, tmp_path)

    resp = await client.post(
        "/api/sessions", json={"title": "RV2", "workspace_path": str(tmp_path)}
    )
    session_b = resp.json()["id"]
    resp = await client.post(
        "/api/dirap/work-items", json={"session_id": session_b, "title": "WI B"}
    )
    task_b = resp.json()["task_id"]

    for path, body in (
        ("/submit", {}),
        ("/review/approve", {"reviewer": "r", "source_evidence_reference": "x", "authority_status": "derived", "authority_reference": "b"}),
        ("/review/reject", {"reviewer": "r", "reason": "no"}),
    ):
        r = await client.post(
            f"/api/dirap/work-items/{task_b}/knowledge-records/{kr_id}{path}", json=body
        )
        assert r.status_code == 404

    # Unknown record under the owning work item
    r = await client.post(
        f"/api/dirap/work-items/{task_a}/knowledge-records/dkr-nope/submit", json={}
    )
    assert r.status_code == 404


# -----------------------------------------------------------------------------
# Reject keeps history
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_sets_owner_rejected_keeps_history(client: AsyncClient, tmp_path: Path) -> None:
    task_id, source_file_id, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json={"reviewer": "reviewer-2", "reason": "không khớp nguồn gốc dữ liệu"},
    )
    assert resp.status_code == 200
    kr = resp.json()
    assert kr["status"] == "rejected"
    assert kr["owner_acceptance_state"] == "rejected"
    # Source linkage and extraction provenance remain intact
    assert kr["source_file_id"] == source_file_id
    assert kr["source_sha256"]
    assert kr["extractor_version"]
    # Verification dimensions stay at defaults (rejection is not verification)
    assert kr["source_verification_state"] == "unverified"
    assert kr["calculation_verification_state"] == "unverified"
    assert kr["authority_status"] == "none"

    # Evidence: reviewer + decision_reason
    evidence = await _evidence_rows(tmp_path, kr_id)
    types = sorted(e["evidence_type"] for e in evidence)
    assert types == ["decision_reason", "reviewer"]
    reason = next(e for e in evidence if e["evidence_type"] == "decision_reason")
    assert reason["reference"] == "không khớp nguồn gốc dữ liệu"

    # Audit: submitted + rejected preserved
    assert len(await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.submitted")) == 1
    rejected = await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.rejected")
    assert len(rejected) == 1
    assert rejected[0]["payload"]["reason"] == "không khớp nguồn gốc dữ liệu"

    # Record still listed
    listing = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records")
    listed = [x for x in listing.json() if x["id"] == kr_id]
    assert len(listed) == 1
    assert listed[0]["status"] == "rejected"


# -----------------------------------------------------------------------------
# Idempotency
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_approve_and_reject_have_exactly_one_winner(
    client: AsyncClient, tmp_path: Path
) -> None:
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    base = f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}"
    assert (await client.post(f"{base}/submit", json={})).status_code == 200

    approve, reject = await asyncio.gather(
        client.post(
            f"{base}/review/approve",
            json={
                "reviewer": "concurrent-reviewer",
                "source_evidence_reference": "doc.txt line 1",
                "authority_status": "expert",
                "authority_reference": "expert-record-1",
            },
            headers={"Idempotency-Key": "concurrent-approve"},
        ),
        client.post(
            f"{base}/review/reject",
            json={"reviewer": "concurrent-reviewer", "reason": "conflicting decision"},
            headers={"Idempotency-Key": "concurrent-reject"},
        ),
    )
    assert sorted([approve.status_code, reject.status_code]) == [200, 409]

    detail = (await client.get(base)).json()
    assert detail["status"] in {"active", "rejected"}
    accepted_audits = await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.accepted")
    rejected_audits = await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.rejected")
    assert len(accepted_audits) + len(rejected_audits) == 1
    evidence = await _evidence_rows(tmp_path, kr_id)
    assert len(evidence) == (3 if detail["status"] == "active" else 2)


@pytest.mark.asyncio
async def test_submit_and_approve_idempotent(client: AsyncClient, tmp_path: Path) -> None:
    """Same Idempotency-Key + same payload replays without extra rows/audits."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    headers = {"Idempotency-Key": "rv-key-1"}

    r1 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit",
        json={"note": "n1"},
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit",
        json={"note": "n1"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == kr_id
    assert len(await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.submitted")) == 1

    # Same key + different payload → 409 conflict
    r3 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit",
        json={"note": "different"},
        headers=headers,
    )
    assert r3.status_code == 409

    # Approve idempotent
    aheaders = {"Idempotency-Key": "rv-approve-1"}
    abody = {
        "reviewer": "reviewer-x",
        "source_evidence_reference": "doc.txt line 1",
        "authority_status": "regulatory",
        "authority_reference": "policy/z/1",
    }
    a1 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json=abody,
        headers=aheaders,
    )
    assert a1.status_code == 200
    a2 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json=abody,
        headers=aheaders,
    )
    assert a2.status_code == 200
    assert a2.json()["status"] == "active"
    # Exactly one approved audit and one evidence set (3 rows, no calculation)
    assert len(await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.accepted")) == 1
    evidence = await _evidence_rows(tmp_path, kr_id)
    assert len(evidence) == 3
# -----------------------------------------------------------------------------
# Contract vocabulary (Codex re-review): authority_status closed set
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_accepts_all_valid_authority_statuses(client: AsyncClient, tmp_path: Path) -> None:
    """Every member of the closed authority vocabulary works on approve."""
    for value in ("regulatory", "organizational", "expert", "derived"):
        task_id, _, kr_id = await _mk_draft(client, tmp_path)
        await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
            json={
                "reviewer": "rv-x",
                "source_evidence_reference": "doc.txt line 1",
                "authority_status": value,
                "authority_reference": f"auth-ref/{value}",
            },
        )
        assert resp.status_code == 200, value
        kr = resp.json()
        assert kr["status"] == "active", value
        assert kr["owner_acceptance_state"] == "accepted", value
        assert kr["authority_status"] == value, value
        # audit payload carries the vocabulary value
        audits = await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.accepted")
        assert len(audits) == 1 and audits[0]["payload"]["owner_acceptance_state"] == "accepted", value
        assert audits[0]["payload"]["authority_status"] == value, value


@pytest.mark.asyncio
async def test_approve_rejects_unknown_authority_statuses(client: AsyncClient, tmp_path: Path) -> None:
    """Any authority_status outside the closed vocabulary is rejected with 422; no side effects."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})
    for bad in ("policy-OIC-ket-luan-04", "banana", "  regulatory  ", "AUTHORITATIVE"):
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
            json={
                "reviewer": "r",
                "source_evidence_reference": "x",
                "authority_status": bad,
                "authority_reference": "b",
            },
        )
        assert resp.status_code == 422, bad
    # record untouched: still review_pending, authority none, no evidence
    detail = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}")
    assert detail.json()["status"] == "review_pending"
    assert detail.json()["authority_status"] == "none"
    assert await _evidence_rows(tmp_path, kr_id) == []


# -----------------------------------------------------------------------------
# Migration contract fix: legacy 'approved' rows -> 'accepted'
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_0019_normalizes_stale_approved_rows(client: AsyncClient, tmp_path: Path) -> None:
    """Legacy owner_acceptance_state='approved' rows are normalized to 'accepted' by 0019."""
    from app.db.migrations import MIGRATIONS

    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/approve",
        json={
            "reviewer": "rv-x",
            "source_evidence_reference": "doc.txt line 1",
            "authority_status": "regulatory",
            "authority_reference": "Kết luận 04/2026",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["owner_acceptance_state"] == "accepted"

    # Simulate legacy rows written before the vocabulary fix
    db_path = str(tmp_path / "test_app.db")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE dirap_knowledge_records SET owner_acceptance_state = 'approved' WHERE id = ?",
            (kr_id,),
        )
        await db.commit()
        async with db.execute(
            "SELECT owner_acceptance_state FROM dirap_knowledge_records WHERE id = ?", (kr_id,)
        ) as cur:
            row = await cur.fetchone()
        assert row["owner_acceptance_state"] == "approved"

    # Apply 0019 exactly as the startup runner would
    sql = next(m[1] for m in MIGRATIONS if m[0] == "0019_dirap_knowledge_review_contract_fix")
    assert isinstance(sql, str) and "approved" in sql and "accepted" in sql
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(sql)
        await db.commit()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT owner_acceptance_state FROM dirap_knowledge_records WHERE id = ?", (kr_id,)
        ) as cur:
            row = await cur.fetchone()
    assert row["owner_acceptance_state"] == "accepted"


# -----------------------------------------------------------------------------
# Reject idempotency
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_idempotent_no_duplicate_rows(client: AsyncClient, tmp_path: Path) -> None:
    """Same Idempotency-Key + same payload replays; different payload conflicts; no extra rows."""
    task_id, _, kr_id = await _mk_draft(client, tmp_path)
    await client.post(f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/submit", json={})

    headers = {"Idempotency-Key": "rv-reject-1"}
    body = {"reviewer": "reviewer-x", "reason": "không khớp nguồn"}
    r1 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json=body,
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json=body,
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"

    # One rejected audit, one evidence set (reviewer + decision_reason), no dupes
    assert len(await _audit_rows(tmp_path, kr_id, "dirap.knowledge_record.rejected")) == 1
    evidence = await _evidence_rows(tmp_path, kr_id)
    assert len(evidence) == 2
    assert sorted(e["evidence_type"] for e in evidence) == ["decision_reason", "reviewer"]

    # Same key + different payload (valid request, same key) → 409 conflict
    r3 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records/{kr_id}/review/reject",
        json={"reviewer": "reviewer-x", "reason": "lý do khác"},
        headers=headers,
    )
    assert r3.status_code == 409
