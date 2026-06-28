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


def _is_warning_source(source_item: dict) -> bool:
    return str(source_item.get("location", "")).strip().lower() == "extraction warning"


def _select_sources(index: list[dict], title: str, limit: int = 3, allow_warning: bool = False) -> list[str]:
    candidates = [item for item in index if allow_warning or not _is_warning_source(item)]
    ranked = sorted(
        candidates,
        key=lambda item: (
            _score(item.get("text", ""), title),
            item.get("kind", "") == "presentation",
        ),
        reverse=True,
    )
    selected = []
    seen = set()
    for item in ranked:
        source_id = item.get("source_id")
        if not source_id or source_id in seen:
            continue
        if _score(item.get("text", ""), title) <= 0:
            continue
        selected.append(source_id)
        seen.add(source_id)
        if len(selected) >= limit:
            break
    return selected


def _bullets_for(title: str) -> list[str]:
    if title == "Sources":
        return [
            "Review source map for slide-level evidence",
            "Verify internal clearance before external use",
        ]
    if title == "Closing or discussion":
        return [
            "Summarize the main historical arc",
            "Connect past milestones to current FAO AMR priorities",
            "Invite discussion on next steps",
        ]
    return [
        f"Summarize the FAO AMR relevance of {title.lower()}",
        "Reuse strong points from previous FAO AMR presentations when available",
        "Support key claims with report evidence and source notes",
    ]


def plan_deck(prompt: str, index: list[dict], max_slides: int = 11) -> dict:
    title = _slug_title(prompt)
    if title == "AMR history in FAO":
        outline = DEFAULT_HISTORY_OUTLINE
    else:
        outline = [title, "Context", "Key messages", "Evidence", "Recommended actions", "Sources"]
    outline = outline[:max_slides]

    slides = []
    for number, slide_title in enumerate(outline, start=1):
        is_title = number == 1
        is_sources_layout = slide_title == "Sources"
        layout = "title" if is_title else "sources" if is_sources_layout else "content"
        allow_warning_sources = is_sources_layout
        slides.append(
            {
                "slide_number": number,
                "layout": layout,
                "title": slide_title,
                "bullets": [] if is_title else _bullets_for(slide_title),
                "speaker_notes": "",
                "source_ids": [] if is_title else _select_sources(index, slide_title, allow_warning=allow_warning_sources),
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
