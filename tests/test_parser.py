from pathlib import Path

from pptx import Presentation

from presentation_search.pptx_parser import parse_presentation


def test_parser_extracts_title_body_table_and_notes(tmp_path: Path):
    path = tmp_path / "AMR_Update_2026.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Antimicrobial use in livestock"
    box = slide.shapes.add_textbox(100, 100, 500, 100)
    box.text_frame.text = "Data through 2025"
    table_shape = slide.shapes.add_table(2, 2, 100, 250, 500, 200)
    table_shape.table.cell(0, 0).text = "Region"
    table_shape.table.cell(0, 1).text = "Africa"
    table_shape.table.cell(1, 0).text = "Indicator"
    table_shape.table.cell(1, 1).text = "AMR"
    slide.notes_slide.notes_text_frame.text = "Internal technical note"
    prs.save(path)

    deck = parse_presentation(path)

    assert deck.filename == "AMR_Update_2026.pptx"
    assert len(deck.slides) == 1
    parsed = deck.slides[0]
    assert parsed.title == "Antimicrobial use in livestock"
    assert "Data through 2025" in parsed.text
    assert "Africa" in parsed.text
    assert "Internal technical note" in parsed.notes
    assert parsed.effective_year == 2025


def test_imports_grouped_text_from_shapes_without_geometry_or_textbox_flag(tmp_path):
    path = tmp_path / "grouped_shapes.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    text = group.shapes.add_textbox(100, 100, 500, 100)
    text.text = "Keep this text"
    # Some third-party decks store a text body without classifying the shape.
    text._element.nvSpPr.cNvSpPr.attrib.pop("txBox")
    prs.save(path)
    assert "Keep this text" in parse_presentation(path).slides[0].text
