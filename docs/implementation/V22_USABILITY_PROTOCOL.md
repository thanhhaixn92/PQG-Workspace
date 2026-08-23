# V2.2 Five-Person Usability Protocol

Gate status: `DEFERRED POST-V2.2` (user decision, 2026-08-15). This protocol remains required for a future human-usability validation, but does not block internal local use or the remaining technical v2.2 gates. An agent or mock session cannot count as a participant.

## Setup

- Use a temporary SQLite database and managed workspace with `uat-codex-` data only.
- Start each participant from the same clean seed and the local webapp home screen. Run `scripts/start-v22-usability.ps1 -Participant P1` through `P5`; it creates a fresh SQLite database and managed workspace per participant, records only process IDs/paths in temporary metadata, and never reuses a prior participant's data.
- Facilitator may say only: “Hãy hoàn thành công việc mẫu bằng ứng dụng.” Do not name tabs, buttons or concepts.
- Record screen/time with consent; do not record credentials or sensitive content.

## Unassisted journey

Each participant must: create a Work; create/edit a plan; open two conversations; send Hermes a prompt and identify its sources; explain that a proposal is not yet a mutation; create and approve an Action Package; locate the report/artifact and storage boundary; archive or restore correctly.

## Seven comprehension questions

Ask at the end and allow at most 30 seconds total:

1. Bạn đang ở Work nào?
2. Bước tiếp theo là gì?
3. Có gì đang chờ bạn duyệt?
4. Hermes đã dùng và loại nguồn nào, vì sao?
5. Đề xuất đã được thực thi hay mới chỉ được chuẩn bị?
6. Đầu ra được lưu ở đâu?
7. Khi Hermes lỗi hoặc trả lời sai, bạn hủy/thử lại ở đâu?

## Participant record

| Participant | Work | Plan | 2 conversations | Source | Proposal understood | Package approved | Artifact found | Archive/restore | Journey time | 7/7 within 30s | Errors/notes | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | — | NOT RUN | — | NOT RUN |
| P2 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | — | NOT RUN | — | NOT RUN |
| P3 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | — | NOT RUN | — | NOT RUN |
| P4 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | — | NOT RUN | — | NOT RUN |
| P5 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | — | NOT RUN | — | NOT RUN |

Participant passes only when the full journey is completed without guidance and all seven answers are correct within 30 seconds. Product gate passes at 4/5 or better. Any P0/P1 found during the study blocks promotion even if 4/5 pass.

Launcher smoke (2026-08-15): `P1` started with an isolated temporary DB/workspace, returned health `ok` (`2.2.0`), and was stopped after verification. This is setup evidence only, not a participant result.
