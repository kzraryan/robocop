"""NICU clinical vocabulary + a fast regex entity extractor for free-text notes.

A curated, NICU-specific term list (conditions, devices, medications, scales).
Overlapping matches are resolved greedily by length so the longest span wins.
"""

from __future__ import annotations

import re

NICU_VOCAB: dict[str, list[str]] = {
    "respiratory distress syndrome": ["respiratory distress syndrome", "RDS", "hyaline membrane disease"],
    "bronchopulmonary dysplasia": ["bronchopulmonary dysplasia", "BPD", "chronic lung disease"],
    "necrotizing enterocolitis": ["necrotizing enterocolitis", "NEC"],
    "retinopathy of prematurity": ["retinopathy of prematurity", "ROP"],
    "sepsis": ["sepsis", "septic", "blood culture", "sepsis evaluation", "sepsis work-up"],
    "jaundice": ["jaundice", "hyperbilirubinemia", "bilirubin", "phototherapy"],
    "patent ductus arteriosus": ["patent ductus arteriosus", "PDA"],
    "apnea": ["apnea", "apnea of prematurity", "apnea and bradycardia", "bradycardia"],
    "desaturation": ["desaturation", "desaturations", "desat", "desats"],
    "anemia": ["anemia of prematurity", "anemia", "transfusion"],
    "intraventricular hemorrhage": ["intraventricular hemorrhage", "IVH", "cranial ultrasound"],
    "feeding intolerance": ["feeding intolerance", "gastric residuals", "abdominal distension", "abdominal girth"],
    "prematurity": ["prematurity", "preterm", "extreme immaturity"],
    "surfactant": ["surfactant", "poractant", "beractant"],
    "caffeine": ["caffeine", "caffeine citrate"],
    "ampicillin": ["ampicillin"],
    "gentamicin": ["gentamicin"],
    "furosemide": ["furosemide", "lasix"],
    "CPAP": ["CPAP", "continuous positive airway pressure"],
    "mechanical ventilation": ["mechanical ventilator", "mechanical ventilation", "intubation", "intubated"],
    "high flow nasal cannula": ["high flow nasal cannula", "HFNC", "high flow"],
    "PICC line": ["PICC line", "PICC", "central line"],
    "umbilical catheter": ["umbilical venous catheter", "UVC", "umbilical arterial catheter", "UAC"],
    "growth": ["weight gain", "growth curve", "enteral feeds", "fortification", "nutrition"],
    "NIPS": ["NIPS", "NIPS score"],
    "FLACC": ["FLACC"],
    "PIPP": ["PIPP"],
    "parental education": ["safe sleep", "discharge readiness", "feeding cues", "parental education"],
}

_COMPILED = [
    (canonical, re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE))
    for canonical, pats in NICU_VOCAB.items()
    for p in pats
]


def extract_entities(text: str) -> list[dict]:
    """Return non-overlapping entity spans: {canonical, mention, start, end}."""
    cands = []
    for canonical, rx in _COMPILED:
        for m in rx.finditer(text):
            cands.append(
                {"canonical": canonical, "mention": m.group(),
                 "start": m.start(), "end": m.end(), "len": m.end() - m.start()}
            )
    cands.sort(key=lambda c: (-c["len"], c["start"]))
    chosen, used = [], []
    for c in cands:
        if any(not (c["end"] <= s or c["start"] >= e) for s, e in used):
            continue
        chosen.append(c)
        used.append((c["start"], c["end"]))
    chosen.sort(key=lambda c: c["start"])
    return [{k: c[k] for k in ("canonical", "mention", "start", "end")} for c in chosen]
