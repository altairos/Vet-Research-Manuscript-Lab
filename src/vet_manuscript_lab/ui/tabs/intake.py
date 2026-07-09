"""Study design and data intake forms (tabs: research question, literature & data)."""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any

import streamlit as st

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.infrastructure.database.literature import LiteratureInput
from vet_manuscript_lab.services.zotero import (
    ZoteroClient,
    ZoteroConfig,
    ZoteroSynchroniser,
)
from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.i18n import translate


def literature_draft(record: Any) -> dict[str, Any]:
    return {
        "record_id": record.id,
        "title": record.title,
        "doi": record.doi,
        "pmid": record.pmid,
        "journal": record.journal,
        "publication_year": record.publication_year,
        "screening_decision": "pending",
    }


def render_intake_question(intake: dict[str, Any]) -> None:
    """Render the PECO research-question form."""

    question = dict(intake.get("research_question_input", {}))
    with st.form("analysis-question"):
        objective = st.text_area(
            translate("field_objective"),
            value=question.get("objective", ""),
            height=68,
        )
        population = st.text_area(
            translate("field_population"),
            value=question.get("population", ""),
            height=68,
        )
        exposure = st.text_area(
            translate("field_exposure"),
            value=question.get("exposure", ""),
            height=68,
        )
        comparator = st.text_area(
            translate("field_comparator"),
            value=question.get("comparator", ""),
            height=68,
        )
        outcome = st.text_area(
            translate("field_outcome"),
            value=question.get("outcome", ""),
            height=68,
        )
        hypothesis = st.text_area(
            translate("field_hypothesis"),
            value=question.get("hypothesis", ""),
            height=68,
        )
        if st.form_submit_button(translate("button_save_question")):
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


def bump_search_form_version(project_id: str) -> None:
    """Increment the search-strategy form version."""

    current = st.session_state.get(f"search_form_version:{project_id}", 0)
    st.session_state[f"search_form_version:{project_id}"] = current + 1


def render_intake_materials(
    app: Application, project_id: str, intake: dict[str, Any]
) -> None:
    """Render literature search and dataset forms."""

    # ---- Literature / search strategy ----------------------------------
    search = dict(intake.get("search_strategy_input", {}))

    st.markdown(f"##### {translate('edit_strategy_header')}")

    search_version = st.session_state.get(f"search_form_version:{project_id}", 0)
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
            translate("button_save_search")
        )
        reset_clicked = reset_col.form_submit_button(translate("button_reset_search"))
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
            bump_search_form_version(project_id)
            st.rerun()

    saved = intake.get("search_strategy_input", {})
    with st.expander(translate("saved_strategy_header"), expanded=False):
        if saved and saved.get("query"):
            st.markdown(
                f"**{translate('saved_strategy_query')}**: {saved.get('query', '')}"
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
            if st.button(translate("button_sync_zotero")):
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
                            title=lit_title,
                            doi=lit_doi.strip() or None,
                        ),
                    )
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.success(translate("success_literature_added"))

    records = app.literature_repository.list_literature_records(project_id)
    if records:
        intake["literature_record_drafts"] = [
            literature_draft(record) for record in records
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
            width="stretch",
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
        translate("field_upload_csv"),
        type=["csv"],
        key="analysis-dataset",
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
                translate("field_id_variable"),
                [translate("option_none"), *columns],
            )
            if st.button(translate("button_save_dataset")):
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

    # ---- Variable spec editor (editable) -------------------------------
    var_specs = intake.get("variable_spec_drafts", [])
    if var_specs:
        import pandas as pd  # type: ignore[import-untyped]

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
            width="stretch",
            hide_index=True,
            key=f"var_editor_{project_id}",
        )
        if st.button(translate("button_save_variables")):
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
