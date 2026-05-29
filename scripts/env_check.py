#!/usr/bin/env python
"""Probe the runtime environment (run this on the server first).

Prints a JSON summary of Python, GPU, key packages, and Ollama availability so
you can confirm the conda env `hackathon` is active and the GPU/LLMs are live.

    python scripts/env_check.py
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import subprocess
import sys

PACKAGES = [
    "numpy", "pandas", "polars", "pyarrow", "duckdb", "sklearn", "lightgbm",
    "xgboost", "shap", "torch", "transformers", "sentence_transformers",
    "spacy", "nltk", "faiss", "rank_bm25", "langchain", "langchain_ollama",
    "ollama", "streamlit", "matplotlib", "plotly", "openpyxl",
]


def _pkg(name: str) -> dict:
    try:
        m = importlib.import_module(name)
        return {"ok": True, "version": getattr(m, "__version__", "unknown")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _gpu() -> dict:
    info: dict = {"torch_cuda": False}
    try:
        import torch

        info["torch_cuda"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["device"] = torch.cuda.get_device_name(0)
            info["count"] = torch.cuda.device_count()
    except Exception:
        pass
    return info


def main() -> None:
    report = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV", "<unset>"),
        "data_root": os.environ.get("CAIDF_DATA_ROOT", "/media/data/caidf_data"),
        "data_root_exists": os.path.isdir(
            os.environ.get("CAIDF_DATA_ROOT", "/media/data/caidf_data")
        ),
        "gpu": _gpu(),
        "ollama_port_11434": _port_open("localhost", 11434),
        "packages": {p: _pkg(p) for p in PACKAGES},
        "cli": {t: bool(shutil.which(t)) for t in ("git", "duckdb", "ollama", "nvidia-smi")},
    }
    try:
        from robocop import llm

        if llm.ping():
            report["ollama_models"] = llm.list_models()
    except Exception as e:  # noqa: BLE001
        report["ollama_models_error"] = str(e)[:120]

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
