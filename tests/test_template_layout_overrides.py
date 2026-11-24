"""Per-slide layout choices let an orchestrator drive template application."""

import pytest
from lxml import etree as ET
from pptx import Presentation
from pptx.util import Inches

from presentation_search.assembly import P
from presentation_search.templating import apply_template


def _decks(tmp_path):
    source = tmp_path / "source.pptx"
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"

    deck = Presentation()
    for title in ("First evidence", "Second evidence"):
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = "Editable evidence body"
    deck.save(source)

    design = Presentation()
    design.slides.add_slide(design.slide_layouts[1]).shapes.title.text = "Example only"
    design.save(template)
    return source, template, output


def test_per_slide_layout_overrides_choose_named_template_relationships(tmp_path):
    source, template, output = _decks(tmp_path)

    report = apply_template(
        source,
        template,
        output,
        layout_overrides={1: "Blank", 2: "Title Only"},
    )

    result = Presentation(output)
    assert [slide.slide_layout.name for slide in result.slides] == ["Blank", "Title Only"]
    assert report["template"]["appliedLayouts"] == ["Blank", "Title Only"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({0: "Blank"}, "slide number 0"),
        ({3: "Blank"}, "slide number 3"),
        ({1: "Missing Layout"}, "Missing Layout"),
    ],
)
def test_invalid_layout_overrides_fail_before_publishing(tmp_path, overrides, message):
    source, template, output = _decks(tmp_path)
    output.write_bytes(b"previous output")

    with pytest.raises(ValueError, match=message):
        apply_template(source, template, output, layout_overrides=overrides)

    assert output.read_bytes() == b"previous output"


def test_two_content_override_uses_the_combined_placeholder_area(tmp_path):
    source = tmp_path / "source.pptx"
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(4), Inches(2)).text = "Left evidence"
    slide.shapes.add_textbox(Inches(5.5), Inches(2), Inches(4), Inches(2)).text = "Right evidence"
    deck.save(source)
    design = Presentation()
    design.slides.add_slide(design.slide_layouts[3])
    design.save(template)

    apply_template(source, template, output, layout_overrides={1: "Two Content"})

    result = Presentation(output)
    content_group = next(shape for shape in result.slides[0].shapes if hasattr(shape, "shapes"))
    assert content_group.width >= result.slide_width * 0.8


def test_source_page_number_placeholder_does_not_shrink_template_content(tmp_path):
    source = tmp_path / "source.pptx"
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2)).text = "Primary evidence"
    page_number = slide.shapes.add_textbox(Inches(9), Inches(7), Inches(0.5), Inches(0.25))
    page_number.text = "19"
    placeholder = ET.Element(P + "ph")
    placeholder.set("type", "sldNum")
    placeholder.set("idx", "99")
    page_number._element.nvSpPr.nvPr.append(placeholder)
    deck.save(source)
    design = Presentation()
    design.slides.add_slide(design.slide_layouts[1])
    design.save(template)

    apply_template(source, template, output, layout_overrides={1: "Title and Content"})

    result = Presentation(output)
    all_text = [shape.text for shape in result.slides[0].shapes if shape.has_text_frame]
    grouped_text = [child.text for shape in result.slides[0].shapes if hasattr(shape, "shapes")
                    for child in shape.shapes if child.has_text_frame]
    assert "Primary evidence" in grouped_text
    assert "19" not in all_text + grouped_text


def test_filled_source_footer_credit_survives_template_application(tmp_path):
    source = tmp_path / "source.pptx"
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2)).text = "Primary evidence"
    credit = slide.shapes.add_textbox(Inches(0.5), Inches(7), Inches(5), Inches(0.25))
    credit.text = "Source: FAO evidence record"
    placeholder = ET.Element(P + "ph")
    placeholder.set("type", "ftr")
    placeholder.set("idx", "98")
    credit._element.nvSpPr.nvPr.append(placeholder)
    deck.save(source)
    design = Presentation()
    design.slides.add_slide(design.slide_layouts[1])
    design.save(template)

    apply_template(source, template, output, layout_overrides={1: "Title and Content"})

    result = Presentation(output)
    texts = [shape.text for shape in result.slides[0].shapes if shape.has_text_frame]
    grouped_text = [child.text for shape in result.slides[0].shapes if hasattr(shape, "shapes")
                    for child in shape.shapes if child.has_text_frame]
    assert "Source: FAO evidence record" in texts
    assert "Primary evidence" in grouped_text

