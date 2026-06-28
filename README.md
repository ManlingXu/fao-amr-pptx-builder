# FAO AMR PPTX Builder Skill

This repository contains a shareable Codex skill for creating editable first-draft PowerPoint decks from FAO AMR source materials.

The skill lives at:

```text
skills/fao-amr-pptx-builder/
```

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

## Validation

Run the focused tests and skill validation with:

```powershell
python -m pytest tests\fao_amr_pptx_builder tests\test_retrieval.py -v
python "C:\Users\徐曼灵\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\fao-amr-pptx-builder
```
