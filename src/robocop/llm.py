"""Local LLM access via Ollama (the only LLM available on the server).

No external API keys — everything runs against the Ollama daemon on
``OLLAMA_HOST`` (default http://localhost:11434). Models pulled on the server
include gemma3:27b, qwen2.5-coder:32b, llama3.1:70b, deepseek-r1:32b, phi4,
llava (vision), and the embedding models mxbai-embed-large / nomic-embed-text.

Uses the lightweight ``ollama`` python client. ``langchain_ollama`` is also
installed if you prefer chains/agents.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import DEFAULT_CHAT_MODEL, DEFAULT_EMBED_MODEL, OLLAMA_HOST


@lru_cache(maxsize=1)
def _client():
    import ollama

    # OLLAMA_HOST may be a bare host:port or a full URL; the client accepts URLs.
    return ollama.Client(host=OLLAMA_HOST)


def list_models() -> list[str]:
    """Names of models currently available on the Ollama server."""
    resp = _client().list()
    models = resp.get("models", []) if isinstance(resp, dict) else resp.models
    out = []
    for m in models:
        name = m.get("model") or m.get("name") if isinstance(m, dict) else getattr(m, "model", None)
        if name:
            out.append(name)
    return out


def chat(
    prompt: str,
    *,
    model: str = DEFAULT_CHAT_MODEL,
    system: str | None = None,
    temperature: float = 0.2,
    **options: Any,
) -> str:
    """Single-turn chat completion. Returns the assistant's text.

    Low default temperature — for clinical/structured extraction you usually
    want determinism over creativity.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = _client().chat(
        model=model,
        messages=messages,
        options={"temperature": temperature, **options},
    )
    return resp["message"]["content"]


def generate(prompt: str, *, model: str = DEFAULT_CHAT_MODEL, **options: Any) -> str:
    """Raw completion (no chat template). Returns generated text."""
    resp = _client().generate(model=model, prompt=prompt, options=options or None)
    return resp["response"]


def embed(texts: str | list[str], *, model: str = DEFAULT_EMBED_MODEL) -> list[list[float]]:
    """Embed one or more texts with an Ollama embedding model.

    Returns a list of vectors (always a list, even for a single input).
    """
    single = isinstance(texts, str)
    items = [texts] if single else list(texts)
    resp = _client().embed(model=model, input=items)
    vectors = resp["embeddings"] if isinstance(resp, dict) else resp.embeddings
    return vectors


def ping() -> bool:
    """True if the Ollama server is reachable."""
    try:
        list_models()
        return True
    except Exception:
        return False
