"""Streamlit UI for the Foundation + Literature & Evidence pipeline.

Run with: streamlit run src/vet_manuscript_lab/ui/app.py
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import streamlit as st
import streamlit.components.v1 as components
from langgraph.types import Command

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.infrastructure.artifacts import LocalArtifactStore
from vet_manuscript_lab.infrastructure.checkpoints import open_checkpointer
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.governance import GovernanceRepository
from vet_manuscript_lab.infrastructure.database.literature import (
    LiteratureInput,
    LiteratureRepository,
)
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.services.documents import DocumentImporter
from vet_manuscript_lab.services.zotero import (
    ZoteroClient,
    ZoteroConfig,
    ZoteroSynchroniser,
)
from vet_manuscript_lab.ui.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    gate_field,
    stage_label,
    translate,
)
from vet_manuscript_lab.ui.theme import (
    apply_theme,
    render_hero,
    render_phase_tracker,
    render_run_metrics,
)
from vet_manuscript_lab.workflow.compliance_graph import build_compliance_pipeline_graph
from vet_manuscript_lab.workflow.state import new_workflow_state

GOLDEN_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "golden_project"
)


@st.cache_data(show_spinner=False)
def _load_golden_fixture() -> dict[str, Any] | None:
    """Load all golden project fixture JSON files (cached).

    Returns ``None`` and records the error in session state when the
    fixture directory cannot be read so the UI can show a helpful message.
    """

    try:

        def _read_json(rel: str) -> dict[str, Any]:
            return json.loads(  # type: ignore[no-any-return]
                (GOLDEN_FIXTURE_ROOT / rel).read_text(encoding="utf-8")
            )

        return {
            "project": _read_json("project.json"),
            "literature": _read_json("literature/records.json"),
            "methodology": _read_json("methodology/findings.json"),
            "dictionary": _read_json("dictionary/variables.json"),
            "analysis_plan": _read_json("analysis_plan/analyses.json"),
        }
    except (OSError, ValueError) as exc:
        st.session_state["golden_fixture_error"] = str(exc)
        return None


@dataclass(slots=True)
class Application:
    repository: FoundationRepository
    literature_repository: LiteratureRepository
    document_importer: DocumentImporter
    governance: GovernanceRepository
    settings: Settings
    graph: Any
    checkpoint_connection: Any


@st.cache_resource
def get_application() -> Application:
    settings = Settings.from_env()
    database = create_database(
        settings.database_url,
        pool_config=settings.pool_config,
    )
    database.create_schema()
    repository = FoundationRepository(database.sessions)
    literature_repository = LiteratureRepository(database.sessions)
    document_importer = DocumentImporter(
        LocalArtifactStore(settings.artifact_root), literature_repository
    )
    governance = GovernanceRepository(database.sessions)
    connection, checkpointer = open_checkpointer(
        database_url=settings.database_url,
        checkpoint_path=settings.checkpoint_path,
    )
    graph = build_compliance_pipeline_graph(checkpointer)
    return Application(
        repository=repository,
        literature_repository=literature_repository,
        document_importer=document_importer,
        governance=governance,
        settings=settings,
        graph=graph,
        checkpoint_connection=connection,
    )


def _interrupt_values(snapshot: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for task in snapshot.tasks:
        for pending in task.interrupts:
            if isinstance(pending.value, dict):
                values.append(pending.value)
    return values


def _render_sidebar_header() -> None:
    st.sidebar.markdown(
        f"""<div class="sidebar-brand"><strong>{translate("app_title")}</strong>
        <span>{translate("sidebar_tagline")}</span></div>""",
        unsafe_allow_html=True,
    )


def _intake_snapshot(intake: dict[str, Any]) -> str:
    """Return a stable hash of the current intake data for dirty tracking."""

    import hashlib

    payload = json.dumps(intake, sort_keys=True, default=str)
    return hashlib.md5(payload.encode()).hexdigest()


def _snapshot_intake(project_id: str) -> None:
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    st.session_state[f"intake_baseline:{project_id}"] = _intake_snapshot(intake)


def _is_intake_dirty(project_id: str | None) -> bool:
    if project_id is None:
        return False
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    baseline = st.session_state.get(f"intake_baseline:{project_id}")
    if baseline is None:
        return False
    return bool(_intake_snapshot(intake) != baseline)


def _inject_beforeunload(is_dirty: bool) -> None:
    """Inject JS to warn on page leave when there are unsaved changes."""

    flag = "true" if is_dirty else "false"
    components.html(
        f"""
<script>
(function() {{
  window.onbeforeunload = function(e) {{
    if ({flag}) {{
      e.preventDefault();
      return '';
    }}
  }};
}})();
</script>
""",
        height=0,
    )


def _render_language_switch() -> None:
    """Persist the active UI language (English / Chinese) in session state."""

    st.sidebar.divider()
    st.sidebar.markdown(f"#### {translate('sidebar_language_header')}")
    options = list(SUPPORTED_LANGUAGES)
    current = st.session_state.get("language", DEFAULT_LANGUAGE)
    if current not in options:
        current = DEFAULT_LANGUAGE
    selected = st.sidebar.selectbox(
        translate("language_label"),
        options=options,
        format_func=lambda code: LANGUAGE_LABELS[code],
        index=options.index(current),
        label_visibility="collapsed",
    )
    st.session_state["language"] = selected


def _render_project_creation(app: Application) -> None:
    with st.sidebar.expander(translate("sidebar_new_project"), expanded=False):
        species_options = ["canine", "feline"]
        with st.form("create_project", clear_on_submit=True):
            title = st.text_input(translate("field_project_title"))
            owner_id = st.text_input(translate("field_owner_id"))
            species = st.multiselect(
                translate("field_species_scope"),
                species_options,
                format_func=lambda code: translate(f"species_{code}"),
                default=["canine"],
            )
            submitted = st.form_submit_button(
                translate("button_create"), type="primary", use_container_width=True
            )
        if submitted:
            try:
                project = app.repository.create_project(
                    ProjectInput(
                        title=title,
                        study_type="retrospective_observational_clinical_study",
                        species_scope=species,
                        owner_id=owner_id,
                    )
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["project_id"] = project.id
                st.session_state["project_created_notice"] = translate(
                    "success_project_created", name=project.title
                )
                st.rerun()


def _render_projects(app: Application) -> None:
    """Show project creation/deletion notices."""

    notice = st.session_state.pop("project_created_notice", None)
    if isinstance(notice, str):
        st.sidebar.success(notice)


def _inject_context_menu_js() -> None:
    """Inject JS that adds right-click context menus to project list items.

    The menu element and MutationObserver are created once on the parent
    window, but ``attachListeners`` runs on **every** component re-render so
    that newly rendered project items always receive context-menu bindings
    and stale hidden action buttons are always cleaned up.
    """

    rename_label = translate("ctx_rename")
    delete_label = translate("ctx_delete")
    components.html(
        f"""
<script>
(function() {{
  const parent = window.parent.document;
  const w = window.parent;

  /* --- Create menu element (once) --- */
  let menu = parent.getElementById('st-ctx-menu');
  if (!menu) {{
    menu = parent.createElement('div');
    menu.id = 'st-ctx-menu';
    menu.style.cssText =
      'position:fixed;display:none;background:#fff;'
      + 'border:1px solid #d0d5d2;border-radius:10px;'
      + 'box-shadow:0 8px 28px rgba(0,0,0,.18);'
      + 'z-index:2147483647;min-width:160px;padding:4px 0;'
      + 'font-size:14px;overflow:visible;';
    parent.body.appendChild(menu);
    w.addEventListener('click', function() {{
      menu.style.display = 'none';
    }});
    w.addEventListener('scroll', function() {{
      menu.style.display = 'none';
    }}, true);
  }}

  function showMenu(x, y, projectId) {{
    menu.innerHTML = '';
    var renameItem = parent.createElement('div');
    renameItem.className = 'ctx-menu-item';
    renameItem.textContent = '\\u2702  {rename_label}';
    renameItem.onclick = function(e) {{
      e.stopPropagation();
      menu.style.display = 'none';
      triggerCtxAction('rename', projectId);
    }};
    menu.appendChild(renameItem);

    var sep = parent.createElement('div');
    sep.className = 'ctx-sep';
    menu.appendChild(sep);

    var deleteItem = parent.createElement('div');
    deleteItem.className = 'ctx-menu-item danger';
    deleteItem.textContent = '\\u2717  {delete_label}';
    deleteItem.onclick = function(e) {{
      e.stopPropagation();
      menu.style.display = 'none';
      triggerCtxAction('delete', projectId);
    }};
    menu.appendChild(deleteItem);

    menu.style.display = 'block';
    /* Viewport boundary detection so the menu is never clipped */
    var rect = menu.getBoundingClientRect();
    var vw = w.innerWidth || parent.documentElement.clientWidth;
    var vh = w.innerHeight || parent.documentElement.clientHeight;
    if (x + rect.width > vw - 8) x = vw - rect.width - 8;
    if (y + rect.height > vh - 8) y = vh - rect.height - 8;
    if (x < 4) x = 4;
    if (y < 4) y = 4;
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
  }}

  function triggerCtxAction(action, projectId) {{
    /* Verify the project still exists as a visible list item */
    if (!parent.querySelector(
      '[data-project-id="' + projectId + '"]'
    )) return;
    var marker = (action === 'rename' ? 'rn:' : 'dl:') + projectId;
    var buttons = parent.querySelectorAll(
      '[data-testid="stSidebar"] button'
    );
    for (var i = 0; i < buttons.length; i++) {{
      if (buttons[i].textContent.indexOf(marker) !== -1) {{
        buttons[i].click();
        return;
      }}
    }}
  }}

  function attachListeners() {{
    /* Hide all context-menu action buttons thoroughly */
    parent.querySelectorAll(
      '[data-testid="stSidebar"] button'
    ).forEach(function(btn) {{
      var t = btn.textContent || '';
      if (t.indexOf('rn:') !== -1 || t.indexOf('dl:') !== -1) {{
        var c = btn.closest('[data-testid="stElementContainer"]')
              || btn.closest('.stButton');
        if (c) {{
          c.style.setProperty('display', 'none', 'important');
          c.style.height = '0';
          c.style.overflow = 'hidden';
          c.style.padding = '0';
          c.style.margin = '0';
        }} else {{
          btn.style.setProperty('display', 'none', 'important');
        }}
      }}
    }});
    /* Attach context-menu listeners to clickable project items */
    parent.querySelectorAll('[data-project-clickable="true"]').forEach(
      function(el) {{
        if (el.getAttribute('data-ctx-bound')) return;
        el.setAttribute('data-ctx-bound', '1');
        el.addEventListener('contextmenu', function(e) {{
          e.preventDefault();
          e.stopPropagation();
          var pid = el.getAttribute('data-project-id');
          showMenu(e.clientX, e.clientY, pid);
        }});
      }}
    );
  }}

  /* Always run on every component re-render */
  attachListeners();

  /* Set up MutationObserver only once on the parent window */
  if (!w._stCtxObserver) {{
    w._stCtxObserver = new w.MutationObserver(function() {{
      attachListeners();
    }});
    w._stCtxObserver.observe(parent.body, {{childList: true, subtree: true}});
  }}
}})();
</script>
""",
        height=0,
    )


def _render_sidebar_project_management(app: Application) -> None:
    """Render clickable project list with right-click rename/delete."""

    st.sidebar.divider()
    st.sidebar.markdown(f"#### {translate('sidebar_project_management')}")

    projects = app.repository.list_projects()
    if not projects:
        return

    current_pid = st.session_state.get("project_id")
    confirm_id = st.session_state.get("confirm_delete")
    rename_target = st.session_state.get("rename_target")
    pending_switch = st.session_state.get("pending_project_switch")

    for project in projects:
        species_str = ", ".join(
            translate(f"species_{s}") for s in (project.species_scope or [])
        )
        is_active = current_pid == project.id
        active_cls = " active" if is_active else ""
        active_badge = "\u25b8 " if is_active else ""

        st.sidebar.markdown(
            f"""<div class="project-list-item{active_cls}"
            data-project-clickable="true"
            data-project-id="{project.id}">
            <strong>{active_badge}{project.title}</strong>
            <span>{translate("project_item_owner")}: {project.owner_id or "-"} | 
            {translate("project_item_species")}: {species_str or "-"}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        if st.sidebar.button(
            "\u2192",
            key=f"select_{project.id}",
            use_container_width=True,
            disabled=is_active,
        ):
            if _is_intake_dirty(current_pid) and project.id != current_pid:
                st.session_state["pending_project_switch"] = project.id
            else:
                st.session_state["project_id"] = project.id
                _snapshot_intake(project.id)
            st.rerun()

        # Hidden action buttons — JS right-click menu clicks these
        if st.sidebar.button(f"rn:{project.id}", key=f"_rn_{project.id}"):
            st.session_state["rename_target"] = project.id
            st.rerun()
        if st.sidebar.button(f"dl:{project.id}", key=f"_dl_{project.id}"):
            st.session_state["confirm_delete"] = project.id
            st.rerun()

        # ---- Rename inline form ----
        if rename_target == project.id:
            with st.sidebar.form(f"rename_form_{project.id}"):
                new_title = st.text_input(
                    translate("field_new_title"),
                    value=project.title,
                    key=f"rename_input_{project.id}",
                )
                col_save, col_cancel = st.columns(2)
                if col_save.form_submit_button(
                    translate("button_rename_project"),
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        app.repository.rename_project(project.id, new_title)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state.pop("rename_target", None)
                        st.session_state["project_renamed_notice"] = translate(
                            "success_project_renamed"
                        )
                        st.rerun()
                if col_cancel.form_submit_button(
                    translate("label_no"), use_container_width=True
                ):
                    st.session_state.pop("rename_target", None)
                    st.rerun()

        # ---- Delete confirmation ----
        if confirm_id == project.id:
            st.sidebar.warning(translate("confirm_delete_project"))
            c_del, c_cancel = st.sidebar.columns(2)
            if c_del.button(
                "OK",
                type="primary",
                use_container_width=True,
                key=f"confirm_del_{project.id}",
            ):
                try:
                    app.repository.delete_project(project.id)
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("confirm_delete", None)
                    if current_pid == project.id:
                        st.session_state.pop("project_id", None)
                    st.session_state["project_deleted_notice"] = translate(
                        "success_project_deleted"
                    )
                    st.rerun()
            if c_cancel.button(
                translate("label_no"),
                use_container_width=True,
                key=f"cancel_del_{project.id}",
            ):
                st.session_state.pop("confirm_delete", None)
                st.rerun()

    # ---- Unsaved-changes confirmation on project switch ----
    if pending_switch is not None:
        st.sidebar.warning(translate("confirm_unsaved_changes"))
        c_yes, c_no = st.sidebar.columns(2)
        if c_yes.button(
            translate("label_discard"),
            type="primary",
            use_container_width=True,
            key="discard_yes",
        ):
            st.session_state["project_id"] = pending_switch
            st.session_state.pop("pending_project_switch", None)
            _snapshot_intake(pending_switch)
            st.rerun()
        if c_no.button(
            translate("label_stay"),
            use_container_width=True,
            key="discard_no",
        ):
            st.session_state.pop("pending_project_switch", None)
            st.rerun()

    deleted_notice = st.session_state.pop("project_deleted_notice", None)
    renamed_notice = st.session_state.pop("project_renamed_notice", None)
    if isinstance(deleted_notice, str):
        st.sidebar.success(deleted_notice)
    if isinstance(renamed_notice, str):
        st.sidebar.success(renamed_notice)

    # Inject the right-click context menu after all items are rendered
    _inject_context_menu_js()


def _literature_draft(record: Any) -> dict[str, Any]:
    return {
        "record_id": record.id,
        "title": record.title,
        "doi": record.doi,
        "pmid": record.pmid,
        "journal": record.journal,
        "publication_year": record.publication_year,
        "screening_decision": "pending",
    }


def _render_intake_question(intake: dict[str, Any]) -> None:
    """Render the PECO research-question form."""

    question = dict(intake.get("research_question_input", {}))
    with st.form("analysis-question"):
        objective = st.text_area(
            translate("field_objective"),
            value=question.get("objective", ""),
            height=68,
        )
        peco_cols = st.columns(4)
        population = peco_cols[0].text_input(
            translate("field_population"), value=question.get("population", "")
        )
        exposure = peco_cols[1].text_input(
            translate("field_exposure"), value=question.get("exposure", "")
        )
        comparator = peco_cols[2].text_input(
            translate("field_comparator"), value=question.get("comparator", "")
        )
        outcome = peco_cols[3].text_input(
            translate("field_outcome"), value=question.get("outcome", "")
        )
        hypothesis = st.text_input(
            translate("field_hypothesis"), value=question.get("hypothesis", "")
        )
        if st.form_submit_button(translate("button_save_question"), type="primary"):
            required = (objective, population, exposure, outcome)
            if not all(value.strip() for value in required):
                st.error(translate("error_required_fields"))
            else:
                intake["research_question_input"] = {
                    "objective": objective.strip(),
                    "population": population.strip(),
                    "exposure": exposure.strip(),
                    "comparator": comparator.strip(),
                    "outcome": outcome.strip(),
                    "hypothesis": hypothesis.strip(),
                }
                st.success(translate("success_question_saved"))


def _bump_search_form_version(project_id: str) -> None:
    """Increment the search-strategy form version.

    The search form widgets are keyed by this version so that bumping it
    forces them to reinitialize from the currently saved strategy, defeating
    Streamlit's widget-state stickiness.
    """

    current = st.session_state.get(f"search_form_version:{project_id}", 0)
    st.session_state[f"search_form_version:{project_id}"] = current + 1


def _render_intake_materials(
    app: Application, project_id: str, intake: dict[str, Any]
) -> None:
    """Render literature search and dataset forms."""

    # ---- Literature / search strategy ----------------------------------
    search = dict(intake.get("search_strategy_input", {}))

    st.markdown(f"##### {translate('edit_strategy_header')}")

    # Version the form widgets so they reinitialize from the saved strategy
    # whenever it changes externally (e.g. loading Golden inputs) or when the
    # user requests a reset. This avoids Streamlit's widget-state stickiness,
    # which otherwise prevents saved databases from appearing prefilled.
    search_version = st.session_state.get(
        f"search_form_version:{project_id}", 0
    )
    ss_query_key = f"ss_query:{project_id}:{search_version}"
    ss_dbs_key = f"ss_databases:{project_id}:{search_version}"
    ss_date_key = f"ss_date:{project_id}:{search_version}"
    for key, value in (
        (ss_query_key, search.get("query", "")),
        (
            ss_dbs_key,
            search.get("databases", ["PubMed", "CAB Abstracts"]),
        ),
        (ss_date_key, search.get("date_range", "2018-01-01/2026-12-31")),
    ):
        if key not in st.session_state:
            st.session_state[key] = value

    with st.form("search-strategy"):
        query = st.text_area(
            translate("field_search_query"),
            key=ss_query_key,
            height=68,
        )
        date_col, db_col = st.columns([1, 2])
        date_range = date_col.text_input(
            translate("field_date_range"),
            key=ss_date_key,
        )
        databases = db_col.multiselect(
            translate("field_databases"),
            ["PubMed", "CAB Abstracts", "Web of Science", "Scopus"],
            key=ss_dbs_key,
        )
        save_col, reset_col = st.columns(2)
        submitted = save_col.form_submit_button(
            translate("button_save_search"), type="primary"
        )
        reset_clicked = reset_col.form_submit_button(
            translate("button_reset_search")
        )
        if submitted:
            if not query.strip():
                st.error(translate("error_search_required"))
            else:
                intake["search_strategy_input"] = {
                    "query": query.strip(),
                    "databases": databases,
                    "date_range": date_range.strip(),
                }
                st.success(translate("success_search_saved"))
        if reset_clicked:
            # Bump the widget version so the form reinitializes from the
            # currently saved strategy on the next render.
            _bump_search_form_version(project_id)
            st.rerun()

    # View the currently saved strategy *after* the form so it reflects the
    # latest intake (including a save performed in the same script run).
    saved = intake.get("search_strategy_input", {})
    with st.expander(translate("saved_strategy_header"), expanded=False):
        if saved and saved.get("query"):
            st.markdown(
                f"**{translate('saved_strategy_query')}**: "
                f"{saved.get('query', '')}"
            )
            st.markdown(
                f"**{translate('saved_strategy_databases')}**: "
                f"{', '.join(saved.get('databases', [])) or '-'}"
            )
            st.markdown(
                f"**{translate('saved_strategy_date_range')}**: "
                f"{saved.get('date_range', '-')}"
            )
        else:
            st.info(translate("saved_strategy_empty"))

    col_zotero, col_manual = st.columns(2)
    with col_zotero:
        st.markdown("##### Zotero")
        if app.settings.zotero_enabled:
            if st.button(translate("button_sync_zotero"), type="primary"):
                try:
                    client = ZoteroClient(
                        ZoteroConfig(
                            library_id=app.settings.zotero_library_id,
                            api_key=app.settings.zotero_api_key,
                            library_type=app.settings.zotero_library_type,
                        )
                    )
                    result = ZoteroSynchroniser(
                        client, app.literature_repository
                    ).sync_library(project_id=project_id, fetch_attachments=True)
                except Exception as exc:
                    st.error(translate("error_zotero_sync", error=exc))
                else:
                    st.success(
                        translate(
                            "success_zotero_sync",
                            fetched=result.fetched,
                            created=result.created,
                        )
                    )
        else:
            st.info(translate("info_zotero_config"))
    with col_manual:
        st.markdown(f"##### {translate('manual_entry_header')}")
        with st.form("manual-literature", clear_on_submit=True):
            lit_title = st.text_input(translate("field_literature_title"))
            lit_doi = st.text_input("DOI", placeholder="10.1038/...")
            if st.form_submit_button(translate("button_add_literature")):
                try:
                    app.literature_repository.create_literature_record(
                        project_id=project_id,
                        data=LiteratureInput(
                            title=lit_title, doi=lit_doi.strip() or None
                        ),
                    )
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.success(translate("success_literature_added"))

    records = app.literature_repository.list_literature_records(project_id)
    if records:
        intake["literature_record_drafts"] = [
            _literature_draft(record) for record in records
        ]
        st.dataframe(
            [
                {
                    translate("col_title"): r.title,
                    "DOI": r.doi or "",
                    translate("col_year"): r.publication_year or "",
                }
                for r in records
            ],
            use_container_width=True,
            hide_index=True,
        )
        record_labels = {r.id: r.title for r in records}
        target_id = st.selectbox(
            translate("field_pdf_record"),
            list(record_labels),
            format_func=lambda value: record_labels[value],
        )
        pdf = st.file_uploader(translate("field_import_pdf"), type=["pdf"])
        if pdf is not None and st.button(translate("button_archive_pdf")):
            import_result = app.document_importer.import_bytes(
                project_id=project_id,
                literature_record_id=target_id,
                attachment_key=pdf.name,
                pdf_bytes=pdf.getvalue(),
            )
            st.success(
                translate(
                    "success_pdf_archived",
                    hash=import_result.content_hash[:20],
                )
            )
    else:
        st.warning(translate("warning_no_literature"))

    # ---- Dataset -------------------------------------------------------
    st.markdown(f"##### {translate('tab_dataset_variables')}")
    uploaded = st.file_uploader(
        translate("field_upload_csv"), type=["csv"], key="analysis-dataset"
    )
    if uploaded is not None:
        content = uploaded.getvalue()
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        if not rows or not rows[0]:
            st.error(translate("error_empty_csv"))
        else:
            columns = rows[0]
            st.caption(
                translate(
                    "dataset_dimensions",
                    rows=len(rows) - 1,
                    columns=len(columns),
                    names=", ".join(columns),
                )
            )
            outcome_var = st.selectbox(translate("field_outcome_variable"), columns)
            exposure_var = st.selectbox(translate("field_exposure_variable"), columns)
            id_var = st.selectbox(
                translate("field_id_variable"), [translate("option_none"), *columns]
            )
            if st.button(translate("button_save_dataset"), type="primary"):
                from vet_manuscript_lab.domain.conventions import sha256_bytes

                dataset_id = str(uuid.uuid4())
                intake["dataset_summary"] = {
                    "dataset_id": dataset_id,
                    "dataset_version_id": str(uuid.uuid4()),
                    "name": uploaded.name,
                    "row_count": len(rows) - 1,
                    "variable_count": len(columns),
                    "content_hash": sha256_bytes(content),
                    "locked": False,
                }
                intake["variable_spec_drafts"] = [
                    {
                        "name": name,
                        "var_type": "continuous",
                        "role": (
                            "outcome"
                            if name == outcome_var
                            else "exposure"
                            if name == exposure_var
                            else "id"
                            if name == id_var
                            else "covariate"
                        ),
                        "unit": None,
                        "missing_code": None,
                    }
                    for name in columns
                ]
                st.success(translate("success_dataset_saved"))
    elif intake.get("dataset_summary"):
        dataset = intake["dataset_summary"]
        st.success(
            translate(
                "success_dataset_ready",
                name=dataset["name"],
                rows=dataset["row_count"],
            )
        )

    # ---- Variable spec editor (editable) --------------------------------
    var_specs = intake.get("variable_spec_drafts", [])
    if var_specs:
        import pandas as pd

        st.markdown(f"###### {translate('tab_dataset_variables')}")
        var_types = [
            translate("label_var_continuous"),
            translate("label_var_categorical"),
            translate("label_var_binary"),
            translate("label_var_ordinal"),
        ]
        _type_map = {
            "continuous": translate("label_var_continuous"),
            "categorical": translate("label_var_categorical"),
            "binary": translate("label_var_binary"),
            "ordinal": translate("label_var_ordinal"),
        }
        _type_rmap = {v: k for k, v in _type_map.items()}

        var_rows: list[dict[str, Any]] = []
        for vs in var_specs:
            var_rows.append(
                {
                    "name": vs.get("name", ""),
                    "var_type": _type_map.get(
                        vs.get("var_type", "continuous"),
                        translate("label_var_continuous"),
                    ),
                    "role": vs.get("role", "covariate"),
                    "unit": vs.get("unit") or "",
                    "missing_code": vs.get("missing_code") or "",
                }
            )
        edited = st.data_editor(
            pd.DataFrame(var_rows),
            num_rows="dynamic",
            column_config={
                "var_type": st.column_config.SelectboxColumn(
                    options=var_types,
                    required=True,
                ),
                "role": st.column_config.SelectboxColumn(
                    options=[
                        "outcome",
                        "exposure",
                        "id",
                        "covariate",
                    ],
                    required=True,
                ),
            },
            use_container_width=True,
            hide_index=True,
            key=f"var_editor_{project_id}",
        )
        if st.button(translate("button_save_variables"), type="primary"):
            updated_specs = []
            for _, r in edited.iterrows():
                updated_specs.append(
                    {
                        "name": str(r["name"]),
                        "var_type": _type_rmap.get(r["var_type"], "continuous"),
                        "role": str(r["role"]),
                        "unit": str(r["unit"]) or None,
                        "missing_code": str(r["missing_code"]) or None,
                    }
                )
            intake["variable_spec_drafts"] = updated_specs
            st.success(translate("success_question_saved"))


def _compute_intake_ready(intake: dict[str, Any]) -> bool:
    """Return *True* when all four intake requirements are satisfied."""

    return all(
        [
            bool(intake.get("research_question_input")),
            bool(intake.get("search_strategy_input")),
            bool(intake.get("literature_record_drafts")),
            bool(intake.get("dataset_summary")),
        ]
    )


def _thread_session_key(project_id: str) -> str:
    return f"thread_id:{project_id}"


def _set_active_thread(project_id: str, thread_id: str) -> None:
    st.session_state[_thread_session_key(project_id)] = thread_id
    st.session_state["thread_id"] = thread_id


def _get_active_thread(project_id: str) -> str | None:
    thread_id = st.session_state.get(_thread_session_key(project_id))
    return thread_id if isinstance(thread_id, str) else None


def _drive_pipeline_to_completion(
    app: Application, state: dict[str, Any], thread_id: str
) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    for _ in range(50):
        snapshot = app.graph.get_state(config)
        pending = _interrupt_values(snapshot)
        if not pending:
            break
        app.graph.invoke(Command(resume=_auto_resume_payload(pending[0])), config)


def _start_workflow(app: Application, project_id: str) -> None:
    thread_id = str(uuid.uuid4())
    run = app.repository.create_run(project_id, thread_id)
    state = new_workflow_state(
        project_id=project_id,
        workflow_run_id=run.id,
        thread_id=thread_id,
        now=utc_now(),
    )
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    if isinstance(intake, dict):
        cast(dict[str, Any], state).update(intake)
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    app.governance.sync_state(app.graph.get_state(config).values)
    _set_active_thread(project_id, thread_id)


# ---------------------------------------------------------------------------
# Literature + Evidence renderers
# ---------------------------------------------------------------------------


def _render_literature_records(state: dict[str, Any]) -> None:
    """Display the literature record drafts in a table with screening status."""

    records = state.get("literature_record_drafts", [])
    if not records:
        st.info(translate("info_no_literature"))
        return

    st.subheader(translate("section_literature"))

    summary = state.get("literature_summary", {})
    if summary:
        col1, col2 = st.columns(2)
        col1.metric(
            translate("label_included_count"),
            summary.get("included_count", 0),
        )
        col2.metric(
            translate("label_excluded_count"),
            summary.get("excluded_count", 0),
        )

    st.caption(translate("info_screening_hint"))

    rows = []
    for rec in records:
        decision = rec.get("screening_decision", "pending")
        if decision == "included":
            icon = "\u2705"
        elif decision == "excluded":
            icon = "\u274c"
        else:
            icon = "\u23f3"
        rows.append(
            {
                translate("col_record_id"): rec.get("record_id", "")[:12],
                translate("col_title"): rec.get("title", ""),
                translate("col_doi"): rec.get("doi", ""),
                translate("label_screening_auto"): f"{icon} {decision}",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_evidence_items(state: dict[str, Any]) -> None:
    """Display extracted evidence drafts and their source spans."""

    drafts = state.get("evidence_drafts", [])
    spans = state.get("source_span_drafts", [])
    if not drafts:
        st.info(translate("info_no_evidence"))
        return

    st.subheader(translate("section_evidence"))

    summary = state.get("evidence_summary", {})
    if summary:
        col1, col2 = st.columns(2)
        col1.metric(
            translate("label_total_evidence"),
            summary.get("total_evidence_items", 0),
        )
        col2.metric(
            translate("label_items_review"),
            summary.get("items_requiring_review", 0),
        )

    span_lookup: dict[str, dict[str, Any]] = {s["span_id"]: s for s in spans}

    rows = []
    for draft in drafts:
        first_span_id = (
            draft.get("source_span_ids", [""])[0]
            if draft.get("source_span_ids")
            else ""
        )
        span = span_lookup.get(first_span_id, {})
        rows.append(
            {
                translate("col_concept"): draft.get("concept", ""),
                translate("col_value"): str(draft.get("value", ""))[:120],
                translate("col_page"): span.get("page", ""),
                translate("col_section"): span.get("section_label", ""),
                translate("col_review"): (
                    translate("label_yes")
                    if draft.get("requires_human_review")
                    else translate("label_no")
                ),
                translate("col_status"): draft.get("extraction_status", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander(translate("section_source_spans"), expanded=False):
        span_rows = []
        for span in spans:
            span_rows.append(
                {
                    translate("col_span_id"): span.get("span_id", "")[:16],
                    translate("col_record_id"): span.get("literature_record_id", "")[
                        :12
                    ],
                    translate("col_page"): span.get("page", ""),
                    translate("col_section"): span.get("section_label", ""),
                }
            )
        if span_rows:
            st.dataframe(span_rows, use_container_width=True, hide_index=True)
        else:
            st.info(translate("info_no_evidence"))


def _render_search_strategy_detail(state: dict[str, Any]) -> None:
    """Show the search strategy artifact details when available."""

    artifacts = state.get("artifacts", {})
    strategy = artifacts.get("search_strategy")
    if strategy is None:
        return
    with st.expander(translate("gate.search_strategy.title"), expanded=False):
        st.caption(translate("gate.search_strategy.summary"))
        st.json(
            {
                "version": strategy.get("version"),
                "version_id": strategy.get("version_id"),
                "content_hash": strategy.get("content_hash"),
            }
        )


def _render_guideline_mapping(state: dict[str, Any]) -> None:
    """Display the reporting guideline mapping and protocol scope."""

    artifacts = state.get("artifacts", {})
    guideline = artifacts.get("guideline_mapping")
    protocol = artifacts.get("protocol")
    if guideline is None and protocol is None:
        return

    st.subheader(translate("section_guideline"))

    if guideline:
        guideline_type = guideline.get("guideline", "STROBE-Vet")
        st.metric(translate("label_guideline_type"), guideline_type)

    if protocol:
        col1, col2 = st.columns(2)
        endpoint = protocol.get("primary_endpoint", "-")
        eligibility = protocol.get("eligibility", "-")
        col1.metric(translate("label_primary_endpoint"), endpoint)
        col2.metric(translate("label_eligibility"), eligibility)
        status = protocol.get("status", "")
        if status:
            st.caption(f"{translate('label_manuscript_status')}: {status}")

    with st.expander(translate("expander_artifact_refs"), expanded=False):
        detail = {}
        if guideline:
            detail["guideline_mapping"] = {
                "version_id": guideline.get("version_id", ""),
                "content_hash": guideline.get("content_hash", ""),
            }
        if protocol:
            detail["protocol"] = {
                "version_id": protocol.get("version_id", ""),
                "content_hash": protocol.get("content_hash", ""),
            }
        if detail:
            st.json(detail)


def _render_methodology_findings(state: dict[str, Any]) -> None:
    """Display methodology critic findings in a table."""

    findings = state.get("methodology_findings", [])
    if not findings:
        st.info(translate("info_no_methodology"))
        return

    st.subheader(translate("section_methodology"))

    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    col1, col2 = st.columns(2)
    col1.metric(translate("label_findings_count"), len(findings))
    col2.metric(translate("label_warnings_count"), warning_count)

    rows = []
    for f in findings:
        rows.append(
            {
                translate("col_category"): f.get("category", ""),
                translate("col_severity"): f.get("severity", ""),
                translate("col_rationale"): f.get("rationale", ""),
                translate("col_recommendation"): f.get("recommendation", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_analysis_plan(state: dict[str, Any]) -> None:
    """Display analysis plan summary and variable specs."""

    plan_summary = state.get("analysis_plan_summary")
    if plan_summary is None:
        st.info(translate("info_no_analysis_plan"))
        return

    st.subheader(translate("section_analysis_plan"))

    col1, col2, col3 = st.columns(3)
    col1.metric(
        translate("label_analysis_count"),
        plan_summary.get("analysis_count", 0),
    )
    col2.metric(
        translate("label_findings_count"),
        plan_summary.get("findings_count", 0),
    )
    plan_locked = plan_summary.get("locked", False)
    col3.metric(
        translate("label_plan_locked"),
        translate("label_yes") if plan_locked else translate("label_no"),
    )

    locks = state.get("locks", {})
    dataset_locked = "dataset" in locks
    if dataset_locked:
        st.caption(translate("label_dataset_locked"))

    analyses = state.get("analysis_spec_drafts", [])
    if analyses:
        rows = []
        for a in analyses:
            rows.append(
                {
                    translate("col_analysis_name"): a.get("name", ""),
                    translate("col_estimand"): a.get("estimand", ""),
                    translate("col_method"): a.get("model_type", ""),
                    translate("col_class"): a.get("analysis_class", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_statistical_results(state: dict[str, Any]) -> None:
    """Display statistical results from the analysis run."""

    run_summary = state.get("analysis_run_summary")
    drafts = state.get("result_drafts", [])
    if not drafts and run_summary is None:
        st.info(translate("info_no_results"))
        return

    st.subheader(translate("section_results"))

    if run_summary:
        col1, col2, col3 = st.columns(3)
        col1.metric(
            translate("label_run_status"),
            run_summary.get("status", ""),
        )
        col2.metric(
            translate("label_result_count"),
            run_summary.get("result_count", 0),
        )
        col3.metric(
            translate("label_reproducible"),
            translate("label_yes")
            if run_summary.get("is_reproducible")
            else translate("label_no"),
        )

    if drafts:
        rows = []
        for d in drafts:
            lower = d.get("uncertainty_lower")
            upper = d.get("uncertainty_upper")
            ci = f"{lower} - {upper}" if lower is not None and upper is not None else ""
            rows.append(
                {
                    translate("col_analysis_name"): d.get("estimand", ""),
                    translate("col_estimate"): str(d.get("estimate", "")),
                    translate("col_ci"): ci,
                    translate("col_p_value"): str(d.get("p_value", "")),
                    translate("col_method"): d.get("method", ""),
                    translate("col_class"): d.get("analysis_class", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_effect_plots(state: dict[str, Any]) -> None:
    """Render simple bar-chart visualisations of numeric estimates."""

    drafts = state.get("result_drafts", [])
    plot_data: list[dict[str, Any]] = []
    for d in drafts:
        try:
            estimate = float(d.get("estimate", ""))
        except (TypeError, ValueError):
            continue
        lower = d.get("uncertainty_lower")
        upper = d.get("uncertainty_upper")
        ci_str = ""
        if lower is not None and upper is not None:
            try:
                ci_str = f"{float(lower):.3g} to {float(upper):.3g}"
            except (TypeError, ValueError):
                ci_str = f"{lower} to {upper}"
        plot_data.append(
            {
                translate("col_analysis_name"): d.get("estimand", ""),
                translate("col_estimate"): estimate,
                "CI": ci_str,
                translate("col_method"): d.get("method", ""),
            }
        )
    if not plot_data:
        st.info(translate("info_no_plot_data"))
        return

    st.subheader(translate("section_figures"))
    import pandas as pd

    df = pd.DataFrame(plot_data).set_index(translate("col_analysis_name"))
    st.bar_chart(df[translate("col_estimate")])
    st.dataframe(
        df.drop(columns=[translate("col_estimate")]),
        use_container_width=True,
        hide_index=True,
    )


def _render_analysis_provenance(state: dict[str, Any]) -> None:
    """Display reproducibility provenance from the analysis run artifact."""

    artifacts = state.get("artifacts", {})
    results_artifact = artifacts.get("analysis_results")
    if results_artifact is None:
        return

    payload = results_artifact.get("payload", results_artifact)
    if not isinstance(payload, dict):
        return

    st.subheader(translate("section_provenance"))

    col1, col2 = st.columns(2)
    col1.metric(
        translate("label_script_hash"),
        str(payload.get("script_hash", ""))[:20] + "...",
    )
    col2.metric(translate("label_seed"), payload.get("seed", ""))

    col3, col4 = st.columns(2)
    plan_ver = str(payload.get("plan_version_id", ""))[:20]
    col3.metric(translate("label_plan_ref"), plan_ver + "..." if plan_ver else "-")
    ds_ver = str(payload.get("dataset_version_id", ""))[:20]
    col4.metric(translate("label_dataset_ref"), ds_ver + "..." if ds_ver else "-")

    col5, col6 = st.columns(2)
    col5.metric(
        translate("label_exit_code"),
        payload.get("exit_code", "-"),
    )
    env = payload.get("environment", "-")
    col6.metric(translate("label_environment"), str(env)[:40])

    package_versions = payload.get("package_versions", {})
    if package_versions:
        with st.expander(translate("label_package_versions"), expanded=False):
            if isinstance(package_versions, dict):
                pv_rows = [
                    {"Package": k, "Version": v} for k, v in package_versions.items()
                ]
                st.dataframe(pv_rows, use_container_width=True, hide_index=True)
            else:
                st.write(package_versions)

    stdout = payload.get("stdout", "")
    stderr = payload.get("stderr", "")
    if stdout or stderr:
        with st.expander(translate("label_stdout"), expanded=False):
            st.code(stdout, language="text")
        if stderr:
            with st.expander(translate("label_stderr"), expanded=False):
                st.code(stderr, language="text")


def _render_usage_summary(state: dict[str, Any]) -> None:
    """Display AI model usage and cost breakdown if available."""

    usage = state.get("ai_usage")
    if not usage:
        return

    st.subheader(translate("section_usage"))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        translate("label_total_invocations"),
        usage.get("total_invocations", 0),
    )
    col2.metric(
        translate("label_total_cost"),
        f"${usage.get('total_cost_cents', 0) / 100:.2f}",
    )
    col3.metric(
        translate("label_input_tokens"),
        usage.get("total_input_tokens", 0),
    )
    col4.metric(
        translate("label_output_tokens"),
        usage.get("total_output_tokens", 0),
    )

    fallback = usage.get("fallback_count", 0)
    failure = usage.get("failure_count", 0)
    if fallback or failure:
        st.caption(
            f"{translate('label_fallbacks')}: {fallback} | "
            f"{translate('label_failures')}: {failure}"
        )

    cost_by_stage = usage.get("cost_by_stage", {})
    if cost_by_stage:
        stage_rows = []
        for task_kind, data in cost_by_stage.items():
            if task_kind == "__total__":
                continue
            stage_rows.append(
                {
                    translate("col_task_kind"): task_kind,
                    translate("col_invocations"): data.get("invocations", 0),
                    translate("col_cost_cents"): (
                        f"${data.get('cost_cents', 0) / 100:.2f}"
                    ),
                    translate("col_tokens"): (
                        data.get("input_tokens", 0) + data.get("output_tokens", 0)
                    ),
                }
            )
        if stage_rows:
            st.dataframe(stage_rows, use_container_width=True, hide_index=True)


def _auto_resume_payload(interrupt: dict[str, Any]) -> dict[str, Any]:
    """Build a resume payload matching the interrupt's gate type.

    The compliance pipeline has three interrupt shapes:
    - Standard approval gates (question/protocol/search/analysis_plan/results):
      ``{decision, reviewer_id, reviewer_role}``
    - Review disposition gate: ``{reviewer_id, reviewer_role, decisions: [...]}``
    - Final sign-off gate: ``{decision, authoriser_id, authoriser_role}``
    """

    gate = interrupt.get("gate", "")
    if gate == "review":
        findings = interrupt.get("findings", [])
        decisions = [
            {"finding_id": f.get("finding_id", ""), "decision": "reject"}
            for f in findings
        ]
        return {
            "reviewer_id": "golden-demo",
            "reviewer_role": "reviewer",
            "decisions": decisions,
        }
    if gate == "final_sign_off":
        return {
            "decision": "approved",
            "authoriser_id": "golden-demo-pi",
            "authoriser_role": "principal_investigator",
            "reason": "Auto-approved for golden project demo",
        }
    # Standard approval gate
    return {
        "decision": "approved",
        "reviewer_id": "golden-demo",
        "reviewer_role": "investigator",
    }


def _fixture_to_literature_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture literature records to WorkflowState drafts."""

    records = fixture.get("literature", {}).get("records", [])
    return [
        {
            "record_id": rec.get("literature_id", ""),
            "title": rec.get("title", ""),
            "doi": rec.get("doi"),
            "pmid": None,
            "journal": rec.get("journal"),
            "publication_year": rec.get("year"),
        }
        for rec in records
    ]


def _fixture_to_variable_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture variables to WorkflowState drafts."""

    return list(fixture.get("dictionary", {}).get("variables", []))


def _fixture_to_analysis_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture analyses to WorkflowState drafts."""

    return list(fixture.get("analysis_plan", {}).get("plan", {}).get("analyses", []))


def _fixture_to_methodology_findings(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture methodology findings to WorkflowState entries."""

    return list(fixture.get("methodology", {}).get("findings", []))


def _golden_research_question(fixture: dict[str, Any]) -> dict[str, str]:
    rq = fixture.get("project", {}).get("research_question", {})
    return {
        "objective": (
            "Assess the association between synthetic treatment A and overall "
            "survival in a retrospective canine/feline referral cohort."
        ),
        "population": rq.get("population", ""),
        "exposure": rq.get("exposure", ""),
        "comparator": rq.get("comparator", ""),
        "outcome": rq.get("outcome", ""),
        "hypothesis": (
            "Synthetic treatment A is associated with improved overall survival "
            "after adjusting for age and species."
        ),
    }


def _golden_search_strategy() -> dict[str, Any]:
    return {
        "query": (
            '(veterinary OR canine OR feline) AND (survival OR "time-to-event") '
            "AND (retrospective OR observational) AND (treatment OR exposure)"
        ),
        "databases": ["PubMed", "CAB Abstracts", "Web of Science"],
        "date_range": "2021-01-01/2026-12-31",
    }


def _golden_dataset_summary(fixture: dict[str, Any]) -> dict[str, Any]:
    from vet_manuscript_lab.domain.conventions import sha256_bytes

    dictionary = fixture.get("dictionary", {})
    dataset = dictionary.get("dataset", {})
    csv_bytes = (GOLDEN_FIXTURE_ROOT / "data" / "cases_synthetic.csv").read_bytes()
    return {
        "dataset_id": "golden-dataset",
        "dataset_version_id": "golden-dataset-v1",
        "name": dataset.get("name", "Golden Project dataset"),
        "row_count": dataset.get("row_count", 0),
        "variable_count": dataset.get("column_count", 0),
        "content_hash": sha256_bytes(csv_bytes),
        "locked": False,
    }


def _build_golden_workspace_intake(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "research_question_input": _golden_research_question(fixture),
        "search_strategy_input": _golden_search_strategy(),
        "literature_record_drafts": _fixture_to_literature_drafts(fixture),
        "dataset_summary": _golden_dataset_summary(fixture),
        "variable_spec_drafts": _fixture_to_variable_drafts(fixture),
        "analysis_spec_drafts": _fixture_to_analysis_drafts(fixture),
        "methodology_findings": _fixture_to_methodology_findings(fixture),
    }


def _ensure_golden_workspace_project(app: Application, fixture: dict[str, Any]) -> str:
    project_meta = fixture.get("project", {}).get("project", {})
    title = str(project_meta.get("title", "Golden Project")).strip()
    for project in app.repository.list_projects():
        if project.title == title:
            return project.id

    project = app.repository.create_project(
        ProjectInput(
            title=title,
            study_type=str(
                project_meta.get(
                    "study_type", "retrospective_observational_clinical_study"
                )
            ),
            species_scope=list(project_meta.get("species_scope", ["canine", "feline"])),
            owner_id="golden-demo",
        )
    )
    return project.id


def _seed_golden_literature_records(
    app: Application, project_id: str, fixture: dict[str, Any]
) -> None:
    for record in fixture.get("literature", {}).get("records", []):
        doi = record.get("doi")
        if (
            isinstance(doi, str)
            and doi
            and app.literature_repository.find_by_doi(project_id, doi)
        ):
            continue
        app.literature_repository.create_literature_record(
            project_id=project_id,
            data=LiteratureInput(
                title=str(record.get("title", "")),
                doi=doi if isinstance(doi, str) and doi else None,
                publication_year=record.get("year"),
                journal=record.get("journal"),
                creators=[{"name": author} for author in record.get("authors", [])],
                metadata_json={
                    "tags": record.get("tags", []),
                    "abstract": record.get("abstract", ""),
                    "fixture": "golden_project",
                },
            ),
        )


def _prepare_golden_workspace(app: Application) -> str:
    fixture = _load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = _ensure_golden_workspace_project(app, fixture)
    _seed_golden_literature_records(app, project_id, fixture)
    st.session_state[f"analysis_intake:{project_id}"] = _build_golden_workspace_intake(
        fixture
    )
    st.session_state["project_id"] = project_id
    st.session_state.pop(_thread_session_key(project_id), None)
    st.session_state.pop("thread_id", None)
    # Force the search-strategy form to reinitialize from the freshly loaded
    # Golden inputs (otherwise Streamlit widget stickiness keeps old values).
    _bump_search_form_version(project_id)
    return project_id


def _run_golden_workspace_pipeline(app: Application) -> tuple[str, str]:
    fixture = _load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = _ensure_golden_workspace_project(app, fixture)
    _seed_golden_literature_records(app, project_id, fixture)
    intake = _build_golden_workspace_intake(fixture)
    st.session_state[f"analysis_intake:{project_id}"] = intake
    st.session_state["project_id"] = project_id

    thread_id = f"golden-workspace-{uuid.uuid4().hex[:8]}"
    run = app.repository.create_run(project_id, thread_id)
    state = new_workflow_state(
        project_id=project_id,
        workflow_run_id=run.id,
        thread_id=thread_id,
        now=utc_now(),
        species_scope=list(
            fixture.get("project", {})
            .get("project", {})
            .get("species_scope", ["canine", "feline"])
        ),
    )
    cast(dict[str, Any], state).update(intake)
    _drive_pipeline_to_completion(
        app, cast(dict[str, Any], state), thread_id
    )
    _set_active_thread(project_id, thread_id)
    return project_id, thread_id


def _render_manuscript(state: dict[str, Any]) -> None:
    """Display manuscript sections with word counts and content."""

    summary = state.get("manuscript_summary")
    sections = state.get("section_drafts", [])
    if not summary and not sections:
        st.info(translate("info_no_manuscript"))
        return

    st.subheader(translate("section_manuscript"))

    if summary:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            translate("label_manuscript_version"),
            summary.get("version", 1),
        )
        col2.metric(translate("label_section_count"), summary.get("section_count", 0))
        col3.metric(translate("label_claim_count"), summary.get("claim_count", 0))
        status = summary.get("status", "")
        col4.metric(translate("label_manuscript_status"), status)

    total_words = sum(s.get("word_count", 0) for s in sections)
    if total_words:
        st.caption(f"{translate('label_word_count')}: {total_words}")

    # Build a section → claims lookup for evidence highlighting
    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    support_by_claim: dict[str, int] = {}
    for sp in supports:
        cid = sp.get("claim_id", "")
        support_by_claim[cid] = support_by_claim.get(cid, 0) + 1

    claims_by_section: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        sid = c.get("section_id", "")
        claims_by_section.setdefault(sid, []).append(c)

    for section in sorted(sections, key=lambda s: s.get("order", 0)):
        stype = section.get("section_type", "section")
        content = section.get("content", "")
        sid = section.get("section_id", "")
        section_claims = claims_by_section.get(sid, [])
        header = stype.title()
        if section_claims:
            header += f" ({len(section_claims)} {translate('label_claim_bound')})"
        with st.expander(header, expanded=False):
            st.write(content)
            if section_claims:
                st.markdown(f"**{translate('label_claim_bound')}:**")
                badges = []
                for c in section_claims:
                    cid = c.get("claim_id", "")
                    ctype = c.get("claim_type", "")
                    count = support_by_claim.get(cid, 0)
                    if ctype == "hypothesis":
                        status_label = translate("label_claim_status_hypothesis")
                        icon = "\U0001f914"
                    elif count > 0:
                        status_label = translate("label_claim_status_supported")
                        icon = "\u2705"
                    else:
                        status_label = translate("label_claim_status_unsupported")
                        icon = "\u26a0\ufe0f"
                    text_preview = c.get("text", "")[:80]
                    badges.append(f"{icon} {status_label}: {text_preview}")
                for badge in badges:
                    st.markdown(f"- {badge}")


def _render_claims(state: dict[str, Any]) -> None:
    """Display manuscript claims with support linkage."""

    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    if not claims:
        st.info(translate("info_no_claims"))
        return

    st.subheader(translate("section_claims"))

    support_counts: dict[str, int] = {}
    for s in supports:
        cid = s.get("claim_id", "")
        support_counts[cid] = support_counts.get(cid, 0) + 1

    rows = []
    for c in claims:
        cid = c.get("claim_id", "")
        count = support_counts.get(cid, 0)
        rows.append(
            {
                translate("col_claim_type"): c.get("claim_type", ""),
                translate("col_claim_text"): c.get("text", "")[:200],
                translate("col_certainty"): c.get("certainty", ""),
                translate("col_has_support"): (
                    translate("label_yes") if count else translate("label_no")
                ),
                translate("col_support_count"): count,
                translate("col_ref_numbers"): str(c.get("referenced_numbers", [])),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_citations(state: dict[str, Any]) -> None:
    """Display citation drafts linking claims to literature records."""

    citations = state.get("citation_drafts", [])
    if not citations:
        st.info(translate("info_no_citations"))
        return

    st.subheader(translate("section_citations"))
    rows = []
    for c in citations:
        rows.append(
            {
                translate("col_citation_key"): c.get("citation_key", ""),
                translate("col_lit_record"): c.get("literature_record_id", "")[:16],
                translate("col_section"): c.get("section_id", "")[:24],
                translate("col_claim_type"): c.get("claim_id", "")[:24],
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_claim_audit(state: dict[str, Any]) -> None:
    """Display claim audit results (factual support, numeric consistency, etc.)."""

    artifacts = state.get("artifacts", {})
    audit = artifacts.get("claim_audit")
    if audit is None:
        st.info(translate("info_no_claim_audit"))
        return

    st.subheader(translate("section_claim_audit"))

    status = audit.get("status", "")
    col1, col2 = st.columns(2)
    col1.metric(
        translate("label_audit_passed"),
        translate("label_yes") if "passed" in status else translate("label_no"),
    )
    col2.metric(
        translate("label_audit_errors"),
        "0" if "passed" in status else ">0",
    )
    st.caption(f"status: {status}")


def _render_review(state: dict[str, Any]) -> None:
    """Display reviewer critique findings and revision decisions."""

    findings = state.get("review_findings", [])
    decisions = state.get("revision_decisions", [])
    revision_summary = state.get("revision_summary")
    if not findings and not revision_summary:
        st.info(translate("info_no_review"))
        return

    st.subheader(translate("section_review"))

    if findings:
        decision_map = {  # noqa: F841
            d.get("finding_id", ""): d.get("decision", "") for d in decisions
        }
        rows = []
        for f in findings:
            rows.append(
                {
                    translate("col_category"): f.get("category", ""),
                    translate("col_severity"): f.get("severity", ""),
                    translate("col_location"): f.get("location", ""),
                    translate("col_rationale"): f.get("rationale", ""),
                    translate("col_recommendation"): f.get("recommendation", ""),
                    translate("col_status"): f.get("status", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if revision_summary:
        with st.expander(translate("section_revision"), expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                translate("label_revision_round"),
                revision_summary.get("round", 0),
            )
            col2.metric(
                translate("label_accepted"),
                revision_summary.get("accepted_count", 0),
            )
            col3.metric(
                translate("label_rejected"),
                revision_summary.get("rejected_count", 0),
            )
            col4.metric(
                translate("label_deferred"),
                revision_summary.get("deferred_count", 0),
            )


def _render_revision_diff(state: dict[str, Any]) -> None:
    """Display section-level before/after diff from the latest revision round."""

    import difflib

    revision_summary = state.get("revision_summary")
    if revision_summary is None:
        return

    diffs = revision_summary.get("section_diffs", [])
    if not diffs:
        return

    st.subheader(translate("section_revision_diff"))

    for d in diffs:
        section_id = d.get("section_id", "")
        before = d.get("before_content", "")
        after = d.get("after_content", "")
        resolved = d.get("resolved_finding_ids", [])

        if before == after:
            continue

        with st.expander(section_id, expanded=False):
            if resolved:
                st.caption(
                    f"{translate('label_resolved_findings')}: {', '.join(resolved)}"
                )

            col_before, col_after = st.columns(2)
            with col_before:
                st.markdown(f"**{translate('col_before')}**")
                if before:
                    before_lines = before.splitlines(keepends=False)
                    after_lines = after.splitlines(keepends=False)
                    diff = difflib.unified_diff(
                        before_lines,
                        after_lines,
                        lineterm="",
                        n=1,
                    )
                    diff_text = "\n".join(diff)
                    if diff_text.strip():
                        st.code(diff_text, language="diff")
                    else:
                        st.write(before)
                else:
                    st.caption(translate("label_no_changes"))

            with col_after:
                st.markdown(f"**{translate('col_after')}**")
                st.write(after)


def _render_claim_traceability(state: dict[str, Any]) -> None:
    """Display interactive claim → evidence / result / citation traceability chain."""

    claims = state.get("claim_drafts", [])
    if not claims:
        return

    supports = state.get("support_drafts", [])
    evidence = state.get("evidence_drafts", [])
    results = state.get("result_drafts", [])
    spans = state.get("source_span_drafts", [])
    records = state.get("literature_record_drafts", [])
    citations = state.get("citation_drafts", [])

    # Build lookup indexes
    support_by_claim: dict[str, list[dict[str, Any]]] = {}
    for s in supports:
        cid = s.get("claim_id", "")
        support_by_claim.setdefault(cid, []).append(s)

    evidence_by_id: dict[str, dict[str, Any]] = {
        e.get("evidence_id", ""): e for e in evidence
    }
    result_by_id: dict[str, dict[str, Any]] = {
        r.get("result_id", ""): r for r in results
    }
    span_by_id: dict[str, dict[str, Any]] = {s.get("span_id", ""): s for s in spans}
    record_by_id: dict[str, dict[str, Any]] = {
        r.get("record_id", ""): r for r in records
    }
    citation_by_claim: dict[str, list[dict[str, Any]]] = {}
    for c in citations:
        cid = c.get("claim_id", "")
        if cid:
            citation_by_claim.setdefault(cid, []).append(c)

    st.subheader(translate("section_traceability"))

    for c in claims:
        cid = c.get("claim_id", "")
        ctype = c.get("claim_type", "")
        text = c.get("text", "")
        certainty = c.get("certainty", "")
        section_id = c.get("section_id", "")

        claim_supports = support_by_claim.get(cid, [])
        has_support = len(claim_supports) > 0
        is_factual = ctype in ("factual", "result", "statistical")

        header = f"`{cid}` [{ctype}]"
        if not has_support and is_factual:
            header += " \u26a0\ufe0f"

        with st.expander(header, expanded=False):
            st.write(text)
            st.caption(
                f"{translate('col_certainty')}: {certainty} "
                f"| {translate('col_section_type')}: {section_id}"
            )

            if not has_support and is_factual:
                st.warning(translate("label_claim_unsupported_warning"))

            # --- Supports ---
            if claim_supports:
                for _idx, s in enumerate(claim_supports, 1):
                    stype = s.get("support_type", "")
                    source_id = s.get("source_id", "")
                    relation = s.get("relation", "")
                    audit_status = s.get("audit_status", "")

                    st.markdown(
                        f"**{translate('label_support_type')}:** {stype} "
                        f"| **{translate('label_relation')}:** {relation} "
                        f"| **{translate('label_audit_status')}:** "
                        f"{audit_status}"
                    )

                    if stype == "evidence_item":
                        ev = evidence_by_id.get(source_id, {})
                        if ev:
                            concept = ev.get("concept", "")
                            value = ev.get("value", "")
                            st.markdown(
                                f"  - **{translate('col_concept')}:** {concept}"
                            )
                            st.markdown(f"  - **{translate('col_value')}:** {value}")
                            if ev.get("units"):
                                units = ev.get("units")
                                st.markdown(f"  - {translate('col_unit')}: {units}")
                            if ev.get("population"):
                                pop = ev.get("population")
                                st.markdown(f"  - {translate('col_population')}: {pop}")
                            # Source spans
                            span_ids = ev.get("source_span_ids", [])
                            for sid in span_ids:
                                span = span_by_id.get(sid, {})
                                if span:
                                    rec_id = span.get("literature_record_id", "")
                                    rec = record_by_id.get(rec_id, {})
                                    st.markdown(
                                        f"  - {translate('label_span_page')}: "
                                        f"{span.get('page', '')} "
                                        f"| {translate('label_span_section')}: "
                                        f"{span.get('section_label', '')}"
                                    )
                                    if rec:
                                        st.markdown(
                                            f"  - {translate('col_title')}: "
                                            f"{rec.get('title', '')} "
                                            f"| DOI: {rec.get('doi', '') or '-'}"
                                        )
                                    if span.get("quote_hash"):
                                        st.caption(
                                            f"{translate('label_quote_hash')}: "
                                            f"{str(span.get('quote_hash', ''))[:24]}..."
                                        )

                    elif stype == "statistical_result":
                        res = result_by_id.get(source_id, {})
                        if res:
                            lower = res.get("uncertainty_lower")
                            upper = res.get("uncertainty_upper")
                            ci_str = (
                                f"{lower} - {upper}"
                                if lower is not None and upper is not None
                                else ""
                            )
                            st.markdown(
                                f"  - **{translate('col_estimate')}:** "
                                f"{res.get('estimate', '')}"
                            )
                            if ci_str:
                                st.markdown(f"  - **{translate('col_ci')}:** {ci_str}")
                            st.markdown(
                                f"  - **{translate('col_p_value')}:** "
                                f"{res.get('p_value', '')}"
                            )
                            st.markdown(
                                f"  - **{translate('col_method')}:** "
                                f"{res.get('method', '')}"
                            )
                    st.markdown("---")

            # --- Citations ---
            claim_citations = citation_by_claim.get(cid, [])
            if claim_citations:
                for cit in claim_citations:
                    rec_id = cit.get("literature_record_id", "")
                    rec = record_by_id.get(rec_id, {})
                    locator = cit.get("locator", "")
                    st.markdown(
                        f"**{translate('col_citation_key')}:** "
                        f"{cit.get('citation_key', '')}"
                    )
                    if rec:
                        st.markdown(
                            f"  - {translate('col_title')}: {rec.get('title', '')}"
                        )
                        st.markdown(f"  - DOI: {rec.get('doi', '') or '-'}")
                    if locator:
                        st.markdown(
                            f"  - {translate('label_citation_locator')}: {locator}"
                        )


def _render_compliance(state: dict[str, Any]) -> None:
    """Display STROBE-Vet compliance audit findings and checklist summary."""

    findings = state.get("compliance_findings", [])
    checklist = state.get("checklist_summary")
    readiness = state.get("export_readiness")
    if not findings and checklist is None:
        st.info(translate("info_no_compliance"))
        return

    st.subheader(translate("section_compliance"))

    if readiness:
        st.metric(translate("label_export_readiness"), readiness)

    if checklist:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(translate("label_passed"), checklist.get("passed", 0))
        col2.metric(translate("label_failed"), checklist.get("failed", 0))
        col3.metric(
            translate("label_not_applicable"),
            checklist.get("not_applicable", 0),
        )
        col4.metric(translate("label_needs_review"), checklist.get("needs_review", 0))

    if findings:
        rows = []
        for f in findings:
            rows.append(
                {
                    translate("col_rule_id"): f.get("rule_id", ""),
                    translate("col_category"): f.get("category", ""),
                    translate("col_severity"): f.get("severity", ""),
                    translate("col_status"): f.get("status", ""),
                    translate("col_evidence"): f.get("evidence", ""),
                    translate("col_recommendation"): f.get("recommendation", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


@st.cache_data(show_spinner=False)
def _regenerate_export_package(_state_hash: str) -> tuple[Any, ...] | None:
    """Placeholder kept for potential future caching; current implementation
    regenerates inline in ``_render_export`` to access live state.
    """

    return None


def _render_export(state: dict[str, Any]) -> None:
    """Display export package summary with download buttons for components."""

    package = state.get("export_package")
    if package is None:
        st.info(translate("info_no_export"))
        return

    st.subheader(translate("section_export"))

    col1, col2 = st.columns(2)
    col1.metric(translate("col_components"), package.get("component_count", 0))
    col2.metric(
        translate("label_manuscript_status"),
        package.get("status", ""),
    )
    st.caption(f"{translate('col_package_uri')}: `{package.get('package_uri', '')}`")

    # Regenerate components for download from current state
    from vet_manuscript_lab.services.export import (
        ExportInput,
        MockExportGenerator,
        create_docx_renderer,
    )

    sections = tuple(dict(s) for s in state.get("section_drafts", []))
    citations = tuple(dict(c) for c in state.get("citation_drafts", []))
    results = tuple(dict(r) for r in state.get("result_drafts", []))
    literature = tuple(dict(r) for r in state.get("literature_record_drafts", []))
    analysis_plan = dict(state.get("analysis_plan_summary") or {})
    ai_usage = dict(state.get("ai_usage") or {})
    manuscript = dict(state.get("manuscript_summary") or {})
    sign_off = dict(state.get("approvals", {}).get("final_sign_off", {}))
    sign_off["approval_id"] = (
        state.get("sign_off_binding", {}).get("approval_id", "")
        if state.get("sign_off_binding")
        else ""
    )

    try:
        renderer = create_docx_renderer()
        generator = MockExportGenerator(docx_renderer=renderer)
        export_result = generator.generate(
            ExportInput(
                sections=sections,
                citations=citations,
                results=results,
                literature_records=literature,
                analysis_plan_summary=analysis_plan,
                ai_usage=ai_usage,
                sign_off_approval=sign_off,
                manuscript_summary=manuscript,
            )
        )
    except Exception as exc:
        st.error(f"{translate('label_regenerating')} {exc}")
        return

    # Download buttons for each component
    import base64

    dl_cols = st.columns(min(len(export_result.components), 5))
    for i, comp in enumerate(export_result.components):
        col = dl_cols[i % len(dl_cols)]
        label_key = {
            "manuscript": "label_download_qmd",
            "references": "label_download_bib",
            "manifest": "label_download_manifest",
            "docx": "label_download_docx",
        }.get(comp.role, "col_filename")
        label = translate(label_key) if label_key != "col_filename" else comp.filename

        # DOCX content is base64; other components are plain text
        is_binary = comp.media_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        )
        if is_binary:
            try:
                data = base64.b64decode(comp.content)
                col.download_button(
                    label,
                    data=data,
                    file_name=comp.filename,
                    mime=comp.media_type,
                    key=f"dl-{comp.role}",
                )
            except Exception:
                col.download_button(
                    label,
                    data=comp.content.encode(),
                    file_name=comp.filename,
                    mime="text/plain",
                    key=f"dl-{comp.role}-fallback",
                )
        else:
            col.download_button(
                label,
                data=comp.content.encode("utf-8"),
                file_name=comp.filename,
                mime=comp.media_type,
                key=f"dl-{comp.role}",
            )

    # Component table
    comp_rows = []
    for comp in export_result.components:
        comp_rows.append(
            {
                translate("col_filename"): comp.filename,
                translate("col_media_type"): comp.media_type,
                translate("col_task_kind"): comp.role,
            }
        )
    if comp_rows:
        st.dataframe(comp_rows, use_container_width=True, hide_index=True)


def _render_ai_disclosure(state: dict[str, Any]) -> None:
    """Render a formatted AI-usage disclosure block suitable for inclusion
    in the supplementary materials of the manuscript."""

    usage = state.get("ai_usage")
    if not usage:
        st.info(translate("info_no_ai_usage"))
        return

    st.subheader(translate("section_ai_disclosure"))

    total_invocations = usage.get("total_invocations", 0)
    total_cost = usage.get("total_cost_cents", 0)
    total_input_tokens = usage.get("total_input_tokens", 0)
    total_output_tokens = usage.get("total_output_tokens", 0)
    fallback = usage.get("fallback_count", 0)
    failure = usage.get("failure_count", 0)

    # Summary metrics
    col1, col2 = st.columns(2)
    col1.metric(translate("label_total_invocations"), total_invocations)
    col2.metric(
        translate("label_total_cost"),
        f"${total_cost / 100:.2f}",
    )

    # Formatted disclosure text (preview)
    lines = [
        "# AI Usage Disclosure",
        "",
        (
            "This manuscript was prepared with assistance from "
            "AI-based language models during the drafting, review, and "
            "revision phases."
        ),
        "",
        "## Summary of Model Usage",
        f"- Total model invocations: {total_invocations}",
        f"- Total estimated cost: ${total_cost / 100:.2f} USD",
        f"- Input tokens consumed: {total_input_tokens:,}",
        f"- Output tokens consumed: {total_output_tokens:,}",
    ]
    if fallback or failure:
        lines.append("")
        lines.append("## Fallbacks and Failures")
        lines.append(f"- Fallback invocations: {fallback}")
        lines.append(f"- Failed invocations: {failure}")

    cost_by_stage = usage.get("cost_by_stage", {})
    if cost_by_stage:
        lines.append("")
        lines.append("## Breakdown by Task")
        lines.append(
            f"| {translate('col_task_kind')} | "
            f"{translate('col_invocations')} | "
            f"{translate('label_total_cost')} |"
        )
        lines.append("|---|---|---|")
        for task_kind, data in cost_by_stage.items():
            if task_kind == "__total__":
                continue
            invocations = data.get("invocations", 0)
            cost_cents = data.get("cost_cents", 0)
            lines.append(f"| {task_kind} | {invocations} | ${cost_cents / 100:.2f} |")

    lines.append("")
    lines.append(
        "All AI-assisted content was reviewed and validated by the "
        "authors prior to publication."
    )

    disclosure_text = "\n".join(lines)
    with st.expander(translate("section_ai_disclosure"), expanded=False):
        st.code(disclosure_text, language="markdown")
    st.download_button(
        translate("label_download_manifest"),
        data=disclosure_text.encode("utf-8"),
        file_name="ai_usage_disclosure.md",
        mime="text/markdown",
    )


def _render_workspace_actions(app: Application) -> None:
    notice = st.session_state.pop("golden_workspace_notice", None)
    if isinstance(notice, str):
        st.success(notice)

    st.subheader(translate("workspace_actions_header"))
    st.caption(translate("workspace_actions_caption"))
    col_load, col_run = st.columns(2)
    load_clicked = col_load.button(
        translate("golden_workspace_load"), use_container_width=True
    )
    run_clicked = col_run.button(
        translate("golden_workspace_run"),
        type="primary",
        use_container_width=True,
    )

    if load_clicked:
        try:
            with st.spinner(translate("golden_workspace_loading")):
                project_id = _prepare_golden_workspace(app)
        except (OSError, ValueError) as exc:
            st.error(translate("golden_demo_load_error", error=str(exc)))
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_loaded", id=project_id[:8]
            )
            st.rerun()

    if run_clicked:
        try:
            with st.spinner(translate("golden_workspace_running")):
                project_id, _thread_id = _run_golden_workspace_pipeline(app)
        except (OSError, ValueError) as exc:
            st.error(translate("golden_demo_load_error", error=str(exc)))
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_finished", id=project_id[:8]
            )
            st.rerun()


def _render_review_disposition(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    """Render the per-finding review disposition form.

    Each review finding gets its own accept / reject / defer control.
    Accepted findings trigger a revision cycle; all-rejected proceeds
    to the final compliance audit.
    """

    findings = gate.get("findings", [])
    if not findings:
        st.info(translate("review_no_findings"))
        return

    st.subheader(translate("review_disposition_header"))
    st.caption(translate("review_disposition_caption"))

    role_options = ["reviewer", "investigator"]
    required_role = gate.get("required_reviewer_role", "reviewer")
    default_index = (
        role_options.index(required_role) if required_role in role_options else 0
    )

    decision_options = ["accept", "reject", "defer"]
    decision_labels = {d: translate(f"decision_{d}") for d in decision_options}

    decisions: list[dict[str, str]] = []

    with st.form("review_disposition_form"):
        col_id, col_role = st.columns(2)
        reviewer_id = col_id.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "Mona"),
        )
        reviewer_role = col_role.selectbox(
            translate("field_reviewer_role"),
            role_options,
            index=default_index,
            format_func=lambda role: translate(f"role_{role}"),
        )

        st.divider()
        for f in findings:
            fid = f.get("finding_id", "")
            with st.container(border=True):
                sev = f.get("severity", "")
                cat = f.get("category", "")
                loc = f.get("location", "")
                st.markdown(
                    f"**{translate('label_finding_id')}:** `{fid}` "
                    f"| **{translate('col_severity')}:** {sev} "
                    f"| **{translate('col_category')}:** {cat}"
                )
                if loc:
                    st.caption(f"{translate('col_location')}: {loc}")
                st.write(f.get("rationale", ""))
                rec = f.get("recommendation", "")
                if rec:
                    st.info(rec)

                choice = st.radio(
                    translate("field_decision"),
                    decision_options,
                    format_func=lambda d: decision_labels[d],
                    horizontal=True,
                    key=f"rev_decision_{fid}",
                )
                reason = st.text_input(
                    translate("field_finding_reason"),
                    key=f"rev_reason_{fid}",
                )
                decisions.append(
                    {
                        "finding_id": fid,
                        "decision": choice,
                        "reason": reason,
                    }
                )

        submitted = st.form_submit_button(
            translate("button_submit_review"),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state["default_reviewer_id"] = reviewer_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "reviewer_id": reviewer_id,
                        "reviewer_role": reviewer_role,
                        "decisions": decisions,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def _render_sign_off_approval(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    """Render the final sign-off form with authoriser identity."""

    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    st.subheader(translate("pending_action_header"))
    st.caption(
        translate(
            "pending_action_caption",
            stage=stage_label("final_sign_off"),
        )
    )
    st.caption(gate.get("summary", ""))

    role_options = ["principal_investigator", "corresponding_author"]
    with st.form("approval_final_sign_off"):
        col_id, col_role = st.columns(2)
        authoriser_id = col_id.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "PI"),
        )
        authoriser_role = col_role.selectbox(
            translate("field_reviewer_role"),
            role_options,
            format_func=lambda r: translate(f"role_{r}"),
        )
        decision = st.selectbox(
            translate("field_decision"),
            ["approved", "rejected"],
            format_func=lambda v: translate(f"decision.{v}"),
        )
        reason = st.text_area(translate("field_comment"))
        submitted = st.form_submit_button(
            translate("button_submit_decision"),
            type="primary",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        st.session_state["default_reviewer_id"] = authoriser_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "decision": decision,
                        "authoriser_id": authoriser_id,
                        "authoriser_role": authoriser_role,
                        "reason": reason,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def _render_pending_approval(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    gate_name = gate.get("gate", "")

    # Dispatch based on gate type
    if gate_name == "review":
        _render_review_disposition(app, config, gate)
        return
    if gate_name == "final_sign_off":
        _render_sign_off_approval(app, config, gate)
        return

    # Standard approval gates (question / protocol / search_strategy /
    # analysis_plan / results_interpretation)
    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    st.subheader(translate("pending_action_header"))
    st.caption(translate("pending_action_caption", stage=stage_label(gate_name)))
    st.write(
        {
            translate("pending_action_gate"): gate_field(gate_name, "title"),
            translate("pending_action_next"): stage_label(
                gate.get("proposed_next_stage")
            ),
        }
    )
    st.caption(gate_field(gate_name, "summary"))

    role_options = ["investigator", "statistician"]
    required_role = gate.get("required_reviewer_role", "investigator")
    default_index = (
        role_options.index(required_role) if required_role in role_options else 0
    )
    with st.form(f"approval_{gate_name}"):
        reviewer_id = st.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "Mona"),
        )
        reviewer_role = st.selectbox(
            translate("field_reviewer_role"),
            role_options,
            index=default_index,
            format_func=lambda role: translate(f"role_{role}"),
        )
        decision = st.selectbox(
            translate("field_decision"),
            gate["allowed_decisions"],
            format_func=lambda value: translate(f"decision.{value}"),
        )
        comment = st.text_area(translate("field_comment"))
        submitted = st.form_submit_button(
            translate("button_submit_decision"),
            type="primary",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        st.session_state["default_reviewer_id"] = reviewer_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "decision": decision,
                        "reviewer_id": reviewer_id,
                        "reviewer_role": reviewer_role,
                        "comment": comment,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def _render_approval_timeline(state: dict[str, Any]) -> None:
    """Render a chronological timeline of approvals and locks."""

    approvals = state.get("approvals", {})
    locks = state.get("locks", {})
    if not approvals and not locks:
        return

    st.subheader(translate("section_timeline"))

    events: list[dict[str, Any]] = []

    for gate_key, ap in approvals.items():
        events.append(
            {
                "sort_key": ap.get("decided_at", ""),
                translate("col_event_type"): translate("col_decision"),
                translate("col_gate"): stage_label(gate_key),
                translate("col_decision"): ap.get("decision", ""),
                translate("col_reviewer"): (
                    f"{ap.get('reviewer_id', '')} ({ap.get('reviewer_role', '')})"
                ),
                translate("col_decided_at"): ap.get("decided_at", ""),
                translate("col_message"): ap.get("comment", ""),
            }
        )

    for lock_key, lk in locks.items():
        events.append(
            {
                "sort_key": lk.get("locked_at", ""),
                translate("col_event_type"): translate("col_lock_type"),
                translate("col_gate"): lk.get("lock_type", lock_key),
                translate("col_decision"): "locked",
                translate("col_reviewer"): lk.get("locked_by", ""),
                translate("col_decided_at"): lk.get("locked_at", ""),
                translate("col_message"): (
                    f"version: {str(lk.get('subject_version_id', ''))[:16]}"
                ),
            }
        )

    events.sort(key=lambda e: e["sort_key"])
    for e in events:
        del e["sort_key"]

    if events:
        st.dataframe(
            events,
            use_container_width=True,
            hide_index=True,
        )


def _render_pipeline_bar(
    app: Application,
    project_id: str,
    intake: dict[str, Any],
    ready: bool,
    state: dict[str, Any],
    pending: list[dict[str, Any]],
    config: dict[str, Any] | None,
    snapshot: Any,
    thread_id: str | None,
) -> None:
    """Render the pipeline-control section as a standalone bar.

    Previously embedded inside ``st.tabs``; now extracted to sit directly
    beneath the hero / title area so the run button and approval gates are
    always visible regardless of which content tab is active.
    """

    with st.container(border=True):
        st.markdown(
            f"""<div class="pipeline-bar-header">
            <strong>{translate("tab_pipeline_control")}</strong>
            </div>""",
            unsafe_allow_html=True,
        )

        requirements = {
            translate("tab_research_question"): bool(
                intake.get("research_question_input")
            ),
            translate("readiness_search"): bool(intake.get("search_strategy_input")),
            translate("readiness_literature"): bool(
                intake.get("literature_record_drafts")
            ),
            translate("readiness_dataset"): bool(intake.get("dataset_summary")),
        }
        status_cols = st.columns(4)
        for col, (label, complete) in zip(
            status_cols, requirements.items(), strict=True
        ):
            col.metric(
                label,
                translate("label_ready") if complete else translate("label_incomplete"),
            )

        if st.button(
            translate("button_start_full_run"),
            type="primary",
            disabled=not ready,
            help=None if ready else translate("start_disabled_help"),
        ):
            _start_workflow(app, project_id)
            st.rerun()

        if thread_id is not None and config is not None:
            render_phase_tracker(state.get("current_stage"))
            render_run_metrics(state, thread_id)
            next_nodes = ", ".join(snapshot.next) if snapshot.next else "-"
            st.caption(f"{translate('label_next')}: {next_nodes}")
            if pending:
                _render_pending_approval(app, config, pending[0])
            _render_search_strategy_detail(state)
            with st.expander(translate("expander_artifact_refs"), expanded=False):
                st.json(state.get("artifacts", {}))
            with st.expander(translate("expander_approvals_locks"), expanded=False):
                st.json(
                    {
                        "approvals": state.get("approvals", {}),
                        "locks": state.get("locks", {}),
                    }
                )
            _render_approval_timeline(state)
            if not pending and state.get("run_status") == "complete":
                st.success(translate("success_pipeline_complete"))


def _render_workflow(app: Application, project_id: str) -> None:
    intake = st.session_state.setdefault(f"analysis_intake:{project_id}", {})
    ready = _compute_intake_ready(intake)

    thread_id = _get_active_thread(project_id)
    state: dict[str, Any] = {}
    pending: list[dict[str, Any]] = []
    config: dict[str, Any] | None = None
    snapshot: Any = None
    if thread_id is not None:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = app.graph.get_state(config)
        state = snapshot.values
        pending = _interrupt_values(snapshot)

    # ---- Pipeline & approval bar (always visible, not inside tabs) ----
    _render_pipeline_bar(
        app, project_id, intake, ready, state, pending, config, snapshot, thread_id
    )

    (
        tab_design,
        tab_data,
        tab_lit,
        tab_method,
        tab_manuscript,
        tab_review,
        tab_export,
    ) = st.tabs(
        [
            translate("tab_intake_question"),
            translate("tab_intake_data"),
            translate("tab_lit_evidence"),
            translate("tab_method_stats"),
            translate("tab_manuscript"),
            translate("tab_review_compliance"),
            translate("tab_export"),
        ]
    )

    # ---- Tab: Study design --------------------------------------------
    with tab_design:
        _render_intake_question(intake)

    # ---- Tab: Data preparation ----------------------------------------
    with tab_data:
        _render_intake_materials(app, project_id, intake)

    # ---- Result tabs (guarded by state availability) ------------------
    with tab_lit:
        if state:
            _render_literature_records(state)
            _render_evidence_items(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_method:
        if state:
            _render_guideline_mapping(state)
            _render_methodology_findings(state)
            _render_analysis_plan(state)
            _render_statistical_results(state)
            _render_effect_plots(state)
            _render_analysis_provenance(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_manuscript:
        if state:
            _render_manuscript(state)
            _render_claim_traceability(state)
            _render_citations(state)
            _render_claim_audit(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_review:
        if state:
            _render_review(state)
            _render_revision_diff(state)
            _render_compliance(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_export:
        if state:
            _render_export(state)
            _render_usage_summary(state)
            _render_ai_disclosure(state)
        else:
            st.info(translate("info_start_pipeline"))


def _ensure_golden_project_exists(app: Application) -> None:
    """Ensure the Golden Project fixture is present in the project list."""

    if st.session_state.get("_golden_seeded"):
        return
    fixture = _load_golden_fixture()
    if fixture is None:
        return
    _ensure_golden_workspace_project(app, fixture)
    st.session_state["_golden_seeded"] = True


def main() -> None:
    st.set_page_config(
        page_title=translate("page_title"), page_icon=":microscope:", layout="wide"
    )
    apply_theme()
    _render_sidebar_header()
    app = get_application()

    # Ensure Golden Project is available in the project list
    _ensure_golden_project_exists(app)

    # Sidebar: project notices
    _render_projects(app)

    project_id = st.session_state.get("project_id")
    active_project_id = project_id if isinstance(project_id, str) else None

    # Auto-select first project if none selected
    if active_project_id is None:
        all_projects = app.repository.list_projects()
        if all_projects:
            active_project_id = all_projects[0].id
            st.session_state["project_id"] = active_project_id
            _snapshot_intake(active_project_id)
    elif not st.session_state.get(f"intake_baseline:{active_project_id}"):
        _snapshot_intake(active_project_id)

    # Sidebar: clickable project list + right-click menu
    _render_sidebar_project_management(app)

    # Sidebar: new project creation
    _render_project_creation(app)

    # Sidebar: language switch (at bottom)
    _render_language_switch()

    # Inject beforeunload warning if data is dirty
    _inject_beforeunload(_is_intake_dirty(active_project_id))

    # Main area
    render_hero()
    if active_project_id is not None:
        _render_workflow(app, active_project_id)


if __name__ == "__main__":
    main()
