from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from math import log

from .freshness import freshness_score
from .models import SearchResult, SlideDocument

TOKEN_RE = re.compile(r"[^\W_]+")
RECENCY_TERMS = {"latest", "newest", "recent", "current", "updated", "update"}
STOPWORDS = RECENCY_TERMS | set(
    "a an and are for from in is of on or our presentation slide the this to with material find show me".split()
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
        self.replace(slides or [])

    @property
    def slides(self) -> list[SlideDocument]:
        return self._snapshot[0]

    def replace(self, slides: list[SlideDocument]) -> None:
        documents = list(slides)
        fields = []
        document_frequency = Counter()
        for slide in documents:
            title = set(tokenize(slide.title))
            terms = title.union(tokenize(" ".join((slide.text, slide.notes, slide.deck_name, slide.deck_title))))
            fields.append((title, terms))
            document_frequency.update(terms)
        # Publish the new documents, their token fields and frequencies together.
        self._snapshot = documents, fields, document_frequency

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

    def search(self, query: str, limit: int = 15, latest_only: bool = True) -> list[SearchResult]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        slides, fields, frequencies = self._snapshot
        # Smoothed inverse document frequency gives specific terms more weight.
        # Words outside this corpus carry only the base weight.
        weights = {
            term: 1 + log((len(slides) + 1) / (frequencies[term] + 1)) if term in frequencies else 1.0
            for term in set(query_tokens)
        }
        denominator = 3 * sum(weights.values())
        phrase = " ".join(query_tokens)
        requests_recency = not RECENCY_TERMS.isdisjoint(TOKEN_RE.findall(query.lower()))
        counts = Counter(s.family_key for s in slides)
        best = {}
        for slide in slides:
            best[slide.family_key] = max(best.get(slide.family_key, (0, "", 0.0)), date_order(slide))
        candidates = []
        for slide, (title, terms) in zip(slides, fields):
            latest = date_order(slide) == best[slide.family_key]
            if latest_only and not latest:
                continue
            matches = weights.keys() & terms
            if not matches:
                continue
            # Full-slide matches supply the evidence; titles receive an extra boost.
            coverage = sum(weights[t] * (3 if t in title else 2) for t in matches) / denominator
            phrase_bonus = 0.1 if phrase in f"{slide.title} {slide.text}".lower() else 0.0
            relevance = min(1.0, coverage + phrase_bonus)
            fresh = freshness_score(slide.effective_year, slide.date_confidence, datetime.now().year)
            # For a content question, recency boosts evidence already matched.
            # A direct request for recent material keeps the full date weighting.
            freshness_weight = 0.22 if requests_recency else 0.22 * relevance
            status = (
                "DATE UNKNOWN" if not period(slide) else ("LATEST" if latest else "NEWER VERSION AVAILABLE")
            )
            candidates.append(
                SearchResult(
                    slide=slide,
                    relevance_score=round(relevance, 6),
                    freshness_score=fresh,
                    final_score=round(relevance * 0.78 + fresh * freshness_weight, 6),
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
