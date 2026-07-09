"""Methodology and statistics rendering (tab: Methodology & Statistics)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.i18n import translate


def render_guideline_mapping(state: dict[str, Any]) -> None:
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
        col1.metric(
            translate("label_primary_endpoint"),
            protocol.get("primary_endpoint", "-"),
        )
        col2.metric(
            translate("label_eligibility"),
            protocol.get("eligibility", "-"),
        )
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


def render_methodology_findings(state: dict[str, Any]) -> None:
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


def render_analysis_plan(state: dict[str, Any]) -> None:
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
    if "dataset" in locks:
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


def render_statistical_results(state: dict[str, Any]) -> None:
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


def render_effect_plots(state: dict[str, Any]) -> None:
    """Render bar-chart visualisations of numeric estimates."""

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
    import pandas as pd  # type: ignore[import-untyped]

    df = pd.DataFrame(plot_data).set_index(translate("col_analysis_name"))
    st.bar_chart(df[translate("col_estimate")])
    st.dataframe(
        df.drop(columns=[translate("col_estimate")]),
        use_container_width=True,
        hide_index=True,
    )


def render_analysis_provenance(state: dict[str, Any]) -> None:
    """Display reproducibility provenance from the analysis run."""

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
    col3.metric(
        translate("label_plan_ref"),
        plan_ver + "..." if plan_ver else "-",
    )
    ds_ver = str(payload.get("dataset_version_id", ""))[:20]
    col4.metric(
        translate("label_dataset_ref"),
        ds_ver + "..." if ds_ver else "-",
    )

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
                st.dataframe(
                    pv_rows,
                    use_container_width=True,
                    hide_index=True,
                )
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


def render_usage_summary(state: dict[str, Any]) -> None:
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
