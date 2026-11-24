import csv
import hashlib
import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches

from scripts.run_public_corpus_demo import run_demo


def write_deck(folder, name, titles, *, width=10):
    path = folder / (name + ".pptx")
    deck = Presentation()
    deck.slide_width = Inches(width)
    for title in titles:
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = title
    deck.save(path)
    return {"id": name, "title": "Source " + name, "source_page": f"https://example.org/{name}",
            "download_url": f"https://example.org/{name}.pptx",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def manifest(root, rows):
    with (root / "verified.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def get_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_confirmed_public_demo_exports_reordered_native_slides_with_web_provenance(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    a = write_deck(files, "a", ["Welcome", "Antibiotic stewardship"])
    b = write_deck(files, "b", ["Feed management"])
    write_deck(files, "stale", ["Unlisted phrase"])
    for row in (a, b):
        row.update(author="Example Author", license="CC BY 4.0", issued="2024-10-01")
    manifest(tmp_path, [a, b])
    result = run_demo(tmp_path, tmp_path / "output", ["antibiotic stewardship", "feed management"],
                      confirm=True, reverse_sections=True)
    run = Path(result["output_directory"])
    assert result["status"] == "completed"
    assert (result["indexed_decks"], result["indexed_slides"], result["source_decks"]) == (2, 3, 2)
    assert result["revision"] == 2
    assert [slide.shapes.title.text for slide in Presentation(run / "editable_draft.pptx").slides] == [
        "Feed management", "Antibiotic stewardship"]
    sources = get_json(run / "source_map.json")
    assert [(s["outputSlide"], s["deckTitle"], s["slideNumber"], s["sourcePage"], s["downloadUrl"])
            for s in sources] == [
        (1, b["title"], 1, b["source_page"], b["download_url"]),
        (2, a["title"], 2, a["source_page"], a["download_url"])]
    search_result = get_json(run / "search_results.json")[0]["results"][0]
    assert search_result["url"] == a["source_page"]
    for key in ("author", "license", "issued"):
        assert search_result[key] == sources[0][key] == a[key]


def test_underfilled_or_unconfirmed_plan_does_not_generate_a_draft(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    valid = write_deck(files, "a", ["Stewardship"])
    changed = write_deck(files, "b", ["Obsolete content"])
    manifest(tmp_path, [valid, {**changed, "sha256": "0" * 64}])
    missing = run_demo(tmp_path, tmp_path / "out", ["missingphrase"], confirm=True)
    assert missing["status"] == "incomplete_plan"
    assert missing["underfilled_sections"] == ["missingphrase"]
    assert get_json(Path(missing["output_directory"]) / "versions.json") == [
        {"query": "missingphrase", "firstHitSlideId": None, "versions": []}]
    assert missing["indexed_decks"] == 1
    assert missing["index_failures"][0]["id"] == "b"
    preview = run_demo(tmp_path, tmp_path / "out", ["stewardship"])
    assert preview["status"] == "preview"
    assert preview["output_directory"] != missing["output_directory"]
    assert not list((tmp_path / "out").rglob("*.pptx"))
    with pytest.raises(ValueError, match="output directory"):
        run_demo(tmp_path, files / "drafts", ["stewardship"])


def test_incompatible_ranked_candidate_is_disclosed_and_replaced(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    a = write_deck(files, "a", ["Stewardship", "Farm education"])
    b = write_deck(files, "b", ["Consumer education"], width=12)
    manifest(tmp_path, [a, b])
    result = run_demo(tmp_path, tmp_path / "out", ["stewardship", "consumer education"], confirm=True)
    assert result["status"] == "completed"
    assert result["skipped_incompatible"][0]["deckName"] == "b.pptx"
    assert "dimensions" in result["skipped_incompatible"][0]["reason"]
    source_map = get_json(Path(result["output_directory"]) / "source_map.json")
    assert [(s["deckName"], s["slideNumber"]) for s in source_map] == [("a.pptx", 1), ("a.pptx", 2)]

def test_optional_template_applies_through_plan_and_draft_api(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    manifest(tmp_path, [write_deck(files, "a", ["Antibiotic stewardship"])])
    template = tmp_path / "design.pptx"
    design = Presentation()
    design.slide_width = Inches(12)
    design.slide_height = Inches(6.75)
    design.slides.add_slide(design.slide_layouts[1]).shapes.title.text = "Template example"
    design.save(template)
    result = run_demo(tmp_path, tmp_path / "out", ["stewardship"], confirm=True, template=template)
    assert result["status"] == "completed"
    assert result["template"] == "design.pptx"
    run = Path(result["output_directory"])
    assert get_json(run / "revised_plan.json")["templateId"]
    draft = Presentation(run / "editable_draft.pptx")
    assert draft.slide_width == design.slide_width and draft.slide_height == design.slide_height
    assert len(draft.slides) == 1
    assert "Antibiotic stewardship" in [shape.text for shape in draft.slides[0].shapes if shape.has_text_frame]

def test_versions_preview_reports_only_actual_members_of_first_hit_family(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    rows = []
    for year in ("2022", "2023"):
        row = write_deck(files, f"farm-report-{year}", ["Stewardship"])
        rows.append({**row, "issued": year})
    other = write_deck(files, "other-2021", ["Stewardship"])
    manifest(tmp_path, [*rows, {**other, "issued": "2021"}])
    result = run_demo(tmp_path, tmp_path / "out", ["stewardship"])
    assert result["status"] == "preview"
    group, = get_json(Path(result["output_directory"]) / "versions.json")
    latest, previous = group["versions"]
    assert group["firstHitSlideId"] == latest["slideId"]
    assert [latest["issued"], previous["issued"]] == ["2023", "2022"]
    assert [latest["deckTitle"], previous["sourcePage"]] == [rows[1]["title"], rows[0]["source_page"]]


def test_interactive_review_exports_exact_candidate_ranks_in_selected_order(tmp_path, monkeypatch, capsys):
    files = tmp_path / "presentations"
    files.mkdir()
    manifest(tmp_path, [write_deck(files, "a", ["Feed nutrition", "Feed planning", "Feed monitoring"])])
    answers = iter(["2,1", "yes"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    result = run_demo(tmp_path, tmp_path / "out", ["feed"], interactive=True)
    assert result["status"] == "completed"
    run = Path(result["output_directory"])
    first, second, _ = get_json(run / "search_results.json")[0]["results"]
    source_map = get_json(run / "source_map.json")
    assert [s["slideId"] for s in source_map] == [second["slideId"], first["slideId"]]
    assert len(result["interactive_rejections"]) == 0
    output = capsys.readouterr().out
    assert "Revision 2" in output and "Source a · original slide" in output


@pytest.mark.parametrize("answers", [["", "no"], ["", ""], ["", None], [None]])
def test_interactive_decline_or_end_of_input_keeps_only_preview(tmp_path, monkeypatch, answers):
    files = tmp_path / "presentations"
    files.mkdir()
    manifest(tmp_path, [write_deck(files, "a", ["Feed nutrition"])])
    replies = iter(answers)

    def answer(_):
        value = next(replies)
        if value is None:
            raise EOFError
        return value

    monkeypatch.setattr("builtins.input", answer)
    result = run_demo(tmp_path, tmp_path / "out", ["feed"], interactive=True)
    assert result["status"] == "preview"
    run = Path(result["output_directory"])
    assert (run / "revised_plan.json").is_file()
    assert not (run / "editable_draft.pptx").exists()


def test_interactive_incompatible_choices_are_rejected_without_substitution(tmp_path, monkeypatch, capsys):
    files = tmp_path / "presentations"
    files.mkdir()
    manifest(tmp_path, [write_deck(files, "a", ["Feed education"]),
                        write_deck(files, "b", ["Feed planning"], width=12)])
    replies = iter(["1,2", "2", "yes"])
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    result = run_demo(tmp_path, tmp_path / "out", ["feed"], interactive=True)
    assert result["status"] == "completed"
    run = Path(result["output_directory"])
    second = get_json(run / "search_results.json")[0]["results"][1]
    assert [s["slideId"] for s in get_json(run / "source_map.json")] == [second["slideId"]]
    assert result["interactive_rejections"][0]["input"] == "1,2"
    assert "Selection rejected" in capsys.readouterr().out


def test_lower_ranked_lead_can_unlock_a_complete_multisection_briefing(tmp_path):
    files = tmp_path / "presentations"
    files.mkdir()
    a = write_deck(files, "a", ["Farm education"], width=12)
    b = write_deck(files, "b", ["Education", "Nutrition"])
    manifest(tmp_path, [a, b])
    result = run_demo(tmp_path, tmp_path / "out", ["farm education", "nutrition"], confirm=True)
    assert result["status"] == "completed"
    first, second = result["selection_attempts"]
    assert first["filled_sections"] == 1
    assert second["lead_candidate_rank"] == 2 and second["selected"]
    sources = get_json(Path(result["output_directory"]) / "source_map.json")
    assert [(s["deckName"], s["slideNumber"]) for s in sources] == [("b.pptx", 1), ("b.pptx", 2)]


def test_published_example_traces_every_slide_to_a_pinned_catalogue_entry():
    from io import BytesIO
    from zipfile import ZipFile

    from scripts.fetch_public_corpus import read_catalog

    folder = Path(__file__).parents[1] / "examples" / "public_corpus"
    rows = read_catalog(folder / "catalog.csv")
    checksums = {r["sha256"] for r in rows}
    assert len(checksums) == len(rows) >= 100 and "" not in checksums
    assert len({r["download_url"] for r in rows}) == len(rows)
    by_source = {r["source_page"]: r for r in rows}
    with ZipFile(folder / "Vietnam_AMR_demo.zip") as example:
        deck = Presentation(BytesIO(example.read("Vietnam_AMR_demo.pptx")))
        credits = json.loads(example.read("source_map.json"))
        assert example.testzip() is None
    assert len(deck.slides) == len(credits) == 3
    assert len({s["sourcePage"] for s in credits}) == 2
    for idx, (slide, credit) in enumerate(zip(deck.slides, credits), 1):
        assert idx == credit["outputSlide"]
        assert credit["sourceHash"] == by_source[credit["sourcePage"]]["sha256"]
        assert credit["title"] == slide.shapes.title.text


def test_sector_filter_limits_search_and_carries_archive_provenance(tmp_path):
    folder = tmp_path / "presentations"
    folder.mkdir()
    rows = [
        dict(write_deck(folder, "farm", ["Antibiotic stewardship"]), sector="animal", training_country="Latvia", zip_member="farm.pptx"),
        dict(write_deck(folder, "ward", ["Antibiotic stewardship"]), sector="human", training_country="", zip_member=""),
    ]
    manifest(tmp_path, rows)
    result = run_demo(tmp_path, tmp_path / "out", ["stewardship"], sectors=["animal"], confirm=True)
    assert result["status"] == "completed" and result["indexed_decks"] == 1
    [source] = get_json(Path(result["output_directory"]) / "source_map.json")
    assert (source["sector"], source["archiveMember"]) == ("animal", "farm.pptx")
    assert source["trainingCountry"] == "Latvia"
    with pytest.raises(ValueError, match="selected sectors"):
        run_demo(tmp_path, tmp_path / "out", ["stewardship"], sectors=["one-health"])
