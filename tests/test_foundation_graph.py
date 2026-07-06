from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.workflow.foundation_graph import (
    build_foundation_graph,
    guideline_mapping_node,
)
from vet_manuscript_lab.workflow.state import new_workflow_state


def interrupt_payloads(snapshot: Any) -> list[dict[str, Any]]:
    return [
        pending.value
        for task in snapshot.tasks
        for pending in task.interrupts
        if isinstance(pending.value, dict)
    ]


class FoundationGraphTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-1",
            workflow_run_id="run-1",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_sqlite_checkpoint_resumes_across_graph_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "checkpoints.sqlite"
            thread_id = "resume-thread"
            config = {"configurable": {"thread_id": thread_id}}

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            graph = build_foundation_graph(saver)
            graph.invoke(self.initial_state(thread_id), config)
            first_snapshot = graph.get_state(config)
            self.assertEqual(interrupt_payloads(first_snapshot)[0]["gate"], "question")
            connection.close()

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            resumed_graph = build_foundation_graph(saver)
            resumed_graph.invoke(
                Command(
                    resume={
                        "decision": "approved",
                        "reviewer_id": "investigator-1",
                        "reviewer_role": "investigator",
                    }
                ),
                config,
            )
            second_snapshot = resumed_graph.get_state(config)
            self.assertEqual(interrupt_payloads(second_snapshot)[0]["gate"], "protocol")

            result = resumed_graph.invoke(
                Command(
                    resume={
                        "decision": "approved",
                        "reviewer_id": "investigator-1",
                        "reviewer_role": "investigator",
                    }
                ),
                config,
            )
            self.assertEqual(result["run_status"], "complete")
            self.assertEqual(result["artifacts"]["protocol"]["status"], "locked")
            self.assertEqual(result["locks"]["protocol"]["locked_by"], "investigator-1")
            connection.close()

    def test_rejected_question_creates_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_foundation_graph(saver)
            config = {"configurable": {"thread_id": "revision-thread"}}
            graph.invoke(self.initial_state("revision-thread"), config)
            graph.invoke(
                Command(
                    resume={
                        "decision": "changes_requested",
                        "reviewer_id": "investigator-1",
                        "reviewer_role": "investigator",
                        "comment": "Clarify outcome",
                    }
                ),
                config,
            )
            snapshot = graph.get_state(config)
            self.assertEqual(
                snapshot.values["artifacts"]["research_question"]["version"], 2
            )
            self.assertEqual(interrupt_payloads(snapshot)[0]["gate"], "question")
            connection.close()

    def test_approval_gate_cannot_be_bypassed(self) -> None:
        state = self.initial_state("bypass-thread")
        state["artifacts"] = {
            "research_question": {
                "artifact_id": "question-1",
                "version_id": "question-v1",
                "artifact_type": "research_question",
                "version": 1,
                "status": "in_review",
                "content_hash": "sha256:abc",
                "uri": "mock://question/1",
                "media_type": "application/json",
                "created_at": "2026-07-06T00:00:00Z",
            }
        }
        with self.assertRaisesRegex(PermissionError, "Missing required approval"):
            guideline_mapping_node(state)


if __name__ == "__main__":
    unittest.main()
