"""Dataset importer: hash, validate, and prepare a DatasetVersion.

The importer accepts a CSV file path or a pre-loaded DataFrame, computes
a content hash, validates the variable dictionary, and returns a
``DatasetSpec`` ready for locking.  In MVP the data file is not moved —
only its hash and metadata are recorded.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.services.analysis.dictionary import DatasetDictionary
from vet_manuscript_lab.services.analysis.types import DatasetSpec, VariableSpec


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Outcome of a dataset import attempt."""

    dataset: DatasetSpec
    dictionary: DatasetDictionary
    warnings: tuple[str, ...]


class DatasetImporter:
    """Import and validate a clinical case dataset.

    Usage::

        importer = DatasetImporter()
        result = importer.import_csv(
            path=Path("cases.csv"),
            dataset_id="ds-001",
            name="Canine CKD cohort",
            variables=variable_specs,
        )
    """

    def import_csv(
        self,
        *,
        path: Path,
        dataset_id: str,
        name: str,
        variables: tuple[VariableSpec, ...],
    ) -> ImportResult:
        """Import a CSV file and return a validated ``ImportResult``."""

        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        content = path.read_bytes()
        content_hash = sha256_bytes(content)
        row_count, column_count = self._count_csv(content)

        dictionary = DatasetDictionary.validate(variables)

        # Verify that header matches variable names
        warnings: list[str] = []
        header_names = self._read_csv_header(content)
        dict_names = dictionary.variable_names
        header_set = frozenset(header_names)
        if header_set != dict_names:
            missing_in_file = dict_names - header_set
            extra_in_file = header_set - dict_names
            if missing_in_file:
                raise PolicyViolation(
                    f"CSV header is missing variables defined in dictionary: "
                    f"{sorted(missing_in_file)}"
                )
            if extra_in_file:
                warnings.append(
                    f"CSV contains columns not in dictionary: "
                    f"{sorted(extra_in_file)} (ignored)"
                )

        spec = DatasetSpec(
            dataset_id=dataset_id,
            name=name,
            row_count=row_count,
            column_count=column_count,
            content_hash=content_hash,
            uri=str(path),
            media_type="text/csv",
            version=1,
            variables=variables,
        )
        return ImportResult(
            dataset=spec,
            dictionary=dictionary,
            warnings=tuple(warnings),
        )

    def import_dataframe(
        self,
        *,
        df: Any,  # pandas or polars DataFrame — duck-typed
        dataset_id: str,
        name: str,
        content_hash: str,
        variables: tuple[VariableSpec, ...],
    ) -> ImportResult:
        """Import a pre-loaded DataFrame with an externally-provided hash.

        The caller is responsible for computing ``content_hash`` from the
        canonical serialization of the DataFrame.
        """

        row_count = len(df)
        column_names = list(df.columns)
        column_count = len(column_names)

        dictionary = DatasetDictionary.validate(variables)

        warnings: list[str] = []
        header_set = frozenset(str(c) for c in column_names)
        dict_names = dictionary.variable_names
        if header_set != dict_names:
            missing_in_df = dict_names - header_set
            extra_in_df = header_set - dict_names
            if missing_in_df:
                raise PolicyViolation(
                    f"DataFrame is missing variables defined in dictionary: "
                    f"{sorted(missing_in_df)}"
                )
            if extra_in_df:
                warnings.append(
                    f"DataFrame contains columns not in dictionary: "
                    f"{sorted(extra_in_df)} (ignored)"
                )

        spec = DatasetSpec(
            dataset_id=dataset_id,
            name=name,
            row_count=row_count,
            column_count=column_count,
            content_hash=content_hash,
            uri=f"dataframe://{dataset_id}",
            media_type="application/x-dataframe",
            version=1,
            variables=variables,
        )
        return ImportResult(
            dataset=spec,
            dictionary=dictionary,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _count_csv(content: bytes) -> tuple[int, int]:
        """Return (data_row_count, column_count) excluding header."""

        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        if not rows:
            raise PolicyViolation("CSV file is empty")
        header = rows[0]
        data_rows = len(rows) - 1  # exclude header
        return data_rows, len(header)

    @staticmethod
    def _read_csv_header(content: bytes) -> list[str]:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(text.splitlines())
        try:
            return next(reader)
        except StopIteration:
            return []


def compute_csv_hash(path: Path) -> str:
    """Compute a SHA-256 content hash for a CSV file."""

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


__all__ = [
    "DatasetImporter",
    "ImportResult",
    "compute_csv_hash",
]
