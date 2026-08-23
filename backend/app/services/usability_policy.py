"""DIRAP v3.0 — Usability policy v1 (pure, read-only calculation).

Nguồn quyết định: ``docs/implementation/USABILITY_POLICY_DECISION.md``
(Codex chốt phương án C, 2026-08-10) và nhiệm vụ "Khả dụng chỉ đọc".

Nguyên tắc:
- ``authority_status`` là dữ kiện gốc (5 giá trị đóng); không dùng, không lưu,
  không suy diễn thêm nhãn thẩm quyền dẫn xuất ngoài tập năm giá trị đóng.
- ``overall_usability_state`` là giá trị tính lúc đọc từ bốn chiều dữ kiện gốc;
  không bao giờ được ghi vào cơ sở dữ liệu.
- Quy tắc của từng mục đích ưu tiên hơn thuật toán chung (đúng quyết định chốt).

Mô-đun này thuần túy: không phụ thuộc HTTP, FastAPI hay cơ sở dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Từ vựng đóng
# ---------------------------------------------------------------------------

# Sáu mục đích sử dụng chuẩn — duy nhất, không thêm bớt.
QUERY_TYPES: tuple[str, ...] = (
    "official_search",
    "exploratory_search",
    "analysis_input",
    "legal_review",
    "context_packaging",
    "memory_query",
)

POLICY_VERSION = "v1"

# Bộ năm giá trị tương đương "any" theo quyết định: gồm cả ``none``.
_AUTHORITY_ANY: frozenset[str] = frozenset(
    ("none", "regulatory", "organizational", "expert", "derived")
)
# official_search và legal_review v1: chỉ chấp nhận regulatory.
# derived chưa được xét cho hai mục đích này (thiếu dữ kiện nguồn gốc).
_AUTHORITY_OFFICIAL_LEGAL: frozenset[str] = frozenset(("regulatory",))
# analysis_input v1: chấp nhận bốn giá trị ngoài none.
_AUTHORITY_ANALYSIS: frozenset[str] = frozenset(
    ("regulatory", "organizational", "expert", "derived")
)

_USABLE = "usable"
_PARTIAL = "partial_usable"
_UNUSABLE = "unusable"

_DIM_LABELS = {
    "source_verification_state": "Nguồn chưa được xác minh",
    "calculation_verification_state": "Tính toán chưa được xác minh",
    "owner_acceptance_state": "Chủ sở hữu chưa xác nhận",
    "authority_status": "Thẩm quyền nguồn không thuộc tập chấp nhận cho mục đích này",
}


@dataclass(frozen=True)
class UsabilityExclusion:
    """Một điều kiện chưa đạt của chính sách."""

    dimension: str
    required_state: str
    actual_state: str
    reason: str


@dataclass(frozen=True)
class UsabilityResult:
    """Kết quả tính khả dụng cho một mục đích (chỉ đọc, không lưu)."""

    overall_usability_state: str
    exclusions: list[UsabilityExclusion] = field(default_factory=list)


def _exclusion(dimension: str, required_state: str, actual_state: str) -> UsabilityExclusion:
    return UsabilityExclusion(
        dimension=dimension,
        required_state=required_state,
        actual_state=actual_state,
        reason=_DIM_LABELS.get(dimension, f"Điều kiện chưa đạt: {dimension}"),
    )


def _missing(
    dimensions: dict[str, str],
    checks: list[tuple[str, str]],
) -> list[UsabilityExclusion]:
    """Các điều kiện chưa đạt theo danh sách (dimension, required_state)."""
    exclusions: list[UsabilityExclusion] = []
    for dimension, required in checks:
        actual = dimensions.get(dimension)
        if actual != required:
            exclusions.append(_exclusion(dimension, required, actual or "unknown"))
    return exclusions


# ---------------------------------------------------------------------------
# Đánh giá theo từng mục đích — quy tắc cụ thể ưu tiên hơn thuật toán chung
# ---------------------------------------------------------------------------


def _official_search(dim: dict[str, str]) -> UsabilityResult:
    exclusions = _missing(
        dim,
        [
            ("source_verification_state", "verified"),
            ("calculation_verification_state", "verified"),
            ("owner_acceptance_state", "accepted"),
            ("authority_status", "regulatory"),
        ],
    )
    if not exclusions:
        return UsabilityResult(_USABLE)
    # partial: nguồn + thẩm quyền đã đạt nhưng còn thiếu tính toán hoặc chủ sở hữu.
    if dim["source_verification_state"] == "verified" and dim["authority_status"] == "regulatory":
        return UsabilityResult(_PARTIAL, exclusions)
    return UsabilityResult(_UNUSABLE, exclusions)


def _exploratory_search(dim: dict[str, str]) -> UsabilityResult:
    if dim["source_verification_state"] == "verified":
        # Bản chất thăm dò: chỉ cần nguồn xác minh; không bao giờ "usable".
        return UsabilityResult(_PARTIAL)
    return UsabilityResult(
        _UNUSABLE,
        _missing(dim, [("source_verification_state", "verified")]),
    )


def _analysis_input(dim: dict[str, str]) -> UsabilityResult:
    exclusions = _missing(
        dim,
        [
            ("source_verification_state", "verified"),
            ("calculation_verification_state", "verified"),
        ],
    )
    if dim["authority_status"] not in _AUTHORITY_ANALYSIS:
        exclusions.append(
            _exclusion(
                "authority_status",
                "regulatory|organizational|expert|derived",
                dim["authority_status"],
            )
        )
    if not exclusions:
        return UsabilityResult(_USABLE)
    if dim["source_verification_state"] == "verified":
        return UsabilityResult(_PARTIAL, exclusions)
    return UsabilityResult(_UNUSABLE, exclusions)


def _legal_review(dim: dict[str, str]) -> UsabilityResult:
    exclusions = _missing(
        dim,
        [
            ("source_verification_state", "verified"),
            ("calculation_verification_state", "verified"),
            ("owner_acceptance_state", "accepted"),
            ("authority_status", "regulatory"),
        ],
    )
    if not exclusions:
        return UsabilityResult(_USABLE)
    # legal_review: không có bậc partial — mọi trường hợp còn lại là unusable.
    return UsabilityResult(_UNUSABLE, exclusions)


def _context_packaging(dim: dict[str, str]) -> UsabilityResult:
    exclusions = _missing(
        dim,
        [
            ("source_verification_state", "verified"),
            ("owner_acceptance_state", "accepted"),
        ],
    )
    if not exclusions:
        return UsabilityResult(_USABLE)
    return UsabilityResult(_UNUSABLE, exclusions)


def _memory_query(dim: dict[str, str]) -> UsabilityResult:
    exclusions = _missing(dim, [("owner_acceptance_state", "accepted")])
    if not exclusions:
        # Các chiều còn lại không phải điều kiện chặn trong v1 (kể cả au=none).
        return UsabilityResult(_USABLE)
    return UsabilityResult(_UNUSABLE, exclusions)


_EVALUATORS = {
    "official_search": _official_search,
    "exploratory_search": _exploratory_search,
    "analysis_input": _analysis_input,
    "legal_review": _legal_review,
    "context_packaging": _context_packaging,
    "memory_query": _memory_query,
}


# ---------------------------------------------------------------------------
# API thuần cho service/endpoint
# ---------------------------------------------------------------------------


def evaluate_usability(
    *,
    source_verification_state: str,
    calculation_verification_state: str,
    owner_acceptance_state: str,
    authority_status: str,
    query_type: str,
) -> UsabilityResult:
    """Tính khả dụng cho đúng một mục đích từ bốn chiều dữ kiện gốc.

    ``query_type`` không hợp lệ → ``ValueError`` (endpoint chuyển thành 422).
    """
    evaluator = _EVALUATORS.get(query_type)
    if evaluator is None:
        raise ValueError(f"Unknown query_type: {query_type!r}")
    dimensions = {
        "source_verification_state": source_verification_state,
        "calculation_verification_state": calculation_verification_state,
        "owner_acceptance_state": owner_acceptance_state,
        "authority_status": authority_status,
    }
    return evaluator(dimensions)


def usable_for_query_types(
    *,
    source_verification_state: str,
    calculation_verification_state: str,
    owner_acceptance_state: str,
    authority_status: str,
) -> list[str]:
    """Mọi mục đích trong sáu loại chuẩn đạt ``usable`` cho bản ghi này."""
    usable: list[str] = []
    for query_type in QUERY_TYPES:
        result = evaluate_usability(
            source_verification_state=source_verification_state,
            calculation_verification_state=calculation_verification_state,
            owner_acceptance_state=owner_acceptance_state,
            authority_status=authority_status,
            query_type=query_type,
        )
        if result.overall_usability_state == _USABLE:
            usable.append(query_type)
    return usable