"""Analysis services: dataset dictionary, importer, and statistics runner."""

from __future__ import annotations

from vet_manuscript_lab.services.analysis.dictionary import DatasetDictionary
from vet_manuscript_lab.services.analysis.importer import DatasetImporter, ImportResult
from vet_manuscript_lab.services.analysis.runner import (
    AnalysisRunResult,
    MockStatisticsRunner,
    RunResult,
    StatisticsRunner,
)
from vet_manuscript_lab.services.analysis.subprocess_runner import (
    SubprocessStatisticsRunner,
)
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    ResultSpec,
    VariableRole,
    VariableSpec,
    VariableType,
)

__all__ = [
    "AnalysisClass",
    "AnalysisRunResult",
    "AnalysisSpec",
    "DatasetDictionary",
    "DatasetImporter",
    "DatasetSpec",
    "ImportResult",
    "MockStatisticsRunner",
    "ResultSpec",
    "RunResult",
    "StatisticsRunner",
    "SubprocessStatisticsRunner",
    "VariableRole",
    "VariableSpec",
    "VariableType",
]
