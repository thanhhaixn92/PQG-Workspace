"""DIRAP v3.0 — Controlled knowledge search (pure, deterministic).

Nguồn quyết định: ``docs/implementation/CONTROLLED_KNOWLEDGE_SEARCH_DECISION.md``
(Codex, 2026-08-10).

Nguyên tắc:
- Chỉ tìm trong ``content`` và ``provenance`` của bản ghi thuộc đúng nhiệm vụ
  (việc lọc theo ``task_id`` thuộc về tầng SQL/endpoint).
- Chuẩn hóa khoảng trắng + so khớp cụm từ không phân biệt hoa/thường bằng
  ``casefold()``; không dùng SQL ``LIKE`` làm logic chính ở đây.
- Không AI, vector, FTS, tìm kiếm ngữ nghĩa, chỉ mục hay kho dữ liệu song song.
- Lọc chính sách qua ``evaluate_usability`` (policy v1) **trước** khi phân trang.
- Chỉ đọc: không ghi, không audit, không đổi dữ liệu.

Mô-đun thuần túy: không phụ thuộc HTTP, FastAPI hay cơ sở dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.usability_policy import evaluate_usability

_ACC_PARTIAL = "partial_usable"
_ACC_USABLE = "usable"

# Những mục đích chỉ trả bản ghi ``usable`` (không bao giờ ``partial_usable``).
_STRICT_ONLY_USABLE = frozenset(
    (
        "official_search",
        "analysis_input",
        "legal_review",
        "context_packaging",
        "memory_query",
    )
)
# exploratory_search trả ``usable`` hoặc ``partial_usable`` (luôn kèm mức khả dụng).
_EXPLORATORY = "exploratory_search"


def normalize_search_text(text: str) -> str:
    """Chuẩn hóa văn bản tìm kiếm: casefold + gộp khoảng trắng.

    Dùng cho cả truy vấn và nội dung so khớp để hai bên so sánh cùng một dạng.
    """
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class SearchMatch:
    """Kết quả đối sánh cụm từ với một bản ghi."""

    matched: bool
    matched_field: str  # "content" | "provenance" | "both" | ""


def find_match(content: str, provenance: str | None, query_normalized: str) -> SearchMatch:
    """So khớp cụm từ đã chuẩn hóa trong content và/hoặc provenance.

    Không phân biệt hoa/thường và không phụ thuộc số khoảng trắng
    (cả hai bên đã qua ``normalize_search_text``).
    """
    content_norm = normalize_search_text(content)
    in_content = query_normalized in content_norm
    provenance_norm = normalize_search_text(provenance or "")
    in_provenance = query_normalized in provenance_norm
    if in_content and in_provenance:
        return SearchMatch(True, "both")
    if in_content:
        return SearchMatch(True, "content")
    if in_provenance:
        return SearchMatch(True, "provenance")
    return SearchMatch(False, "")


def content_excerpt(content: str, max_chars: int = 200) -> str:
    """Rút gọn nội dung để hiển thị trong kết quả tìm kiếm."""
    stripped = " ".join(content.split())
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max_chars - 1].rstrip() + "…"


def _policy_allows(query_type: str, usability_state: str) -> bool:
    """Lọc chính sách v1: exploratory chấp nhận usable/partial, còn lại chỉ usable."""
    if usability_state == _ACC_USABLE:
        return True
    if query_type == _EXPLORATORY and usability_state == _ACC_PARTIAL:
        return True
    return False


@dataclass(frozen=True)
class SearchRecord:
    """Một bản ghi tri thức ứng viên (bốn chiều + nội dung để đối sánh)."""

    record_id: str
    content: str
    provenance: str | None
    lifecycle_state: str
    source_verification_state: str
    calculation_verification_state: str
    owner_acceptance_state: str
    authority_status: str


@dataclass(frozen=True)
class SearchResultItem:
    """Một kết quả được phép trả về sau lọc chính sách."""

    record_id: str
    content_excerpt: str
    provenance: str | None
    lifecycle_state: str
    source_verification_state: str
    calculation_verification_state: str
    owner_acceptance_state: str
    authority_status: str
    matched_field: str
    usability_state: str


@dataclass(frozen=True)
class SearchOutcome:
    """Kết quả đã lọc + phân trang (total = tổng sau lọc, trước slice)."""

    items: list[SearchResultItem]
    total: int


def search_records(
    records: list[SearchRecord],
    *,
    query: str,
    query_type: str,
    limit: int,
    offset: int,
) -> SearchOutcome:
    """Tìm → lọc chính sách → phân trang.

    - ``query`` đã là cụm từ (có thể chưa chuẩn hóa; hàm tự chuẩn hóa).
    - Không bao giờ trả nội dung của bản ghi ``unusable``.
    - Phân trang áp dụng sau khi đã so khớp và lọc chính sách.
    """
    query_norm = normalize_search_text(query)
    allowed: list[SearchResultItem] = []
    for record in records:
        if record.lifecycle_state != "active":
            continue
        match = find_match(record.content, record.provenance, query_norm)
        if not match.matched:
            continue
        result = evaluate_usability(
            source_verification_state=record.source_verification_state,
            calculation_verification_state=record.calculation_verification_state,
            owner_acceptance_state=record.owner_acceptance_state,
            authority_status=record.authority_status,
            query_type=query_type,
        )
        if not _policy_allows(query_type, result.overall_usability_state):
            continue
        allowed.append(
            SearchResultItem(
                record_id=record.record_id,
                content_excerpt=content_excerpt(record.content),
                provenance=record.provenance,
                lifecycle_state=record.lifecycle_state,
                source_verification_state=record.source_verification_state,
                calculation_verification_state=record.calculation_verification_state,
                owner_acceptance_state=record.owner_acceptance_state,
                authority_status=record.authority_status,
                matched_field=match.matched_field,
                usability_state=result.overall_usability_state,
            )
        )
    total = len(allowed)
    page = allowed[offset : offset + limit]
    return SearchOutcome(items=page, total=total)
