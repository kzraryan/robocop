# Server environment (`hackathon-gi`)

Confirmed snapshot of the hackathon compute. Re-check anytime with
`python scripts/env_check.py`.

## Hardware
- **GPU:** 1× NVIDIA A100 80GB (CUDA, `torch.cuda` available)
- **CPU/RAM:** 24 cores · ~216 GB RAM
- Disk free: ~38 GB (keep large derived artifacts out of git / tidy up)

## Python
- Conda env **`hackathon`**, Python **3.11**, at `/opt/conda/envs/hackathon`
- Activate before working: `conda activate hackathon`

## LLMs — local only (Ollama)
No external LLM API clients are installed (no `openai`, no `anthropic`).
Everything goes through **Ollama on `localhost:11434`**. Models pulled include:

- General: `gemma3:27b`, `gemma3:12b`, `llama3.1:70b`, `llama3.1:8b`, `phi4`, `mistral:7b`
- Reasoning: `deepseek-r1:32b` / `:14b`
- Coding: `qwen2.5-coder:32b` / `:14b` / `:7b`, `qwen3-coder:30b`
- Vision: `llava:13b`, `llava:7b`
- Embeddings: `mxbai-embed-large`, `nomic-embed-text`

Helpers: `robocop.llm` (chat / generate / embed / list_models / ping).
`langchain` + `langchain-ollama` + `langgraph` are also installed.

## Key packages (all preinstalled — don't `pip install` over the env)
- Data: pandas 2.3, polars 1.40, pyarrow, **duckdb 1.5**, openpyxl (xlsx)
- ML: scikit-learn 1.8, xgboost, lightgbm, statsmodels, imbalanced-learn, **shap**
- DL/NLP: torch 2.6+cu124, transformers 4.57, **sentence-transformers**, spacy 3.8
  (no models downloaded yet), nltk, gensim, flair, spark-nlp
- Retrieval/vector: **faiss**, **rank-bm25** (no chroma/qdrant/weaviate)
- Graph: networkx
- App/viz: **streamlit 1.56**, panel, plotly, altair, bokeh, matplotlib, seaborn
- Web: fastapi, flask, uvicorn

## Not present (plan around these)
catboost, optuna, lifelines/sksurv, scispacy, medcat, presidio, pyhealth,
gradio (broken), dash, chromadb, qdrant, openai/anthropic clients,
psycopg/pymongo/redis python drivers. Postgres/Neo4j daemons are **not** running.

## Workflow
Write & commit on your laptop → `git pull` on the server → run there (data + GPU
live on the server). See the top-level `README.md`.
