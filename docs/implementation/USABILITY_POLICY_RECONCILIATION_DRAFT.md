# Hồ sơ thiết kế — Hòa giải chính sách khả dụng với dữ kiện thẩm quyền

> **Trạng thái:** DRAFT v0.2 — chờ Codex rà soát và chốt quyết định. **Hoàn toàn không có mã nguồn.**
> **Ngày:** 2026-08-09 · **Tác giả:** Hermes (nhiệm vụ thiết kế theo yêu cầu người dùng)
> **Phạm vi:** chỉ tạo tài liệu; không triển khai policy engine, API, migration, tìm kiếm hay agent.
> **Lịch sử:** v0.2 (2026-08-09) — theo yêu cầu người dùng: phương án B/C thu hẹp `official_search`/`legal_review` về `{regulatory}` ở phiên bản chính sách đầu; `derived` bị hoãn tới khi có dữ kiện nguồn gốc và quy tắc kiểm chứng (Q6 = quyết định tương lai).

---

## 1. Xung đột hiện hành

| | Chính sách khả dụng (nguồn chuẩn) | Hợp đồng dữ liệu hiện hành |
|---|---|---|
| Nguồn | `usability_policy_spec.md` (mục 2, 3) và `query_policy_matrix.csv` | `knowledge_lifecycle_and_verification.md` mục 3.2 (Dimension 4); schema `DirapKnowledgeAuthorityStatus` + migration 0018 (đã chấp nhận) |
| Điều kiện thẩm quyền | `authoritative` (dùng cho `official_search`, `analysis_input`, `legal_review`); `any` cho các loại còn lại | Không có nhãn `authoritative`. `authority_status` chỉ nhận đúng **5 giá trị đóng**: `none`, `regulatory`, `organizational`, `expert`, `derived` |

Kết luận: **`authoritative` là một điều kiện chính sách, không phải giá trị dữ liệu.** Nó không tồn tại trong bộ nhãn gốc của bản thân nguồn chuẩn `knowledge_lifecycle_and_verification.md`, do đó không thể lưu xuống cơ sở dữ liệu như một giá trị thứ sáu của `authority_status`. Việc "có đủ thẩm quyền" phải được **tính ra** tại thời điểm đánh giá khả dụng, từ tập nhãn gốc.

Xung đột nội bộ của nguồn (cần chốt, xem mục 8):

- `usability_policy_spec.md` mục 2 `exploratory_search`: `authority_status = any`; nhưng mục 3 (thuật toán) quy `partial_usable` khi `source_verification_state == verified AND authority_status == authoritative`. Hai quy tắc mâu thuẫn nhau về vai trò của `authoritative` trong `partial_usable`.
- Bảng `memory_query` (mục 2): dòng `overall_usability` bị treo cột (`**usable** nếu owner_acceptance | accepted`) — lỗi trình bày, cần xác nhận ý định "usable nếu `owner_acceptance_state = accepted`".

## 2. Nguyên tắc: dữ kiện gốc và kết quả đánh giá chính sách

1. **`authority_status` là dữ kiện gốc** — một trong bốn chiều xác minh độc lập, chỉ nhận 5 giá trị đóng `none | regulatory | organizational | expert | derived`, chỉ được ghi qua quy trình rà soát có kiểm soát (đã chấp nhận ở lát Knowledge Review).
2. **"Đủ thẩm quyền cho mục đích X" là kết quả đánh giá của chính sách** tại thời điểm truy vấn, không phải một thuộc tính lưu trữ.
3. **Tuyệt đối không thêm nhãn `authoritative` vào cơ sở dữ liệu**, không ghi đè `authority_status`, không thêm cột mới. `authoritative` nếu được giữ lại (xem mục 5) chỉ tồn tại trong ngôn ngữ chính sách như một **điều kiện dẫn xuất** (derived policy condition) có bảng ánh xạ rõ ràng sang tập nhãn gốc.
4. Nhất quán với nguyên tắc +1 của `knowledge_lifecycle_and_verification.md` mục 3.3: `overall_usability_state` là giá trị **tính toán**, không bao giờ được lưu làm dữ liệu nền.

## 3. Sáu mục đích sử dụng chuẩn (không thay đổi so với nguồn)

| # | Query type | Ý nghĩa (theo nguồn) | Ghi chú alias (CSV `legacy_aliases`) |
|---|---|---|---|
| 1 | `official_search` | Tìm kiếm chính thức | — |
| 2 | `exploratory_search` | Tìm kiếm thăm dò | — |
| 3 | `analysis_input` | Đầu vào phân tích | alias: `comparison_report`, `chart_generation` |
| 4 | `legal_review` | Rà soát pháp lý | alias: `audit_export` |
| 5 | `context_packaging` | Đóng gói ngữ cảnh | — |
| 6 | `memory_query` | Truy vấn ghi nhớ chủ động | — |

Các alias là tên cũ ánh xạ vào mục đích chuẩn, **không phải mục đích mới** — không thêm, không trùng, không tự tạo thêm mục đích nào khác.

### 3.1 Yêu cầu tối thiểu theo nguồn (trích chính xác `usability_policy_spec.md` mục 2 + CSV)

| Query type | source_verification_required | calculation_verification_required | owner_acceptance_required | authority_required | overall ghi trong nguồn |
|---|---|---|---|---|---|
| `official_search` | `verified` | `verified` | `accepted` | `authoritative` | usable nếu đủ 4; partial_usable nếu source_verification + authority; còn lại unusable |
| `exploratory_search` | `verified` | `any` | `any` | `any` | partial_usable nếu source verified; unusable nếu không |
| `analysis_input` | `verified` | `verified` | `any` | `authoritative` | usable nếu calculation đạt; partial_usable nếu chỉ source |
| `legal_review` | `verified` | `verified` | `accepted` | `authoritative` | usable bắt buộc đủ 4 chiều |
| `context_packaging` | `verified` | `any` | `accepted` | `any` | usable nếu source + owner; unusable nếu thiếu |
| `memory_query` | `any` | `any` | `accepted` | `any` | usable nếu owner acceptance (cột nguồn lỗi trình bày — Q5) |

Lưu ý: `any` trong nguồn hiện **không loại trừ `none`**; việc có nên loại trừ hay không là câu hỏi chính sách (Q3).

## 4. Điều kiện tối thiểu đề xuất theo từng mục đích — tập giá trị thẩm quyền cụ thể

Bảng dưới bỏ từ khóa mơ hồ, quy thẳng **từng tập giá trị `authority_status` được chấp nhận** theo từng phương án ánh xạ (chi tiết phương án tại mục 5). Các chiều còn lại giữ nguyên yêu cầu nguồn; `*` = bắt buộc khớp đúng giá trị.

| Query type | source_verification | calculation_verification | owner_acceptance | authority_status — Phương án A | authority_status — Phương án B | authority_status — Phương án C |
|---|---|---|---|---|---|---|
| `official_search` | `verified`* | `verified`* | `accepted`* | {regulatory, organizational, expert, derived} | {regulatory} | {regulatory} |
| `exploratory_search` | `verified`* | any | any | any (không loại trừ gì) | any (không loại trừ gì) | {none, regulatory, organizational, expert, derived} |
| `analysis_input` | `verified`* | `verified`* | any | {regulatory, organizational, expert, derived} | {regulatory, organizational, expert, derived} | {regulatory, organizational, expert, derived} |
| `legal_review` | `verified`* | `verified`* | `accepted`* | {regulatory, organizational, expert, derived} | {regulatory} | {regulatory} |
| `context_packaging` | `verified`* | any | `accepted`* | any | any | {none, regulatory, organizational, expert, derived} |
| `memory_query` | any | any | `accepted`* | any | any | {none, regulatory, organizational, expert, derived} |

Giải thích nhanh:

- Phương án A và B đều diễn giải `authoritative` = tập con của 5 nhãn; A lấy **mọi nhãn khác `none`**, B lấy **tập hẹp theo rủi ro mục đích** (phiên bản chính sách đầu tiên: {regulatory} cho `official_search`/`legal_review`; expert/organizational chỉ được phép cho đầu vào phân tích).
- Phương án C **bỏ hẳn từ khóa `authoritative`** khỏi ngôn ngữ chính sách: mỗi mục đích khai báo trực tiếp tập nhãn chấp nhận; `any` được viết tường minh là cả 5 giá trị (kể cả `none`) — sự lựa chọn "any có gồm none hay không" thể hiện rõ ngay trong tập.
- `derived` **không được xét** cho `official_search`/`legal_review` trong phiên bản chính sách đầu tiên, vì hệ thống chưa lưu và kiểm chứng chuỗi nguồn gốc của giá trị derived. Chỉ sau khi có dữ kiện nguồn gốc, bằng chứng kế thừa và quy tắc kiểm chứng riêng mới mở lại (Q6 — quyết định tương lai).

## 5. Ba phương án ánh xạ thẩm quyền — ưu/nhược/rủi ro/khuyến nghị

### Phương án A — "Mọi nhãn khác `none` đều đủ thẩm quyền"

`authoritative` ≙ `authority_status ≠ none` (tức {regulatory, organizational, expert, derived}).

- Ưu: đơn giản nhất; không cần bảng ánh xạ; dễ giải thích.
- Nhược: gom `organizational` (chuẩn nội bộ cơ quan) ngang hàng `regulatory` (quy phạm pháp luật) cho các mục đích chính thức/pháp lý.
- Rủi ro: **cao về mặt pháp lý** — nguồn nội bộ xuất hiện trong `official_search`/`legal_review` dưới dán nhãn "đủ thẩm quyền", sai tinh thần của `legal_review` ("yêu cầu cao nhất" — CSV dòng 5).
- Khuyến nghị: chỉ cân nhắc khi người dùng chấp nhận rủi ro trên; xác suất được Codex chấp nhận thấp.

### Phương án B — "Tập con theo rủi ro mục đích" (giữ từ khóa `authoritative` như điều kiện dẫn xuất)

Định nghĩa `authoritative` = tập được khai báo theo từng mục đích trong bảng policy version (phiên bản chính sách đầu tiên: `official_search`/`legal_review` = {regulatory}; `analysis_input` = {regulatory, organizational, expert, derived}; `derived` chưa được xét cho các mục đích rủi ro cao vì thiếu dữ kiện nguồn gốc).

- Ưu: giữ nguyên văn chính sách nguồn (`authoritative` vẫn là thuật ngữ), nhưng ý nghĩa được buộc vào bảng ánh xạ cụ thể — hết mơ hồ; kiểm soát được rủi ro theo mục đích.
- Nhược: cần một cấu trúc "bảng ánh xạ authoritative → tập nhãn" kèm theo `policy_version`; thêm một lớp cấu hình phải kiểm soát qua ADR (đúng tinh thần `usability_policy_spec.md` mục 4).
- Rủi ro: hai nơi phải đồng bộ (bảng policy + bảng ánh xạ); nếu lệch version sẽ tính sai khả dụng.
- Khuyến nghị: **phương án bám sát nguồn nhất**; phù hợp nếu muốn giữ tính tương thích với văn bản chính sách đã duyệt.

### Phương án C — "Khai báo trực tiếp, không có từ khóa trung gian"

Bỏ hẳn `authoritative` khỏi ngôn ngữ chính sách; mỗi query type liệt kê thẳng tập nhãn chấp nhận (như bảng mục 4, cột C).

- Ưu: triệt để hết mơ hồ; chính sách và dữ liệu dùng **một bộ từ vựng**; không cần lớp ánh xạ trung gian; đúng tinh thần tối giản của yêu cầu thiết kế.
- Nhược: phải sửa văn bản `usability_policy_spec.md` và CSV (bỏ/đổi cột `authority_required = authoritative`), cần quyết định và ADR; lệch một chút so với "nguồn chuẩn duy nhất" hiện có.
- Rủi ro: nếu không cập nhật đồng bộ cả ba tài liệu nguồn, sẽ tái xuất hiện từ khóa cũ trong tham chiếu.
- Khuyến nghị: **phương án tối giản và bền vững nhất về lâu dài**; được ưu tiên nếu sắp tới mở tìm kiếm/agent và muốn chính sách tự mô tả đầy đủ.

> **Không tự chọn, không tự phê duyệt.** Người soạn trình cả ba phương án để Codex/người dùng chốt tại mục 8 (Q1). Nếu giữ `authoritative` (A hoặc B), bắt buộc kèm bảng ánh xạ sát mục 4 khi triển khai.

## 6. Hợp đồng đầu ra tương lai (chỉ đọc) — khẳng định không API ghi

Khi chính sách được triển khai (ngoài phạm vi nhiệm vụ này), hợp đồng đề xuất bám nguyên dạng `GET /api/v1/knowledge-records/{id}/usability` tại `usability_policy_spec.md` mục 1:

```json
{
  "record_id": "uuid",
  "source_verification_state": "verified",
  "calculation_verification_state": "verified",
  "owner_acceptance_state": "accepted",
  "authority_status": "regulatory",
  "overall_usability_state": "usable",
  "policy_version": "policy-v1",
  "exclusions": [
    {
      "dimension": "calculation_verification_state",
      "reason": "…",
      "required_state": "verified",
      "actual_state": "unverified"
    }
  ],
  "usable_for_query_types": ["official_search", "context_packaging"]
}
```

Khẳng định:

- **Chỉ đọc:** không có API ghi `overall_usability_state`, `policy_version`, `exclusions`, `usable_for_query_types`. Các giá trị này là kết quả tính toán tại thời điểm truy vấn.
- Giá trị luôn được tính lại từ 4 chiều gốc hiện tại theo `policy_version` được chọn (tương thích phiên bản cũ theo `usability_policy_spec.md` mục 4).
- `overall_usability_state` **không bao giờ được persist** làm dữ liệu nền (nhất quán `knowledge_lifecycle_and_verification.md` mục 3.3 và 3.4).
- Bốn chiều gốc vẫn là những trường duy nhất được ghi, qua quy trình rà soát đã chấp nhận.

## 7. Phạm vi không được triển khai (trong nhiệm vụ này và tới khi có quyết định)

- **Policy engine** tính `overall_usability_state` — chưa viết mã, chưa thêm endpoint.
- **Tìm kiếm** (chính thức, thăm dò, ngữ nghĩa) — chưa mở.
- **Agent sử dụng tri thức / query planning** — chưa mở.
- **Tự động đưa dữ kiện vào memory** (`memory_query` chỉ là mục đích chính sách, không phải hành vi tự động hiện hành).
- **AI** hỗ trợ đánh giá; **triển khai / vận hành sản xuất**.
- Mọi thay đổi mã nguồn, migration, kiểm thử, cấu hình, dữ liệu, `AI_STATE.json` và các tài liệu nguồn đã khóa.

## 8. Quyết định cần Codex/người dùng chốt

1. **(Q1) Chọn phương án ánh xạ**: A, B hay C (mục 5)? Kèm xác nhận tập giá trị `authority_status` cho từng mục đích đúng như cột tương ứng ở mục 4.
2. **(Q2) Số phận từ khóa `authoritative`**: giữ làm điều kiện dẫn xuất (A/B) hay bỏ hẳn khỏi ngôn ngữ chính sách (C)? Nếu bỏ/sửa `usability_policy_spec.md` + CSV, cần ADR do đây là "nguồn chuẩn duy nhất".
3. **(Q3) Ý nghĩa của `any`**: `exploratory_search`, `context_packaging`, `memory_query` có loại trừ `none` không? (nguồn hiện không loại trừ).
4. **(Q4) Mâu thuẫn nội bộ nguồn — quy tắc `partial_usable`**: theo thuật toán (spec mục 3) hay theo bảng `exploratory_search` (spec mục 2)? Cụ thể: `partial_usable` có bắt buộc `authority_status` ở mức "đủ thẩm quyền" hay chỉ cần `source_verification_state = verified`?
5. **(Q5) Xác nhận ý định `memory_query`**: usable khi `owner_acceptance_state = accepted` (bảng nguồn lỗi trình bày — cần xác nhận, không tự sửa nguồn).
6. **(Q6) `derived` — quyết định tương lai, không phải ngoại lệ cho chính sách hiện tại**: phiên bản chính sách đầu tiên **không** xếp `derived` cho `official_search`/`legal_review` (chỉ chấp nhận `{regulatory}`), vì hệ thống chưa lưu/kiểm chứng chuỗi nguồn gốc. Chỉ sau khi hệ thống có dữ kiện nguồn gốc, bằng chứng kế thừa và chính sách kiểm chứng riêng, mới mở lại câu hỏi: `derived` được chấp nhận với điều kiện gì (vd. derived ← regulatory, kèm chuỗi dẫn xuất đã kiểm chứng)? Q6 **không được dùng** để nới điều kiện hiện tại.
7. **(Q7) `organizational` trong bối cảnh pháp lý**: có được chấp nhận trong `official_search`/`legal_review` không (đề xuất mặc định của các phương án B/C: **không**)?
8. **(Q8) Quản trị `policy_version`**: ai ấn định phiên bản mặc định, cơ chế migration chính sách và kiểm soát ADR như thế nào khi chính sách đổi (spec mục 4 mới chỉ nêu nguyên tắc)?
9. **(Q9) Hiển thị `partial_usable`/`exclusions`**: khi mở tìm kiếm, kết quả bị loại trừ một phần hiển thị và giải thích ra sao (liên quan chức năng tìm kiếm tương lai)?
10. **(Q10) Alias cũ**: giữ `comparison_report`, `chart_generation`, `audit_export` làm alias ánh xạ, hay loại bỏ hẳn khi chính thức hóa (không tạo query type mới)?

---

## Phụ lục A — Đối chiếu thuật ngữ với ba nguồn (QA nội bộ)

| Thuật ngữ dùng trong hồ sơ | Nguồn xác nhận |
|---|---|
| 6 query type: `official_search`, `exploratory_search`, `analysis_input`, `legal_review`, `context_packaging`, `memory_query` | `usability_policy_spec.md` mục 2; `query_policy_matrix.csv` các dòng 2–7 |
| `authority_status` 5 giá trị `none/regulatory/organizational/expert/derived` | `knowledge_lifecycle_and_verification.md` mục 3.2 Dimension 4; hợp đồng dữ liệu đã chấp nhận (migration 0018) |
| `overall_usability_state`, `policy_version`, `exclusions`, `usable_for_query_types` | `usability_policy_spec.md` mục 1 (API) |
| 4 chiều gốc + chiều +1 dẫn xuất | `knowledge_lifecycle_and_verification.md` mục 3.1–3.3 |
| `partial_usable` có `exclusions` | `usability_policy_spec.md` mục 3 (thuật toán) |
| Alias `comparison_report`, `chart_generation` → `analysis_input`; `audit_export` → `legal_review` | `query_policy_matrix.csv` cột `legacy_aliases` |

**QA đã thực hiện (hồ sơ này):**

- [x] Mọi thuật ngữ đối chiếu đúng ba nguồn bắt buộc (bảng trên).
- [x] Đúng 6 mục đích sử dụng, không thiếu, không trùng, không tự tạo mục đích mới (alias tách riêng).
- [x] Không đề xuất thêm `authoritative` vào dữ liệu gốc — chỉ là biểu diễn chính sách (mục 2, 5).
- [x] Không đề xuất ghi `overall_usability_state` vào cơ sở dữ liệu (mục 6) — chỉ đọc, tính lại mỗi truy vấn.
- [x] Không đề xuất API write cho bất kỳ giá trị chính sách nào.
- [x] Các xung đột chưa thể tự quyết đều được đưa hết vào mục 8, không âm thầm chọn phương án.
- [x] v0.2: trong phương án B/C, `official_search` và `legal_review` chỉ chấp nhận `{regulatory}`; `derived` không bị coi là tương đương `regulatory` và không được xét cho hai mục đích rủi ro cao ở phiên bản đầu; Q6 được ghi là quyết định tương lai.
