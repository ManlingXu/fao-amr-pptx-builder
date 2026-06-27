### Task 1: Skill Skeleton And Dependency Setup

**Files:**
- Create: `skills/fao-amr-pptx-builder/SKILL.md`
- Create: `skills/fao-amr-pptx-builder/agents/openai.yaml`
- Create: `skills/fao-amr-pptx-builder/references/fao-amr-style.md`
- Create: `skills/fao-amr-pptx-builder/references/deck-defaults.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: design spec at `docs/superpowers/specs/2026-06-28-fao-amr-pptx-builder-design.md`
- Produces: discoverable skill metadata and references for later scripts

- [ ] **Step 1: Initialize the skill folder**

Run:

```powershell
python "C:\Users\寰愭浖鐏礬.codex\skills\.system\skill-creator\scripts\init_skill.py" fao-amr-pptx-builder --path skills --resources scripts,references --interface display_name="FAO AMR PPTX Builder" --interface short_description="Build editable FAO AMR PowerPoint drafts from reusable slides and reports." --interface default_prompt="Create an editable FAO AMR PowerPoint deck from my OneDrive materials and supplied template."
```

Expected: `skills/fao-amr-pptx-builder/` exists with `SKILL.md`, `agents/openai.yaml`, `scripts/`, and `references/`.

- [ ] **Step 2: Add dependencies**

Modify `pyproject.toml` dependencies to include:

```toml
  "python-docx>=1.1.0",
  "python-pptx>=1.0.0",
```

Expected: dependencies list still parses as TOML.

- [ ] **Step 3: Replace `SKILL.md` with final trigger and workflow**

Write:

```markdown
---
name: fao-amr-pptx-builder
description: Use when creating, drafting, revising, or assembling editable PowerPoint decks for FAO antimicrobial resistance work from reusable FAO AMR PowerPoint slides, reports, OneDrive-synced source folders, uploaded templates, or prompts such as "give me a PPT of AMR history in FAO"
---

# FAO AMR PPTX Builder

Create editable FAO AMR PowerPoint drafts from a OneDrive-synced materials folder and a supplied PowerPoint template.

## Workflow

1. Identify the user prompt, local OneDrive materials folder, and template `.pptx` path.
2. If the source is a OneDrive URL, ask for the synced local folder path.
3. Create an output folder under `outputs/fao-amr-pptx/<slug>/`.
4. Run `scripts/scan_sources.py` to create `sources.json`.
5. Run `scripts/build_source_index.py` to create `source_index.json`.
6. Run `scripts/plan_deck.py` to create `deck_plan.json`.
7. Run `scripts/create_pptx.py` to create `draft.pptx` and `source_map.md`.
8. Return the PPTX path, source map path, and a concise note about evidence coverage.

## Defaults

- Create a first draft directly unless the materials folder is missing.
- Use previous PPTs first, then reports for facts, data, figures, timelines, and citations.
- Use the supplied template as the normal visual system.
- Build editable text and shapes. Do not flatten slides into images.
- Keep source traceability for every substantive slide.

## Revision

For review requests, use `scripts/revise_deck.py` with the prior `deck_plan.json`, `source_index.json`, and review instruction, then regenerate the PPTX.

## References

- Read `references/fao-amr-style.md` for FAO AMR tone and evidence rules.
- Read `references/deck-defaults.md` for default outlines and slide density.
```

- [ ] **Step 4: Write reference files**

Write `references/fao-amr-style.md`:

```markdown
# FAO AMR Style

- Use clear, institutional, evidence-grounded language.
- Prefer "antimicrobial resistance (AMR)" on first use, then "AMR".
- Connect AMR to food and agriculture, animal health, food safety, environment, livelihoods, and One Health when relevant.
- Avoid unsupported claims. Every substantive slide needs source traceability.
- Prefer concise bullets over report prose.
- Mention FAO, One Health, Quadripartite collaboration, country support, surveillance, governance, and responsible antimicrobial use when relevant to the prompt.
```

Write `references/deck-defaults.md`:

```markdown
# Deck Defaults

Default length: 10 to 12 slides.

Default "AMR history in FAO" outline:

1. Title
2. Why AMR matters to FAO
3. Early FAO engagement and food/agriculture relevance
4. Key milestones timeline
5. FAO Action Plan evolution
6. One Health and Quadripartite collaboration
7. Country support and governance
8. Data, surveillance, and evidence
9. Current priorities
10. Closing or discussion
11. Sources

Slide rules:

- One main message per slide.
- Use 3 to 5 bullets for content slides.
- Keep bullets short enough for editing in PowerPoint.
- Add compact source notes in speaker notes and the source map.
```

- [ ] **Step 5: Validate skill metadata**

Run:

```powershell
python "C:\Users\寰愭浖鐏礬.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\fao-amr-pptx-builder
```

Expected: validation passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pyproject.toml skills/fao-amr-pptx-builder
git commit -m "Add FAO AMR PPTX builder skill skeleton"
```

---

