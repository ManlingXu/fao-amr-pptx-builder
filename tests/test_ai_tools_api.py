"""Exercise the Copilot-facing analysis and layout-decision contracts."""
from __future__ import annotations

import base64
import io
import time

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pptx import Presentation

from presentation_search.api import create_app
from presentation_search.auth import Identity
from presentation_search.config import Settings


def _presentation_bytes() -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Zambia stewardship"
    slide.placeholders[1].text = "farmers traditional leaders antibiotics"
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


@pytest.fixture
def ai_app(tmp_path, monkeypatch):
    def principal(self, request: Request):
        return request.headers.get("X-Test-Owner", "alice")

    monkeypatch.setattr(Identity, "principal", principal)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "Zambia.pptx").write_bytes(_presentation_bytes())
    settings = Settings(
        _env_file=None,
        auth_mode="local_demo",
        local_presentation_path=inputs,
        drafts_path=tmp_path / "jobs",
    )
    return settings, create_app(settings=settings)


def _slide_id(client: TestClient) -> str:
    response = client.post("/api/search", json={"query": "Zambia farmers"})
    assert response.status_code == 200, response.text
    return response.json()["results"][0]["slideId"]


def _wait(client: TestClient, job: dict) -> dict:
    for _ in range(300):
        result = client.get(job["statusUrl"]).json()
        if result["status"] in {"completed", "failed"}:
            assert result["status"] == "completed", result
            return result
        time.sleep(0.02)
    pytest.fail("Draft did not finish")


def _completed_draft(client: TestClient) -> dict:
    response = client.post(
        "/api/drafts",
        json={
            "title": "Zambia brief",
            "slide_ids": [_slide_id(client)],
            "confirmed": True,
        },
    )
    assert response.status_code == 202, response.text
    return _wait(client, response.json())


def _upload_template(client: TestClient) -> dict:
    presentation = Presentation()
    sample = presentation.slides.add_slide(presentation.slide_layouts[0])
    sample.shapes.title.text = "Brand sample"
    output = io.BytesIO()
    presentation.save(output)
    response = client.post(
        "/api/templates",
        json={
            "file_name": "Brand.pptx",
            "content_base64": base64.b64encode(output.getvalue()).decode(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_analyze_slides_resolves_real_source_and_preserves_requested_order(ai_app):
    _, app = ai_app
    with TestClient(app) as client:
        slide_id = _slide_id(client)
        response = client.post("/api/slides/analyze", json={"slide_ids": [slide_id]})

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["slides"]) == 1
    analysis = data["slides"][0]
    assert analysis["slideId"] == slide_id
    assert analysis["deckName"] == "Zambia.pptx"
    assert analysis["slideNumber"] == 1
    assert analysis["title"] == "Zambia stewardship"
    assert analysis["wordCount"] == 6
    assert analysis["textShapeCount"] == 2
    assert analysis["pictureCount"] == 0
    assert analysis["tableCount"] == 0
    assert analysis["chartCount"] == 0
    assert analysis["groupCount"] == 0
    assert analysis["contentType"] == "text"
    assert analysis["density"] in {"low", "medium", "high"}
    assert analysis["recommendedLayoutAction"] in {"reuse", "reflow", "review"}
    assert 0 <= analysis["occupancyRatio"] <= 1
    assert any("structural" in item.lower() for item in data["limitations"])


def test_analyze_slides_rejects_unknown_duplicate_and_changed_sources(ai_app):
    settings, app = ai_app
    with TestClient(app) as client:
        slide_id = _slide_id(client)
        assert client.post(
            "/api/slides/analyze", json={"slide_ids": [slide_id, slide_id]}
        ).status_code == 422
        assert client.post(
            "/api/slides/analyze", json={"slide_ids": ["missing"]}
        ).status_code == 409
        (settings.local_presentation_path / "Zambia.pptx").write_bytes(_presentation_bytes() + b"changed")
        stale = client.post("/api/slides/analyze", json={"slide_ids": [slide_id]})

    assert stale.status_code == 409
    assert "source" in stale.json()["detail"].lower()


def test_completed_draft_has_owner_scoped_heuristic_layout_report(ai_app):
    _, app = ai_app
    with TestClient(app) as client:
        completed = _completed_draft(client)
        response = client.get(completed["statusUrl"] + "/layout-report")
        denied = client.get(
            completed["statusUrl"] + "/layout-report",
            headers={"X-Test-Owner": "bob"},
        )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["jobId"] == completed["jobId"]
    assert report["slideCount"] == 1
    assert report["slides"][0]["slideNumber"] == 1
    assert isinstance(report["slides"][0]["issues"], list)
    assert any("heuristic" in item.lower() for item in report["limitations"])
    assert denied.status_code == 404


def test_apply_template_accepts_validated_ai_layout_override(ai_app):
    _, app = ai_app
    with TestClient(app) as client:
        original = _completed_draft(client)
        template = _upload_template(client)
        request = {
            "template_id": template["templateId"],
            "confirmed": True,
            "layout_overrides": [{"output_slide": 1, "layout_name": "Title Only"}],
        }
        response = client.post(original["statusUrl"] + "/template", json=request)
        assert response.status_code == 202, response.text
        revised = _wait(client, response.json())
        output = Presentation(io.BytesIO(client.get(revised["downloadUrl"]).content))

        unknown = client.post(
            original["statusUrl"] + "/template",
            json={
                **request,
                "layout_overrides": [{"output_slide": 1, "layout_name": "Invented by AI"}],
            },
        )
        outside = client.post(
            original["statusUrl"] + "/template",
            json={
                **request,
                "layout_overrides": [{"output_slide": 2, "layout_name": "Title Only"}],
            },
        )

    assert revised["layoutOverrides"] == [{"outputSlide": 1, "layoutName": "Title Only"}]
    assert output.slides[0].slide_layout.name == "Title Only"
    assert unknown.status_code == 422
    assert outside.status_code == 422


def test_apply_template_rejects_ambiguous_template_layout_name_before_queueing(ai_app):
    _, app = ai_app
    with TestClient(app) as client:
        original = _completed_draft(client)
        presentation = Presentation()
        presentation.slide_layouts[0].name = "Duplicate"
        presentation.slide_layouts[1].name = "Duplicate"
        output = io.BytesIO()
        presentation.save(output)
        template_response = client.post(
            "/api/templates",
            json={
                "file_name": "Ambiguous.pptx",
                "content_base64": base64.b64encode(output.getvalue()).decode(),
            },
        )
        assert template_response.status_code == 201, template_response.text
        template = template_response.json()
        assert template["layoutNames"].count("Duplicate") == 2

        response = client.post(
            original["statusUrl"] + "/template",
            json={
                "template_id": template["templateId"],
                "confirmed": True,
                "layout_overrides": [{"output_slide": 1, "layout_name": "Duplicate"}],
            },
        )

    assert response.status_code == 422
    assert "ambiguous" in response.json()["detail"].lower()

