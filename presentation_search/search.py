from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from .freshness import freshness_score
from .models import SearchResult, SlideDocument

TOKEN_RE = re.compile(r"[^\W_]+")
STOPWORDS = set(
    "a an and are for from in is of on or our presentation slide the this to with material find show me latest newest recent current updated update".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def period(slide: SlideDocument) -> str:
    return slide.report_date or (str(slide.effective_year) if slide.effective_year else "")


def date_order(slide: SlideDocument) -> tuple[int, str, float]:
    # A report period outranks a speculative year inferred from an unlabeled title or filename.
    if slide.date_confidence >= 0.95:
        tier = 3
    elif slide.date_reason == "slide year":
        tier = 2
    else:
        tier = 1 if period(slide) else 0
    return tier, period(slide), slide.date_confidence


class SearchIndex:
    def __init__(self, slides: list[SlideDocument] | None = None):
        self.slides = list(slides or [])

    def replace(self, slides: list[SlideDocument]) -> None:
        self.slides = list(slides)

    def __len__(self) -> int:
        return len(self.slides)

    def lookup(self, ids: list[str]) -> list[SlideDocument]:
        by_id = {s.id: s for s in self.slides}
        return [by_id[s] for s in ids]

    def versions(self, slide_id: str) -> list[SlideDocument]:
        slides = self.slides
        selected = next((s for s in slides if s.id == slide_id), None)
        if not selected:
            raise KeyError(slide_id)
        return sorted(
            (s for s in slides if s.family_key == selected.family_key), key=date_order, reverse=True
        )

    def _relevance(self, query_tokens: list[str], slide: SlideDocument) -> float:
        if not query_tokens:
            return 0.0
        title_tokens = set(tokenize(slide.title))
        body_tokens = set(tokenize(" ".join([slide.text, slide.notes, slide.deck_name])))
        unique = set(query_tokens)
        coverage = (2 * len(unique & title_tokens) + len(unique & body_tokens)) / (len(unique) * 3)
        phrase_bonus = 0.1 if " ".join(query_tokens) in f"{slide.title} {slide.text}".lower() else 0.0
        return min(1.0, coverage + phrase_bonus)

    def search(self, query: str, limit: int = 15, latest_only: bool = True) -> list[SearchResult]:
        query_tokens = tokenize(query)
        slides = self.slides
        counts = Counter(s.family_key for s in slides)
        best = {}
        for slide in slides:
            best[slide.family_key] = max(best.get(slide.family_key, (0, "", 0.0)), date_order(slide))
        candidates = []
        for slide in slides:
            latest = date_order(slide) == best[slide.family_key]
            if latest_only and not latest:
                continue
            relevance = self._relevance(query_tokens, slide)
            if not relevance:
                continue
            fresh = freshness_score(slide.effective_year, slide.date_confidence, datetime.now().year)
            status = (
                "DATE UNKNOWN" if not period(slide) else ("LATEST" if latest else "NEWER VERSION AVAILABLE")
            )
            candidates.append(
                SearchResult(
                    slide=slide,
                    relevance_score=round(relevance, 6),
                    freshness_score=fresh,
                    final_score=round(relevance * 0.78 + fresh * 0.22, 6),
                    freshness_status=status,
                    related_versions=counts[slide.family_key],
                    explanation=[f"Date basis: {slide.date_reason}"],
                )
            )
        candidates.sort(key=lambda r: (r.final_score, date_order(r.slide), r.slide.id), reverse=True)
        seen = set()
        result = []
        for item in candidates:
            if latest_only and item.slide.family_key in seen:
                continue
            result.append(item)
            seen.add(item.slide.family_key)
            if len(result) == max(1, min(limit, 15)):
                break
        return result
