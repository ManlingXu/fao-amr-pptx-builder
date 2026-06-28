# FAO AMR PPTX Builder Skill

This repository contains a shareable Codex skill for creating editable first-draft PowerPoint decks from FAO AMR source materials.

The skill lives at:

```text
skills/fao-amr-pptx-builder/
```

## Current Status

This is a working v1 Codex skill. It can be installed into another Codex setup and used to generate editable `.pptx` drafts, as long as the receiving environment has:

- Access to this private GitHub repository.
- Python 3.10 or newer.
- The Python dependencies in `pyproject.toml`.
- A local folder containing the FAO AMR materials, such as a OneDrive-synced folder.
- A PowerPoint template file when template-based output is desired.

The skill does not include FAO source materials or templates. Users provide those at generation time.

## Install In Codex

Ask Codex to install the skill from this repository path:

```text
Install the Codex skill from https://github.com/ManlingXu/fao-amr-pptx-builder/tree/main/skills/fao-amr-pptx-builder
```

For private-repo installs, the target machine must already have GitHub access through an authenticated browser, Git credentials, or `GITHUB_TOKEN` / `GH_TOKEN`.

After installation, restart Codex so the new skill is discovered.

It is designed for prompts such as:

```text
Use the FAO AMR PPTX builder to give me a PPT of AMR history in FAO using this template and the materials in my local OneDrive AMR folder.
```

For v1, OneDrive materials must be available as a synced local folder. The skill does not connect directly to Microsoft Graph or OneDrive cloud APIs.

## What It Produces

- `draft.pptx` - editable PowerPoint deck
- `deck_plan.json` - slide-by-slide plan
- `source_map.json` - source traceability per slide

If the indexed materials do not contain relevant non-warning evidence, the planner creates a short evidence-gap deck plan instead of pretending to have a sourced full deck.

## Manual Script Workflow

From the repository root:

```powershell
python skills\fao-amr-pptx-builder\scripts\scan_sources.py --source-folder "C:\path\to\OneDrive AMR Materials" --output outputs\fao-amr-pptx\sources.json
python skills\fao-amr-pptx-builder\scripts\build_source_index.py --sources outputs\fao-amr-pptx\sources.json --output outputs\fao-amr-pptx\source_index.json
python skills\fao-amr-pptx-builder\scripts\plan_deck.py --prompt "give me a PPT of AMR history in FAO" --index outputs\fao-amr-pptx\source_index.json --output outputs\fao-amr-pptx\deck_plan.json
python skills\fao-amr-pptx-builder\scripts\create_pptx.py --plan outputs\fao-amr-pptx\deck_plan.json --index outputs\fao-amr-pptx\source_index.json --template "C:\path\to\template.pptx" --output outputs\fao-amr-pptx\draft.pptx --source-map outputs\fao-amr-pptx\source_map.json
```

The template argument is optional; when omitted, the generator uses a clean editable default PowerPoint layout.

## Source Materials

Do not commit real FAO source materials to this repository. Point the workflow at a local folder containing approved materials, such as synced OneDrive files, when generating a deck.

Supported input formats include `.pptx`, `.pdf`, `.docx`, `.txt`, `.md`, and `.html`, depending on installed optional Python packages.

## V1 Limits

- The skill uses local files only; it does not call Microsoft Graph or pull directly from OneDrive cloud URLs.
- Complex legacy slide designs are rebuilt into editable text/shapes using the chosen template rather than copied pixel-perfectly.
- Charts and figures from reports are not automatically redrawn as fully editable charts in v1; the source map points back to the relevant materials.

## Validation

Run the focused tests and skill validation with:

```powershell
python -m pip install -e .[dev]
python -m pytest tests\fao_amr_pptx_builder -v
```

When developing inside Codex, also run the local `skill-creator` quick validation script against `skills\fao-amr-pptx-builder`.
