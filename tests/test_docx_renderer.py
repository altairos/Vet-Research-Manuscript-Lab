"""Tests for the DOCX renderer service.

Covers MockDocxRenderer determinism, QuartoDocxRenderer availability
detection, PandocDocxRenderer availability detection, auto-detection
factory, and integration with MockExportGenerator.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.services.export import (
    DocxRenderInput,
    ExportInput,
    MockDocxRenderer,
    MockExportGenerator,
    PandocDocxRenderer,
    QuartoDocxRenderer,
    create_docx_renderer,
)


class MockDocxRendererTests(unittest.TestCase):
    def test_render_produces_valid_result(self) -> None:
        renderer = MockDocxRenderer()
        result = renderer.render(
            DocxRenderInput(
                qmd_content="---\ntitle: Test\n---\n\n## Results\n\nSome text.",
                bib_content="% No references",
                title="Test Manuscript",
            )
        )
        self.assertTrue(result.docx_base64)
        self.assertTrue(result.content_hash.startswith("sha256:"))
        self.assertEqual(result.renderer_name, "mock")

    def test_determinism_same_input_same_hash(self) -> None:
        renderer = MockDocxRenderer()
        inputs = DocxRenderInput(
            qmd_content="Test content",
            bib_content="% empty",
            title="Same Title",
        )
        out1 = renderer.render(inputs)
        out2 = renderer.render(inputs)
        self.assertEqual(out1.content_hash, out2.content_hash)
        self.assertEqual(out1.docx_base64, out2.docx_base64)

    def test_different_input_different_hash(self) -> None:
        renderer = MockDocxRenderer()
        out1 = renderer.render(
            DocxRenderInput(qmd_content="A", bib_content="", title="T1")
        )
        out2 = renderer.render(
            DocxRenderInput(qmd_content="B", bib_content="", title="T2")
        )
        self.assertNotEqual(out1.content_hash, out2.content_hash)

    def test_media_type_is_docx(self) -> None:
        renderer = MockDocxRenderer()
        result = renderer.render(
            DocxRenderInput(qmd_content="test", bib_content="", title="T")
        )
        self.assertIn("wordprocessingml", result.media_type)


class QuartoDocxRendererTests(unittest.TestCase):
    def test_is_available_returns_bool(self) -> None:
        renderer = QuartoDocxRenderer()
        self.assertIsInstance(renderer.is_available(), bool)

    def test_render_raises_if_not_available(self) -> None:
        renderer = QuartoDocxRenderer(quarto_bin=None)
        self.assertFalse(renderer.is_available())
        with self.assertRaises(FileNotFoundError):
            renderer.render(
                DocxRenderInput(qmd_content="test", bib_content="", title="T")
            )


class PandocDocxRendererTests(unittest.TestCase):
    def test_is_available_returns_bool(self) -> None:
        renderer = PandocDocxRenderer()
        self.assertIsInstance(renderer.is_available(), bool)

    def test_render_raises_if_not_available(self) -> None:
        renderer = PandocDocxRenderer(pandoc_bin=None)
        self.assertFalse(renderer.is_available())
        with self.assertRaises(FileNotFoundError):
            renderer.render(
                DocxRenderInput(qmd_content="test", bib_content="", title="T")
            )


class CreateDocxRendererTests(unittest.TestCase):
    def test_returns_a_renderer(self) -> None:
        renderer = create_docx_renderer()
        # Should be one of the three implementations
        name = type(renderer).__name__
        self.assertIn(
            name,
            {"QuartoDocxRenderer", "PandocDocxRenderer", "MockDocxRenderer"},
        )

    def test_prefer_pandoc(self) -> None:
        renderer = create_docx_renderer(prefer="pandoc")
        name = type(renderer).__name__
        self.assertIn(
            name,
            {"PandocDocxRenderer", "MockDocxRenderer"},
        )


class GeneratorWithDocxIntegrationTests(unittest.TestCase):
    def test_generator_without_renderer_has_no_docx(self) -> None:
        gen = MockExportGenerator()
        inputs = ExportInput(
            sections=(
                {
                    "section_type": "introduction",
                    "content": "Intro text",
                    "order": 0,
                },
            ),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "test-so"},
            manuscript_summary={
                "manuscript_id": "m1",
                "title": "Test MS",
            },
        )
        result = gen.generate(inputs)
        roles = {c.role for c in result.components}
        self.assertNotIn("docx", roles)
        self.assertIn("manuscript", roles)

    def test_generator_with_mock_renderer_produces_docx(self) -> None:
        gen = MockExportGenerator(docx_renderer=MockDocxRenderer())
        inputs = ExportInput(
            sections=(
                {
                    "section_type": "results",
                    "content": "The estimate was 2.5.",
                    "order": 0,
                },
            ),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "test-so"},
            manuscript_summary={
                "manuscript_id": "m1",
                "title": "Test MS",
            },
        )
        result = gen.generate(inputs)
        roles = {c.role for c in result.components}
        self.assertIn("docx", roles)
        docx_comp = next(c for c in result.components if c.role == "docx")
        self.assertEqual(docx_comp.filename, "manuscript.docx")
        self.assertTrue(docx_comp.content_hash.startswith("sha256:"))
        self.assertIn("wordprocessingml", docx_comp.media_type)

    def test_docx_component_hash_in_manifest(self) -> None:
        gen = MockExportGenerator(docx_renderer=MockDocxRenderer())
        inputs = ExportInput(
            sections=({"section_type": "intro", "content": "x", "order": 0},),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "so1"},
            manuscript_summary={"manuscript_id": "m1", "title": "T"},
        )
        result = gen.generate(inputs)
        # Manifest component should include docx hash
        import json

        manifest_comp = next(c for c in result.components if c.role == "manifest")
        manifest = json.loads(manifest_comp.content)
        self.assertIn("manuscript.docx", manifest["component_hashes"])

    def test_docx_changes_package_hash(self) -> None:
        inputs = ExportInput(
            sections=({"section_type": "x", "content": "y", "order": 0},),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "so"},
            manuscript_summary={"manuscript_id": "m1", "title": "T"},
        )
        gen_no_docx = MockExportGenerator()
        gen_with_docx = MockExportGenerator(docx_renderer=MockDocxRenderer())
        result_no = gen_no_docx.generate(inputs)
        result_with = gen_with_docx.generate(inputs)
        self.assertNotEqual(result_no.package_hash, result_with.package_hash)

    def test_docx_generator_determinism(self) -> None:
        gen = MockExportGenerator(docx_renderer=MockDocxRenderer())
        inputs = ExportInput(
            sections=({"section_type": "a", "content": "b", "order": 0},),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "so"},
            manuscript_summary={"manuscript_id": "m1", "title": "T"},
        )
        out1 = gen.generate(inputs)
        out2 = gen.generate(inputs)
        self.assertEqual(out1.package_hash, out2.package_hash)


if __name__ == "__main__":
    unittest.main()
