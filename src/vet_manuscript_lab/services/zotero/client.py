"""Read-only Zotero API v3 client wrapper.

Wraps ``pyzotero`` so that the rest of the codebase depends on a narrow
interface that can be substituted with a mock during testing.  Only read
operations are exposed; no create/update/delete calls reach Zotero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vet_manuscript_lab.services.zotero.types import (
    ZoteroAttachment,
    ZoteroItem,
    parse_zotero_attachment,
    parse_zotero_item,
)


@dataclass(frozen=True, slots=True)
class ZoteroConfig:
    """Connection parameters for a single Zotero library."""

    library_id: str
    api_key: str
    library_type: str = "user"  # "user" or "group"


class ZoteroBackend(Protocol):
    """Minimal read-only backend interface the client relies on."""

    def fetch_items(self, since_version: int) -> list[dict[str, Any]]: ...

    def fetch_children(self, item_key: str) -> list[dict[str, Any]]: ...

    def last_modified_version(self) -> int: ...


class ZoteroClient:
    """Thin read-only adapter over the Zotero API v3."""

    def __init__(
        self, config: ZoteroConfig, *, backend: ZoteroBackend | None = None
    ) -> None:
        self.config = config
        self._backend = backend

    def fetch_items(self, *, since_version: int = 0) -> list[ZoteroItem]:
        """Return all library items updated after ``since_version``."""

        raw_items = self._get_backend().fetch_items(since_version)
        return [
            parse_zotero_item(raw, library_id=self.config.library_id)
            for raw in raw_items
        ]

    def fetch_attachments(self, item_key: str) -> list[ZoteroAttachment]:
        """Return attachment metadata for a given Zotero item key."""

        children = self._get_backend().fetch_children(item_key)
        return [
            parse_zotero_attachment(raw)
            for raw in children
            if raw.get("data", {}).get("itemType") == "attachment"
            and raw.get("data", {}).get("linkMode")
            in (
                "imported_file",
                "imported_url",
                "linked_file",
                "linked_url",
            )
        ]

    def latest_version(self) -> int:
        """Return the current library version for incremental sync tracking."""

        return self._get_backend().last_modified_version()

    def _get_backend(self) -> ZoteroBackend:
        if self._backend is not None:
            return self._backend
        return _create_default_backend(self.config)


def _create_default_backend(config: ZoteroConfig) -> ZoteroBackend:
    """Instantiate the real ``pyzotero`` backend lazily.

    Importing pyzotero at module load would couple every test to the network
    library; deferring the import keeps the module importable in offline
    environments.
    """

    from vet_manuscript_lab.services.zotero._pyzotero_backend import (
        PyzoteroBackend,
    )

    return PyzoteroBackend(config)


__all__ = ["ZoteroBackend", "ZoteroClient", "ZoteroConfig"]
