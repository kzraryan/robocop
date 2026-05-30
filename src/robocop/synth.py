"""Generate synthetic, schema-faithful MU NICU data with *coherent* clinical
signal: gestational age drives length of stay, diagnoses, medications,
ventilation, and note content. That coherence is what makes the downstream
similarity / risk / phenotype-graph features actually meaningful.

Everything here is fake (no PHI). Column names/types match
``resources/column_descriptions.txt`` exactly, and we deliberately reproduce the
documented quirks (null sentinels ``/n`` / ``//N``, coded RX routes, etc.).
``NOTE.csv`` uses a layout we define (the guide documents that notes exist + the
five professions, but not their columns).

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

SEXES = ["M", "F"]
RACES = [1, 2, 3, 4, 5, 6]

# Diagnosis catalog: (raw name, ICD-10, condition-key it maps to)
DX_BY_KEY = {
    "RDS": ("Respiratory distress syndrome of newborn", "P22.0"),
    "BPD": ("Bronchopulmonary dysplasia", "P27.1"),
    "NEC": ("Necrotizing enterocolitis of newborn", "P77.9"),
    "ROP": ("Retinopathy of prematurity", "H35.10"),
    "SEPSIS": ("Bacterial sepsis of newborn", "P36.9"),
    "JAUNDICE": ("Neonatal jaundice, unspecified", "P59.9"),
    "PDA": ("Patent ductus arteriosus", "Q25.0"),
    "APNEA": ("Primary apnea of newborn", "P28.4"),
    "ANEMIA": ("Anemia of prematurity", "P61.2"),
    "IVH": ("Intraventricular hemorrhage of newborn", "P52.3"),
}
# Prematurity code by GA band (ICD-10 P07.x).
def _prematurity_dx(ga_weeks: int) -> tuple[str, str]:
    if ga_weeks < 28:
        return ("Extreme immaturity of newborn", "P07.21")
    if ga_weeks < 32:
        return ("Other preterm newborn, 28-31 weeks", "P07.31")
    if ga_weeks < 37:
        return ("Other preterm newborn, 32-36 weeks", "P07.39")
    return ("Newborn, gestation 37 weeks or more", "Z38.00")

CONDITION_SNOMED = {
    "RDS": ("Respiratory distress", 267036007),
    "APNEA": ("Neonatal apnea", 70944005),
    "ANEMIA": ("Anemia of prematurity", 234347009),
    "JAUNDICE": ("Neonatal hyperbilirubinemia", 14783006),
    "NEC": ("Feeding problem of newborn", 78164000),
}

LABS = [
    # RAW_LAB_NAME, LAB_LOINC, SPECIMEN_SOURCE, UNIT, (lo, hi)
    ("Total bilirubin", "1975-2", "Blood", "mg/dL", (3.0, 18.0)),
    ("C-reactive protein", "1988-5", "Blood", "mg/L", (0.1, 60.0)),
    ("Hemoglobin", "718-7", "Blood", "g/dL", (8.0, 19.0)),
    ("White blood cell count", "6690-2", "Blood", "10*3/uL", (3.0, 25.0)),
    ("Glucose", "2345-7", "Blood", "mg/dL", (35.0, 160.0)),
    ("Blood culture", "600-7", "Blood", None, None),  # qualitative -> null num
    ("Urine culture", "630-4", "Urine", None, None),
]
# Medications keyed by the condition that triggers them.
MED_BY_KEY = {
    "APNEA": ("Caffeine citrate", "Intravenous", 5.0, "mg", "Q24H"),
    "RDS": ("Surfactant (poractant alfa)", "OT", 200.0, "mg", "NI"),
    "SEPSIS_A": ("Ampicillin", "Intravenous", 100.0, "mg", "Q12H"),
    "SEPSIS_G": ("Gentamicin", "Intravenous", 4.0, "mg", "Q24H"),
    "BPD": ("Furosemide", "Intravenous", 1.0, "mg", "Q12H"),
    "ROUTINE": ("Vitamin D", "Oral", 400.0, "unit", "Q24H"),
}
VENT_DEVICES = ["CPAP", "Mechanical Ventilator", "High Flow Nasal Cannula", "Nasal Cannula"]
VENT_RESULTS = ["Initiated", "Routine Check", "Changed Out", "Discontinued"]
GI_NAMES = ["Gastric Residuals", "Abdominal Girth", "Tube Placement Check", "Feeding Type"]
TUBES = ["Nasogastric / NG Tube", "Orogastric / OG Tube", "G-Tube"]
GI_RESULTS = ["Routine Checks", "Tube Inserted", "Verified", "Removed"]
PAIN_SCALES = ["NIPS Score Total", "FLACC Score", "PIPP"]

GA_WEEK_CHOICES = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 38, 40]
GA_WEEK_WEIGHTS = [3, 4, 5, 6, 7, 7, 8, 8, 9, 8, 7, 6, 6, 5, 4]


def _d(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _p(rng: random.Random, prob: float) -> bool:
    return rng.random() < prob


def _conditions_for(ga_weeks: int, rng: random.Random) -> dict[str, bool]:
    """Sample comorbidities; preterm infants are far more likely to have them."""
    prem = max(0, 34 - ga_weeks)  # 0 for >=34w, up to 10 for 24w
    f = prem / 10.0               # 0..1 prematurity factor
    return {
        "RDS": _p(rng, 0.15 + 0.8 * f),
        "BPD": _p(rng, 0.02 + 0.6 * f) if ga_weeks < 32 else False,
        "NEC": _p(rng, 0.02 + 0.25 * f),
        "ROP": _p(rng, 0.6 * f) if ga_weeks < 31 else False,
        "SEPSIS": _p(rng, 0.08 + 0.3 * f),
        "JAUNDICE": _p(rng, 0.45 + 0.3 * f),
        "PDA": _p(rng, 0.05 + 0.5 * f) if ga_weeks < 32 else False,
        "APNEA": _p(rng, 0.1 + 0.7 * f) if ga_weeks < 34 else False,
        "ANEMIA": _p(rng, 0.05 + 0.5 * f),
        "IVH": _p(rng, 0.4 * f) if ga_weeks < 30 else False,
    }


# --- note generation ------------------------------------------------------
NOTE_THEMES = {
    "RDS": "Increased work of breathing with grunting and retractions; chest x-ray "
           "consistent with respiratory distress syndrome. Surfactant administered "
           "and respiratory support escalated.",
    "BPD": "Chronic oxygen requirement persists at corrected gestational age; "
           "evolving bronchopulmonary dysplasia. Diuretics continued and slow "
           "respiratory weaning planned.",
    "APNEA": "Frequent apnea and bradycardia spells with desaturations overnight. "
             "Caffeine therapy continued; episodes monitored on cardiorespiratory "
             "monitor.",
    "NEC": "Abdominal distension with increased gastric residuals and bloody stool; "
           "feeds held and necrotizing enterocolitis work-up initiated with serial "
           "abdominal radiographs. Bowel rest and antibiotics started.",
    "SEPSIS": "Temperature instability and lethargy prompted a sepsis evaluation "
              "with blood culture, CBC, and CRP. Empiric ampicillin and gentamicin "
              "started pending cultures.",
    "JAUNDICE": "Visible jaundice with rising total bilirubin. Phototherapy "
                "initiated and bilirubin trended; reassessing need for escalation.",
    "PDA": "Murmur with widened pulse pressure; echocardiogram confirmed a patent "
           "ductus arteriosus. Fluid management optimized and cardiology consulted.",
    "ROP": "Retinopathy of prematurity screening exam completed by ophthalmology; "
           "findings documented and follow-up interval set.",
    "ANEMIA": "Anemia of prematurity with low hemoglobin; iron supplementation "
              "continued and transfusion threshold reviewed.",
    "IVH": "Cranial ultrasound performed to evaluate for intraventricular "
           "hemorrhage; results reviewed with the family.",
    "growth": "Steady weight gain along the growth curve, tolerating fortified "
              "enteral feeds. Nutrition optimized for corrected gestational age.",
    "parental": "Met with parents at bedside to discuss the plan of care and "
                "discharge readiness, with education on safe sleep and feeding cues.",
    "therapy": "Bedside developmental evaluation; improving tone and feeding "
               "coordination with non-nutritive sucking. Continue positioning and "
               "oral motor stimulation.",
}
PROVIDER_TITLE = {
    "MD": "Attending Neonatology Progress Note",
    "RN": "Nursing Shift Note",
    "OT": "Occupational Therapy Note",
    "PT": "Physical Therapy Note",
    "SLP": "Speech-Language Pathology Note",
}
# Which themes each profession tends to write about.
PROVIDER_FOCUS = {
    "MD": ["RDS", "BPD", "SEPSIS", "NEC", "PDA", "JAUNDICE", "APNEA", "ROP", "IVH", "ANEMIA"],
    "RN": ["APNEA", "JAUNDICE", "NEC", "growth", "parental"],
    "OT": ["therapy", "growth"],
    "PT": ["therapy", "growth"],
    "SLP": ["therapy", "NEC"],
}


def _make_note_text(provider: str, ga_weeks: int, dol: int, active: list[str],
                    rng: random.Random) -> str:
    title = PROVIDER_TITLE[provider]
    focus = [k for k in PROVIDER_FOCUS[provider] if k in active or k in ("growth", "parental", "therapy")]
    if not focus:
        focus = ["growth"]
    chosen = rng.sample(focus, k=min(2, len(focus)))
    body = " ".join(NOTE_THEMES[t] for t in chosen)
    cga = ga_weeks + dol // 7
    header = (
        f"{title}\nDay of life {dol}, corrected gestational age ~{cga} weeks.\n\n"
        "Assessment:\n"
    )
    return header + body + "\n\nPlan:\n- Continue current management and reassess on rounds."


# --- main generator -------------------------------------------------------
def generate(n_patients: int = 200, seed: int = 7, out_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed)
    out_dir = Path(out_dir or config.RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    demo, enc, dx, cond, labs, rx, procs = [], [], [], [], [], [], []
    vitals, gi, pain, vent, notes = [], [], [], [], []

    base = datetime(2018, 1, 1)
    for i in range(n_patients):
        patid = f"MU{i + 1:05d}"
        ga_weeks = rng.choices(GA_WEEK_CHOICES, weights=GA_WEEK_WEIGHTS, k=1)[0]
        ga_days = ga_weeks * 7 + rng.randint(0, 6)
        conds = _conditions_for(ga_weeks, rng)
        n_comorbid = sum(conds.values())

        # length of stay driven by prematurity + comorbidity burden
        mu_los = 3 + (40 - ga_weeks) * 2.6 + n_comorbid * 2.5
        los = int(max(3, min(160, rng.normalvariate(mu_los, mu_los * 0.25))))

        birth = base + timedelta(days=rng.randint(0, 2000), hours=rng.randint(0, 23))
        admit = birth + timedelta(hours=rng.randint(0, 12))
        discharge = admit + timedelta(days=los)
        encid = f"E{i + 1:06d}"

        demo.append(dict(PATID=patid, RACE=rng.choice(RACES), SEX=rng.choice(SEXES),
                         BIRTH_DATE=_d(birth), GESTATIONAL_AGE=ga_days))

        # DRG by severity
        if ga_weeks < 28:
            drg = "790"
        elif n_comorbid >= 2:
            drg = "791"
        elif ga_weeks < 37:
            drg = "792"
        elif n_comorbid >= 1:
            drg = "793"
        else:
            drg = "795"
        enc.append(dict(PATID=patid, ENC_TYPE="IP", ENCOUNTERID=encid,
                        ADMIT_DATE=_day(admit), DISCHARGE_DATE=_day(discharge),
                        DRG=drg, DRG_TYPE="MS"))

        # prematurity diagnosis (always) + comorbidity diagnoses
        pname, pcode = _prematurity_dx(ga_weeks)
        dx_keys = [("PREM", pname, pcode)]
        for key, present in conds.items():
            if present:
                name, code = DX_BY_KEY[key]
                dx_keys.append((key, name, code))
        for j, (key, name, code) in enumerate(dx_keys):
            dxd = admit + timedelta(days=rng.randint(0, max(1, los // 2)))
            dtype = "10" if code[0] in "PQHZ" else "10"
            dx.append(dict(PATID=patid, ENCOUNTERID=encid, DIAGNOSISID=f"{encid}-DX{j}",
                           RAW_DIAGNOSIS_NAME=name, DX_DATE=_day(dxd), DX=code, DX_TYPE=dtype))

        # SNOMED conditions for a subset of present comorbidities
        cj = 0
        for key, (name, code) in CONDITION_SNOMED.items():
            if conds.get(key):
                rd = admit + timedelta(days=rng.randint(0, los))
                cond.append(dict(PATID=patid, CONDITIONID=f"{encid}-C{cj}",
                                 RAW_CONDITION_NAME=name, CONDITION=code,
                                 CONDITION_TYPE="SM ", REPORT_DATE=_day(rd)))
                cj += 1

        # labs: more draws for sicker infants; bilirubin biased up if jaundice, CRP up if sepsis
        n_labs = rng.randint(4, 8) + n_comorbid * 2
        for j in range(n_labs):
            name, loinc, src, unit, lohi = rng.choice(LABS)
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            if lohi is None:
                num, ru = NULL, NULL
            else:
                lo, hi = lohi
                if name == "Total bilirubin" and conds["JAUNDICE"]:
                    lo = 10.0
                if name == "C-reactive protein" and conds["SEPSIS"]:
                    lo = 20.0
                if name == "Hemoglobin" and conds["ANEMIA"]:
                    hi = 12.0
                num, ru = round(rng.uniform(lo, hi), 1), unit
            labs.append(dict(PATID=patid, ENCOUNTERID=encid, LAB_RESULT_CM_ID=f"{encid}-L{j}",
                             LAB_LOINC=loinc, SPECIMEN_SOURCE=src, RAW_LAB_NAME=name,
                             RESULT_UNIT=ru, RESULT_NUM=num, SPECIMEN_DATE=_d(sd)))

        # medications tied to conditions
        med_keys = ["ROUTINE"]
        if conds["APNEA"]:
            med_keys.append("APNEA")
        if conds["RDS"]:
            med_keys.append("RDS")
        if conds["SEPSIS"]:
            med_keys += ["SEPSIS_A", "SEPSIS_G"]
        if conds["BPD"]:
            med_keys.append("BPD")
        for j, mk in enumerate(med_keys):
            name, route, dose, unit, freq = MED_BY_KEY[mk]
            start = admit + timedelta(days=rng.randint(0, max(1, los - 3)))
            dur = rng.randint(2, 14)
            end = start + timedelta(days=dur)
            rx.append(dict(PATID=patid, ENCOUNTERID=encid, PRESCRIBINGID=f"{encid}-RX{j}",
                           RAW_RX_MED_NAME=name, RX_START_DATE=_day(start), RX_END_DATE=_day(end),
                           RX_ROUTE=route, RX_DOSE_ORDERED=dose, RX_DOSE_ORDERED_UNIT=unit,
                           RX_QUANTITY=dose * dur, RX_REFILLS=NULL2, RX_FREQUENCY=freq,
                           ACTIVE_MEDICATION="Y" if end >= discharge else "N"))

        # procedures tied to conditions
        proc_list = []
        if conds["RDS"]:
            proc_list.append("Endotracheal intubation")
        if los > 21:
            proc_list.append("PICC line placement")
        if conds["ROP"] and _p(rng, 0.5):
            proc_list.append("Laser photocoagulation for ROP")
        if conds["SEPSIS"] and _p(rng, 0.5):
            proc_list.append("Lumbar puncture")
        if conds["JAUNDICE"] and _p(rng, 0.2):
            proc_list.append("Exchange transfusion")
        for j, name in enumerate(proc_list):
            procs.append(dict(PATID=patid, ENCOUNTERID=encid, PROCEDURESID=f"{encid}-P{j}",
                              RAW_PROCEDURE_NAME=name))

        # vitals: weight curve grows from a GA-appropriate birth weight
        bw = round(0.5 + (ga_weeks - 23) * 0.11 + rng.uniform(-0.1, 0.1), 2)  # kg
        wt = max(0.4, bw)
        for day in range(0, los, rng.choice([1, 2])):
            md = admit + timedelta(days=day, hours=8)
            wt += rng.uniform(0.005, 0.025)
            vitals.append(dict(PATID=patid, ENCOUNTERID=encid, VITALID=f"{encid}-V{day}",
                               MEASURE_DATE=_d(md), SYSTOLIC=rng.randint(45, 80),
                               DIASTOLIC=rng.randint(25, 50),
                               HT=round(30 + (ga_weeks - 23) * 1.1 + day * 0.05, 1),
                               WT=round(wt, 2)))

        # vent events scale with respiratory burden
        n_vent = (4 if conds["RDS"] else 0) + (3 if conds["BPD"] else 0) + (2 if conds["APNEA"] else 0)
        for j in range(rng.randint(0, max(1, n_vent))):
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            dev = "Mechanical Ventilator" if conds["RDS"] and j == 0 else rng.choice(VENT_DEVICES)
            res = VENT_RESULTS[0] if j == 0 else rng.choice(VENT_RESULTS)
            vent.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-VT{j}",
                             OBSCLIN_START_DATE=_d(sd), RAW_OBSCLIN_NAME=dev,
                             OBSCLIN_RESULT=res, RAW_OBSCLIN_RESULT=res, OBSCLIN_RESULT_UNIT="/N"))

        # GI/enteral feeding observations (more if NEC/feeding issues)
        n_gi = rng.randint(0, 3) + (3 if conds["NEC"] else 0)
        for j in range(n_gi):
            sd = admit + timedelta(days=rng.randint(0, los), hours=rng.randint(0, 23))
            gi.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-GI{j}",
                           OBSCLIN_CODE=f"GI{rng.randint(100, 199)}", OBSCLIN_START_DATE=_d(sd),
                           RAW_OBSCLIN_NAME=rng.choice(GI_NAMES), TUBE_NAME=rng.choice(TUBES),
                           OBSCLIN_RESULT=rng.choice(GI_RESULTS), RAW_OBSCLIN_RESULT=rng.choice(GI_RESULTS),
                           OBSCLIN_RESULT_UNIT="/N"))

        # pain scores
        for j in range(rng.randint(0, 4) + len(proc_list)):
            sd = admit + timedelta(days=rng.randint(0, los))
            pain.append(dict(PATID=patid, ENCOUNTERID=encid, OBSCLINID=f"{encid}-PN{j}",
                             OBSCLIN_CODE=f"PN{rng.randint(100, 199)}", OBSCLIN_START_DATE=_day(sd),
                             RAW_OBSCLIN_NAME=rng.choice(PAIN_SCALES), OBSCLIN_RESULT=rng.randint(0, 10),
                             OBSCLIN_RESULT_UNIT="/N"))

        # notes across professions and the stay, themed by the infant's conditions
        active = [k for k, v in conds.items() if v]
        nnotes = rng.randint(3, 6) + n_comorbid
        for j in range(nnotes):
            provider = rng.choices(list(PROVIDER_TITLE), weights=[5, 6, 2, 2, 2], k=1)[0]
            dol = rng.randint(0, los)
            nd = admit + timedelta(days=dol)
            notes.append(dict(PATID=patid, ENCOUNTERID=encid, NOTEID=f"{encid}-N{j}",
                              NOTE_DATE=_day(nd), PROVIDER_TYPE=provider,
                              NOTE_TEXT=_make_note_text(provider, ga_weeks, dol, active, rng)))

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


def main(n_patients: int = 200, seed: int = 7) -> None:
    config.ensure_dirs()
    frames = generate(n_patients=n_patients, seed=seed)
    out = write_csvs(frames)
    total = sum(len(d) for d in frames.values())
    print(f"Wrote {len(frames)} CSVs ({total} rows) to {out}")
    for name, df in frames.items():
        print(f"  {name:28s} {len(df):6d} rows")


if __name__ == "__main__":  # pragma: no cover
    main()
