#!/usr/bin/env python
"""End-to-end smoke test: data is reachable, notes load, Ollama answers.

    python scripts/smoke_test.py

Safe to run repeatedly. Loads only a small sample of notes and asks the LLM a
trivial question, so it's fast and won't hammer the GPU.
"""

from __future__ import annotations

from robocop import SITES, data, llm, notes
from robocop.config import DATA_ROOT


def main() -> int:
    ok = True

    print(f"[1] DATA_ROOT={DATA_ROOT} exists={DATA_ROOT.exists()}")
    if not DATA_ROOT.exists():
        print("    !! data root missing — set CAIDF_DATA_ROOT or run on the server")
        ok = False

    for site in SITES:
        inv = data.inventory(site)
        print(f"[2] {site}: {len(inv)} files on disk")

    for site in SITES:
        try:
            df = data.load_notes(site)
            ndf = notes.normalize(df) if len(df) else df
            print(f"[3] {site}: loaded {len(df)} note rows -> {len(ndf)} non-empty")
        except Exception as e:  # noqa: BLE001
            print(f"[3] {site}: notes load failed: {e}")

    print(f"[4] Ollama reachable: {llm.ping()}")
    if llm.ping():
        print(f"    models: {', '.join(llm.list_models()[:8])} ...")
        reply = llm.chat("Reply with the single word: ready", temperature=0)
        print(f"    chat sanity -> {reply.strip()[:60]!r}")

    print("\nSMOKE TEST:", "PASS" if ok else "CHECK WARNINGS ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
