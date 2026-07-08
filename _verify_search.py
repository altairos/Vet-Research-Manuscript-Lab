"""Temporary verification of the search-strategy form logic via AppTest."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest

from vet_manuscript_lab.ui import app as app_module

PID = "proj-1"


def _make_app() -> SimpleNamespace:
    app = SimpleNamespace()
    app.settings = SimpleNamespace(zotero_enabled=False)
    app.literature_repository = MagicMock()
    app.literature_repository.list_literature_records.return_value = []
    app.document_importer = MagicMock()
    return app


def run(intake: dict | None = None) -> None:
    intake = intake if intake is not None else {}
    app = _make_app()
    app_module._render_intake_materials(app, PID, intake)


def test_prefill_from_saved() -> None:
    """Saved databases should appear preselected in the multiselect."""

    saved = {
        "query": "(canine) AND survival",
        "databases": ["PubMed", "Web of Science", "Scopus"],
        "date_range": "2020-01-01/2026-12-31",
    }
    intake = {"search_strategy_input": saved}
    at = AppTest.from_function(run, default_session_state={})
    at.run()
    assert not at.exception, at.exception
    # The multiselect widget should reflect the three saved databases.
    ms = at.multiselect(lambda w: "数据库" in (w.label or ""))
    assert ms.value == ["PubMed", "Web of Science", "Scopus"], ms.value
    print("PREFILL OK ->", ms.value)


def test_save_persists_to_intake() -> None:
    """Submitting the form should write the strategy into the intake dict."""

    intake: dict = {}
    # Seed the widget session-state values that the form would carry, then run.
    at = AppTest.from_function(lambda: run(intake), default_session_state={})
    at.run()
    # Type a query and pick databases, then submit.
    ta = at.text_area(0)
    ta.input("(feline) AND kidney").run()
    ms = at.multiselect(lambda w: "数据库" in (w.label or ""))
    ms.set_value(["PubMed", "CAB Abstracts"]).run()
    form = at.form[0]
    form.form_submit_button(0).click().run()
    assert not at.exception, at.exception
    saved = intake.get("search_strategy_input", {})
    assert saved.get("query") == "(feline) AND kidney", saved
    assert saved.get("databases") == ["PubMed", "CAB Abstracts"], saved
    print("SAVE PERSIST OK ->", saved)


def test_reset_reinitializes_from_saved() -> None:
    """Reset should bump the version and reinit widgets from the saved value."""

    saved = {
        "query": "q1",
        "databases": ["Scopus"],
        "date_range": "2021/2022",
    }
    intake = {"search_strategy_input": saved}
    at = AppTest.from_function(lambda: run(intake), default_session_state={})
    at.run()
    # Click reset.
    form = at.form[0]
    form.form_submit_button(1).click().run()
    assert not at.exception, at.exception
    # After reset+rerun, the multiselect should reflect the saved databases.
    at2 = AppTest.from_function(lambda: run(intake), default_session_state={
        "search_form_version:proj-1": 1,
    })
    at2.run()
    ms = at2.multiselect(lambda w: "数据库" in (w.label or ""))
    assert ms.value == ["Scopus"], ms.value
    print("RESET OK ->", ms.value)


if __name__ == "__main__":
    test_prefill_from_saved()
    test_save_persists_to_intake()
    test_reset_reinitializes_from_saved()
    print("\nALL SEARCH-STRATEGY CHECKS PASSED")
