import json

import pytest
from pptx import Presentation

from presentation_search import studio_model
from presentation_search.studio_service import StudioService

from test_local_brief_workflow import corpus_fixture


def test_review_reorder_export_then_restyle_retains_versions(tmp_path):
    svc = StudioService(corpus_fixture(tmp_path), tmp_path / "exports")
    state = svc.new_session()
    first = svc.turn(state, "Zambia stewardship", {"count": 2, "min_year": 2024})
    assert first["stats"]["decks"] == 2 and len(first["slides"]) == 2
    assert not first["model_used"]
    moved = svc.turn(state, "move slide 2 to slide 1")
    assert moved["slides"][0]["id"] == first["slides"][1]["id"]
    version = svc.turn(state, "", action="generate")["versions"][0]
    assert svc.turn(state, "confirm")["versions"] == [version]
    path = svc.output_dir / version["id"]
    pptx = Presentation(path / version["files"]["pptx"])
    sources = json.loads((path / version["files"]["sources"]).read_text())
    checks = json.loads((path / version["files"]["qa"]).read_text())
    assert checks["source_hashes_and_excerpts_verified"]
    assert all(r["sourcePage"] in sl.notes_slide.notes_text_frame.text for r, sl in zip(sources, pptx.slides))
    assert sources[0]["slideId"] == moved["slides"][0]["id"]
    restyled = svc.turn(state, "", {"template": "field"}, action="generate")
    assert len(restyled["versions"]) == 2 and restyled["versions"][0] == version
    assert svc.turn(state, "", {"min_year": 2025})["slides"] == []


@pytest.mark.parametrize("mode", ["compilation", "reconstruction", "hybrid"])
def test_generation_modes_reopen_in_office_package(tmp_path, mode):
    svc = StudioService(corpus_fixture(tmp_path), tmp_path / "versions")
    state = svc.new_session()
    svc.turn(state, "Zambia stewardship", {"count": 2, "mode": mode, "audience": "Farm advisers"})
    version = svc.turn(state, "", action="generate")["versions"][0]
    deck = Presentation(svc.output_dir / version["id"] / version["files"]["pptx"])
    assert len(deck.slides) == 2
    assert all("Farm advisers" in page.notes_slide.notes_text_frame.text for page in deck.slides)


def test_credential_gate_budget_and_transaction_rollback(tmp_path, monkeypatch):
    svc = StudioService(corpus_fixture(tmp_path), tmp_path / "versions")
    state = svc.new_session()
    before = svc.turn(state, "Zambia stewardship", {"count": 2})
    monkeypatch.setenv("PPT_STUDIO_ENABLE_OPENAI", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    def no_network(*args, **kwargs):
        raise AssertionError("A model request must not be sent when budget is denied")
    monkeypatch.setattr(studio_model.httpx, "post", no_network)
    with pytest.raises(ValueError, match="budget"):
        svc.turn(state, "", {"model": "openai"}, reserve_model=lambda *_: False)
    assert svc.snapshot(state) == before


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_model_writing_preserves_immutable_evidence(tmp_path, monkeypatch, provider):
    svc = StudioService(corpus_fixture(tmp_path), tmp_path / "versions")
    state = svc.new_session()

    def adapt(instructions, data, max_output_tokens, reserve, requested_provider):
        assert requested_provider == provider
        assert data["language"] == "zh" and data["audience"] == "农民"
        return {"pages": [{"id": r["id"], "title": "培训资料", "body": "介绍来源资料中的培训活动。",
                           "notes": "请听众举出一个与本地工作有关的例子。"} for r in data["slides"]]}
    monkeypatch.setattr(studio_model, "request_json", adapt)
    result = svc.turn(state, "Zambia stewardship", {"model": provider, "language": "zh", "audience": "农民",
                                                    "count": 2, "mode": "reconstruction"})
    assert result["model_used"] and result["slides"][0]["title"] == "培训资料"
    assert "介绍" not in result["slides"][0]["evidence"]
    version = svc.turn(state, "confirm")["versions"][0]
    deck = Presentation(svc.output_dir / version["id"] / version["files"]["pptx"])
    assert deck.slides[0].shapes.title.text == "培训资料"
    assert "请听众举出" in deck.slides[0].notes_slide.notes_text_frame.text
