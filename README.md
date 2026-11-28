# Teams PowerPoint Assistant

Find approved existing slides, use a constrained Copilot decision layer to plan and rerank them, choose real template layouts, confirm the latest plan revision, and assemble an editable PowerPoint draft for Teams.

**中文：** 从批准的共享 PPTX 中选页，核对来源、版本和数据时间；确认顺序后生成可编辑初稿。也可以在对话中上传 PPT 模板，为新初稿或已完成的初稿更换模板，并返回有访问权限控制的 SharePoint 链接。

[中文开始](docs/START_HERE_CN.md) · [Start here](docs/START_HERE_EN.md) · **[V2 Storyline workflow](docs/V2_WORKFLOW_EN.md)** · **[V2 中文流程](docs/V2_WORKFLOW_CN.md)** · [Copilot setup](docs/COPILOT_STUDIO_EN.md) · [CSI handoff](docs/CSI_HANDOFF_EN.md)

## PPT Builder Studio

[Open the live browser demo](https://ppt-builder-studio.light-sun-3036.chatgpt.site) to try Teams Mode and inspect Developer Mode. The browser edition works with 40 bilingual summaries linked to pages in six public decks. To run the full workflow locally, use `.\start-studio.cmd` on Windows or `./start-studio.sh` on macOS/Linux, then open `http://127.0.0.1:8768/`. Python 3.11 or later is required.

For the original slide collection, run `.\.venv\Scripts\python.exe scripts\prepare_amr_corpus.py` after the first Windows launch, then relaunch Studio. The 28 November 2026 refresh verified 183 original decks and 4,697 slides. Public-source availability can change between downloads. [Installation, user and developer guides, architecture, Copilot Studio migration and CSI handoff](docs/studio/README.md)

## 本地 AMR 演示工作台

在 Windows 解压最新版仓库，双击 `start-amr.cmd`。首次启动按 184 份正式目录准备本地资料，复用能通过校验的旧课件，再打开 <http://127.0.0.1:8765>。实际可用数取决于发布方下载情况。新版首页用对话完成选页与导出。输入主题和页数，助手会先给出逐页方案。你可以追问来源或要求调整，确认后下载可编辑初稿，再上传自己的 PPTX 或 POTX 模板。

[全库对话录屏指南与可复制台词](docs/RECORD_LOCAL_DEMO_CN.md) · [历史七份课件练习](docs/LOCAL_AMR_DEMO_CN.md) · [正式目录及来源分布](examples/public_corpus/amr/SOURCES_CN.md)

选页使用本地逐页索引，检索标题、正文、备注，以及与国家、物种和专题相关的线索。选择 Ollama 时，本机模型从候选页中挑选证据。PowerPoint 备注与 `source_map.json` 记录原文件、页码和发布者链接。统一编排模式可以把证据重新排成简报页。证据不足时，界面显示缺少的页数。每次生成会创建独立的输出文件夹。

## One workflow

1. **Understand:** Copilot Studio supplies the conversational LLM and collects the request.
2. **Expand, search and rerank:** Copilot can generate complementary lexical queries. The backend returns real source pages; a grounded prompt may rerank only those candidates and must preserve copied evidence and gaps.
3. **Plan and revise:** the backend saves a revisioned storyline with exact candidate slide IDs. Follow-up requests can reorder sections and selected slides without losing source provenance.
4. **Analyze and design:** Python reports observable page structure. Copilot may choose only among layout names returned by the uploaded template; Python validates and applies those choices.
5. **Confirm and assemble:** the user approves the exact current plan revision, slides, order and template treatment. The backend rechecks sources and produces an editable draft.
6. **Check and deliver:** a heuristic report flags off-canvas objects, substantive overlaps and very dense text. Copilot returns only the completed authenticated link, warnings and source map.

The [V2 plan workflow](docs/V2_WORKFLOW_EN.md) adds four versioned planning tools (Create/Read/Revise/Finalize), with real-user authentication and current-revision checks. The [V3 Copilot setup](docs/COPILOT_STUDIO_EN.md#v3-configure-the-ai-decision-prompts) adds four manual prompt blueprints plus `AnalyzeSlides`, validated per-slide layout overrides and `GetLayoutReport`. Backend processing is implemented; the prompts, connector, chat attachment path and Teams publication still require tenant configuration and validation. Original direct formatting is retained, so this remains constrained template application rather than arbitrary generative redesign.

The local workbench supports topic-based drafting with a deterministic index or an installed Ollama model. The Copilot tools described above use separate tenant configuration. Both routes use evidence from source slides.

## Try the 184-deck AMR collection

The catalogue contains 4,708 original slides on antimicrobial use, resistance and stewardship. Animal and One Health together cover 95 presentations. In the November 2026 replay, 183 of 184 files (4,697 slides) downloaded and verified. Each entry lists a representative original slide, publisher and pinned file hash. Discovery checks seven institutional source collections. Candidates require content and provenance review before inclusion. Another 169 distinct, parseable candidate files (3,143 pages) have a [separate pinned download list](examples/public_corpus/amr/candidate-fetch.csv) for content review.

[31 个来源网站与课件数量](examples/public_corpus/amr/SOURCES_CN.md) · [选页逻辑与 AI 的作用](docs/AMR_SELECTION_LOGIC_CN.md) · [AMR 专题演示与下载步骤](examples/public_corpus/amr/README.md) · [Browse the verified AMR catalogue](examples/public_corpus/amr/catalog.csv)

### Run the 10-slide template showcase

After downloading the AMR corpus, create three editable versions of the same ten-slide Zambia presentation:

```powershell
.\.venv\Scripts\python.exe scripts\run_amr_ten_slide_showcase.py --corpus-dir .local\amr --output-dir build\amr-ten-slide-showcase
```

Open `AMR_10_Slide_Original.pptx`, `AMR_10_Slide_Blue.pptx` and `AMR_10_Slide_Green.pptx` in that order to compare the original design with two template treatments. The script verifies that slide order, provenance, substantive text and notes remain aligned. Pass `--template-a` and `--template-b` to use two local PPTX/POTX templates instead of the generated demonstration templates.

This deterministic local showcase demonstrates ten-slide assembly, structural analysis, template application and provenance preservation. It does not call an LLM or Microsoft service and does not represent Copilot's grounded reranking or layout decisions.

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

## Connect the twelve tools

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
| `AnalyzeSlides` | Inspect selected pages structurally before making a layout decision |
| `GetLayoutReport` | Review heuristic layout risks in a completed output |

Production uses Entra user authentication and a separately authorized Graph service identity. The API-key definition is for a local or controlled pilot. `flow-design.json` is a configuration blueprint, not an importable agent or solution. Follow the [Chinese](docs/COPILOT_STUDIO_CN.md) or [English](docs/COPILOT_STUDIO_EN.md) setup guide.

**V3 is backend code plus Copilot prompt/topic blueprints, not an already-published Teams agent.** The LLM plans, expands queries, reranks and chooses allowed layouts only after the four prompt actions have been configured in Copilot Studio. The local demos remain deterministic and do not call a model.

## Operating boundary

The pilot uses one approved source library whose entire contents are accessible to the same authorized audience. App-only Graph indexing does not apply each user's individual SharePoint file permissions. Entra scopes API job access to the requester; saved output files follow the destination folder's SharePoint permissions. API-key users share one identity.

Run one service process on one instance with persistent storage. Dates and version grouping contain heuristics; supported native slides retain their formatting, but representative files still need final PowerPoint checks. See [acceptance](docs/ACCEPTANCE.md) and [verification](docs/VERIFICATION.md).

Template uploads are private to the authenticated requester and excluded from the search index. The backend accepts macro-free PPTX/POTX files up to 16 MiB; chat channels can impose smaller limits or restrict these file types. Templates must define their branding in slide masters/layouts; sample slides are excluded from output. Files whose visual design exists only on sample slides need the design moved into the master/layout first.

Live tenant OAuth, Graph grants, hosting, connector import and Teams publication require CSI configuration and validation. Use [`.env.production.example`](.env.production.example), the [CSI handoff](docs/CSI_HANDOFF_EN.md) and [deployment guide](deploy/README.md).

## Repository map

| Path | Contents |
|---|---|
| `presentation_search/` | Search, dates, identity, structural analysis, jobs, layout checks, original-slide assembly and SharePoint provider |
| `integrations/copilot-studio/` | Two connector templates, agent instructions, workflow and four AI prompt blueprints |
| `scripts/`, `deploy/` | Local run, connector export, packaging and host setup |
| `data/presentations/`, `examples/output/` | Synthetic sources and demo result |
| `examples/public_corpus/` | Verified public download catalogue, walkthrough and worked PowerPoint example |
| `docs/`, `tests/` | Bilingual setup, acceptance and focused regression tests |
| `.github/workflows/tests.yml` | Proposed test-only CI; no deployment or tenant credentials |
