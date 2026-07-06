"""``pyzotero`` adapter implementing the ``ZoteroBackend`` protocol.

Kept in a separate module so that ``client.py`` stays importable without
``pyzotero`` installed.  The adapter translates between pyzotero's generator /
pagination API and the simple list-returning interface the client expects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vet_manuscript_lab.services.zotero.client import ZoteroConfig

if TYPE_CHECKING:
    from pyzotero.zotero import Zotero


class PyzoteroBackend:
    """Adapts ``pyzotero.zotero.Zotero`` to the ``ZoteroBackend`` protocol."""

    def __init__(self, config: ZoteroConfig) -> None:
        self._config = config
        self._zotero: Zotero | None = None

    def fetch_items(self, since_version: int) -> list[dict[str, Any]]:
        zotero = self._get_zotero()
        result = zotero.items(since=since_version) if since_version else zotero.items()
        return list(result)

    def fetch_children(self, item_key: str) -> list[dict[str, Any]]:
        zotero = self._get_zotero()
        return list(zotero.children(item_key))

    def last_modified_version(self) -> int:
        zotero = self._get_zotero()
        return int(zotero.last_modified_version())

    def _get_zotero(self) -> Zotero:
        if self._zotero is None:
            from pyzotero.zotero import Zotero

            self._zotero = Zotero(
                library_id=self._config.library_id,
                library_type=self._config.library_type,
                api_key=self._config.api_key,
            )
        return self._zotero


__all__ = ["PyzoteroBackend"]
