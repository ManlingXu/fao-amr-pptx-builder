from datetime import datetime, timezone

from presentation_search.models import SlideDocument
from presentation_search.search import SearchIndex


def document(key, title, body):
    return SlideDocument(
        id=key, deck_id=key, deck_name=f"{key}.pptx", slide_number=1,
        title=title, text=body, notes="", source_url=f"https://example.test/{key}.pptx",
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc), effective_year=None,
        date_confidence=0.0, date_reason="unknown", family_key=key,
    )


def test_distinctive_evidence_in_slide_body_can_outweigh_common_title_terms():
    evidence = document("outreach", "Community engagement", "Radio programmes for traditional leaders")
    background = [
        document(f"policy-{n}", "Prudent use of antibiotics", "Prudent use of antibiotics farming policy")
        for n in range(8)
    ]
    index = SearchIndex([evidence, *background])
    hits = index.search("prudent use of antibiotics radio programmes traditional leaders")
    assert hits[0].slide.id == "outreach"


def test_replace_refreshes_documents_fields_and_document_frequency_together():
    orchard = document("orchard", "Orchard", "Trees")
    fishery = document("fishery", "Fishery", "Water")
    index = SearchIndex([orchard, fishery, *(document(f"f{n}", "Fishery", "") for n in range(8))])
    assert index.search("orchard fishery")[0].slide.id == "orchard"
    index.replace([orchard, fishery, *(document(f"o{n}", "Orchard", "") for n in range(8))])
    assert index.search("orchard fishery")[0].slide.id == "fishery"
    assert index.search("f1") == []
    index.replace([])
    assert index.search("orchard") == []


def test_catalogue_title_supplies_context_separately_from_original_slide_text():
    slide = document("opaque-id", "Community outreach", "Radio broadcasts and public meetings")
    slide.deck_title = "National stewardship in Kenya"
    assert SearchIndex([slide]).search("Kenya")[0].slide is slide
    assert "Kenya" not in slide.text


def test_recency_boost_tracks_relevance_except_for_explicit_recency_queries():
    recent = document("update-2025", "Outreach", "Outreach")
    recent.effective_year = datetime.now().year
    recent.date_confidence = 1.0
    index = SearchIndex([recent])
    regular = index.search("outreach radio programmes")[0]
    explicit = index.search("latest outreach radio programmes")[0]
    assert regular.relevance_score == explicit.relevance_score
    assert regular.final_score < explicit.final_score
