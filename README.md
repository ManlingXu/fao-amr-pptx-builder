# FAO AMR Knowledge Assistant

An English-language RAG chatbot for FAO antimicrobial resistance (AMR) documents. The app indexes FAO AMR reports, webpages, and uploaded internal files, then answers questions with document-grounded citations.

## What it does

- Ingests PDF, HTML, Markdown, and plain text documents.
- Stores searchable chunks in a local SQLite FTS5 knowledge base.
- Provides a web chat interface for English Q&A.
- Returns cited source snippets for every answer.
- Supports three answer providers:
  - `extractive`: no LLM required; returns grounded evidence from indexed documents.
  - `ollama`: local open-source model through Ollama.
  - `openai`: OpenAI Responses API through a backend-held API key.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
python scripts\ingest_sample.py
uvicorn amr_rag.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Configure the model provider

Edit `.env`:

```env
MODEL_PROVIDER=extractive
```

For Ollama:

```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

For OpenAI:

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.5
```

Keep the OpenAI key on the server only. Do not commit it to GitHub or expose it in browser code.

## Ingest FAO sources

The starter source list lives in `data/sources/fao_amr_sources.json`.

```powershell
python scripts\ingest_sources.py --default
```

You can also upload internal FAO documents from the web UI.

## Suggested internal deployment path

For an internal FAO pilot, start with `extractive` or `ollama` in a closed network. If FAO security policy permits approved external model APIs, switch `MODEL_PROVIDER` to `openai` on the backend server. The retrieval layer stays the same either way.

## Repository layout

```text
src/amr_rag/          Python app, ingestion, search, providers
static/               English web chat UI
scripts/              CLI ingestion helpers
data/sources/         Seed source metadata
data/sample_docs/     Small starter document for local testing
tests/                Retrieval tests
```

## FAO AMR PPTX Builder Skill

This repository includes a shareable Codex skill at `skills/fao-amr-pptx-builder/`.

Use it when you want Codex to create an editable PowerPoint draft from repeated FAO AMR materials:

```text
Use the FAO AMR PPTX builder to give me a PPT of AMR history in FAO using this template and the materials in my local OneDrive AMR folder.
```

For v1, OneDrive materials must be available as a synced local folder. The skill does not connect directly to Microsoft Graph or OneDrive cloud APIs.

The generated output includes:

- `draft.pptx` - editable PowerPoint deck
- `deck_plan.json` - slide-by-slide plan
- `source_map.json` - source traceability per slide
