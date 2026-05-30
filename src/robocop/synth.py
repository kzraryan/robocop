"""Generate synthetic, schema-faithful MU NICU data.

Everything here is fake (no PHI). Column names/types match
``resources/column_descriptions.txt`` exactly, and we deliberately reproduce the
documented quirks (null sentinels like ``/n`` / ``//N``, coded RX routes, etc.)
so LLM-written SQL is exercised realistically. ``NOTE.csv`` uses a layout we
define (the guide documents that notes exist + the 5 professions, but not their
columns).

Run via ``python -m robocop.synth`` or ``scripts/build_index.py``.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import config

NULL = "/n"      # documented numeric/text null sentinel
NULL2 = "//N"    # documented refills/freq null sentinel

# --- clinical vocabularies (small, NICU-flavored) -------------------------
SEXES = ["M", "F", "U"]
RACES = [1, 2, 3, 4, 5, 6]  # numeric codes per doc

DIAGNOSES = [
    ("Respiratory distress syndrome", "P22.0"),
    ("Necrotizing enterocolitis", "P77.9"),
    ("Extreme immaturity of newborn", "P07.21"),
    ("Other preterm infants", "P07.31"),
    ("Neonatal jaundice", "P59.9"),
    ("Patent ductus arteriosus", "Q25.0"),
    ("Bronchopulmonary dysplasia", "P27.1"),
    ("Sepsis of newborn", "P36.9"),
    ("Apnea of prematurity", "P28.4"),
    ("Retinopathy of prematurity", "H35.10"),
]
CONDITIONS = [
    ("Respiratory distress", 267036007),
    ("Feeding problem of newborn", 78164000),
    ("Neonatal apnea", 70944005),
    ("Anemia of prematurity", 234347009),
    ("Hyperbilirubinemia", 14783006),
]
LABS = [
    # RAW_LAB_NAME, LAB_LOINC, SPECIMEN_SOURCE, UNIT, (lo, hi)
    ("Total bilirubin", "1975-2", "Blood", "mg/dL", (3.0, 18.0)),
    ("C-reactive protein", "1988-5", "Blood", "mg/L", (0.1, 60.0)),
    ("Hemoglobin", "718-7", "Blood", "g/dL", (8.0, 19.0)),
    ("White blood cell count", "6690-2", "Blood", "10*3/uL", (3.0, 25.0)),
    ("Glucose", "2345-7", "Blood", "mg/dL", (35.0, 160.0)),
    ("Blood culture", "600-7", "Blood", None, None),       # qualitative -> null num
    ("Urine culture", "630-4", "Urine", None, None),
]
MEDS = [
    # RAW_RX_MED_NAME, route, dose, unit, freq
    ("Caffeine citrate", "Intravenous", 5.0, "mg", "Q24H"),
    ("Ampicillin", "Intravenous", 100.0, "mg", "Q12H"),
    ("Gentamicin", "Intravenous", 4.0, "mg", "Q24H"),
    ("Surfactant (poractant alfa)", "OT", 200.0, "mg", "NI"),
    ("Vitamin D", "Oral", 400.0, "unit", "Q24H"),
    ("Furosemide", "Intravenous", 1.0, "mg", "Q12H"),
]
PROCEDURES = [
    "Endotracheal intubation",
    "PICC line placement",
    "Umbilical venous catheter insertion",
    "Lumbar puncture",
    "Exchange transfusion",
    "Laser photocoagulation for ROP",
]
VENT_DEVICES = ["CPAP", "Mechanical Ventilator", "High Flow Nasal Cannula", "Nasal Cannula"]
VENT_RESULTS = ["Initiated", "Routine Check", "Changed Out", "Discontinued"]
GI_NAMES = ["Gastric Residuals", "Abdominal Girth", "Tube Placement Check", "Feeding Type"]
TUBES = ["Nasogastric / NG Tube", "Orogastric / OG Tube", "G-Tube"]
GI_RESULTS = ["Routine Checks", "Tube Inserted", "Verified", "Removed"]
PAIN_SCALES = ["NIPS Score Total", "FLACC Score", "PIPP"]


def _d(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# --- note generation ------------------------------------------------------
NOTE_THEMES = {
    "feeding_intolerance": (
        "Abdominal distension noted with increased gastric residuals. Feeds held "
        "and abdominal girth monitored. Concern for feeding intolerance; NEC ruled "
        "out by abdominal radiograph. Advanced enteral feeds slowly as tolerated."
    ),
    "respiratory": (
        "Frequent desaturations and apneic episodes overnight requiring increased "
        "FiO2. Currently on CPAP with good work of breathing. Plan to wean to high "
        "flow nasal cannula as respiratory status improves. Caffeine continued."
    ),
    "sepsis": (
        "Increased lethargy and temperature instability. Sepsis work-up initiated "
        "with blood culture, CBC, and CRP. Started empiric ampicillin and "
        "gentamicin pending culture results. Monitoring for clinical deterioration."
    ),
    "jaundice": (
        "Visible jaundice with rising total bilirubin. Phototherapy initiated and "
        "bilirubin trended every 12 hours. Hydration maintained. Will reassess need "
        "for exchange transfusion if levels continue to climb."
    ),
    "growth": (
        "Steady weight gain along growth curve. Tolerating full enteral feeds with "
        "fortification. Nutrition optimized; anthropometric measurements within "
        "expected range for corrected gestational age."
    ),
    "parental": (
        "Met with parents at bedside to discuss plan of care and discharge "
        "readiness. Provided education on safe sleep, feeding cues, and follow-up "
        "appointments. Family engaged and asking appropriate questions."
    ),
    "therapy": (
        "Bedside evaluation completed. Infant demonstrates improving tone and "
        "feeding coordination with non-nutritive sucking. Recommend continued "
        "developmental positioning and oral motor stimulation prior to feeds."
    ),
}

PROVIDER_STYLE = {
    "MD": ("Attending Progress Note", ["respiratory", "sepsis", "jaundice", "feeding_intolerance"]),
    "RN": ("Nursing Shift Note", ["respiratory", "feeding_intolerance", "growth", "parental"]),
    "OT": ("Occupational Therapy Note", ["therapy", "growth"]),
    "PT": ("Physical Therapy Note", ["therapy", "growth"]),
    "SLP": ("Speech-Language Pathology Note", ["therapy", "feeding_intolerance"]),
}


def _make_note_text(provider: str, ga_weeks: int, dol: int, rng: random.Random) -> str:
    title, themes = PROVIDER_STYLE[provider]
    chosen = rng.sample(themes, k=min(2, len(themes)))
    body = " ".join(NOTE_THEMES[t] for t in chosen)
    header = (
        f"{title}\n"
        f"Day of life {dol}, corrected gestational age ~{ga_weeks + dol // 7} weeks.\n\n"
        "Subjective/Assessment:\n"
    )
    plan = "\n\nPlan:\n- Continue current management and reassess on rounds."
    return header + body + plan


# --- main generator -------------------------------------------------------
def generate(n_patients: int = 150, seed: int = 7, out_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed)
    out_dir = Path(out_dir or config.RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    demo, enc, dx, cond, labs, rx, procs = [], [], [], [], [], [], []
    vitals, gi, pain, vent, notes = [], [], [], [], []

    base = datetime(2018, 1, 1)
    for i in range(n_patients):
        patid = f"MU{i + 1:05d}"
        # gestational age in days (doc: e.g. 275). NICU spans extreme prematurity
        # (~23 wk / 161 d) through term (~42 wk / 294 d).
        ga_days = rng.randint(161, 294)
        ga_weeks = ga_days // 7
        birth = base + timedelta(days=rng.randint(0, 2000), hours=rng.randint(0, 23))
        los = rng.randint(5, 90)               # length of stay (days)
        admit = birth + timedelta(hours=rng.randint(0, 12))
        discharge = admit + timedelta(days=los)
        encid = f"E{i + 1:06d}"

        demo.append(dict(PATID=patid, RACE=rng.choice(RACES), SEX=rng.choice(SEXES),
                         BIRTH_DATE=_d(birth), GESTATIONAL_AGE=ga_days))
        drg, drg_type = rng.choice([("790", "MS"), ("791", "MS"), ("793", "MS")])
        enc.append(dict(PATID=patid, ENC_TYPE="IP", ENCOUNTERID=encid,
                        ADMIT_DATE=_day(admit), DISCHARGE_DATE=_day(discharge),
                        DRG=drg, DRG_TYPE=drg_type))

        # diagnoses (1-4)
        for j, (name, code) in enumerate(rng.sample(DIAGNOSES, rng.randint(1, 4))):
            dxd = admit + timedelta(days=rng.randint(0, max(1, los // 2)))
            dx.append(dict(PATID=patid, ENCOUNTERID=encid, DIAGNOSISID=f"{encid}-DX{j}",
                           RAW_DIAGNOSIS_NAME=name, DX_DATE=_day(dxd), DX=code, DX_TYPE="10"))

        # conditions (1-3)
        for j, (name, code) in enumerate(rng.sample(CONDITIONS, rng.randint(1, 3))):
            rd = admit + timedelta(days=rng.randint(0, los))
            cond.append(dict(PATID=patid, CONDITIONID=f"{encid}-C{j}", RAW_CONDITION_NAME=name,
                             CONDITION=code, CONDITION_TYPE="SM ", REPORT_DATE=_day(rd)))

        # labs (several)
        for j in range(rng.randint(4, 12)):
            name, loinc, src, unit, rng_ = rng.choice(LABS)
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            if rng_ is None:  # qualitative -> null numeric + null unit
                num, ru = NULL, NULL
            else:
                num = round(rng.uniform(*rng_), 1)
                ru = unit
            labs.append(dict(PATID=patid, ENCOUNTERID=encid, LAB_RESULT_CM_ID=f"{encid}-L{j}",
                             LAB_LOINC=loinc, SPECIMEN_SOURCE=src, RAW_LAB_NAME=name,
                             RESULT_UNIT=ru, RESULT_NUM=num, SPECIMEN_DATE=_d(sd)))

        # meds (1-4)
        for j, (name, route, dose, unit, freq) in enumerate(rng.sample(MEDS, rng.randint(1, 4))):
            start = admit + timedelta(days=rng.randint(0, max(1, los - 3)))
            dur = rng.randint(2, 14)
            end = start + timedelta(days=dur)
            active = "Y" if end >= discharge else "N"
            rx.append(dict(PATID=patid, ENCOUNTERID=encid, PRESCRIBINGID=f"{encid}-RX{j}",
                           RAW_RX_MED_NAME=name, RX_START_DATE=_day(start), RX_END_DATE=_day(end),
                           RX_ROUTE=route, RX_DOSE_ORDERED=dose, RX_DOSE_ORDERED_UNIT=unit,
                           RX_QUANTITY=dose * dur, RX_REFILLS=NULL2, RX_FREQUENCY=freq,
                           ACTIVE_MEDICATION=active))

        # procedures (0-3)
        for j, name in enumerate(rng.sample(PROCEDURES, rng.randint(0, 3))):
            procs.append(dict(PATID=patid, ENCOUNTERID=encid, PROCEDURESID=f"{encid}-P{j}",
                              RAW_PROCEDURE_NAME=name))

        # vitals (daily-ish)
        wt = rng.uniform(0.6, 1.8)  # kg
        for day in range(0, los, rng.choice([1, 2])):
            md = admit + timedelta(days=day, hours=8)
            wt += rng.uniform(0.0, 0.03)
            vitals.append(dict(PATID=patid, ENCOUNTERID=encid, VITALID=f"{encid}-V{day}",
                               MEASURE_DATE=_d(md), SYSTOLIC=rng.randint(45, 80),
                               DIASTOLIC=rng.randint(25, 50), HT=round(rng.uniform(35, 50), 1),
                               WT=round(wt, 2)))

        # GI obs (0-5)
        for j in range(rng.randint(0, 5)):
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            gi.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-GI{j}",
                           OBSCLIN_CODE=f"GI{rng.randint(100, 199)}", OBSCLIN_START_DATE=_d(sd),
                           RAW_OBSCLIN_NAME=rng.choice(GI_NAMES), TUBE_NAME=rng.choice(TUBES),
                           OBSCLIN_RESULT=rng.choice(GI_RESULTS), RAW_OBSCLIN_RESULT=rng.choice(GI_RESULTS),
                           OBSCLIN_RESULT_UNIT="/N"))

        # pain scores (0-6)
        for j in range(rng.randint(0, 6)):
            sd = admit + timedelta(days=rng.randint(0, los))
            pain.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-PN{j}",
                             OBSCLIN_CODE=f"PN{rng.randint(100, 199)}", OBSCLIN_START_DATE=_day(sd),
                             RAW_OBSCLIN_NAME=rng.choice(PAIN_SCALES), OBSCLIN_RESULT=rng.randint(0, 10),
                             OBSCLIN_RESULT_UNIT="/N"))

        # vent obs (0-6)
        for j in range(rng.randint(0, 6)):
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            res = rng.choice(VENT_RESULTS)
            vent.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-VT{j}",
                             OBSCLIN_START_DATE=_d(sd), RAW_OBSCLIN_NAME=rng.choice(VENT_DEVICES),
                             OBSCLIN_RESULT=res, RAW_OBSCLIN_RESULT=res, OBSCLIN_RESULT_UNIT="/N"))

        # notes (3-8) across professions and the stay
        nnotes = rng.randint(3, 8)
        for j in range(nnotes):
            provider = rng.choice(list(PROVIDER_STYLE))
            dol = rng.randint(0, los)
            nd = admit + timedelta(days=dol)
            notes.append(dict(PATID=patid, ENCOUNTERID=encid, NOTEID=f"{encid}-N{j}",
                              NOTE_DATE=_day(nd), PROVIDER_TYPE=provider,
                              NOTE_TEXT=_make_note_text(provider, ga_weeks, dol, rng)))

    frames = {
        "DEMOGRAPHIC": pd.DataFrame(demo),
        "ENCOUNTER": pd.DataFrame(enc),
        "DIAGNOSIS": pd.DataFrame(dx),
        "CONDITION": pd.DataFrame(cond),
        "LAB_RESULT_CM": pd.DataFrame(labs),
        "PRESCRIBING": pd.DataFrame(rx),
        "PROCEDURES": pd.DataFrame(procs),
        "VITAL": pd.DataFrame(vitals),
        "OBS_CLIN_NICU_ENTERAL_GI": pd.DataFrame(gi),
        "OBS_CLIN_NICU_PAIN_SCORES": pd.DataFrame(pain),
        "OBS_CLIN_NICU_VENT": pd.DataFrame(vent),
        "NOTE": pd.DataFrame(notes),
    }
    return frames


def write_csvs(frames: dict[str, pd.DataFrame], out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    return out_dir


def main(n_patients: int = 150, seed: int = 7) -> None:
    config.ensure_dirs()
    frames = generate(n_patients=n_patients, seed=seed)
    out = write_csvs(frames)
    total = sum(len(d) for d in frames.values())
    print(f"Wrote {len(frames)} CSVs ({total} rows) to {out}")
    for name, df in frames.items():
        print(f"  {name:28s} {len(df):6d} rows")


if __name__ == "__main__":  # pragma: no cover
    main()
