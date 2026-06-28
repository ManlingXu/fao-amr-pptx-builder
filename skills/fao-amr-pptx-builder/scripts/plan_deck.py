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

FAO_AMR_KEYWORDS = {
    "action",
    "agrifood",
    "agriculture",
    "amr",
    "antimicrobial",
    "collaboration",
    "country",
    "countries",
    "evidence",
    "fao",
    "food",
    "governance",
    "health",
    "milestones",
    "one",
    "plan",
    "quadripartite",
    "resistance",
    "responsible",
    "surveillance",
    "timeline",
    "use",
}

STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "for",
    "give",
    "in",
    "me",
    "of",
    "on",
    "ppt",
    "powerpoint",
    "the",
    "to",
}


def _slug_title(prompt: str) -> str:
    lowered = prompt.lower()
    if "history" in lowered and "fao" in lowered and "amr" in lowered:
        return "AMR history in FAO"
    cleaned = re.sub(r"\b(give|make|create|me|a|an|ppt|powerpoint|deck|of|about)\b", " ", lowered)
    words = [word for word in re.findall(r"[a-z0-9]+", cleaned) if word]
    return " ".join(words[:8]).strip().title() or "FAO AMR PowerPoint Draft"


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", text.lower()) if term not in STOPWORDS}


def _evidence_score(text: str, query: str) -> int:
    haystack = text.lower()
    query_terms = _terms(query)
    title_score = sum(3 for term in query_terms if term in haystack)
    keyword_score = sum(1 for term in FAO_AMR_KEYWORDS if term in haystack)
    return title_score + keyword_score


def _is_warning_source(source_item: dict) -> bool:
    return str(source_item.get("location", "")).strip().lower() == "extraction warning"


def _usable_index(index: list[dict], query: str) -> list[dict]:
    return [
        item
        for item in index
        if not _is_warning_source(item)
        and item.get("source_id")
        and str(item.get("text", "")).strip()
        and _evidence_score(item.get("text", ""), query) > 0
    ]


def _select_sources(index: list[dict], title: str, limit: int = 3, allow_warning: bool = False) -> list[str]:
    candidates = [item for item in index if allow_warning or not _is_warning_source(item)]
    ranked = sorted(
        candidates,
        key=lambda item: (
            _evidence_score(item.get("text", ""), title),
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
        if _evidence_score(item.get("text", ""), title) <= 0:
            continue
        selected.append(source_id)
        seen.add(source_id)
        if len(selected) >= limit:
            break
    return selected


def _split_fragments(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    fragments = re.split(r"(?<=[.!?;])\s+|\s+[•\-]\s+", normalized)
    return [fragment.strip(" .;:\t\r\n") for fragment in fragments if fragment.strip(" .;:\t\r\n")]


def _presentation_bullet(fragment: str, max_words: int = 18, max_chars: int = 140) -> str:
    words = fragment.split()
    if len(words) > max_words:
        fragment = " ".join(words[:max_words])
    if len(fragment) > max_chars:
        fragment = fragment[:max_chars].rsplit(" ", 1)[0]
    return fragment.strip(" .;:")


def _ranked_fragments(index: list[dict], title: str) -> list[tuple[int, bool, str, str]]:
    ranked: list[tuple[int, bool, str, str]] = []
    for item in index:
        source_id = item.get("source_id", "")
        if not source_id or _is_warning_source(item):
            continue
        for fragment in _split_fragments(item.get("text", "")):
            score = _evidence_score(fragment, title)
            if score <= 0:
                continue
            ranked.append((score, item.get("kind", "") == "presentation", fragment, source_id))
    return sorted(ranked, key=lambda entry: (entry[0], entry[1], len(entry[2])), reverse=True)


def _bullets_for(title: str, index: list[dict]) -> list[str]:
    if title == "Sources":
        source_lines = []
        seen = set()
        for item in index:
            source_id = item.get("source_id")
            if not source_id or source_id in seen or _is_warning_source(item):
                continue
            seen.add(source_id)
            source_lines.append(
                _presentation_bullet(
                    f"{item.get('relative_path', 'source')} ({item.get('location', 'source')})"
                )
            )
            if len(source_lines) >= 5:
                break
        return source_lines or ["No usable source evidence was available"]

    bullets: list[str] = []
    seen_text = set()
    for _score_value, _is_presentation, fragment, _source_id in _ranked_fragments(index, title):
        bullet = _presentation_bullet(fragment)
        key = bullet.lower()
        if key in seen_text:
            continue
        bullets.append(bullet)
        seen_text.add(key)
        if len(bullets) >= 3:
            break
    return bullets


def _source_ids_for_bullets(title: str, index: list[dict], limit: int = 3) -> list[str]:
    source_ids: list[str] = []
    seen = set()
    for _score_value, _is_presentation, _fragment, source_id in _ranked_fragments(index, title):
        if source_id in seen:
            continue
        source_ids.append(source_id)
        seen.add(source_id)
        if len(source_ids) >= limit:
            break
    return source_ids


def _evidence_gap_plan(prompt: str, title: str) -> dict:
    gap_title = f"Evidence gap: {title}"
    return {
        "prompt": prompt,
        "title": gap_title,
        "slides": [
            {
                "slide_number": 1,
                "layout": "title",
                "title": gap_title,
                "bullets": [],
                "speaker_notes": "",
                "source_ids": [],
            },
            {
                "slide_number": 2,
                "layout": "content",
                "title": "Evidence gap",
                "bullets": [
                    "No relevant non-warning source evidence was found in the indexed materials",
                    "A polished FAO AMR deck needs traceable prior slides, reports, or approved source notes",
                ],
                "speaker_notes": "",
                "source_ids": [],
            },
            {
                "slide_number": 3,
                "layout": "content",
                "title": "Materials needed",
                "bullets": [
                    "Add OneDrive-synced FAO AMR presentations, action plans, reports, or surveillance materials",
                    "Rerun source scanning and indexing before drafting the full deck",
                ],
                "speaker_notes": "",
                "source_ids": [],
            },
        ],
    }


def plan_deck(prompt: str, index: list[dict], max_slides: int = 11) -> dict:
    title = _slug_title(prompt)
    usable_index = _usable_index(index, f"{prompt} {title}")
    if not usable_index:
        return _evidence_gap_plan(prompt, title)

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
                "bullets": [] if is_title else _bullets_for(slide_title, usable_index),
                "speaker_notes": "",
                "source_ids": []
                if is_title
                else _select_sources(index, slide_title, allow_warning=allow_warning_sources)
                if is_sources_layout
                else _source_ids_for_bullets(slide_title, usable_index),
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
