import csv
import hashlib
import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches


def make_corpus(tmp, widths=(10, 13.333), *, include_table=False):
    sources = tmp / "presentations"
    sources.mkdir()
    rows, selections = [], []
    for index, width in enumerate(widths, start=1):
        deck = Presentation()
        deck.slide_width = Inches(width)
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = f"Veterinary stewardship {index}"
        body = f"Farmers in district {index} discussed prudent antibiotic use at the meeting."
        slide.placeholders[1].text = body
        if include_table and index == 1:
            table = slide.shapes.add_table(3, 2, Inches(1), Inches(2), Inches(8), Inches(3)).table
            for i, row in enumerate((("District", "Attendees (people)"), ("North", "39"), ("East", "42"))):
                for j, text in enumerate(row):
                    table.cell(i, j).text = text
        slide.notes_slide.notes_text_frame.text = f"Field report {index}."
        key = f"source-{index}"
        path = sources / f"{key}.pptx"
        deck.save(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(dict(id=key, sha256=digest, title=f"Community outreach {index}", author=f"Author {index}",
                         publisher="Training service", source_page=f"https://example.org/{key}",
                         download_url=f"https://example.org/{key}.pptx", license="CC BY", issued="2024"))
        selections.append(dict(slide_id=f"page-{index}", deck_id=key, slide_number=1, source_hash=digest,
                               evidence=body, reason="Outreach activities"))
    with (tmp / "verified.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return selections


@pytest.mark.parametrize("widths,mode", [((10, 10), "native"), ((10, 13.333), "evidence_excerpts")])
def test_sources_follow_selected_pages_into_both_designs(tmp_path, widths, mode):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path, widths)[::-1]
    files = export_brief(tmp_path, tmp_path / "output", "Veterinary outreach", selected)
    assert files["assembly_mode"] == mode
    records = json.loads(Path(files["source_map"]).read_text(encoding="utf-8"))
    assert [record["sourcePage"] for record in records] == ["https://example.org/source-2", "https://example.org/source-1"]
    for name in ("draft", "styled"):
        ppt = Presentation(files[name])
        assert len(ppt.slides) == 2
        for slide, number in zip(ppt.slides, [2, 1]):
            notes = slide.notes_slide.notes_text_frame.text
            for value in [f"Field report {number}.", f"Author {number}", f"https://example.org/source-{number}", "Original slide 1"]:
                assert value in notes
    assert Path(files["draft"]).read_bytes() != Path(files["styled"]).read_bytes()


def test_custom_master_dimensions_and_background_are_applied(tmp_path):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path)
    template = Presentation()
    template.slide_master.background.fill.solid()
    template.slide_master.background.fill.fore_color.rgb = RGBColor.from_string("ABBCC0")
    path = tmp_path / "custom.pptx"
    template.save(path)
    files = export_brief(tmp_path, tmp_path / "out", "Local briefing", selected, template=path)
    deck = Presentation(files["styled"])
    assert deck.slide_width == template.slide_width
    assert deck.slide_master.background.fill.fore_color.rgb == RGBColor.from_string("ABBCC0")


@pytest.mark.parametrize("fault", ["source_hash", "evidence", "duplicate"])
def test_unverified_selections_do_not_create_artifacts(tmp_path, fault):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path)
    if fault == "duplicate":
        selected = [selected[0], selected[0]]
    else:
        selected[0][fault] = "unverified"
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        export_brief(tmp_path, output, "Brief", selected)
    assert not list(output.glob("*.pptx"))


def test_existing_draft_is_never_replaced(tmp_path):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "draft.pptx").write_bytes(b"previous")
    with pytest.raises(FileExistsError):
        export_brief(tmp_path, output, "Brief", selected)
    assert (output / "draft.pptx").read_bytes() == b"previous"
    assert not (output / "styled.pptx").exists()


def test_native_export_uses_the_bytes_that_were_verified(tmp_path, monkeypatch):
    from presentation_search import brief_export
    selected = make_corpus(tmp_path, (10, 10))
    assemble = brief_export.assemble_slides

    def update_source_then_assemble(paths, destination):
        sources = tmp_path / "presentations"
        (sources / "source-1.pptx").write_bytes((sources / "source-2.pptx").read_bytes())
        return assemble(paths, destination)

    monkeypatch.setattr(brief_export, "assemble_slides", update_source_then_assemble)
    files = brief_export.export_brief(tmp_path, tmp_path / "out", "Brief", selected)
    assert Presentation(files["draft"]).slides[0].shapes.title.text == "Veterinary stewardship 1"


def test_mixed_deck_keeps_table_evidence_with_headers_and_units(tmp_path):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path, include_table=True)
    selected[0]["evidence"] = "39"
    files = export_brief(tmp_path, tmp_path / "out", "Outreach", selected)
    slide = Presentation(files["draft"]).slides[0]
    table = next(shape.table for shape in slide.shapes if shape.has_table)
    assert [[cell.text for cell in row.cells] for row in table.rows] == [
        ["District", "Attendees (people)"], ["North", "39"], ["East", "42"]]


def test_reflow_normalizes_compatible_native_files_on_request(tmp_path):
    from presentation_search.brief_export import export_brief
    selected = make_corpus(tmp_path, (10, 10))
    files = export_brief(tmp_path, tmp_path / "out", "Outreach", selected, reflow=True)
    assert files["assembly_mode"] == "evidence_excerpts"
    deck = Presentation(files["draft"])
    assert deck.slide_width == Inches(13.333)
    assert any(s.has_text_frame and "Original slide 1" in s.text for s in deck.slides[0].shapes)
