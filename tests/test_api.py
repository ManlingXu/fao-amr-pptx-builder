from datetime import datetime, timezone

from fastapi.testclient import TestClient

from presentation_search.api import create_app
from presentation_search.config import Settings
from presentation_search.models import SlideDocument
from presentation_search.search import SearchIndex


def make_slide(i: int) -> SlideDocument:
    return SlideDocument(
        id=str(i),
        deck_id=f"deck-{i}",
        deck_name=f"AMR_Deck_{i}_2026.pptx",
        slide_number=i + 1,
        title=f"AMR topic {i}",
        text=f"Antimicrobial resistance livestock Africa evidence item {i}. Data through 2025.",
        notes="",
        source_url=f"https://example.test/deck-{i}",
        modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_year=2025,
        date_confidence=1.0,
        date_reason="explicit data period",
        family_key=f"amr topic {i}",
        content_type="current_data",
    )


def test_copilot_search_returns_expected_schema_and_caps_results_at_15():
    app = create_app(
        index=SearchIndex([make_slide(i) for i in range(20)]), settings=Settings(auth_mode="local_demo")
    )
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 44000))

    response = client.get("/api/copilot/search", params={"q": "AMR livestock Africa", "limit": 100})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "AMR livestock Africa"
    assert len(payload["results"]) == 15
    assert set(payload["results"][0]) == {"title", "snippet", "url"}
    assert "Slide" in payload["results"][0]["title"]


def test_health_reports_ready():
    app = create_app(index=SearchIndex([make_slide(1)]))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["slides"] == 1


def test_copilot_search_requires_api_key_when_configured():
    app = create_app(
        index=SearchIndex([make_slide(1)]),
        settings=Settings(copilot_api_key="secret"),
    )
    client = TestClient(app)

    denied = client.get("/api/copilot/search", params={"q": "AMR"})
    allowed = client.get(
        "/api/copilot/search",
        params={"q": "AMR"},
        headers={"X-API-Key": "secret"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_detailed_search_requires_api_key_when_configured():
    app = create_app(
        index=SearchIndex([make_slide(1)]),
        settings=Settings(copilot_api_key="secret"),
    )
    client = TestClient(app)
    body = {"query": "AMR"}

    assert client.post("/api/search", json=body).status_code == 401
    assert client.post("/api/search", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    allowed = client.post("/api/search", json=body, headers={"X-API-Key": "secret"})
    assert allowed.status_code == 200
    assert allowed.json()["results"][0]["deckName"] == "AMR_Deck_1_2026.pptx"
