"""Natural-language -> DuckDB SQL using a local Ollama coding model, grounded in
the column descriptions. The model only proposes SQL; we validate it (read-only,
single SELECT) before executing.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

import pandas as pd

from . import config
from .schema import schema_prompt

# Statement-level keywords that must never appear (word-boundary matched).
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|"
    r"export|import|install|load|call|replace|truncate|grant|revoke|vacuum|"
    r"reindex|merge)\b",
    re.IGNORECASE,
)
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_LIMIT = re.compile(r"\blimit\b", re.IGNORECASE)


class SQLValidationError(ValueError):
    """Raised when generated/edited SQL is not a safe single SELECT."""


@dataclass
class SQLResult:
    sql: str            # the validated, ready-to-run SQL
    df: pd.DataFrame
    row_count: int


def _strip_fences(text: str) -> str:
    m = _FENCE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def validate_sql(sql: str, limit: int | None = None) -> str:
    """Return a safe, single-statement SELECT (LIMIT appended if missing).

    Raises ``SQLValidationError`` otherwise. This is pure/testable (no DB, no LLM).
    """
    if limit is None:
        limit = config.DEFAULT_SQL_LIMIT

    sql = _strip_fences(sql)
    # Drop trailing semicolons / whitespace, reject multiple statements.
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise SQLValidationError("Empty query.")
    # Multiple statements? (a ';' followed by more non-space content)
    if ";" in sql:
        remainder = sql.split(";", 1)[1].strip()
        if remainder:
            raise SQLValidationError("Only a single statement is allowed.")
        sql = sql.split(";", 1)[0].strip()

    head = sql.lstrip("(").lower()
    if not (head.startswith("select") or head.startswith("with")):
        raise SQLValidationError("Only read-only SELECT/WITH queries are allowed.")

    forbidden = _FORBIDDEN.search(sql)
    if forbidden:
        raise SQLValidationError(f"Disallowed keyword: {forbidden.group(0).upper()}")

    if not _LIMIT.search(sql):
        sql = f"{sql}\nLIMIT {limit}"
    return sql


def _ollama_chat(system: str, user: str, model: str, host: str, temperature: float) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 (trusted localhost)
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"]


_SYSTEM = """You are an expert DuckDB SQL engineer for a NICU clinical dataset.
Rules:
- Output ONLY a single read-only SQL SELECT query. No prose, no explanation.
- Use ONLY the tables and columns from the provided schema. Reference tables by
  their bare name (the search_path is already set).
- Honor the per-column NOTE hints. In particular: columns may contain the null
  sentinels '/n', '//n' or '//N' (text), so cast/guard before numeric math, e.g.
  TRY_CAST(RESULT_NUM AS DOUBLE) and WHERE RESULT_NUM NOT IN ('/n','//n','//N').
- Dates are stored as text; use strptime()/TRY_CAST when comparing.
- Prefer standardized codes (LAB_LOINC, DX, CONDITION) for deterministic matching
  and RAW_* text columns (ILIKE '%...%') for free-text physician prompts.
- Always include a reasonable LIMIT."""


def build_user_prompt(question: str) -> str:
    return f"Schema:\n{schema_prompt()}\n\nQuestion: {question}\n\nSQL:"


def generate_sql(
    question: str,
    model: str | None = None,
    host: str | None = None,
    temperature: float = 0.0,
) -> str:
    """Ask the local coding model for SQL and return the validated query."""
    raw = _ollama_chat(
        _SYSTEM,
        build_user_prompt(question),
        model or config.CODER_MODEL,
        host or config.OLLAMA_HOST,
        temperature,
    )
    return validate_sql(raw)


def run_sql(sql: str, con, limit: int | None = None) -> SQLResult:
    """Validate then execute ``sql`` on a DuckDB connection -> SQLResult."""
    safe = validate_sql(sql, limit=limit)
    df = con.execute(safe).fetchdf()
    return SQLResult(sql=safe, df=df, row_count=len(df))
