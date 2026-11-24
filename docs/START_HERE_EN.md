# Start here

Search approved shared PPTX slides, review sources and reporting dates, confirm the exact slide order, then assemble an editable draft. You can also upload a PowerPoint template and apply it to a new or completed draft.

Copilot Studio supplies the conversational LLM for storyline planning, query expansion, grounded candidate reranking and constrained layout decisions. The Python backend handles deterministic search, source checks, PPTX structure analysis, assembly, template execution and layout-risk checks; it requires no additional model or vector-search service.

## 1. Run the local example

Use Python 3.11 or later. From the repository root:

```text
python -m venv .venv
```

Use `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS/Linux in place of `<VENV_PYTHON>`:

```text
<VENV_PYTHON> -m pip install -e ".[test]"
<VENV_PYTHON> scripts/run_demo.py
<VENV_PYTHON> scripts/run_template_demo.py
```

The script searches synthetic material, simulates confirmation of three selected slides, creates and polls a job, and saves `examples/output/Demo_Draft.pptx` and provenance JSON. It calls neither Microsoft services nor an LLM; it does not establish tenant integration.

## 2. Run the local API

Run `start-local.cmd` on Windows or `bash start-local.sh` on macOS/Linux, then open <http://127.0.0.1:8000/docs>. Setup creates a local `.env` only if one does not exist. Local mode binds loopback.

## 3. Connect the organization

CSI supplies the approved environment, Entra identities, Graph grants, source/output folders and HTTPS host using the [handoff](CSI_HANDOFF_EN.md). Follow [Copilot setup](COPILOT_STUDIO_EN.md) to import the connector operations, manually configure the four AI prompts, selection workflow and [template upload topic](TEMPLATE_WORKFLOW_EN.md), then test and publish to Teams. The prompt JSON files are configuration blueprints; GitHub does not install them into a tenant. Validate PPTX/POTX attachments on the actual channel first.

Use one approved source library whose entire contents are available to every pilot user. API user identity and Graph application permissions are separate; this version does not trim the source index to individual file permissions.

## Boundaries

- Date/version ranking describes indexed evidence and can require human review.
- Creation requires confirmation; a changed source requires refresh, reselection and confirmation again.
- Supported editable content and notes are retained. An uploaded template can supply masters, layouts, theme and slide dimensions. Source direct formatting remains, and complex slides require layout review.
- `AnalyzeSlides` reports observable page structure, not picture meaning. `GetLayoutReport` is a heuristic risk screen, not a replacement for desktop PowerPoint review.
- Source inputs are PPTX, templates are PPTX/POTX. No PDF/DOCX ingestion, standalone chat UI or extra model is included.
- Return the SharePoint `webUrl` in Teams; destination-folder permissions apply. The API `downloadUrl` requires authentication.
- Use one instance and one service process, with Entra for production. See [acceptance](ACCEPTANCE.md) for the supported file and deployment limits.

## V2 planning workflow

The repository now includes a revisioned presentation-plan backend: grounded section planning, multi-turn section/slide edits, and draft creation after approval of the latest revision. The Copilot Studio dialog must still be configured in an approved tenant. See [V2 workflow](V2_WORKFLOW_EN.md) and [Copilot setup](COPILOT_STUDIO_EN.md).

## V3 AI decision layer

The repository now also includes four structured prompt blueprints, structural slide analysis, validated per-slide template layout overrides and a completed-file layout-risk report. AI reranking and layout choice become active only after the prompt actions, loops, variables and output validation are configured as described in the [V3 Copilot section](COPILOT_STUDIO_EN.md#v3-configure-the-ai-decision-prompts). A local run that reports `llm_called: false` is still deterministic.
