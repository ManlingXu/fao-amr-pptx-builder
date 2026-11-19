# Start here

Search approved shared PPTX slides, review sources and reporting dates, confirm the exact slide order, then assemble an editable draft. You can also upload a PowerPoint template and apply it to a new or completed draft.

Copilot Studio supplies the conversational LLM. The Python backend handles deterministic search, source checks, assembly and storage; it requires no additional model or vector-search service.

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

CSI supplies the approved environment, Entra identities, Graph grants, source/output folders and HTTPS host using the [handoff](CSI_HANDOFF_EN.md). Follow [Copilot setup](COPILOT_STUDIO_EN.md) to import six tools, configure selection and [template upload topics](TEMPLATE_WORKFLOW_EN.md), test and publish to Teams. Validate PPTX/POTX attachments on the actual channel first.

Use one approved source library whose entire contents are available to every pilot user. API user identity and Graph application permissions are separate; this version does not trim the source index to individual file permissions.

## Boundaries

- Date/version ranking describes indexed evidence and can require human review.
- Creation requires confirmation; a changed source requires refresh, reselection and confirmation again.
- Supported editable content and notes are retained. An uploaded template can supply masters, layouts, theme and slide dimensions. Source direct formatting remains, and complex slides require layout review.
- Source inputs are PPTX, templates are PPTX/POTX. No PDF/DOCX ingestion, standalone chat UI or extra model is included.
- Return the SharePoint `webUrl` in Teams; destination-folder permissions apply. The API `downloadUrl` requires authentication.
- Use one instance and one service process, with Entra for production. See [acceptance](ACCEPTANCE.md) for the supported file and deployment limits.
