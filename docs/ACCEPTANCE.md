# Acceptance checks / 验收清单

## Local code checks

From the repository root after installing `.[test]`:

```text
python -m pytest
python scripts/run_demo.py
python scripts/run_template_demo.py
```

The local gate covers search/date evidence, version ranking, confirmation and ordered selection, owner-scoped API jobs, source revalidation, native-slide assembly, safe failures and connector input contracts. The demonstration must return a completed, readable PPTX and an ordered source map. See [verification](VERIFICATION.md) for the current evidence.

Focused regression cases also cover oversized SharePoint sources alongside valid files, retained prior index on Graph failures, explicit written reporting dates ahead of later target years, invalid dates and Azure persistent-path rejection before configuration changes.

## Organizational acceptance — CSI still completes

| Check | Expected result |
|---|---|
| Two real users | Entra connector uses each requester; API job ownership works |
| Full source audience | Every allowed user may access every configured source, including notes and embedded data |
| Graph grants | Approved source reads and destination writes succeed; access outside the approved resources fails |
| Search review | Deck, slide, reporting date, uncertainty and related versions can be reviewed |
| Explicit confirmation | Declining or changing a selection does not create the old selection; order matches the confirmed list |
| Changed/deleted source | Source drift blocks creation until refresh and reselection |
| Native-slide fidelity | Representative drafts open in desktop PowerPoint with editable supported objects and correct notes/styles |
| Template upload and replacement | Actual chat channel passes original PPTX/POTX bytes, requester-bound template ID is used, replacement creates a new draft and original provenance/notes remain |
| Template appearance | Master/layout branding and background appear, sample slides are excluded, source content fits the target canvas without stretching |
| AI selection grounding | Expanded searches use real `SearchSlides` results; every reranked ID and copied evidence is validated before the saved plan changes |
| AI layout grounding | Every override names an existing output slide and an exact layout returned by the uploaded template; invented values are rejected |
| Layout risk report | Completed output reports off-canvas, overlap and density heuristics without claiming pixel-perfect rendering |
| Completed result | Teams shows the exact completed SharePoint link; destination permissions match the approved audience |
| Failures and capacity | Queue full, unsupported source, restart and upload failure produce useful safe errors |
| Publication and operation | Agent sharing, Teams installation, hosting, budget, maintenance and retention are recorded |

Local Graph/Entra mocks and LibreOffice rendering cannot substitute for live tenant or desktop PowerPoint acceptance.

## Supported boundary

- **Inputs:** approved source PPTX; at most 20 unique slides per draft. API searches return at most 15 candidates per request. Uploaded templates accept PPTX/POTX up to 16 MiB decoded bytes, subject to stricter channel limits.
- **Sizes:** 64 MiB per source, 256 MiB combined selected source bytes and 128 MiB output.
- **Preservation:** supported native source objects, images, notes and self-contained chart workbooks; required package dependencies are copied. Embedded workbook data is included.
- **Template application:** template master/layout/theme and dimensions are applied without importing template sample slides. Source direct formatting is retained. Copilot may choose an exact per-slide layout from the uploaded template; Python then performs deterministic grouping/scaling. This is not arbitrary generative slide redesign. Check representative files in desktop PowerPoint.
- **Rejection:** mismatched slide/notes canvases, incompatible document-wide styles and unsupported/protected dependencies, including macros, encryption, OLE and linked media/data. This is not a guarantee for every PowerPoint feature.
- **Identity:** one common approved source audience; no per-file user ACL trimming. Entra API job ownership and SharePoint output permissions are separate.
- **Operations:** one process/instance, two draft workers and twelve outstanding jobs. Incomplete jobs fail on restart. No distributed queue or proactive Teams notification.
- **Dates:** evidence-based heuristics and version families require human review when ambiguous. A newer indexed result is not proof of scientific correctness or global currency.

中文要点：本地验收证明代码与合成样例的行为；真实账号、附件传递、Graph 授权、连接器、Teams 发布、文件权限与桌面 PowerPoint 效果仍由 CSI 验收。支持原页复用与上传模板替换，保留来源和可编辑内容；复杂页面排版仍需检查。

## V2 storyline acceptance

The automated test suite also covers V2 `PlanPresentation`, `GetPresentationPlan`, `RevisePresentationPlan`, and `CreateDraftFromPlan`:

- An audience/purpose-specific outline contains actual approved source slide IDs, deck/page identifiers and reporting periods; it displays missing-section gaps instead of fabricating information.
- A follow-up can reorder sections and their slide IDs. A stale `expected_revision` produces HTTP 409 and does not overwrite the current plan.
- A user cannot read or revise another user's saved plan; uploaded templates must belong to the same requester. An omitted template during revision retains the previous choice.
- Draft generation rejects `confirmed=false`, requires confirmation of the latest plan revision, and outputs the ordered original slides with source map. Creation still revalidates changed source files before assembly.
- New capabilities are backed by a synthetic HTTP demonstration (`python scripts/run_storyline_demo.py`), not by production Copilot conversational evidence.

Live CSI acceptance must test the **actual agent's multi-turn planning**, tool input mappings, user approval behavior, individual account authorization, template compatibility and resource consumption. A generic LLM planning statement is not proof of an executed tool call or a completed PPTX. See [V2 guide](V2_WORKFLOW_EN.md).

## V3 AI-decision acceptance

- Exercise all four configured Prompt actions with the Zambia example and at least one out-of-scope query. Confirm the agent shows gaps instead of filling them with weak pages.
- Inject an unknown slide ID, duplicate ID, fabricated evidence snippet, unknown template layout and out-of-range output slide. Validation must block every case before a draft/template job is created.
- Confirm that the AI-reranked IDs are persisted through `RevisePresentationPlan`; calling only `PlanPresentation` is not evidence that reranking ran.
- Compare `AnalyzeSlides` with representative text, picture, table, chart and grouped-object pages. Do not interpret object counts as picture relevance.
- Open final outputs in desktop PowerPoint and compare them with `GetLayoutReport`. Record false positives and false negatives; a clean report is not proof of perfect layout.
