"""Minimal Ollama chat helpers (stdlib only) for chat, RAG answers, and JSON
entity extraction. Streaming is supported by reading newline-delimited JSON from
``/api/chat``. No provider SDK required."""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Iterator

from . import config


def _post(path: str, payload: dict, host: str, timeout: int = 300):
    req = urllib.request.Request(
        f"{host.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (trusted localhost)


def chat(
    messages: list[dict],
    model: str | None = None,
    host: str | None = None,
    temperature: float = 0.2,
) -> str:
    payload = {"model": model or config.CODER_MODEL, "messages": messages,
               "stream": False, "options": {"temperature": temperature}}
    with _post("/api/chat", payload, host or config.OLLAMA_HOST) as resp:
        return json.loads(resp.read().decode("utf-8"))["message"]["content"]


def chat_stream(
    messages: list[dict],
    model: str | None = None,
    host: str | None = None,
    temperature: float = 0.2,
) -> Iterator[str]:
    payload = {"model": model or config.CODER_MODEL, "messages": messages,
               "stream": True, "options": {"temperature": temperature}}
    with _post("/api/chat", payload, host or config.OLLAMA_HOST) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line.decode("utf-8"))
            piece = obj.get("message", {}).get("content", "")
            if piece:
                yield piece
            if obj.get("done"):
                break


def list_models(host: str | None = None) -> list[str]:
    try:
        req = urllib.request.Request(f"{(host or config.OLLAMA_HOST).rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return sorted(m["model"] for m in data.get("models", []))
    except Exception:  # noqa: BLE001 - server may be down
        return []


# --- task helpers ---------------------------------------------------------
_RAG_SYSTEM = (
    "You are a neonatology clinical assistant. Answer ONLY from the provided "
    "patient notes. Cite the patient ID and note date for each claim (e.g. "
    "'MU00012, 2020-03-04'). If the notes do not contain the answer, say so."
)


def rag_messages(question: str, contexts: list[dict]) -> list[dict]:
    """contexts: list of {patid, note_date, provider_type, text}."""
    blocks = [
        f"[{c['patid']} · {c['note_date']} · {c.get('provider_type','')}]\n{c['text']}"
        for c in contexts
    ]
    user = f"Question: {question}\n\nPatient notes:\n" + "\n\n".join(blocks) + "\n\nAnswer:"
    return [{"role": "system", "content": _RAG_SYSTEM},
            {"role": "user", "content": user}]


_EXTRACT_SYSTEM = "You are a clinical NLP system for NICU notes. Output JSON only."


def extract_entities_llm(note: str, model: str | None = None, host: str | None = None) -> list[dict]:
    prompt = (
        "Extract clinical entities from the NICU note. Return ONLY a JSON array "
        "(no prose, no markdown). Each item has keys: 'text' (verbatim span), "
        "'type' (condition|medication|device|finding), 'canonical' (normalized).\n\n"
        f"Note: {note}"
    )
    raw = chat(
        [{"role": "system", "content": _EXTRACT_SYSTEM},
         {"role": "user", "content": prompt}],
        model=model, host=host, temperature=0.0,
    )
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
