from types import SimpleNamespace

from pptx import Presentation
from pptx.util import Inches

from presentation_search.brief_export import _excerpt_heading, _excerpt_text, _source_paragraphs


def box(slide, name, text, top):
    shape = slide.shapes.add_textbox(Inches(.5), Inches(top), Inches(10), Inches(.7))
    shape.name = name
    shape.text = text
    return shape


def test_excerpt_uses_authored_heading_and_preserves_sampling_caveat():
    slide = Presentation().slides.add_slide(Presentation().slide_layouts[6])
    box(slide, "Title 7", "Clinical Surveillance", .1)
    box(slide, "TextBox 4", "Source: p. 13", 5.1)
    box(slide, "TextBox 5", "VARSS REPORT 2024", 5.6)
    box(slide, "Group caption", "30% of mammal submissions were from cattle.", 1.4)
    box(slide, "Scope", "These samples should not be used to estimate national prevalence.", 3.4)
    p = SimpleNamespace(title="Slide 12", notes="")
    parts = _source_paragraphs(slide)
    record = {"deckTitle": "Animal surveillance 2024", "issued": "2024", "slideNumber": 12,
              "evidence": "30% of mammal submissions were from cattle."}
    heading = _excerpt_heading(p, slide, parts, record)
    assert "Clinical Surveillance" in heading
    text = _excerpt_text(p, parts, record["evidence"], heading, 450)
    assert "30%" in text and "should not" in text
    assert "Source: p. 13" not in text and "VARSS REPORT" not in text


def test_complete_evidence_paragraph_retains_surrounding_context():
    slide = Presentation().slides.add_slide(Presentation().slide_layouts[6])
    box(slide, "Footer", "© 2020 VMD", 6.1)
    body = "In 2020, sales decreased by 10% among participating herds in the study."
    box(slide, "Body", body, 2)
    page = SimpleNamespace(title="Sales", notes="")
    text = _excerpt_text(page, _source_paragraphs(slide), "decreased by 10%", "Sales", 350)
    assert text == body


def test_excerpt_omits_a_trailing_introduction_without_its_list():
    page = SimpleNamespace(notes="")
    parts = ["In total, 18 visits were recorded.", "The percentages by species were:"]
    assert _excerpt_text(page, parts, parts[0], "Outreach visits", 100) == parts[0]


def test_wide_data_strip_keeps_the_source_figure_and_omits_banner():
    from io import BytesIO
    from PIL import Image
    from presentation_search.brief_export import _dominant_image
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    def picture(width, height, top):
        stream = BytesIO()
        Image.new("RGB", (width, height), "white").save(stream, "PNG")
        stream.seek(0)
        return slide.shapes.add_picture(stream, Inches(0.3), Inches(top),
                                        Inches(9), Inches(9 * height / width))
    picture(1500, 48, 2)
    chosen = picture(1200, 108, 3)
    chosen.crop_top = .08804
    source = _dominant_image(slide, deck)
    assert source.image.blob == chosen.image.blob
    assert source.crop_top == chosen.crop_top
