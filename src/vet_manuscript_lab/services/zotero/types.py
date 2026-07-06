"""Typed representations of Zotero API responses.

These dataclasses decouple the rest of the codebase from the raw JSON payloads
returned by the Zotero API.  The ``pyzotero`` client converts its output into
these structures before handing them to the mapper and synchroniser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ZoteroAttachment:
    """A single attachment linked to a Zotero item."""

    attachment_key: str
    filename: str
    content_type: str
    md5_hash: str | None
    size_bytes: int | None
    download_url: str | None


@dataclass(frozen=True, slots=True)
class ZoteroItem:
    """Normalised Zotero library item."""

    item_key: str
    item_type: str
    title: str
    creators: list[dict[str, Any]] = field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    publication_year: int | None = None
    journal: str | None = None
    bibtex_key: str | None = None
    library_id: str | None = None
    version: int = 0
    raw_json: dict[str, Any] = field(default_factory=dict)
    attachments: list[ZoteroAttachment] = field(default_factory=list)


def parse_zotero_item(
    raw: dict[str, Any], *, library_id: str | None = None
) -> ZoteroItem:
    """Build a ``ZoteroItem`` from a pyzotero ``item`` JSON payload.

    The Zotero API stores bibliographic fields inside ``data``.  DOI is stored
    in ``DOI`` (or ``extra`` as a fallback for some item types); PMID is often
    embedded in ``Extra`` as ``PMID: <number>``.
    """

    data = dict(raw.get("data", {}))
    key = str(raw.get("key", data.get("key", "")))
    item_type = str(data.get("itemType", "journalArticle"))
    title = str(data.get("title", "")).strip()

    doi = data.get("DOI") or data.get("doi")
    extra = str(data.get("extra", ""))
    pmid = _extract_pmid(extra)

    creators = list(data.get("creators", []))

    publication_year = _extract_year(data.get("date"))

    journal = (
        data.get("publicationTitle")
        or data.get("journal")
        or data.get("proceedingsTitle")
    )

    return ZoteroItem(
        item_key=key,
        item_type=item_type,
        title=title,
        creators=creators,
        doi=str(doi).strip() if doi else None,
        pmid=str(pmid).strip() if pmid else None,
        publication_year=publication_year,
        journal=str(journal).strip() if journal else None,
        bibtex_key=str(data.get("citationKey", "")).strip() or None,
        library_id=library_id or str(raw.get("library", {}).get("id", "")) or None,
        version=int(raw.get("version") or data.get("version") or 0),
        raw_json=dict(raw),
    )


def parse_zotero_attachment(raw: dict[str, Any]) -> ZoteroAttachment:
    """Build a ``ZoteroAttachment`` from a pyzotero attachment payload."""

    data = dict(raw.get("data", {}))
    return ZoteroAttachment(
        attachment_key=str(raw.get("key", data.get("key", ""))),
        filename=str(data.get("filename", "")),
        content_type=str(data.get("contentType", "application/octet-stream")),
        md5_hash=data.get("md5"),
        size_bytes=data.get("size"),
        download_url=str(data.get("url", "")) or None,
    )


def _extract_pmid(extra_text: str) -> str | None:
    """Extract a PMID from a Zotero ``Extra`` field.

    PubMed IDs are commonly stored as ``PMID: 12345678`` or ``PMID:12345678``
    inside the free-form Extra field.
    """

    if not extra_text:
        return None
    for line in extra_text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("PMID"):
            parts = stripped.split(":", 1)
            if len(parts) == 2 and parts[1].strip().isdigit():
                return parts[1].strip()
    return None


def _extract_year(date_value: Any) -> int | None:
    """Best-effort extraction of a four-digit year from a Zotero date field."""

    if date_value is None:
        return None
    text = str(date_value)
    # Zotero dates can be "2024-03-15", "2024", "March 15, 2024", etc.
    for token in text.replace("-", " ").split():
        token = token.strip(",.")
        if token.isdigit() and len(token) == 4 and int(token) >= 1900:
            return int(token)
    return None
