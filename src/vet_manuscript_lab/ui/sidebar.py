"""Sidebar rendering: header, project list, creation, language switch, context menu."""

from __future__ import annotations

import streamlit as st

from vet_manuscript_lab.infrastructure.database.repository import ProjectInput
from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    translate,
)
from vet_manuscript_lab.ui.state import is_intake_dirty, snapshot_intake


def render_sidebar_header() -> None:
    st.sidebar.markdown(
        f"""<div class="sidebar-brand"><strong>{translate("app_title")}</strong>
        <span>{translate("sidebar_tagline")}</span></div>""",
        unsafe_allow_html=True,
    )


def render_language_switch() -> None:
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


def render_project_creation(app: Application) -> None:
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
                translate("button_create"), type="primary", width="stretch"
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


def render_projects(app: Application) -> None:
    """Show project creation/deletion notices."""

    notice = st.session_state.pop("project_created_notice", None)
    if isinstance(notice, str):
        st.sidebar.success(notice)


def inject_context_menu_js() -> None:
    """Inject JS that adds right-click context menus to project list items."""

    rename_label = translate("ctx_rename")
    delete_label = translate("ctx_delete")
    st.iframe(
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
        height=1,
    )


def render_sidebar_project_management(app: Application) -> None:
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
            disabled=is_active,
        ):
            if is_intake_dirty(current_pid) and project.id != current_pid:
                st.session_state["pending_project_switch"] = project.id
            else:
                st.session_state["project_id"] = project.id
                snapshot_intake(project.id)
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
                    width="stretch",
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
                    translate("label_no"), width="stretch"
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
                width="stretch",
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
                width="stretch",
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
            width="stretch",
            key="discard_yes",
        ):
            st.session_state["project_id"] = pending_switch
            st.session_state.pop("pending_project_switch", None)
            snapshot_intake(pending_switch)
            st.rerun()
        if c_no.button(
            translate("label_stay"),
            width="stretch",
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
    inject_context_menu_js()
