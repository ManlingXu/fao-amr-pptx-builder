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
