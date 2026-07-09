"""Table and collapsible-detail helpers for the design system."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st


def _esc(text: Any) -> str:
    return html.escape(str(text))


def clean_table(
    rows: list[dict[str, Any]],
    columns_map: dict[str, str],
    *,
    truncate_fields: set[str] | None = None,
    truncate_len: int = 16,
) -> None:
    """Render a DataFrame with mapped columns and truncated long values.

    Parameters
    ----------
    rows
        List of raw dict rows.
    columns_map
        Mapping of ``raw_field → display_label``. Only fields in this map
        are shown, in the given order.
    truncate_fields
        Set of fields whose values should be truncated (e.g. hashes, IDs).
    """

    if not rows:
        return

    truncate_fields = truncate_fields or set()
    display_rows: list[dict[str, Any]] = []
    for row in rows:
        d: dict[str, Any] = {}
        for raw_field, display_label in columns_map.items():
            val = row.get(raw_field, "")
            if raw_field in truncate_fields and isinstance(val, str):
                val = val[:truncate_len] if len(val) > truncate_len else val
            d[display_label] = val
        display_rows.append(d)

    st.dataframe(display_rows, use_container_width=True, hide_index=True)


def collapsible_details(
    label: str,
    content: str | dict[str, Any],
    *,
    expanded: bool = False,
) -> None:
    """Render a collapsible section for technical details.

    When *content* is a dict, it is rendered as a ``st.json`` block inside
    an expander; when it is a string, it is rendered as preformatted text.
    """

    with st.expander(label, expanded=expanded):
        if isinstance(content, dict):
            st.json(content)
        else:
            st.code(content, language="text")


def short_hash(full_hash: str, length: int = 12) -> str:
    """Truncate a hash string for display, e.g. ``sha256:abc...`` → ``abc...``."""

    if not full_hash:
        return ""
    # Strip common prefixes
    for prefix in ("sha256:", "sha1:", "md5:"):
        if full_hash.startswith(prefix):
            full_hash = full_hash[len(prefix) :]
            break
    if len(full_hash) <= length:
        return full_hash
    return full_hash[:length] + "..."


def copy_button_html(value: str, key: str = "") -> str:
    """Return an HTML ``<button>`` that copies *value* to the clipboard.

    Uses a data attribute so a global JS listener can handle the click.
    """

    import html as _html

    safe_val = _html.escape(value)
    safe_key = _html.escape(key or value[:8])
    return (
        f'<button class="vrl-copy-btn" data-copy="{safe_val}" '
        f'title="Copy" '
        f'style="border:1px solid #D8DED6;border-radius:6px;'
        f"background:#fff;color:#6B7280;padding:.15rem .4rem;"
        f'cursor:pointer;font-size:.72rem;">{safe_key}</button>'
    )


def inject_copy_js() -> None:
    """Inject JS that wires up ``.vrl-copy-btn`` click → clipboard."""

    import streamlit.components.v1 as components

    components.html(
        """
<script>
(function() {
  var doc = window.parent.document;
  doc.querySelectorAll('.vrl-copy-btn:not([data-wired])').forEach(function(btn) {
    btn.setAttribute('data-wired', '1');
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      var val = btn.getAttribute('data-copy');
      navigator.clipboard.writeText(val).then(function() {
        var orig = btn.textContent;
        btn.textContent = '\\u2713';
        btn.style.color = '#2F855A';
        setTimeout(function() {
          btn.textContent = orig;
          btn.style.color = '#6B7280';
        }, 1500);
      });
    });
  });
})();
</script>
""",
        height=0,
    )


__all__ = [
    "clean_table",
    "collapsible_details",
    "copy_button_html",
    "inject_copy_js",
    "short_hash",
]
