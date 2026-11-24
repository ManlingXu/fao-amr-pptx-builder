"""Per-slide layout choices let an orchestrator drive template application."""

from pptx import Presentation

import pytest

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

