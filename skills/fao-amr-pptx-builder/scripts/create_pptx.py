from __future__ import annotations

import argparse
import json
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt


def _source_lookup(index: list[dict]) -> dict[str, dict]:
    return {item["source_id"]: item for item in index if item.get("source_id")}


def _add_title_slide(prs: Presentation, title: str) -> None:
    layout = prs.slide_layouts[0] if len(prs.slide_layouts) > 0 else prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    if slide.shapes.title is not None:
        slide.shapes.title.text = title
        return

    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.0), Inches(1.0))
    box.text_frame.text = title


def _body_placeholder(slide):
    for shape in slide.placeholders:
        if shape.placeholder_format.idx != 0 and hasattr(shape, "text_frame"):
            return shape
    return None


def _add_content_slide(prs: Presentation, slide_plan: dict, sources: dict[str, dict]) -> None:
    layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)
    if slide.shapes.title is not None:
        slide.shapes.title.text = slide_plan["title"]
    else:
        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12.0), Inches(0.6))
        title_box.text_frame.text = slide_plan["title"]

    body = _body_placeholder(slide)
    if body is None:
        body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.2), Inches(4.8))

    frame = body.text_frame
    frame.clear()
    for bullet_index, bullet in enumerate(slide_plan.get("bullets", [])):
        paragraph = frame.paragraphs[0] if bullet_index == 0 else frame.add_paragraph()
        paragraph.text = bullet
        paragraph.level = 0
        paragraph.font.size = Pt(24)

    note_lines = []
    for source_id in slide_plan.get("source_ids", []):
        source = sources.get(source_id)
        if source is None:
            continue
        note_lines.append(f"{source_id}: {source['relative_path']} ({source['location']})")
    if note_lines:
        slide.notes_slide.notes_text_frame.text = "\n".join(note_lines)


def _write_source_map(plan: dict, sources: dict[str, dict], source_map: Path) -> None:
    payload = {"title": plan.get("title", "Deck"), "slides": []}
    for slide in plan.get("slides", []):
        slide_sources = []
        for source_id in slide.get("source_ids", []):
            source = sources.get(source_id)
            if source is None:
                continue
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


def create_pptx(
    plan: dict,
    index: list[dict],
    output: Path,
    template: Path | None = None,
    source_map: Path | None = None,
) -> None:
    prs = Presentation(str(template)) if template else Presentation()
    sources = _source_lookup(index)

    for slide in plan.get("slides", []):
        if slide.get("layout") == "title":
            _add_title_slide(prs, slide["title"])
        else:
            _add_content_slide(prs, slide, sources)

    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output)

    if source_map is not None:
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
