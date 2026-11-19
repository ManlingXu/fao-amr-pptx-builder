# Teams PowerPoint Assistant

Find approved existing slides, review sources and reporting dates, confirm the slide order, and assemble an editable draft for Teams.

**中文：** 从批准的共享 PPTX 中选页，核对来源、版本和数据时间；用户确认顺序后保留原页格式生成可编辑初稿，并返回有访问权限控制的 SharePoint 链接。

[中文开始](docs/START_HERE_CN.md) · [Start here](docs/START_HERE_EN.md) · [Copilot setup](docs/COPILOT_STUDIO_EN.md) · [CSI handoff](docs/CSI_HANDOFF_EN.md)

## One workflow

1. **Understand:** Copilot Studio supplies the conversational LLM and collects the request.
2. **Search and review:** the backend searches approved PPTX slides and returns the source deck, slide number, reporting date and date evidence. Related versions are available for review.
3. **Confirm:** the user approves the exact slides and their order before creation.
4. **Assemble:** the backend rechecks source files and copies supported original slides and dependencies into a draft, retaining native editable content and source formatting.
5. **Deliver:** Copilot checks the job result and returns its authenticated SharePoint link, warnings and source map.

This version has no new factual-slide generation, template redesign, PDF/DOCX ingestion, separate chat UI, vector search or additional backend LLM. The local API demonstration uses synthetic content and does not provide a Copilot conversation.

## Try locally

Use Python 3.11 or later. From the repository root on macOS/Linux:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/python scripts/run_demo.py
```

On Windows, substitute `.venv/Scripts/python.exe` for `.venv/bin/python`. The demo saves a three-slide draft and provenance in `examples/output/`. It calls no Microsoft service or model. All included sample decks are synthetic; they are not FAO evidence.

For the local API, run `start-local.cmd` on Windows or `bash start-local.sh` on macOS/Linux, then open <http://127.0.0.1:8000/docs>.

## Connect the four tools

| Copilot tool | Purpose |
|---|---|
| `SearchSlides` | Find candidates with source and date evidence |
| `GetSlideVersions` | Review related source versions |
| `CreateDraft` | Submit explicitly confirmed, ordered slide IDs |
| `GetDraftStatus` | Retrieve progress and the completed result |

Production uses Entra user authentication and a separately authorized Graph service identity. The API-key definition is for a local or controlled pilot. `flow-design.json` is a configuration blueprint, not an importable agent or solution. Follow the [Chinese](docs/COPILOT_STUDIO_CN.md) or [English](docs/COPILOT_STUDIO_EN.md) setup guide.

## Operating boundary

The pilot uses one approved source library whose entire contents are accessible to the same authorized audience. App-only Graph indexing does not apply each user's individual SharePoint file permissions. Entra scopes API job access to the requester; saved output files follow the destination folder's SharePoint permissions. API-key users share one identity.

Run one service process on one instance with persistent storage. Dates and version grouping contain heuristics; supported native slides retain their formatting, but representative files still need final PowerPoint checks. See [acceptance](docs/ACCEPTANCE.md) and [verification](docs/VERIFICATION.md).

Live tenant OAuth, Graph grants, hosting, connector import and Teams publication require CSI configuration and validation. Use [`.env.production.example`](.env.production.example), the [CSI handoff](docs/CSI_HANDOFF_EN.md) and [deployment guide](deploy/README.md).

## Repository map

| Path | Contents |
|---|---|
| `presentation_search/` | Search, dates, identity, jobs, original-slide assembly and SharePoint provider |
| `integrations/copilot-studio/` | Two connector templates, instructions and configuration blueprint |
| `scripts/`, `deploy/` | Local run, connector export, packaging and host setup |
| `data/presentations/`, `examples/output/` | Synthetic sources and demo result |
| `docs/`, `tests/` | Bilingual setup, acceptance and focused regression tests |
| `.github/workflows/tests.yml` | Proposed test-only CI; no deployment or tenant credentials |
