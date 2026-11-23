"""V2 storyline planning, revision safety, ownership and end-to-end draft creation."""
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


def deck(path, title, body):
    p = Presentation()
    slide = p.slides.add_slide(p.slide_layouts[1])
    slide.shapes.title.text = title
    slide.placeholders[1].text = body
    slide.notes_slide.notes_text_frame.text = "Synthetic speaker notes"
    p.save(path)


@pytest.fixture
def client(tmp_path, monkeypatch):
    def principal(self, request: Request):
        return request.headers.get("X-Test-Owner", "alice")

    monkeypatch.setattr(Identity, "principal", principal)
    sources = tmp_path / "sources"
    sources.mkdir()
    deck(sources / "Africa_AMR_2025.pptx", "AMR surveillance in Africa", "Data through 2025. Livestock evidence.")
    deck(sources / "One_Health_2026.pptx", "One Health policy", "As of 2026-08. Policy and planning.")
    deck(sources / "Africa_AMR_2022.pptx", "AMR surveillance in Africa", "Data through 2021. Livestock evidence.")
    s = Settings(_env_file=None, auth_mode="local_demo",
                 local_presentation_path=sources, drafts_path=tmp_path / "private")
    with TestClient(create_app(settings=s)) as app:
        yield app


def plan_request(**extra):
    return {
        "title": "AMR situation in Africa",
        "audience": "Veterinary authorities",
        "purpose": "Conference briefing",
        "sections": [
            {"title": "Situation", "query": "AMR surveillance livestock Africa", "slide_count": 1},
            {"title": "One Health", "query": "One Health policy", "slide_count": 1},
        ],
        **extra,
    }


def test_plan_creates_grounded_storyline_and_completes_draft(client):
    created = client.post("/api/plans", json=plan_request())
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["revision"] == 1
    assert plan["isReadyForDraft"] is True
    assert plan["requiresUserConfirmation"] is True
    assert plan["needsReview"] is False
    assert plan["sections"][0]["title"] == "Situation"
    assert plan["sections"][1]["title"] == "One Health"
    assert len(plan["sourceMap"]) == 2
    assert plan["sourceMap"][0]["deckName"] == "Africa_AMR_2025.pptx"
    assert plan["sourceMap"][0]["reportDate"] == "2025"
    assert plan["sourceMap"][1]["deckName"] == "One_Health_2026.pptx"
    assert "owner" not in plan
    plan_id = plan["planId"]
    assert client.get(f"/api/plans/{plan_id}").json() == plan

    # No generation until confirmation.
    failed = client.post(f"/api/plans/{plan_id}/draft",
                         json={"expected_revision": 1, "confirmed": False})
    assert failed.status_code == 422
    result = client.post(f"/api/plans/{plan_id}/draft",
                         json={"expected_revision": 1, "confirmed": True})
    assert result.status_code == 202, result.text

    job = result.json()
    for _ in range(250):
        progress = client.get(job["statusUrl"]).json()
        if progress["status"] in {"completed", "failed"}:
            break
        time.sleep(.02)
    else:
        pytest.fail("V2 draft timed out")
    assert progress["status"] == "completed", progress
    assert [s["deckName"] for s in progress["sourceMap"]] == [
        "Africa_AMR_2025.pptx", "One_Health_2026.pptx"
    ]
    document = client.get(progress["downloadUrl"])
    assert document.status_code == 200
    prs = Presentation(io.BytesIO(document.content))
    assert len(prs.slides) == 2
    assert [slide.shapes.title.text for slide in prs.slides] == [
        "AMR surveillance in Africa", "One Health policy"
    ]


def test_multiturn_edit_requires_fresh_revision_and_reorders_sections(client):
    p = client.post("/api/plans", json=plan_request()).json()
    plan_id = p["planId"]
    first_id = p["sections"][0]["slideIds"][0]
    second_id = p["sections"][1]["slideIds"][0]
    payload = {
        "expected_revision": 1,
        "sections": [
            {"title": "Policy first", "query": "One Health policy", "slide_ids": [second_id]},
            {"title": "AMR evidence", "query": "AMR Africa", "slide_ids": [first_id]},
        ],
    }
    updated = client.put(f"/api/plans/{plan_id}", json=payload)
    assert updated.status_code == 200, updated.text
    new = updated.json()
    assert new["revision"] == 2
    assert [s["title"] for s in new["sections"]] == ["Policy first", "AMR evidence"]
    assert [s["deckName"] for s in new["sourceMap"]] == [
        "One_Health_2026.pptx", "Africa_AMR_2025.pptx"
    ]
    assert client.put(f"/api/plans/{plan_id}", json=payload).status_code == 409
    assert client.post(f"/api/plans/{plan_id}/draft",
                       json={"expected_revision": 1, "confirmed": True}).status_code == 409
    # The newest revision remains intact.
    assert client.get(f"/api/plans/{plan_id}").json() == new


def test_plan_does_not_hallucinate_missing_sources_and_can_be_repaired(client):
    created = client.post("/api/plans", json=plan_request(
        sections=[{"title": "Missing", "query": "xenobacterial purple goat", "slide_count": 3}]
    ))
    assert created.status_code == 201
    p = created.json()
    assert p["needsReview"] is True
    assert p["isReadyForDraft"] is False
    assert p["sections"][0]["slideIds"] == []
    assert client.post(f"/api/plans/{p['planId']}/draft",
                       json={"expected_revision": 1, "confirmed": True}).status_code == 409
    repair = client.post("/api/search", json={"query": "One Health"}).json()["results"][0]
    patched = client.put(f"/api/plans/{p['planId']}", json={
        "expected_revision": 1, "sections": [{
            "title": "Available evidence", "query": "One Health",
            "slide_ids": [repair["slideId"]],
        }]
    })
    assert patched.status_code == 200, patched.text
    assert patched.json()["isReadyForDraft"] is True


def test_plan_validates_duplicates_unknown_ids_and_owner(client):
    p = client.post("/api/plans", json=plan_request()).json()
    plan_id = p["planId"]
    ids = [s["slideIds"][0] for s in p["sections"]]
    assert client.get(f"/api/plans/{plan_id}", headers={"X-Test-Owner": "bob"}).status_code == 404
    assert client.put(f"/api/plans/{plan_id}", headers={"X-Test-Owner": "bob"},
                      json={"expected_revision": 1, "sections": []}).status_code in (404, 422)
    assert client.post(f"/api/plans/{plan_id}/draft",
                       headers={"X-Test-Owner": "bob"},
                       json={"expected_revision": 1, "confirmed": True}).status_code == 404
    assert client.put(f"/api/plans/{plan_id}", json={
        "expected_revision": 1,
        "sections": [
            {"title": "A", "query": "AMR", "slide_ids": [ids[0]]},
            {"title": "B", "query": "One Health", "slide_ids": [ids[0]]},
        ],
    }).status_code == 422
    assert client.put(f"/api/plans/{plan_id}", json={
        "expected_revision": 1,
        "sections": [{"title": "Unknown", "query": "AMR", "slide_ids": ["nonexistent-id"]}],
    }).status_code == 422
    assert client.get(f"/api/plans/{plan_id}").json()["revision"] == 1


def test_plan_template_id_must_belong_to_requester(client):
    template = Presentation()
    template.slides.add_slide(template.slide_layouts[1])
    stream = io.BytesIO()
    template.save(stream)
    upload = client.post("/api/templates", json={
        "file_name": "Demo.pptx", "content_base64": base64.b64encode(stream.getvalue()).decode()
    })
    assert upload.status_code == 201, upload.text
    template_id = upload.json()["templateId"]
    allowed = client.post("/api/plans", json=plan_request(template_id=template_id))
    assert allowed.status_code == 201, allowed.text
    denied = client.post("/api/plans", headers={"X-Test-Owner": "bob"},
                         json=plan_request(template_id=template_id))
    assert denied.status_code == 404
    p = allowed.json()
    assert p["templateId"] == template_id
    assert client.put(f"/api/plans/{p['planId']}", json={
        "expected_revision": 1, "template_id": "0" * 32,
        "sections": [{"title": "AMR", "query": "AMR",
                      "slide_ids": [p["sections"][0]["slideIds"][0]]}],
    }).status_code == 404


def test_bad_section_limits_and_invalid_plan_ids(client):
    assert client.post("/api/plans", json=plan_request(
        sections=[{"title": "Huge", "query": "AMR", "slide_count": 21}]
    )).status_code == 422
    assert client.post("/api/plans", json=plan_request(
        sections=[{"title": "Empty", "query": "  ", "slide_count": 1}]
    )).status_code == 422
    assert client.get("/api/plans/../../etc/passwd").status_code != 200
    assert client.get("/api/plans/aaaa").status_code == 404
