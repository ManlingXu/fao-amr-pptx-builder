from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

ContentType = Literal[
    "current_data",
    "project_update",
    "policy",
    "methodology",
    "definition",
    "recommendation",
    "historical",
    "unknown",
]


@dataclass(slots=True)
class DateSignal:
    effective_year: int | None
    confidence: float
    reason: str
    modified_time_confidence: float = 0.20
    report_date: str | None = None


@dataclass(slots=True)
class SlideDocument:
    id: str
    deck_id: str
    deck_name: str
    slide_number: int
    title: str
    text: str
    notes: str
    source_url: str
    modified_at: datetime | None
    effective_year: int | None
    date_confidence: float
    date_reason: str
    family_key: str
    content_type: ContentType = "unknown"
    report_date: str | None = None
    source_hash: str = ""
    source_key: str = ""
    deck_title: str = ""


@dataclass(slots=True)
class DeckDocument:
    id: str
    filename: str
    path: Path
    source_url: str
    modified_at: datetime | None
    slides: list[SlideDocument] = field(default_factory=list)


@dataclass(slots=True)
class SearchResult:
    slide: SlideDocument
    relevance_score: float
    freshness_score: float
    final_score: float
    freshness_status: str
    related_versions: int
    explanation: list[str]
