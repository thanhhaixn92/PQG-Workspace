#!/usr/bin/env python3
"""Fail-closed classifier and provenance validator for PQG Smoke tracking."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence


FULL_RECEIPT_CONTEXT = "pqg/smoke-full"
FULL_RECEIPT_DESCRIPTION = "PQG full runtime smoke passed"
TRACKING_RECEIPT_CONTEXT = "pqg/tracking-integrity"
TRACKING_RECEIPT_DESCRIPTION = "PQG tracking equivalence verified"
WORKFLOW_PATH = ".github/workflows/smoke.yml"
ZERO_SHA = "0" * 40
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
TRACKING_PATHS = frozenset(
    {
        "docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md",
        "docs/project-memory/PROJECT_CHANGELOG.md",
        "docs/project-memory/PROJECT_CONTEXT.md",
        "docs/project-memory/PROJECT_MEMORY.md",
        "docs/project-memory/REMEDIATION_MASTER_PLAN_CONTEXT.md",
    }
)


@dataclass(frozen=True)
class Change:
    status: str
    path: str


@dataclass(frozen=True)
class Decision:
    mode: str
    reason: str
    anchor_sha: str = ""
    predecessor_sha: str = ""
    tracking_depth: int = 0


class GateError(RuntimeError):
    """Raised when Git or GitHub evidence cannot be validated safely."""


def _changes_are_tracking_only(changes: Sequence[Change]) -> bool:
    return bool(changes) and all(
        change.status == "M" and change.path in TRACKING_PATHS for change in changes
    )


def _change_failure(changes: Sequence[Change], label: str) -> str:
    if not changes:
        return f"{label} has no classifiable changed paths"
    for change in changes:
        if change.status != "M":
            return f"{label} path {change.path!r} has status {change.status!r}"
        if change.path not in TRACKING_PATHS:
            return f"{label} path {change.path!r} is outside the tracking allowlist"
    return f"{label} is not tracking-only"


def classify_candidate(
    *,
    event_name: str,
    ref_name: str,
    before_sha: str,
    head_sha: str,
    parent_sha: str,
    head_changes: Sequence[Change],
    parent_changes: Sequence[Change],
    parent_parent_sha: str = "",
    cumulative_changes: Sequence[Change] = (),
    anchor_is_tracking: bool = False,
) -> Decision:
    """Classify a direct push against a bounded two-tracking-commit window."""

    if event_name != "push":
        return Decision("full", f"event {event_name!r} is not an eligible push")
    if ref_name != "pqg-workspace":
        return Decision("full", f"ref {ref_name!r} is not pqg-workspace")
    if not SHA_PATTERN.fullmatch(before_sha) or before_sha == ZERO_SHA:
        return Decision("full", "push does not have a valid non-zero before SHA")
    if not SHA_PATTERN.fullmatch(head_sha):
        return Decision("full", "head SHA is invalid")
    if not SHA_PATTERN.fullmatch(parent_sha) or parent_sha != before_sha:
        return Decision("full", "push is not a single direct child of before SHA")
    if not _changes_are_tracking_only(head_changes):
        return Decision("full", _change_failure(head_changes, "head commit"))
    if not _changes_are_tracking_only(parent_changes):
        return Decision(
            "tracking",
            "first tracking child anchored to its direct full-validation parent",
            parent_sha,
            "",
            1,
        )
    if not SHA_PATTERN.fullmatch(parent_parent_sha):
        return Decision("full", "tracking predecessor has no valid first parent")
    if anchor_is_tracking:
        return Decision("full", "tracking chain would exceed two consecutive commits")
    if not _changes_are_tracking_only(cumulative_changes):
        return Decision(
            "full",
            _change_failure(cumulative_changes, "cumulative anchor-to-head diff"),
        )
    return Decision(
        "tracking",
        "second tracking child verifies its predecessor and full-validation anchor",
        parent_parent_sha,
        parent_sha,
        2,
    )


def parse_name_status_z(raw: bytes) -> list[Change]:
    """Parse ``git diff --name-status -z --no-renames`` output."""

    tokens = raw.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    if len(tokens) % 2:
        raise GateError("unexpected git name-status token count")
    changes: list[Change] = []
    for index in range(0, len(tokens), 2):
        try:
            status = tokens[index].decode("ascii")
            path = tokens[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GateError("git change metadata is not valid ASCII/UTF-8") from exc
        changes.append(Change(status=status, path=path))
    return changes


def select_receipt(
    payload: Mapping[str, Any],
    *,
    repository: str,
    expected_sha: str,
    kind: str,
) -> tuple[Mapping[str, Any], int]:
    """Select the newest canonical status and bind it to an Actions run ID."""

    contracts = {
        "full": (FULL_RECEIPT_CONTEXT, FULL_RECEIPT_DESCRIPTION),
        "tracking": (TRACKING_RECEIPT_CONTEXT, TRACKING_RECEIPT_DESCRIPTION),
    }
    if kind not in contracts:
        raise GateError(f"unknown receipt kind {kind!r}")
    context, description = contracts[kind]
    if payload.get("sha") != expected_sha:
        raise GateError("commit status response SHA does not match expected SHA")
    statuses = payload.get("statuses")
    if not isinstance(statuses, list):
        raise GateError("commit status response has no statuses list")
    matches = [
        item
        for item in statuses
        if isinstance(item, dict) and item.get("context") == context
    ]
    if not matches:
        raise GateError(f"commit has no {context} receipt")
    latest = max(matches, key=lambda item: str(item.get("created_at", "")))
    if latest.get("state") != "success":
        raise GateError(f"newest {context} receipt is not success")
    if latest.get("description") != description:
        raise GateError(f"{context} description does not match the canonical contract")
    target_url = latest.get("target_url")
    pattern = re.compile(
        rf"^https://github\.com/{re.escape(repository)}/actions/runs/([0-9]+)(?:/.*)?$"
    )
    match = pattern.fullmatch(target_url) if isinstance(target_url, str) else None
    if match is None:
        raise GateError(f"{context} target URL is not a repository Actions run")
    return latest, int(match.group(1))


def verify_run_provenance(
    run: Mapping[str, Any],
    jobs_payload: Mapping[str, Any],
    *,
    repository: str,
    expected_sha: str,
    shape: str,
) -> None:
    """Verify exact workflow/run/job provenance behind a commit status."""

    if shape not in {"full", "tracking"}:
        raise GateError(f"unknown run shape {shape!r}")
    run_repository = run.get("repository")
    if not isinstance(run_repository, dict) or run_repository.get("full_name") != repository:
        raise GateError("Actions run repository does not match")
    expected_fields = {
        "head_sha": expected_sha,
        "path": WORKFLOW_PATH,
        "status": "completed",
        "conclusion": "success",
        "event": "push",
    }
    for field, expected in expected_fields.items():
        if run.get(field) != expected:
            raise GateError(f"Actions run {field} does not match {expected!r}")
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        raise GateError("Actions jobs response has no jobs list")
    by_name: dict[str, Mapping[str, Any]] = {}
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            continue
        name = str(job["name"])
        if name in by_name:
            raise GateError(f"Actions jobs response has duplicate job name {name!r}")
        by_name[name] = job
    expected_jobs = {
        "classify": "success",
        "smoke-full": "success" if shape == "full" else "skipped",
        "tracking-integrity": "skipped" if shape == "full" else "success",
        "smoke-result": "success",
    }
    for name, conclusion in expected_jobs.items():
        if name not in by_name or by_name[name].get("conclusion") != conclusion:
            raise GateError(f"job {name!r} is not {conclusion!r}")


def decide_final_result(
    *, mode: str, classify_result: str, full_result: str, tracking_result: str
) -> tuple[str, str]:
    if (
        classify_result == "success"
        and mode == "full"
        and full_result == "success"
        and tracking_result == "skipped"
    ):
        return "success", FULL_RECEIPT_DESCRIPTION
    if (
        classify_result == "success"
        and mode == "tracking"
        and full_result == "skipped"
        and tracking_result == "success"
    ):
        return "success", TRACKING_RECEIPT_DESCRIPTION
    return "failure", "PQG smoke gate failed closed"


def _git_bytes(args: Iterable[str]) -> bytes:
    command = ["git", *args]
    try:
        return subprocess.run(command, check=True, stdout=subprocess.PIPE).stdout
    except subprocess.CalledProcessError as exc:
        raise GateError(f"git command failed: {' '.join(command)}") from exc


def _parents(commit: str) -> list[str]:
    fields = _git_bytes(["rev-list", "--parents", "-n", "1", commit]).decode("ascii").split()
    return fields[1:]


def _diff_changes(base: str, head: str) -> list[Change]:
    return parse_name_status_z(
        _git_bytes(["diff", "--name-status", "-z", "--no-renames", base, head])
    )


def classify_live(args: argparse.Namespace) -> Decision:
    if args.event_name != "push" or args.ref_name != "pqg-workspace":
        return classify_candidate(
            event_name=args.event_name,
            ref_name=args.ref_name,
            before_sha=args.before_sha,
            head_sha=args.head_sha,
            parent_sha=args.before_sha,
            head_changes=(),
            parent_changes=(),
        )
    if not SHA_PATTERN.fullmatch(args.before_sha) or args.before_sha == ZERO_SHA:
        return Decision("full", "push does not have a valid non-zero before SHA")
    actual_head = _git_bytes(["rev-parse", "HEAD"]).decode("ascii").strip()
    if actual_head != args.head_sha:
        return Decision("full", "checked-out HEAD does not match event head SHA")
    head_parents = _parents(args.head_sha)
    if len(head_parents) != 1:
        return Decision("full", "head is not a single-parent commit")
    parent_sha = head_parents[0]
    head_changes = _diff_changes(parent_sha, args.head_sha)
    parent_parents = _parents(parent_sha)
    parent_parent_sha = parent_parents[0] if len(parent_parents) == 1 else ""
    parent_changes = _diff_changes(parent_parent_sha, parent_sha) if parent_parent_sha else ()
    cumulative_changes: Sequence[Change] = ()
    anchor_is_tracking = False
    if _changes_are_tracking_only(parent_changes):
        cumulative_changes = _diff_changes(parent_parent_sha, args.head_sha)
        anchor_parents = _parents(parent_parent_sha)
        if len(anchor_parents) == 1:
            anchor_is_tracking = _changes_are_tracking_only(
                _diff_changes(anchor_parents[0], parent_parent_sha)
            )
    return classify_candidate(
        event_name=args.event_name,
        ref_name=args.ref_name,
        before_sha=args.before_sha,
        head_sha=args.head_sha,
        parent_sha=parent_sha,
        head_changes=head_changes,
        parent_changes=parent_changes,
        parent_parent_sha=parent_parent_sha,
        cumulative_changes=cumulative_changes,
        anchor_is_tracking=anchor_is_tracking,
    )


def write_github_output(path: str, values: Mapping[str, object]) -> None:
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            rendered = str(value).replace("\r", " ").replace("\n", " ")
            handle.write(f"{key}={rendered}\n")


def _read_json(path: str) -> Mapping[str, Any]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise GateError("JSON payload is not an object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument("--event-name", required=True)
    classify_parser.add_argument("--ref-name", required=True)
    classify_parser.add_argument("--before-sha", required=True)
    classify_parser.add_argument("--head-sha", required=True)
    classify_parser.add_argument("--github-output", required=True)
    receipt_parser = subparsers.add_parser("select-receipt")
    receipt_parser.add_argument("--payload", required=True)
    receipt_parser.add_argument("--repository", required=True)
    receipt_parser.add_argument("--expected-sha", required=True)
    receipt_parser.add_argument("--kind", choices=("full", "tracking"), required=True)
    receipt_parser.add_argument("--github-output", required=True)
    run_parser = subparsers.add_parser("verify-run")
    run_parser.add_argument("--run-payload", required=True)
    run_parser.add_argument("--jobs-payload", required=True)
    run_parser.add_argument("--repository", required=True)
    run_parser.add_argument("--expected-sha", required=True)
    run_parser.add_argument("--shape", choices=("full", "tracking"), required=True)
    final_parser = subparsers.add_parser("decide-final")
    final_parser.add_argument("--mode", required=True)
    final_parser.add_argument("--classify-result", required=True)
    final_parser.add_argument("--full-result", required=True)
    final_parser.add_argument("--tracking-result", required=True)
    final_parser.add_argument("--github-output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "classify":
            decision = classify_live(args)
            write_github_output(args.github_output, decision.__dict__)
            print(json.dumps(decision.__dict__, sort_keys=True))
            return 0
        if args.command == "select-receipt":
            receipt, run_id = select_receipt(
                _read_json(args.payload), repository=args.repository,
                expected_sha=args.expected_sha, kind=args.kind,
            )
            write_github_output(args.github_output, {"run_id": run_id})
            print(json.dumps({"context": receipt["context"], "run_id": run_id}, sort_keys=True))
            return 0
        if args.command == "verify-run":
            verify_run_provenance(
                _read_json(args.run_payload), _read_json(args.jobs_payload),
                repository=args.repository, expected_sha=args.expected_sha, shape=args.shape,
            )
            print(json.dumps({"shape": args.shape, "verified": True}, sort_keys=True))
            return 0
        state, description = decide_final_result(
            mode=args.mode, classify_result=args.classify_result,
            full_result=args.full_result, tracking_result=args.tracking_result,
        )
        write_github_output(args.github_output, {"state": state, "description": description})
        print(json.dumps({"state": state, "description": description}, sort_keys=True))
        return 0
    except (GateError, json.JSONDecodeError, OSError) as exc:
        print(f"P-TRACK gate failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
