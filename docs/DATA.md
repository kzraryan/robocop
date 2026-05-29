# CAIDF NICU data map

> De-identified data. **Stays on the server.** Never copy into git, decks, or
> external services. Always reconcile the names below against
> `python scripts/data_inventory.py` — real file names occasionally differ from
> the official data guide (spelling, date suffixes, "multiple files" dirs).

**Cohort:** NICU — patients 0–1 yr admitted to a neonatal ICU (all causes) who
were discharged home. **13,904 NICU patients** total across sites. Data starts
at the first NICU hospitalization and runs forward through **2024-07-31**;
overall inclusion range **2015-10-01 → 2024-07-31**.

**Sites:** UIC, University of Iowa (Iowa), University of Missouri (MU).
**Note professions (free text):** MD, RN, OT, PT, SLP.

Root: `$CAIDF_DATA_ROOT` (default `/media/data/caidf_data`).

---

## MU — `/MU/NICU/`
**Cohort tables**
- `NICU_EVENTS.csv` — encounters by all five professions
- `NICU_PROVIDERS.csv` — provider types / details
- `NICU_NOTE_METADATA.csv` — metadata for free-text notes (event desc, provider info, note length…)

**Free-text notes** — `/MU/NICU/2024-11-20/` : many CSVs, two columns
`NOTE_ID`, `NOTE` (split across files to keep sizes manageable). `NOTE_ID` links
back to metadata / events / structured data.

**Structured** — `/MU/NICU/STRUCTURED_DATA_V1/`
`ENCOUNTER.csv` (billing + DRG), `CONDITION.csv`, `DEMOGRAPHIC.csv`,
`DIAGNOSIS.csv`, `LAB_RESULT_CM.csv`, `PRESCRIBING.csv`, `PROCEDURES.csv`,
`VITAL.csv`, `OBS_CLIN_NICU_ENTERAL_GI.csv` (feeding/GI tubes),
`OBS_CLIN_NICU_PAIN_SCORES.csv`, `OBS_CLIN_NICU_VENT.csv` (ventilation support).

## UIC — `/UIC/NICU/`
**Free-text notes** — `/UIC/NICU/260303_UIC_Deliverable/260303_UIC_Deliverable/delivery_20260302-165055.csv`

**Structured** — `/UIC/NICU/arpa_h_nicu_structured_deid/`
`arpa_h_nicu_demo_deid.csv`, `..._diagnoses_deid.csv`, `..._encounters_deid.csv`,
`..._labs_deid.csv`, `..._medication_deid.csv`, `..._note_services_deid.csv`
(summary of available records), `..._vitals_deid.csv`, `..._procedures_deid.csv`.

## Iowa — `/Iowa/NICU/` (richest: + nursing care plans, flowsheets, LDAs)
**Free-text notes** — `/Iowa/NICU/redacted_notes/NICUNotes_3REDACTED.csv`

**Structured** — `/Iowa/NICU/` (`*_date_shifted.csv`)
demographics (infant + maternal), diagnoses, encounters, labs, MAR (meds
administered), discharged medications, vitals, head circumference, newborn info
(birth measurements + APGAR), orders on inclusion encounters, outpatient
consults, problem list, procedures, `nicu_patient_journey_shifted.csv`
(encounter/note timeline), `ruca_drop_zip.csv` (rural/urban codes).

- **CarePlans** `/Iowa/NICU/CarePlans/` — Goals / Intervention / Problem
- **Flowsheets** `/Iowa/NICU/Flowsheets/` — many `*_dropped_comment.csv`
  (BloodAdmin, Intervene, Assess, MedVol, NICU_VS_RTV …)
- **LDAs** `/Iowa/NICU/LDAs/` — Lines, Drains & Airways (`nicu_LDAs_*.csv`)

---

## Loading (see `robocop.data`)
```python
from robocop import data, notes
data.inventory("Iowa")              # ground truth: files actually on disk
enc  = data.load("MU", "ENCOUNTER") # fuzzy single-file load
nt   = notes.normalize(data.load_notes("UIC"))  # tidy note_id / text
alln = data.load_all_notes()        # all sites, tagged with `site`
```
