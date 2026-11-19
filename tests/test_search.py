from datetime import datetime, timezone

from presentation_search.models import SlideDocument
from presentation_search.search import SearchIndex


def slide(*, deck: str, year: int, modified_year: int, suffix: str = "") -> SlideDocument:
    return SlideDocument(
        id=f"{deck}-{year}{suffix}",
        deck_id=deck,
        deck_name=f"{deck}_{year}.pptx",
        slide_number=8,
        title="AMR surveillance in Africa",
        text=f"Antimicrobial resistance surveillance in livestock. Data through {year}.",
        notes="",
        source_url=f"https://example.test/{deck}_{year}.pptx",
        modified_at=datetime(modified_year, 11, 9, tzinfo=timezone.utc),
        effective_year=year,
        date_confidence=1.0,
        date_reason="explicit data period",
        family_key="amr surveillance in africa",
        content_type="current_data",
    )


def test_latest_query_prefers_newer_content_even_when_old_file_was_modified_later():
    index = SearchIndex([
        slide(deck="AMR_Update", year=2021, modified_year=2026),
        slide(deck="AMR_Update", year=2025, modified_year=2025),
    ])

    results = index.search("latest AMR surveillance livestock Africa", limit=10)

    assert results[0].slide.effective_year == 2025
    assert results[0].freshness_status == "LATEST"
    assert results[0].related_versions == 2


def test_search_deduplicates_related_slide_versions():
    index = SearchIndex([
        slide(deck="AMR_Update", year=2023, modified_year=2023),
        slide(deck="AMR_Update", year=2024, modified_year=2024),
        slide(deck="AMR_Update", year=2025, modified_year=2025),
    ])

    results = index.search("AMR surveillance Africa", limit=10)

    assert len(results) == 1
    assert results[0].slide.effective_year == 2025
    assert results[0].related_versions == 3
