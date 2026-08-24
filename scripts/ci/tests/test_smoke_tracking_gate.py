from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "smoke_tracking_gate.py"
SPEC = importlib.util.spec_from_file_location("smoke_tracking_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

HEAD = "d" * 40
PARENT = "c" * 40
ANCHOR = "b" * 40
TRACKING_FILE = "docs/project-memory/PROJECT_MEMORY.md"
TRACKING_CHANGE = [gate.Change("M", TRACKING_FILE)]


class ClassifierTests(unittest.TestCase):
    def classify(self, **overrides):
        values = {
            "event_name": "push",
            "ref_name": "pqg-workspace",
            "before_sha": PARENT,
            "head_sha": HEAD,
            "parent_sha": PARENT,
            "head_changes": TRACKING_CHANGE,
            "parent_changes": [gate.Change("M", ".github/workflows/smoke.yml")],
            "parent_parent_sha": ANCHOR,
        }
        values.update(overrides)
        return gate.classify_candidate(**values)

    def test_accepts_first_tracking_child_of_source_anchor(self):
        decision = self.classify()
        self.assertEqual((decision.mode, decision.tracking_depth), ("tracking", 1))
        self.assertEqual(decision.anchor_sha, PARENT)
        self.assertEqual(decision.predecessor_sha, "")

    def test_accepts_second_tracking_child_with_cumulative_allowlist(self):
        decision = self.classify(
            parent_changes=TRACKING_CHANGE,
            parent_parent_sha=ANCHOR,
            cumulative_changes=[
                gate.Change("M", TRACKING_FILE),
                gate.Change("M", "docs/project-memory/PROJECT_CHANGELOG.md"),
            ],
        )
        self.assertEqual((decision.mode, decision.tracking_depth), ("tracking", 2))
        self.assertEqual(decision.anchor_sha, ANCHOR)
        self.assertEqual(decision.predecessor_sha, PARENT)

    def test_third_consecutive_tracking_commit_falls_full(self):
        decision = self.classify(
            parent_changes=TRACKING_CHANGE,
            parent_parent_sha=ANCHOR,
            cumulative_changes=TRACKING_CHANGE,
            anchor_is_tracking=True,
        )
        self.assertEqual(decision.mode, "full")

    def test_cumulative_non_allowlisted_or_rename_falls_full(self):
        for changes in (
            [gate.Change("M", ".github/workflows/smoke.yml")],
            [gate.Change("R100", TRACKING_FILE)],
        ):
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.classify(
                        parent_changes=TRACKING_CHANGE,
                        parent_parent_sha=ANCHOR,
                        cumulative_changes=changes,
                    ).mode,
                    "full",
                )

    def test_pull_request_task_branch_and_multi_commit_push_are_full(self):
        self.assertEqual(self.classify(event_name="pull_request").mode, "full")
        self.assertEqual(self.classify(ref_name="work/example").mode, "full")
        self.assertEqual(self.classify(parent_sha=ANCHOR).mode, "full")

    def test_invalid_or_zero_sha_is_full(self):
        self.assertEqual(self.classify(before_sha=gate.ZERO_SHA).mode, "full")
        self.assertEqual(self.classify(head_sha="invalid").mode, "full")

    def test_incomplete_parent_ancestry_falls_full(self):
        self.assertEqual(
            self.classify(parent_changes=(), parent_parent_sha="").mode,
            "full",
        )

    def test_head_add_delete_rename_or_outside_path_is_full(self):
        for change in (
            gate.Change("A", TRACKING_FILE),
            gate.Change("D", TRACKING_FILE),
            gate.Change("R100", TRACKING_FILE),
            gate.Change("M", "docs/00_PROJECT_CANON.md"),
        ):
            with self.subTest(change=change):
                self.assertEqual(self.classify(head_changes=[change]).mode, "full")

    def test_parses_nul_delimited_git_changes(self):
        raw = b"M\0docs/project-memory/PROJECT_MEMORY.md\0D\0old.md\0"
        self.assertEqual(
            gate.parse_name_status_z(raw),
            [gate.Change("M", TRACKING_FILE), gate.Change("D", "old.md")],
        )


class WorkflowContractTests(unittest.TestCase):
    def test_push_base_fetch_preserves_tracking_ancestry(self):
        workflow = (Path(__file__).parents[3] / ".github/workflows/smoke.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('fetch --no-tags --deepen=4 origin "${BEFORE_SHA}"', workflow)
        self.assertNotIn('fetch --no-tags --depth=1 origin "${BEFORE_SHA}"', workflow)


class ReceiptTests(unittest.TestCase):
    def status(self, kind="full", **overrides):
        context = gate.FULL_RECEIPT_CONTEXT if kind == "full" else gate.TRACKING_RECEIPT_CONTEXT
        description = gate.FULL_RECEIPT_DESCRIPTION if kind == "full" else gate.TRACKING_RECEIPT_DESCRIPTION
        values = {
            "context": context,
            "state": "success",
            "description": description,
            "target_url": "https://github.com/owner/repo/actions/runs/123",
            "created_at": "2026-08-24T10:00:00Z",
        }
        values.update(overrides)
        return values

    def test_selects_full_and_tracking_receipts_and_extracts_run_id(self):
        for kind in ("full", "tracking"):
            with self.subTest(kind=kind):
                _, run_id = gate.select_receipt(
                    {"sha": PARENT, "statuses": [self.status(kind)]},
                    repository="owner/repo", expected_sha=PARENT, kind=kind,
                )
                self.assertEqual(run_id, 123)

    def test_latest_matching_failure_fails_closed(self):
        payload = {"sha": PARENT, "statuses": [
            self.status(created_at="2026-08-24T09:00:00Z"),
            self.status(state="failure", created_at="2026-08-24T10:00:00Z"),
        ]}
        with self.assertRaises(gate.GateError):
            gate.select_receipt(payload, repository="owner/repo", expected_sha=PARENT, kind="full")

    def test_wrong_sha_description_repository_or_run_id_fails_closed(self):
        cases = (
            (HEAD, self.status()),
            (PARENT, self.status(description="wrong")),
            (PARENT, self.status(target_url="https://github.com/other/repo/actions/runs/123")),
            (PARENT, self.status(target_url="https://github.com/owner/repo/actions/runs/not-a-number")),
        )
        for sha, status in cases:
            with self.subTest(sha=sha, status=status):
                with self.assertRaises(gate.GateError):
                    gate.select_receipt(
                        {"sha": sha, "statuses": [status]}, repository="owner/repo",
                        expected_sha=PARENT, kind="full",
                    )


class ProvenanceTests(unittest.TestCase):
    def workflow_run(self, **overrides):
        values = {
            "repository": {"full_name": "owner/repo"},
            "head_sha": PARENT,
            "path": gate.WORKFLOW_PATH,
            "status": "completed",
            "conclusion": "success",
            "event": "push",
        }
        values.update(overrides)
        return values

    def jobs(self, shape="full", **overrides):
        conclusions = {
            "classify": "success",
            "smoke-full": "success" if shape == "full" else "skipped",
            "tracking-integrity": "skipped" if shape == "full" else "success",
            "smoke-result": "success",
        }
        conclusions.update(overrides)
        return {"jobs": [{"name": name, "conclusion": conclusion} for name, conclusion in conclusions.items()]}

    def test_accepts_exact_full_and_tracking_job_shapes(self):
        for shape in ("full", "tracking"):
            with self.subTest(shape=shape):
                gate.verify_run_provenance(
                    self.workflow_run(), self.jobs(shape), repository="owner/repo",
                    expected_sha=PARENT, shape=shape,
                )

    def test_wrong_repo_sha_workflow_event_or_conclusion_fails_closed(self):
        cases = (
            self.workflow_run(repository={"full_name": "other/repo"}),
            self.workflow_run(head_sha=HEAD),
            self.workflow_run(path=".github/workflows/other.yml"),
            self.workflow_run(event="workflow_dispatch"),
            self.workflow_run(conclusion="failure"),
        )
        for run in cases:
            with self.subTest(run=run):
                with self.assertRaises(gate.GateError):
                    gate.verify_run_provenance(
                        run, self.jobs(), repository="owner/repo", expected_sha=PARENT, shape="full"
                    )

    def test_wrong_job_shape_or_duplicate_job_fails_closed(self):
        with self.assertRaises(gate.GateError):
            gate.verify_run_provenance(
                self.workflow_run(), self.jobs("full", **{"smoke-result": "failure"}),
                repository="owner/repo", expected_sha=PARENT, shape="full",
            )
        duplicate = self.jobs()["jobs"] + [{"name": "smoke-result", "conclusion": "success"}]
        with self.assertRaises(gate.GateError):
            gate.verify_run_provenance(
                self.workflow_run(), {"jobs": duplicate}, repository="owner/repo",
                expected_sha=PARENT, shape="full",
            )


class FinalResultTests(unittest.TestCase):
    def test_only_exact_full_or_tracking_shape_succeeds(self):
        accepted = (
            ("full", "success", "success", "skipped"),
            ("tracking", "success", "skipped", "success"),
        )
        for mode, classify, full, tracking in accepted:
            self.assertEqual(gate.decide_final_result(
                mode=mode, classify_result=classify, full_result=full,
                tracking_result=tracking,
            )[0], "success")
        self.assertEqual(gate.decide_final_result(
            mode="tracking", classify_result="success", full_result="success",
            tracking_result="success",
        )[0], "failure")


if __name__ == "__main__":
    unittest.main()
