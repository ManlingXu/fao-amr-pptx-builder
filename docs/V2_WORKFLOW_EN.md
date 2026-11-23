# V2 — AI Storyline Planning and Iterative PPT Assembly

**Status:** Backend implementation and GitHub-tested synthetic workflow. The Copilot Studio conversational topic and Teams publication still require configuration and tenant validation. This is **not** an end-to-end live FAO deployment.

## 1. What V2 adds

The original V1 search-and-assemble workflow remains intact. V2 introduces a **saved, owner-scoped presentation plan** with sections, source references and a revision number. Copilot Studio (the LLM) proposes section titles, queries and adjustments; our backend searches only indexed, approved PPTX files and persists the returned slide IDs. No new scientific facts or unsourced slides are generated.

An example end-user conversation:

1. “Prepare 12 slides for veterinary authorities about AMR in Africa.” The agent proposes background, surveillance, FAO initiatives and priorities.
2. `PlanPresentation` searches each section and returns a planId, section/slide mappings, source dates and coverage gaps.
3. “Reduce the background and move recent FAO activities earlier.” The agent fetches the current plan, searches for additional candidates if needed, and calls `RevisePresentationPlan` with the **complete** new section list and current revision.
4. The agent displays the ordered selection and chosen template, then asks the user to confirm that exact revision.
5. Only after user approval, `CreateDraftFromPlan` creates a job, and `GetDraftStatus` returns the completed PPTX link and provenance.

If a requested section has insufficient matches, the backend reports a **gap**. The user can revise the plan; no fabricated content is filled in. Search is currently lexical, not a semantic vector index. The LLM can improve recall by paraphrasing searches and using several section-specific queries.

## 2. V2 tool contract

| Tool | What it does | Inputs or requirements |
|---|---|---|
| `PlanPresentation` | Saves the first section-by-section proposal and searches approved slides | `title`, `audience`, `purpose`, 1–8 `sections` (`title`, `query`, `slide_count` 1–8), optional owner-scoped `template_id` |
| `GetPresentationPlan` | Reads latest version | Exact `plan_id`; only the owning requester may read |
| `RevisePresentationPlan` | Reorders sections, selects new valid slide IDs, changes emphasis | `plan_id`, `expected_revision`, **full** revised `sections` with `slide_ids`; omitted template ID retains the chosen template |
| `CreateDraftFromPlan` | Enqueues a PPT from the current approved plan | `plan_id`, `expected_revision`, `confirmed=true` **only after the user confirms** |
| `GetDraftStatus` | Reports queued/running/completed/failed and authenticated result | Exact `job_id`; previously present in V1 |

The existing `SearchSlides`, `GetSlideVersions`, `UploadTemplate`, `CreateDraft` and `ApplyTemplate` tools remain usable. There are **10** user-facing connector operations in the V2 definition; administrators can refresh the index separately.

### Template handling

The existing template workflow lets the user upload an owner-scoped PPTX/POTX file and apply its master, layout and theme to an editable draft. It also supports replacing the template for a completed draft (creating a new output). **It does not guarantee automatic semantic rearrangement of arbitrary source layouts**, and complex slides need a desktop PowerPoint review. Template ID ownership, source slide fidelity, speaker notes and source maps remain important acceptance criteria.

## 3. Local demonstration — no CSI access needed

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/python scripts/run_storyline_demo.py
.venv/bin/python scripts/run_template_demo.py
```

On Windows, use `.venv/Scripts/python.exe`. The storyline demo outputs `examples/output/v2/V2_Storyline.json`, `V2_Source_Map.json` and `V2_Editable_Draft.pptx`. It creates a section plan, reverses two sections as a user edit, requires the newest revision and produces an editable original-slide draft from **synthetic** source files. No live Microsoft service or LLM is called by the local demonstration.

## 4. How to connect in Copilot Studio

1. In the CSI-approved environment, generate/import the updated Swagger connector from `scripts/export_connector.py`; it now contains the **four V2 planning operations** in addition to the previous six.
2. Update the agent's Instructions using `integrations/copilot-studio/agent-instructions-en.txt`.
3. Manually implement the V2 section of `integrations/copilot-studio/flow-design.json`. This JSON is a design blueprint, **not an importable Agent, Topic, Flow or Solution**.
4. Bind planId and revision to topic variables. Require explicit confirmation of the selected source IDs, order and template, and set `CreateDraftFromPlan` to **Ask the end user before running** with dynamic invocation disabled.
5. Test at least two real users, including unauthorized plan access, stale revisions, source changes, date ambiguities, template compatibility and SharePoint output ownership/permissions.

Follow the [CSI handoff](CSI_HANDOFF_EN.md), [Copilot Studio setup](COPILOT_STUDIO_EN.md) and [acceptance criteria](ACCEPTANCE.md). Tenant licensing and backend hosting remain unresolved until CSI confirms them.

## 5. Scope and limitations

- The agent needs Copilot Studio to perform LLM reasoning. The Python backend does **not** call Azure OpenAI, a third-party LLM, embeddings or AI Search.
- The V2 plan is persisted under the configured draft-state directory. One backend instance/process is supported; no distributed plan locks, queue, proactive Teams notification or cross-tenant conversation persistence are provided.
- Version and date rules are useful but imperfect; date-unknown sources and potentially incorrect content require expert review. New sources must be approved for the entire pilot audience.
- Content planning is LLM-assisted **after the agent is configured**. Repository tests prove API behavior and file output, not the quality of real LLM planning.
- No automatic new factual slides, polished infographic generation, PDF/DOCX ingestion or fully intelligent template redesign.
- Do not upload real unpublished FAO slides, access tokens or organizational secrets to this public GitHub repository.
