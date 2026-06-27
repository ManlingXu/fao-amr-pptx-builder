# FAO AMR PPTX Builder Skill Design

## Purpose

Create a shareable Codex skill that helps FAO AMR staff produce first-draft PowerPoint decks from reused internal materials. In the real workflow, those materials are kept in OneDrive. The first version treats the OneDrive materials as a synced local folder that Codex can read from the filesystem.

The first version focuses on a repo-contained skill at `skills/fao-amr-pptx-builder/` with bundled scripts, so it can be committed to GitHub and installed into another Codex environment.

The skill should turn prompts such as "give me a PPT of AMR history in FAO" into an editable `.pptx` draft, using sensible defaults instead of asking many setup questions. Review comments from the user should drive later versions of the deck.

## Scope

In scope for the first stage:

- Scan a user-provided folder of previous FAO AMR PowerPoint decks and report materials.
- Support OneDrive-synced local folders as the normal materials location.
- Extract searchable text from `.pptx`, `.pdf`, `.docx`, `.txt`, `.md`, and `.html` where supported by bundled scripts and local dependencies.
- Prefer previous PPT content when it is relevant, because repeated FAO AMR materials should be reused efficiently.
- Use report materials when the deck needs facts, data, figures, timelines, or citations not covered well by old slides.
- Create an editable `.pptx` using an uploaded or specified template when available.
- Rebuild slides into the selected template rather than preserving every complex old-slide visual exactly.
- Produce a source map that records which files informed each generated slide.
- Support iterative revision from user review, such as "make it shorter", "add more FAO Action Plan content", or "make it more technical".

Out of scope for the first stage:

- A full web app for deck generation.
- A PowerPoint add-in or Microsoft Copilot integration.
- Direct Microsoft Graph or OneDrive cloud API integration.
- Pixel-perfect copying of old slides.
- Automatic publication, sharing, or institutional approval workflow.

## User Workflow

1. User installs or checks out the repository containing the skill.
2. User points Codex to the local OneDrive-synced folder containing repeated FAO AMR materials.
3. User gives the deck demand and provides the PowerPoint template at the same time, either by uploading it into the workspace or giving a local template path.
4. User asks Codex for a deck, for example: "Use the FAO AMR PPTX builder to make a PPT about AMR history in FAO using this template and the AMR materials in my OneDrive folder."
5. The skill creates a first draft directly using sensible defaults.
6. Codex returns the `.pptx` path and a source map path.
7. User reviews the deck and asks for a next version.
8. The skill reuses the source map and prior draft context to revise the deck.

## Skill Package

The skill should live at:

```text
skills/fao-amr-pptx-builder/
  SKILL.md
  agents/openai.yaml
  scripts/
    scan_sources.py
    build_source_index.py
    plan_deck.py
    create_pptx.py
    revise_deck.py
  references/
    fao-amr-style.md
    deck-defaults.md
```

The final implementation should avoid unnecessary extra documentation files. An `assets/` folder should exist only if a template or reusable visual asset is actually included.

## Bundled Script Responsibilities

`scan_sources.py`
: Enumerate supported files in a materials folder, including OneDrive-synced local folders, and output structured metadata.

`build_source_index.py`
: Extract text and basic slide/page references into a local JSON index suitable for retrieval.

`plan_deck.py`
: Given a user prompt and source index, create a slide-by-slide plan with titles, key messages, candidate evidence, suggested visuals, and source references.

`create_pptx.py`
: Create an editable `.pptx` from the deck plan and provided template. It should use template layouts when possible and fall back to clean editable text layouts if no template is available.

`revise_deck.py`
: Use a prior deck plan, source map, and user review instruction to produce a revised plan and next `.pptx`.

## Default Deck Behavior

For broad prompts, the skill should create a useful first draft without stopping for clarification. Defaults:

- Audience: FAO or partner staff familiar with AMR at a general policy/programme level.
- Length: about 10 to 12 slides unless the user specifies otherwise.
- Tone: clear, evidence-grounded, FAO-appropriate, concise.
- Slide density: presentation-ready bullets, not long report prose.
- Citation style: compact source notes per slide plus a final sources slide.
- Visual style: follow the supplied template; otherwise use a restrained professional layout.
- Evidence rule: each substantive slide should be traceable to previous PPT or report sources.

For "AMR history in FAO", the default outline should be:

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

## Data Flow

```text
User prompt
  -> skill instructions
  -> source scan/index
  -> relevant source retrieval
  -> deck plan JSON
  -> editable PPTX generation
  -> source map JSON/Markdown
  -> user review
  -> revised plan and next PPTX
```

The deck plan is the central intermediate artifact. It lets Codex inspect, revise, and regenerate decks without redoing every step from scratch.

## Error Handling

- If no source folder is provided, ask for one concrete folder path.
- If the source folder is a OneDrive cloud URL instead of a local synced path, ask the user for the synced local folder path or downloaded folder.
- If no template is provided, continue with a clean default editable layout and mention that the expected workflow is to provide a template with the request.
- If extraction fails for a file, record the file and error but continue with other sources.
- If no relevant materials are found, create a short deck plan explaining the evidence gap and ask for additional materials before generating a polished deck.
- If required Python dependencies are missing, report the exact package names needed.

## Testing And Validation

The implementation should include focused tests for:

- Source scanning recognizes supported files.
- Extracted index keeps file, slide/page, and text references.
- Deck planning returns slide plans with source references.
- PPTX creation writes an editable `.pptx` file.
- Source map records evidence per slide.

Manual validation should include one realistic request:

```text
give me a PPT of AMR history in FAO
```

Success means Codex produces a `.pptx` and source map from sample or real materials, and the deck can be opened and edited in PowerPoint.

## Implementation Decisions

- Use JSON for the first source index and deck plan artifacts. JSON is easier to inspect, commit, attach, and revise during early skill use.
- Use `python-pptx` for first-stage `.pptx` generation. It produces editable slides and keeps the implementation understandable.
- Use best-effort extraction with clear dependency messages. The first implementation should support `.pptx` and plain text first, then add PDF/DOCX extraction when dependencies are available.
- Treat OneDrive as a filesystem source in v1. Direct cloud connector support requires a later authentication and permissions design.
- Treat a user-provided template as the normal path. The no-template default layout is a fallback, not the preferred workflow.
- Do not include real FAO source materials in the GitHub skill package unless the user explicitly adds approved sample files later.
- Include a tiny generated sample fixture for tests if needed, not real internal materials.
