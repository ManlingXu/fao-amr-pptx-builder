# FAO AMR PPTX Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shareable Codex skill that scans a OneDrive-synced FAO AMR materials folder, extracts reusable PPT/report evidence, plans a first-draft deck, and creates an editable `.pptx` from a supplied template.

**Architecture:** The skill lives under `skills/fao-amr-pptx-builder/` and ships with small Python scripts. Scripts communicate through inspectable JSON artifacts: source scan, source index, deck plan, and source map. The design borrows the staged-output workflow from `ningzimu/codex-ppt-skill`, but uses editable `python-pptx` output instead of image-based full-slide rendering.

**Tech Stack:** Codex skill metadata, Python 3.10+, `python-pptx`, existing `pypdf`, optional `python-docx`, JSON artifacts, `pytest`.

## Global Constraints

- Materials are normally in a local OneDrive-synced folder, not fetched through Microsoft Graph in v1.
- User supplies the deck demand and a PowerPoint template at the same time.
- The skill should create a first draft directly with sensible defaults.
- Generated `.pptx` must be editable.
- Previous PPTs are the preferred reusable source; reports provide facts, data, figures, timelines, and citations.
- Rebuild slides into the chosen template; do not attempt pixel-perfect copying of complex old slides in v1.
- Do not commit real internal FAO source materials.
- Use JSON for v1 source index, deck plan, and source map artifacts.

---

## Reference Repo Notes

Learn from [ningzimu/codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill):

- Keep one deck project folder per request.
- Produce intermediate artifacts before final assembly.
- Make the final answer return output paths and a brief build report.
- Keep the skill workflow explicit enough that another Codex session can run it.

Intentional differences:

- This skill must output editable `.pptx` slides, not flattened slide images.
- This skill is FAO AMR-specific and source-grounded.
- This skill must prioritize reusing previous PPT/report materials over creating purely new content.

## File Structure

- Create: `skills/fao-amr-pptx-builder/SKILL.md`  
  Skill trigger, user workflow, defaults, and script invocation order.
- Create: `skills/fao-amr-pptx-builder/agents/openai.yaml`  
  Human-facing skill metadata.
- Create: `skills/fao-amr-pptx-builder/references/fao-amr-style.md`  
  FAO AMR tone, source discipline, and deck-writing defaults.
- Create: `skills/fao-amr-pptx-builder/references/deck-defaults.md`  
  Default deck structure and layout rules.
- Create: `skills/fao-amr-pptx-builder/scripts/scan_sources.py`  
  Filesystem scan for supported source files.
- Create: `skills/fao-amr-pptx-builder/scripts/build_source_index.py`  
  Text extraction and source index creation.
- Create: `skills/fao-amr-pptx-builder/scripts/plan_deck.py`  
  Rule-based first deck plan from prompt and source index.
- Create: `skills/fao-amr-pptx-builder/scripts/create_pptx.py`  
  Editable PPTX generation and source map writing.
- Create: `skills/fao-amr-pptx-builder/scripts/revise_deck.py`  
  Plan revision from a prior deck plan and review instruction.
- Create: `tests/fao_amr_pptx_builder/test_scan_sources.py`
- Create: `tests/fao_amr_pptx_builder/test_build_source_index.py`
- Create: `tests/fao_amr_pptx_builder/test_plan_deck.py`
- Create: `tests/fao_amr_pptx_builder/test_create_pptx.py`
- Create: `tests/fao_amr_pptx_builder/test_revise_deck.py`
- Modify: `pyproject.toml`  
  Add `python-pptx` and `python-docx` dependencies.

### Shared Interfaces

Use these data shapes across tasks:

```python
SourceFile = {
    "path": "C:/.../deck.pptx",
    "relative_path": "deck.pptx",
    "extension": ".pptx",
    "kind": "presentation",
    "size_bytes": 12345,
}

IndexedItem = {
    "source_id": "src001",
    "path": "C:/.../deck.pptx",
    "relative_path": "deck.pptx",
    "kind": "presentation",
    "location": "slide 2",
    "title": "Original deck title or filename",
    "text": "extracted text",
}

DeckPlan = {
    "prompt": "give me a PPT of AMR history in FAO",
    "title": "AMR history in FAO",
    "slides": [
        {
            "slide_number": 1,
            "layout": "title",
            "title": "AMR history in FAO",
            "bullets": [],
            "speaker_notes": "",
            "source_ids": [],
        }
    ],
}
```

---

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
python "C:\Users\徐曼灵\.codex\skills\.system\skill-creator\scripts\init_skill.py" fao-amr-pptx-builder --path skills --resources scripts,references --interface display_name="FAO AMR PPTX Builder" --interface short_description="Build editable FAO AMR PowerPoint drafts from reusable slides and reports." --interface default_prompt="Create an editable FAO AMR PowerPoint deck from my OneDrive materials and supplied template."
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
7. Run `scripts/create_pptx.py` to create `draft.pptx` and `source_map.json`.
8. Return the PPTX path, source map path, and a concise note about evidence coverage.

## Defaults

- Create a first draft directly unless the materials folder is missing.
- Use previous PPTs first, then reports for facts, data, figures, timelines, and citations.
- Use the supplied template as the normal visual system.
- Build editable text and shapes. Do not flatten slides into images.
- Keep source traceability for every substantive slide.

## Revision

For review requests, use `scripts/revise_deck.py` with the prior `deck_plan.json`, `source_index.json`, `source_map.json`, and review instruction, then regenerate the PPTX.

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
python "C:\Users\徐曼灵\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\fao-amr-pptx-builder
```

Expected: validation passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pyproject.toml skills/fao-amr-pptx-builder
git commit -m "Add FAO AMR PPTX builder skill skeleton"
```

---

### Task 2: Source Scanning

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/scan_sources.py`
- Create: `tests/fao_amr_pptx_builder/test_scan_sources.py`

**Interfaces:**
- Produces: `scan_sources(root: Path) -> list[dict]`
- Produces CLI: `python scan_sources.py --source-folder <path> --output <sources.json>`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_scan_sources.py`:

```python
from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/scan_sources.py")


def load_module():
    spec = importlib.util.spec_from_file_location("scan_sources", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_scan_sources_recognizes_supported_files(tmp_path):
    (tmp_path / "history.pptx").write_bytes(b"pptx")
    (tmp_path / "report.pdf").write_bytes(b"pdf")
    (tmp_path / "notes.txt").write_text("AMR notes", encoding="utf-8")
    (tmp_path / "~$temporary.pptx").write_bytes(b"ignore")
    (tmp_path / "image.png").write_bytes(b"ignore")

    module = load_module()
    sources = module.scan_sources(tmp_path)

    names = {item["relative_path"] for item in sources}
    assert names == {"history.pptx", "report.pdf", "notes.txt"}
    assert {item["kind"] for item in sources} == {"presentation", "report", "text"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_scan_sources.py -v
```

Expected: FAIL because `scan_sources.py` does not exist.

- [ ] **Step 3: Implement scanner**

Create `skills/fao-amr-pptx-builder/scripts/scan_sources.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


SUPPORTED = {
    ".pptx": "presentation",
    ".pdf": "report",
    ".docx": "report",
    ".txt": "text",
    ".md": "text",
    ".html": "text",
    ".htm": "text",
}


def scan_sources(root: Path) -> list[dict]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Source folder does not exist or is not a folder: {root}")

    sources: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        extension = path.suffix.lower()
        kind = SUPPORTED.get(extension)
        if not kind:
            continue
        sources.append(
            {
                "path": str(path.resolve()),
                "relative_path": str(path.relative_to(root)),
                "extension": extension,
                "kind": kind,
                "size_bytes": path.stat().st_size,
            }
        )
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan FAO AMR source materials.")
    parser.add_argument("--source-folder", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = scan_sources(Path(args.source_folder))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(sources)} sources to {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_scan_sources.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/scan_sources.py tests/fao_amr_pptx_builder/test_scan_sources.py
git commit -m "Add FAO AMR source scanner"
```

---

### Task 3: Source Index Extraction

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/build_source_index.py`
- Create: `tests/fao_amr_pptx_builder/test_build_source_index.py`

**Interfaces:**
- Consumes: list from `scan_sources.py`
- Produces: `build_source_index(sources: list[dict]) -> list[dict]`
- Produces CLI: `python build_source_index.py --sources sources.json --output source_index.json`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_build_source_index.py`:

```python
from pathlib import Path
import importlib.util

from pptx import Presentation


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/build_source_index.py")


def load_module():
    spec = importlib.util.spec_from_file_location("build_source_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_source_index_extracts_pptx_and_text(tmp_path):
    pptx_path = tmp_path / "history.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "FAO AMR timeline"
    slide.placeholders[1].text = "One Health collaboration and country support"
    prs.save(pptx_path)

    text_path = tmp_path / "brief.txt"
    text_path.write_text("FAO Action Plan on AMR evidence.", encoding="utf-8")

    sources = [
        {"path": str(pptx_path), "relative_path": "history.pptx", "kind": "presentation", "extension": ".pptx"},
        {"path": str(text_path), "relative_path": "brief.txt", "kind": "text", "extension": ".txt"},
    ]

    module = load_module()
    items = module.build_source_index(sources)

    assert len(items) == 2
    assert items[0]["source_id"] == "src001"
    assert items[0]["location"] == "slide 1"
    assert "FAO AMR timeline" in items[0]["text"]
    assert items[1]["location"] == "document"
    assert "Action Plan" in items[1]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_build_source_index.py -v
```

Expected: FAIL because `build_source_index.py` does not exist.

- [ ] **Step 3: Implement source indexer**

Create `skills/fao-amr-pptx-builder/scripts/build_source_index.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _clean(text: str) -> str:
    return " ".join(text.split())


def _extract_pptx(path: Path, base: dict) -> list[dict]:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError("Install python-pptx to extract PowerPoint files.") from exc

    prs = Presentation(str(path))
    items: list[dict] = []
    for index, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text)
        text = _clean("\n".join(parts))
        if text:
            item = dict(base)
            item["location"] = f"slide {index}"
            item["text"] = text
            items.append(item)
    return items


def _extract_text(path: Path, base: dict) -> list[dict]:
    item = dict(base)
    item["location"] = "document"
    item["text"] = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    return [item] if item["text"] else []


def _extract_pdf(path: Path, base: dict) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    reader = PdfReader(str(path))
    items: list[dict] = []
    for index, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if text:
            item = dict(base)
            item["location"] = f"page {index}"
            item["text"] = text
            items.append(item)
    return items


def _extract_docx(path: Path, base: dict) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        return []
    document = Document(str(path))
    text = _clean("\n".join(paragraph.text for paragraph in document.paragraphs))
    if not text:
        return []
    item = dict(base)
    item["location"] = "document"
    item["text"] = text
    return [item]


def build_source_index(sources: list[dict]) -> list[dict]:
    items: list[dict] = []
    for source in sources:
        path = Path(source["path"])
        base = {
            "source_id": "",
            "path": str(path),
            "relative_path": source["relative_path"],
            "kind": source["kind"],
            "title": path.stem.replace("_", " ").replace("-", " "),
        }
        extension = source["extension"]
        if extension == ".pptx":
            extracted = _extract_pptx(path, base)
        elif extension == ".pdf":
            extracted = _extract_pdf(path, base)
        elif extension == ".docx":
            extracted = _extract_docx(path, base)
        else:
            extracted = _extract_text(path, base)
        items.extend(extracted)

    for index, item in enumerate(items, start=1):
        item["source_id"] = f"src{index:03d}"
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAO AMR source index.")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    items = build_source_index(sources)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(items)} indexed items to {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_build_source_index.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/build_source_index.py tests/fao_amr_pptx_builder/test_build_source_index.py pyproject.toml
git commit -m "Add FAO AMR source indexer"
```

---

### Task 4: Deck Planning

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/plan_deck.py`
- Create: `tests/fao_amr_pptx_builder/test_plan_deck.py`

**Interfaces:**
- Consumes: source index list
- Produces: `plan_deck(prompt: str, index: list[dict], max_slides: int = 11) -> dict`
- Produces CLI: `python plan_deck.py --prompt <text> --index source_index.json --output deck_plan.json`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_plan_deck.py`:

```python
from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/plan_deck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("plan_deck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plan_deck_creates_history_outline_with_sources():
    index = [
        {"source_id": "src001", "text": "FAO AMR timeline One Health Quadripartite country support", "relative_path": "history.pptx", "location": "slide 1"},
        {"source_id": "src002", "text": "FAO Action Plan on Antimicrobial Resistance surveillance governance", "relative_path": "action-plan.pdf", "location": "page 2"},
    ]

    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", index)

    assert plan["title"] == "AMR history in FAO"
    assert len(plan["slides"]) >= 10
    assert plan["slides"][0]["layout"] == "title"
    assert any("Key milestones" in slide["title"] for slide in plan["slides"])
    content_slides = [slide for slide in plan["slides"] if slide["layout"] != "title"]
    assert any(slide["source_ids"] for slide in content_slides)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_plan_deck.py -v
```

Expected: FAIL because `plan_deck.py` does not exist.

- [ ] **Step 3: Implement rule-based planner**

Create `skills/fao-amr-pptx-builder/scripts/plan_deck.py`:

```python
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_HISTORY_OUTLINE = [
    "AMR history in FAO",
    "Why AMR matters to FAO",
    "Early FAO engagement and food/agriculture relevance",
    "Key milestones timeline",
    "FAO Action Plan evolution",
    "One Health and Quadripartite collaboration",
    "Country support and governance",
    "Data, surveillance, and evidence",
    "Current priorities",
    "Closing or discussion",
    "Sources",
]


def _slug_title(prompt: str) -> str:
    lowered = prompt.lower()
    if "history" in lowered and "fao" in lowered and "amr" in lowered:
        return "AMR history in FAO"
    cleaned = re.sub(r"\b(give|make|create|me|a|an|ppt|powerpoint|deck|of|about)\b", " ", lowered)
    words = [word for word in re.findall(r"[a-z0-9]+", cleaned) if word]
    return " ".join(words[:8]).strip().title() or "FAO AMR PowerPoint Draft"


def _score(text: str, title: str) -> int:
    terms = set(re.findall(r"[a-z0-9]+", title.lower()))
    haystack = text.lower()
    return sum(1 for term in terms if term in haystack)


def _select_sources(index: list[dict], title: str, limit: int = 3) -> list[str]:
    ranked = sorted(index, key=lambda item: (_score(item.get("text", ""), title), item.get("kind") == "presentation"), reverse=True)
    return [item["source_id"] for item in ranked[:limit] if _score(item.get("text", ""), title) > 0]


def _bullets_for(title: str) -> list[str]:
    if title == "Sources":
        return ["Review source map for slide-level evidence", "Verify internal clearance before external use"]
    if title == "Closing or discussion":
        return ["Summarize the main historical arc", "Connect past milestones to current FAO AMR priorities", "Invite discussion on next steps"]
    return [
        f"Summarize the FAO AMR relevance of {title.lower()}",
        "Reuse strong points from previous FAO AMR presentations when available",
        "Support key claims with report evidence and source notes",
    ]


def plan_deck(prompt: str, index: list[dict], max_slides: int = 11) -> dict:
    title = _slug_title(prompt)
    outline = DEFAULT_HISTORY_OUTLINE if title == "AMR history in FAO" else [title, "Context", "Key messages", "Evidence", "Recommended actions", "Sources"]
    outline = outline[:max_slides]
    slides = []
    for number, slide_title in enumerate(outline, start=1):
        layout = "title" if number == 1 else "sources" if slide_title == "Sources" else "content"
        slides.append(
            {
                "slide_number": number,
                "layout": layout,
                "title": slide_title,
                "bullets": [] if layout == "title" else _bullets_for(slide_title),
                "speaker_notes": "",
                "source_ids": [] if layout == "title" else _select_sources(index, slide_title),
            }
        )
    return {"prompt": prompt, "title": title, "slides": slides}


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan an FAO AMR PPTX deck.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-slides", type=int, default=11)
    args = parser.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    plan = plan_deck(args.prompt, index, max_slides=args.max_slides)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote deck plan with {len(plan['slides'])} slides to {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_plan_deck.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/plan_deck.py tests/fao_amr_pptx_builder/test_plan_deck.py
git commit -m "Add FAO AMR deck planner"
```

---

### Task 5: Editable PPTX Creation

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/create_pptx.py`
- Create: `tests/fao_amr_pptx_builder/test_create_pptx.py`

**Interfaces:**
- Consumes: `deck_plan.json`, `source_index.json`, optional `template.pptx`
- Produces: `create_pptx(plan: dict, index: list[dict], output: Path, template: Path | None = None, source_map: Path | None = None) -> None`
- Produces CLI: `python create_pptx.py --plan deck_plan.json --index source_index.json --template template.pptx --output draft.pptx --source-map source_map.json`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_create_pptx.py`:

```python
from pathlib import Path
import importlib.util

from pptx import Presentation


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/create_pptx.py")


def load_module():
    spec = importlib.util.spec_from_file_location("create_pptx", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_create_pptx_writes_editable_deck_and_source_map(tmp_path):
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "AMR history in FAO", "bullets": [], "source_ids": []},
            {"slide_number": 2, "layout": "content", "title": "Why AMR matters to FAO", "bullets": ["Food and agriculture relevance"], "source_ids": ["src001"]},
        ],
    }
    index = [{"source_id": "src001", "relative_path": "history.pptx", "location": "slide 3", "text": "Food and agriculture relevance"}]
    output = tmp_path / "draft.pptx"
    source_map = tmp_path / "source_map.json"

    module = load_module()
    module.create_pptx(plan, index, output, source_map=source_map)

    assert output.exists()
    assert source_map.exists()
    prs = Presentation(str(output))
    assert len(prs.slides) == 2
    slide_text = "\n".join(shape.text for shape in prs.slides[1].shapes if hasattr(shape, "text"))
    assert "Food and agriculture relevance" in slide_text
    source_map_data = json.loads(source_map.read_text(encoding="utf-8"))
    assert source_map_data["slides"][1]["sources"][0]["relative_path"] == "history.pptx"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_create_pptx.py -v
```

Expected: FAIL because `create_pptx.py` does not exist.

- [ ] **Step 3: Implement PPTX generation**

Create `skills/fao-amr-pptx-builder/scripts/create_pptx.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pptx import Presentation
import json
from pptx.util import Inches, Pt


def _source_lookup(index: list[dict]) -> dict[str, dict]:
    return {item["source_id"]: item for item in index}


def _add_title_slide(prs: Presentation, title: str) -> None:
    layout = prs.slide_layouts[0] if len(prs.slide_layouts) > 0 else prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    if slide.shapes.title:
        slide.shapes.title.text = title
    else:
        box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.0), Inches(1.0))
        box.text_frame.text = title


def _add_content_slide(prs: Presentation, slide_plan: dict, sources: dict[str, dict]) -> None:
    layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    if slide.shapes.title:
        slide.shapes.title.text = slide_plan["title"]
    else:
        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12.0), Inches(0.6))
        title_box.text_frame.text = slide_plan["title"]

    body = None
    for shape in slide.placeholders:
        if shape.placeholder_format.idx != 0 and hasattr(shape, "text_frame"):
            body = shape
            break
    if body is None:
        body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.2), Inches(4.8))

    frame = body.text_frame
    frame.clear()
    for index, bullet in enumerate(slide_plan.get("bullets", [])):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = bullet
        paragraph.level = 0
        paragraph.font.size = Pt(24)

    note_lines = []
    for source_id in slide_plan.get("source_ids", []):
        source = sources.get(source_id)
        if source:
            note_lines.append(f"{source_id}: {source['relative_path']} ({source['location']})")
    if note_lines:
        notes = slide.notes_slide.notes_text_frame
        notes.text = "\n".join(note_lines)


def _write_source_map(plan: dict, sources: dict[str, dict], source_map: Path) -> None:
    payload = {"title": plan.get("title", "Deck"), "slides": []}
    for slide in plan.get("slides", []):
        slide_sources = []
        for source_id in slide.get("source_ids", []):
            source = sources.get(source_id)
            if source:
                slide_sources.append(
                    {
                        "source_id": source_id,
                        "relative_path": source["relative_path"],
                        "location": source["location"],
                    }
                )
        payload["slides"].append(
            {
                "slide_number": slide["slide_number"],
                "title": slide["title"],
                "sources": slide_sources,
            }
        )
    source_map.parent.mkdir(parents=True, exist_ok=True)
    source_map.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def create_pptx(plan: dict, index: list[dict], output: Path, template: Path | None = None, source_map: Path | None = None) -> None:
    prs = Presentation(str(template)) if template else Presentation()
    sources = _source_lookup(index)
    for slide in plan.get("slides", []):
        if slide.get("layout") == "title":
            _add_title_slide(prs, slide["title"])
        else:
            _add_content_slide(prs, slide, sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output)
    if source_map:
        _write_source_map(plan, sources, source_map)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an editable FAO AMR PPTX deck.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template")
    parser.add_argument("--source-map")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    create_pptx(
        plan,
        index,
        Path(args.output),
        template=Path(args.template) if args.template else None,
        source_map=Path(args.source_map) if args.source_map else None,
    )
    print(f"Wrote editable PPTX to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_create_pptx.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/create_pptx.py tests/fao_amr_pptx_builder/test_create_pptx.py
git commit -m "Add editable PPTX generator"
```

---

### Task 6: Revision Workflow

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/revise_deck.py`
- Create: `tests/fao_amr_pptx_builder/test_revise_deck.py`

**Interfaces:**
- Consumes: prior `deck_plan.json`, user review instruction
- Produces: `revise_deck(plan: dict, review: str) -> dict`
- Produces CLI: `python revise_deck.py --plan deck_plan.json --review "make it shorter" --output deck_plan_v2.json`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_revise_deck.py`:

```python
from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/revise_deck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("revise_deck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_revise_deck_shortens_content_slides():
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "Title", "bullets": [], "source_ids": []},
            {"slide_number": 2, "layout": "content", "title": "A", "bullets": ["one", "two", "three"], "source_ids": []},
            {"slide_number": 3, "layout": "content", "title": "B", "bullets": ["one", "two", "three"], "source_ids": []},
            {"slide_number": 4, "layout": "sources", "title": "Sources", "bullets": ["source"], "source_ids": []},
        ],
    }

    module = load_module()
    revised = module.revise_deck(plan, "make it shorter")

    assert len(revised["slides"]) == 3
    assert revised["revision_note"] == "make it shorter"
    assert [slide["slide_number"] for slide in revised["slides"]] == [1, 2, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_revise_deck.py -v
```

Expected: FAIL because `revise_deck.py` does not exist.

- [ ] **Step 3: Implement simple revision rules**

Create `skills/fao-amr-pptx-builder/scripts/revise_deck.py`:

```python
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def _renumber(slides: list[dict]) -> list[dict]:
    for index, slide in enumerate(slides, start=1):
        slide["slide_number"] = index
    return slides


def revise_deck(plan: dict, review: str) -> dict:
    revised = copy.deepcopy(plan)
    review_lower = review.lower()
    slides = revised.get("slides", [])
    if "shorter" in review_lower or "concise" in review_lower:
        title_slides = [slide for slide in slides if slide.get("layout") == "title"]
        source_slides = [slide for slide in slides if slide.get("layout") == "sources" or slide.get("title") == "Sources"]
        content_slides = [slide for slide in slides if slide not in title_slides and slide not in source_slides]
        kept = title_slides + content_slides[: max(1, len(content_slides) - 1)] + source_slides
        revised["slides"] = _renumber(kept)
    elif "more technical" in review_lower:
        for slide in slides:
            if slide.get("layout") == "content":
                slide.setdefault("bullets", []).append("Add technical detail from source evidence during manual review")
    revised["revision_note"] = review
    return revised


def main() -> None:
    parser = argparse.ArgumentParser(description="Revise an FAO AMR deck plan.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    revised = revise_deck(plan, args.review)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(revised, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote revised deck plan to {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_revise_deck.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/revise_deck.py tests/fao_amr_pptx_builder/test_revise_deck.py
git commit -m "Add FAO AMR deck revision helper"
```

---

### Task 7: End-To-End Validation And README Update

**Files:**
- Modify: `README.md`
- Create: `tests/fao_amr_pptx_builder/test_end_to_end_workflow.py`

**Interfaces:**
- Consumes all scripts from earlier tasks
- Produces tested workflow from source folder to editable `.pptx`

- [ ] **Step 1: Write the failing end-to-end test**

Create `tests/fao_amr_pptx_builder/test_end_to_end_workflow.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

from pptx import Presentation


ROOT = Path.cwd()
SCAN = ROOT / "skills/fao-amr-pptx-builder/scripts/scan_sources.py"
INDEX = ROOT / "skills/fao-amr-pptx-builder/scripts/build_source_index.py"
PLAN = ROOT / "skills/fao-amr-pptx-builder/scripts/plan_deck.py"
CREATE = ROOT / "skills/fao-amr-pptx-builder/scripts/create_pptx.py"


def test_end_to_end_workflow_creates_editable_pptx(tmp_path):
    materials = tmp_path / "OneDrive AMR Materials"
    materials.mkdir()
    source_deck = materials / "history.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "FAO AMR timeline"
    slide.placeholders[1].text = "One Health and Action Plan milestones"
    prs.save(source_deck)

    sources = tmp_path / "sources.json"
    index = tmp_path / "source_index.json"
    plan = tmp_path / "deck_plan.json"
    output = tmp_path / "draft.pptx"
    source_map = tmp_path / "source_map.json"

    subprocess.run([sys.executable, str(SCAN), "--source-folder", str(materials), "--output", str(sources)], check=True)
    subprocess.run([sys.executable, str(INDEX), "--sources", str(sources), "--output", str(index)], check=True)
    subprocess.run([sys.executable, str(PLAN), "--prompt", "give me a PPT of AMR history in FAO", "--index", str(index), "--output", str(plan)], check=True)
    subprocess.run([sys.executable, str(CREATE), "--plan", str(plan), "--index", str(index), "--output", str(output), "--source-map", str(source_map)], check=True)

    assert output.exists()
    assert source_map.exists()
    assert json.loads(plan.read_text(encoding="utf-8"))["title"] == "AMR history in FAO"
    generated = Presentation(str(output))
    assert len(generated.slides) >= 10
```

- [ ] **Step 2: Run test to verify it fails if any workflow step is missing**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_end_to_end_workflow.py -v
```

Expected before previous tasks are complete: FAIL. Expected after previous tasks are complete: PASS.

- [ ] **Step 3: Add README usage section**

Append to `README.md`:

```markdown
## FAO AMR PPTX Builder Skill

This repository includes a shareable Codex skill at `skills/fao-amr-pptx-builder/`.

Use it when you want Codex to create an editable PowerPoint draft from repeated FAO AMR materials:

```text
Use the FAO AMR PPTX builder to give me a PPT of AMR history in FAO using this template and the materials in my local OneDrive AMR folder.
```

For v1, OneDrive materials must be available as a synced local folder. The skill does not connect directly to Microsoft Graph or OneDrive cloud APIs.

The generated output includes:

- `draft.pptx` - editable PowerPoint deck
- `deck_plan.json` - slide-by-slide plan
- `source_map.json` - source traceability per slide
```

- [ ] **Step 4: Run all relevant tests**

Run:

```powershell
pytest tests\fao_amr_pptx_builder tests\test_retrieval.py -v
```

Expected: PASS.

- [ ] **Step 5: Validate skill metadata again**

Run:

```powershell
python "C:\Users\徐曼灵\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\fao-amr-pptx-builder
```

Expected: validation passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add README.md tests/fao_amr_pptx_builder/test_end_to_end_workflow.py
git commit -m "Document FAO AMR PPTX builder workflow"
```

---

## Final Verification

Run:

```powershell
pytest -v
python "C:\Users\徐曼灵\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills\fao-amr-pptx-builder
```

Expected:

- All tests pass.
- Skill validation passes.
- A generated `.pptx` from the end-to-end test opens with editable text in PowerPoint.

## Self-Review Notes

- Spec coverage: OneDrive-synced folder, supplied template, reusable previous PPTs, reports, JSON artifacts, editable PPTX, source map, and revision workflow are covered.
- Placeholder scan: no unfinished marker terms or vague deferred-work tasks are intentionally included.
- Type consistency: source scan, index, plan, PPTX creation, revision, and source map all use the shared `source_id`, `slides`, `source_ids`, and JSON artifact names defined above.
