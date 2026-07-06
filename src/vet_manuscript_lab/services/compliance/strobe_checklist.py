"""STROBE-Vet checklist definition.

The 22-item STROBE-Vet checklist for observational studies in
veterinary medicine.  Each item is a frozen ``STROBEItem`` dataclass.
"""

from __future__ import annotations

from vet_manuscript_lab.services.compliance.types import (
    ChecklistCategory,
    STROBEItem,
)

STROBE_VET_ITEMS: tuple[STROBEItem, ...] = (
    STROBEItem(
        item_number=1,
        title="Title and abstract",
        requirement="Indicate the study design with a commonly used term in the title or abstract.",
        category=ChecklistCategory.TITLE_ABSTRACT,
    ),
    STROBEItem(
        item_number=2,
        title="Background / rationale",
        requirement="Explain the scientific background and rationale for the investigation.",
        category=ChecklistCategory.INTRODUCTION,
    ),
    STROBEItem(
        item_number=3,
        title="Objectives",
        requirement="State specific objectives, including any pre-specified hypotheses.",
        category=ChecklistCategory.INTRODUCTION,
    ),
    STROBEItem(
        item_number=4,
        title="Study design",
        requirement="Present key elements of the study design early in the paper.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=5,
        title="Setting",
        requirement="Describe the setting, locations, and relevant dates.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=6,
        title="Participants",
        requirement="Give the eligibility criteria and sources/methods of selection.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=7,
        title="Variables",
        requirement="Clearly define all outcomes, exposures, predictors, and confounders.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=8,
        title="Data sources / measurement",
        requirement="For each variable of interest, give sources of data and details of methods of assessment.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=9,
        title="Bias",
        requirement="Describe any efforts to address potential sources of bias.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=10,
        title="Study size",
        requirement="Explain how the study size was arrived at.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=11,
        title="Quantitative variables",
        requirement="Explain how quantitative variables were handled in the analyses.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=12,
        title="Statistical methods",
        requirement="Describe all statistical methods, including those used to control for confounding.",
        category=ChecklistCategory.METHODS,
    ),
    STROBEItem(
        item_number=13,
        title="Results: participants",
        requirement="Report numbers of individuals at each stage and reasons for non-participation.",
        category=ChecklistCategory.RESULTS,
    ),
    STROBEItem(
        item_number=14,
        title="Results: descriptive data",
        requirement="Give characteristics of study participants and information on exposures and potential confounders.",
        category=ChecklistCategory.RESULTS,
    ),
    STROBEItem(
        item_number=15,
        title="Results: outcome data",
        requirement="Report numbers of outcome events or summary measures.",
        category=ChecklistCategory.RESULTS,
    ),
    STROBEItem(
        item_number=16,
        title="Results: main results",
        requirement="Give unadjusted estimates and confounder-adjustged estimates and their confidence intervals.",
        category=ChecklistCategory.RESULTS,
    ),
    STROBEItem(
        item_number=17,
        title="Results: other analyses",
        requirement="Report category boundaries and sensitivity analyses.",
        category=ChecklistCategory.RESULTS,
    ),
    STROBEItem(
        item_number=18,
        title="Key results",
        requirement="Summarise key results with reference to study objectives.",
        category=ChecklistCategory.DISCUSSION,
    ),
    STROBEItem(
        item_number=19,
        title="Limitations",
        requirement="Discuss limitations of the study, considering sources of potential bias or imprecision.",
        category=ChecklistCategory.DISCUSSION,
    ),
    STROBEItem(
        item_number=20,
        title="Interpretation",
        requirement="Give a cautious overall interpretation of results considering objectives, limitations, and multiplicity of analyses.",
        category=ChecklistCategory.DISCUSSION,
    ),
    STROBEItem(
        item_number=21,
        title="Generalisability",
        requirement="Discuss the generalisability (external validity) of the study results.",
        category=ChecklistCategory.DISCUSSION,
    ),
    STROBEItem(
        item_number=22,
        title="Funding",
        requirement="Give the role of the study funders and the role of the investigators.",
        category=ChecklistCategory.OTHER,
    ),
)


def build_strobe_checklist() -> tuple[STROBEItem, ...]:
    """Return the full STROBE-Vet checklist items."""
    return STROBE_VET_ITEMS


__all__ = [
    "STROBE_VET_ITEMS",
    "build_strobe_checklist",
]
