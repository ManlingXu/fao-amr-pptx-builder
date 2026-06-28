from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def _renumber(slides: list[dict]) -> list[dict]:
    for index, slide in enumerate(slides, start=1):
        slide["slide_number"] = index
    return slides


def _extract_unresolved_source_ids(
    source_map: dict | None,
    known_source_ids: set[str],
) -> tuple[int, list[str]]:
    if not source_map:
        return 0, []

    slides = source_map.get("slides", [])
    unresolved_source_ids: list[str] = []

    if isinstance(slides, dict):
        slide_entries = slides.values()
        slide_count = len(slides)
    else:
        slide_entries = slides
        slide_count = len(slides)

    for slide in slide_entries:
        if isinstance(slide, dict) and "sources" in slide:
            sources = slide.get("sources", [])
        elif isinstance(slide, list):
            sources = slide
        else:
            sources = []

        for source in sources:
            if isinstance(source, str):
                if source not in known_source_ids:
                    unresolved_source_ids.append(source)
                continue
            if not source.get("resolved", True) and source.get("source_id"):
                unresolved_source_ids.append(source["source_id"])

    return slide_count, sorted(set(unresolved_source_ids))


def _build_revision_context(
    source_index: list[dict] | None,
    source_map: dict | None,
) -> dict:
    known_source_ids = {
        item["source_id"]
        for item in (source_index or [])
        if isinstance(item, dict) and item.get("source_id")
    }
    source_map_slide_count, unresolved_source_ids = _extract_unresolved_source_ids(
        source_map,
        known_source_ids,
    )
    return {
        "source_index_count": len(source_index or []),
        "source_map_slide_count": source_map_slide_count,
        "unresolved_source_ids": unresolved_source_ids,
    }


def revise_deck(
    plan: dict,
    review: str,
    source_index: list[dict] | None = None,
    source_map: dict | None = None,
) -> dict:
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
    if source_index is not None or source_map is not None:
        revised["revision_context"] = _build_revision_context(source_index, source_map)
    return revised


def main() -> None:
    parser = argparse.ArgumentParser(description="Revise an FAO AMR deck plan.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--index")
    parser.add_argument("--source-map")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    source_index = json.loads(Path(args.index).read_text(encoding="utf-8")) if args.index else None
    source_map = json.loads(Path(args.source_map).read_text(encoding="utf-8")) if args.source_map else None
    revised = revise_deck(plan, args.review, source_index=source_index, source_map=source_map)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(revised, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote revised deck plan to {output}")


if __name__ == "__main__":
    main()
