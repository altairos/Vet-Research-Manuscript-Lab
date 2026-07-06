# Golden project fixture

This fixture contains **fully synthetic** data for end-to-end regression testing
of the Vet Research Manuscript Lab pipeline. It must never contain real owner,
client, animal, institution, credential, token, attachment, or clinical record
data.

## Contents

| Path | Description |
|---|---|
| `project.json` | Project metadata, research question, and fixture manifest |
| `data/cases_synthetic.csv` | 30-row synthetic canine/feline clinical dataset |
| `dictionary/variables.json` | Validated data dictionary (5 variables with types, roles, units) |
| `analysis_plan/analyses.json` | Prespecified analysis plan (1 primary + 2 secondary analyses) |
| `literature/records.json` | 5 synthetic literature records with DOIs and abstracts |
| `methodology/findings.json` | 4 mock methodology critic findings (confounding, missing data, etc.) |

## Dataset schema

| Variable | Type | Role | Unit |
|---|---|---|---|
| case_id | categorical | id | — |
| species | categorical | covariate | — |
| age_years | continuous | covariate | years |
| treatment_group | binary | exposure | — |
| survival_months | continuous | outcome | months |

## Usage

The golden project fixture is consumed by `tests/test_golden_project.py` for
regression testing. It validates that:

1. The CSV dataset imports and hashes correctly via `DatasetImporter`.
2. The data dictionary passes `DatasetDictionary.validate()`.
3. Analysis plan variables all exist in the dataset dictionary.
4. The mock statistics runner produces deterministic results from the fixture.
5. Literature records and methodology findings are well-formed JSON.

## License

All fixture content is synthetic and may be freely redistributed without
restriction.
# Golden project fixture

This fixture contains synthetic metadata only. It must never contain real owner,
client, animal, institution, credential, token, attachment, or clinical record
data. Later phases may add generated CSV and redistributable publications with
their provenance and licenses documented here.

