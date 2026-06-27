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
