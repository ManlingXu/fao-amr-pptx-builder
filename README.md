# Teams PowerPoint Assistant

Find approved existing slides, propose an audience-specific presentation storyline, revise ordered sections over several turns, confirm the latest plan revision, and assemble an editable PowerPoint draft for Teams.

**中文：** 从批准的共享 PPTX 中选页，核对来源、版本和数据时间；确认顺序后生成可编辑初稿。也可以在对话中上传 PPT 模板，为新初稿或已完成的初稿更换模板，并返回有访问权限控制的 SharePoint 链接。

[中文开始](docs/START_HERE_CN.md) · [Start here](docs/START_HERE_EN.md) · **[V2 Storyline workflow](docs/V2_WORKFLOW_EN.md)** · **[V2 中文流程](docs/V2_WORKFLOW_CN.md)** · [Copilot setup](docs/COPILOT_STUDIO_EN.md) · [CSI handoff](docs/CSI_HANDOFF_EN.md)

## One workflow

1. **Understand:** Copilot Studio supplies the conversational LLM and collects the request.
2. **Search and review:** the backend searches approved PPTX slides and returns the source deck, slide number, reporting date and date evidence. Related versions are available for review.
3. **Plan and revise (V2):** Copilot Studio proposes sections and per-section queries. The backend saves a revisioned plan with real candidate slide IDs. Follow-up requests can reorder sections and selected slides; coverage gaps remain visible.
4. **Confirm:** the user approves the exact current plan revision, slides, order and chosen template before creation.
5. **Assemble:** the backend rechecks source files and copies supported original slides and dependencies into a draft, retaining native editable content and source formatting. Optionally upload a template and apply its master, layout, theme and canvas to the selected slides or to a completed draft.
6. **Deliver:** Copilot checks the job result and returns its authenticated SharePoint link, warnings and source map.

The [V2 plan workflow](docs/V2_WORKFLOW_EN.md) adds four versioned planning tools (Create/Read/Revise/Finalize), with real-user authentication and current-revision checks. The [template upload workflow](docs/TEMPLATE_WORKFLOW_EN.md) includes file-input mapping and two new tools. Backend template processing is implemented; chat attachment support, connector configuration and Teams publication still require tenant validation. Original direct formatting is retained, so applying a template does not automatically redesign every slide.

This version has no new factual-slide generation, PDF/DOCX ingestion, separate chat UI, vector search or additional backend LLM. Local demos use scripted or interactive selections. Copilot conversation requires a connected agent.

## Try the 150-deck AMR collection

Search 3,868 original slides on antimicrobial use, resistance and stewardship. The animal and One Health filters cover 70 presentations. Each entry lists a representative original slide, publisher and pinned download. The local demo supports slide selection, provenance review and editable draft export. The discovery command checks the EU farmer/veterinarian training library, UK annual surveillance releases and CGIAR presentation records. Inspect candidates and compare file hashes before adding a source.

[30 个来源网站与课件数量](examples/public_corpus/amr/SOURCES_CN.md) · [选页逻辑与 AI 的作用](docs/AMR_SELECTION_LOGIC_CN.md) · [AMR 专题演示与下载步骤](examples/public_corpus/amr/README.md) · [Browse the verified AMR catalogue](examples/public_corpus/amr/catalog.csv)

## Try the 120-deck public demo

[中文演示与运行步骤 · Public corpus walkthrough](examples/public_corpus/README.md) · [Download the example PowerPoint with credits](examples/public_corpus/Vietnam_AMR_demo.zip) · [Browse the 120 sources](examples/public_corpus/catalog.csv)

The optional public corpus contains 2,322 slides across 120 verified presentations on AMR, One Health, food safety and livestock. Search the full corpus, review source pages and related versions, choose individual slides and confirm an editable draft. A worked example selects three original slides from two presentations for a briefing on Vietnam. The four synthetic decks below provide a quick offline check.

## Try locally

Use Python 3.11 or later. From the repository root on macOS/Linux:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/python scripts/run_demo.py
.venv/bin/python scripts/run_template_demo.py
```

On Windows, substitute `.venv/Scripts/python.exe` for `.venv/bin/python`. The V1 demo saves a three-slide draft and provenance in `examples/output/`. The V2 demo saves a revised storyline, source map and editable draft in `examples/output/v2/`. It calls no Microsoft service or model. The four source fixtures in `data/presentations/` are synthetic.

For the local API, run `start-local.cmd` on Windows or `bash start-local.sh` on macOS/Linux, then open <http://127.0.0.1:8000/docs>.

## Connect the ten tools

| Copilot tool | Purpose |
|---|---|
| `SearchSlides` | Find candidates with source and date evidence |
| `GetSlideVersions` | Review related source versions |
| `PlanPresentation` | Propose a section-by-section storyline grounded in approved slides |
| `GetPresentationPlan` | Read the current saved plan and revision |
| `RevisePresentationPlan` | Change section order and selected slides; reject stale revisions |
| `CreateDraftFromPlan` | Create only after approval of the exact current plan |
| `UploadTemplate` | Receive the uploaded PPTX/POTX file as bytes and return a private template ID |
| `CreateDraft` | Submit explicitly confirmed, ordered slide IDs and an optional template ID |
| `ApplyTemplate` | Apply an uploaded template to an owned completed draft, creating a new file |
| `GetDraftStatus` | Retrieve progress and the completed result |

Production uses Entra user authentication and a separately authorized Graph service identity. The API-key definition is for a local or controlled pilot. `flow-design.json` is a configuration blueprint, not an importable agent or solution. Follow the [Chinese](docs/COPILOT_STUDIO_CN.md) or [English](docs/COPILOT_STUDIO_EN.md) setup guide.

**V2 is backend code plus a Copilot topic blueprint, not an already-published Teams agent.** The LLM plans content only once Copilot Studio has been configured; the local demos use deterministic section queries and support both synthetic fixtures and the opt-in public corpus.

## Operating boundary

The pilot uses one approved source library whose entire contents are accessible to the same authorized audience. App-only Graph indexing does not apply each user's individual SharePoint file permissions. Entra scopes API job access to the requester; saved output files follow the destination folder's SharePoint permissions. API-key users share one identity.

Run one service process on one instance with persistent storage. Dates and version grouping contain heuristics; supported native slides retain their formatting, but representative files still need final PowerPoint checks. See [acceptance](docs/ACCEPTANCE.md) and [verification](docs/VERIFICATION.md).

Template uploads are private to the authenticated requester and excluded from the search index. The backend accepts macro-free PPTX/POTX files up to 16 MiB; chat channels can impose smaller limits or restrict these file types. Templates must define their branding in slide masters/layouts; sample slides are excluded from output. Files whose visual design exists only on sample slides need the design moved into the master/layout first.

Live tenant OAuth, Graph grants, hosting, connector import and Teams publication require CSI configuration and validation. Use [`.env.production.example`](.env.production.example), the [CSI handoff](docs/CSI_HANDOFF_EN.md) and [deployment guide](deploy/README.md).

## Repository map

| Path | Contents |
|---|---|
| `presentation_search/` | Search, dates, identity, jobs, original-slide assembly and SharePoint provider |
| `integrations/copilot-studio/` | Two connector templates, instructions and configuration blueprint |
| `scripts/`, `deploy/` | Local run, connector export, packaging and host setup |
| `data/presentations/`, `examples/output/` | Synthetic sources and demo result |
| `examples/public_corpus/` | Verified public download catalogue, walkthrough and worked PowerPoint example |
| `docs/`, `tests/` | Bilingual setup, acceptance and focused regression tests |
| `.github/workflows/tests.yml` | Proposed test-only CI; no deployment or tenant credentials |
