"""Map normalised Zotero items to the internal ``LiteratureInput`` domain type.

The mapper is a pure function: given a ``ZoteroItem`` it returns a
``LiteratureInput`` ready for ``LiteratureRepository.create_literature_record``.
It validates that a title is present (required by the domain model) and strips
Zotero-specific prefixes from DOI/PMID values.
"""

from __future__ import annotations

from typing import Any

from vet_manuscript_lab.infrastructure.database.literature import LiteratureInput
from vet_manuscript_lab.services.zotero.types import ZoteroItem


class ZoteroMappingError(ValueError):
    """Raised when a Zotero item cannot be mapped to a domain LiteratureInput."""


def map_zotero_item(item: ZoteroItem) -> LiteratureInput:
    """Convert a ``ZoteroItem`` into a ``LiteratureInput``.

    Raises ``ZoteroMappingError`` if the item has no usable title (the domain
    model requires a non-empty title).  Attachment-only Zotero entries and
    notes are skipped upstream by the synchroniser, but the mapper stays
    defensive.
    """

    title = item.title.strip()
    if not title:
        raise ZoteroMappingError(
            f"Zotero item {item.item_key} has no title; cannot create a "
            "literature record"
        )

    doi = _clean_doi(item.doi) if item.doi else None
    pmid = _clean_pmid(item.pmid) if item.pmid else None

    metadata: dict[str, Any] = {
        "zotero_item_type": item.item_type,
        "zotero_version": item.version,
    }
    if item.attachments:
        metadata["attachment_keys"] = [att.attachment_key for att in item.attachments]

    return LiteratureInput(
        title=title,
        doi=doi,
        pmid=pmid,
        zotero_item_key=item.item_key,
        zotero_library_id=item.library_id,
        bibtex_key=item.bibtex_key,
        creators=list(item.creators),
        publication_year=item.publication_year,
        journal=item.journal,
        metadata_json=metadata,
    )


def _clean_doi(raw: str) -> str | None:
    """Strip common DOI URL prefixes and whitespace."""

    value = raw.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    return value.strip() or None


def _clean_pmid(raw: str) -> str | None:
    """Strip common PMID label prefixes."""

    value = raw.strip()
    for prefix in ("PMID:", "PMID ", "pmid:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    value = value.strip()
    return value if value.isdigit() else None
