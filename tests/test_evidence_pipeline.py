"""Tests for EvidencePipeline integration into evidence_extraction_node.

Verifies that when a pipeline (PDF parser + chunker + retriever) is injected,
the evidence_extraction node uses real retrieval candidates instead of mock
data — while still enforcing every source-span policy invariant.
"""

from __future__ import annotations

import unittest
from typing import Any

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.services.documents.parser import PdfParser
from vet_manuscript_lab.services.retrieval.chunker import TextChunker
from vet_manuscript_lab.services.retrieval.index import (
    HybridRetriever,
    MockBM25Backend,
)
from vet_manuscript_lab.services.retrieval.types import TextChunk
from vet_manuscript_lab.workflow.literature_graph import (
    EvidencePipeline,
    evidence_extraction_node,
)
from vet_manuscript_lab.workflow.state import (
    WorkflowStage,
    new_workflow_state,
)


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Minimal workflow state with pre-screened included records."""

    base = new_workflow_state(
        project_id="proj-pipeline",
        workflow_run_id="run-pipeline",
        thread_id="thread-pipeline",
        now="2026-07-06T00:00:00Z",
    )
    records = overrides.pop("literature_record_drafts", [])
    base["literature_record_drafts"] = records
    base["artifacts"] = {"search_strategy": {"version_id": "v1"}}
    base.update(overrides)
    return base


def _make_included_records(count: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "record_id": f"rec-{i}",
            "title": f"Canine study {i} results on biomarkers",
            "doi": f"10.1000/test{i}",
            "screening_decision": "included",
        }
        for i in range(1, count + 1)
    ]


def _make_pipeline() -> EvidencePipeline:
    """Build an EvidencePipeline with deterministic mock backends."""

    return EvidencePipeline(
        parser=PdfParser(),
        chunker=TextChunker(),
        retriever=HybridRetriever(backend=MockBM25Backend()),
    )


class EvidencePipelineNodeTests(unittest.TestCase):
    """Tests for evidence_extraction_node with an injected pipeline."""

    # -- no pipeline (mock fallback) ---------------------------------------

    def test_no_pipeline_uses_mock_spans(self) -> None:
        """Without a pipeline, the node generates mock spans as before."""

        state = _make_state(literature_record_drafts=_make_included_records(2))
        result = evidence_extraction_node(state)

        drafts = result["evidence_drafts"]
        self.assertEqual(len(drafts), 2)
        for draft in drafts:
            self.assertEqual(draft["concept"], "study_finding")
            self.assertEqual(draft["value"], "mock extracted value")
            self.assertFalse(draft["requires_human_review"])
        self.assertEqual(
            result["current_stage"], WorkflowStage.EVIDENCE_EXTRACTION.value
        )

    # -- pipeline with chunks ----------------------------------------------

    def test_pipeline_with_chunks_uses_retrieval(self) -> None:
        """When chunks are available, the node retrieves real evidence."""

        chunks = [
            TextChunk(
                chunk_id="chunk-1",
                text="The canine biomarker study showed elevated creatinine "
                "levels in the treatment group compared to placebo.",
                page_number=3,
                char_start=0,
                char_end=100,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label="Results",
                literature_record_id="rec-1",
            ),
        ]
        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=chunks,
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)

        drafts = result["evidence_drafts"]
        self.assertEqual(len(drafts), 1)
        draft = drafts[0]
        self.assertEqual(draft["concept"], "retrieved_finding")
        self.assertIn("canine biomarker", draft["value"])
        self.assertTrue(draft["source_span_ids"])

        spans = result["source_span_drafts"]
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span["page"], 3)
        self.assertEqual(span["section_label"], "Results")

    def test_pipeline_no_hits_falls_back_to_mock_span(self) -> None:
        """When retrieval returns no candidates, a mock span is used."""

        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=[],  # empty chunk list → no retrieval hits
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)

        drafts = result["evidence_drafts"]
        self.assertEqual(len(drafts), 1)
        draft = drafts[0]
        self.assertTrue(draft["requires_human_review"])
        self.assertEqual(draft["extraction_status"], "needs_review")
        self.assertTrue(draft["source_span_ids"])

    def test_pipeline_low_score_requires_review(self) -> None:
        """Candidates with low retrieval scores are flagged for review."""

        # Chunk with completely unrelated text → low BM25 overlap score
        chunks = [
            TextChunk(
                chunk_id="chunk-unrelated",
                text="zzzz unrelated xyzzy content",
                page_number=1,
                char_start=0,
                char_end=30,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label=None,
            ),
        ]
        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=chunks,
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)
        draft = result["evidence_drafts"][0]

        # The overlap is zero → retriever returns no candidate → mock fallback
        # OR if it returns with score 0, requires_human_review is True
        if draft["concept"] == "retrieved_finding":
            self.assertTrue(draft["requires_human_review"])
        else:
            # fell back to mock span
            self.assertTrue(draft["requires_human_review"])

    # -- policy invariants are enforced ------------------------------------

    def test_pipeline_maintains_source_span_invariant(self) -> None:
        """Every evidence draft must have at least one source span."""

        chunks = [
            TextChunk(
                chunk_id="chunk-a",
                text="Important clinical finding about canine therapy.",
                page_number=7,
                char_start=0,
                char_end=50,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label="Discussion",
            ),
        ]
        state = _make_state(
            literature_record_drafts=_make_included_records(3),
            _pipeline_chunks=chunks,
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)

        for draft in result["evidence_drafts"]:
            self.assertTrue(
                draft["source_span_ids"],
                f"Evidence {draft['evidence_id']} has no source spans",
            )
            for span_id in draft["source_span_ids"]:
                span_ids = {s["span_id"] for s in result["source_span_drafts"]}
                self.assertIn(span_id, span_ids)

    def test_pipeline_span_has_valid_quote_hash(self) -> None:
        """Source spans created by the pipeline must have sha256 quote hashes."""

        # Chunk text must share words with the record title for MockBM25 overlap
        chunk_text = "Canine study biomarker results for hash verification."
        chunks = [
            TextChunk(
                chunk_id="chunk-hash",
                text=chunk_text,
                page_number=2,
                char_start=10,
                char_end=60,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label="Methods",
            ),
        ]
        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=chunks,
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)
        span = result["source_span_drafts"][0]

        expected_hash = sha256_bytes(chunk_text.encode())
        self.assertEqual(span["quote_hash"], expected_hash)

    def test_pipeline_evidence_ledger_artifact_created(self) -> None:
        """The evidence_ledger artifact and summary are populated correctly."""

        chunks = [
            TextChunk(
                chunk_id="chunk-ledger",
                text="Clinical trial endpoint reached statistical significance.",
                page_number=4,
                char_start=0,
                char_end=60,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label="Results",
            ),
        ]
        state = _make_state(
            literature_record_drafts=_make_included_records(2),
            _pipeline_chunks=chunks,
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)

        self.assertIn("evidence_ledger", result["artifacts"])
        self.assertEqual(result["evidence_summary"]["total_evidence_items"], 2)

    def test_pipeline_audit_event_emitted(self) -> None:
        """An evidence.extracted audit event is emitted."""

        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=[],
        )
        pipeline = _make_pipeline()

        result = evidence_extraction_node(state, pipeline=pipeline)
        events = result["audit_events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "evidence.extracted")


class EvidencePipelineDeterminismTests(unittest.TestCase):
    """Verify pipeline-injected extraction is deterministic."""

    def test_same_chunks_produce_same_span_ids(self) -> None:
        """Running the node twice with the same state yields identical span IDs."""

        chunks = [
            TextChunk(
                chunk_id="chunk-det",
                text="Reproducible evidence content for determinism testing.",
                page_number=1,
                char_start=0,
                char_end=55,
                chunk_index=0,
                attachment_version_id="att-v1",
                section_label="Results",
            ),
        ]
        records = _make_included_records(1)
        pipeline = _make_pipeline()

        state_a = _make_state(literature_record_drafts=records, _pipeline_chunks=chunks)
        state_b = _make_state(literature_record_drafts=records, _pipeline_chunks=chunks)

        result_a = evidence_extraction_node(state_a, pipeline=pipeline)
        result_b = evidence_extraction_node(state_b, pipeline=pipeline)

        span_ids_a = {s["span_id"] for s in result_a["source_span_drafts"]}
        span_ids_b = {s["span_id"] for s in result_b["source_span_drafts"]}
        self.assertEqual(span_ids_a, span_ids_b)


if __name__ == "__main__":
    unittest.main()
