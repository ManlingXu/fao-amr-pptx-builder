from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

from presentation_search.layout_validation import validate_layout


def _save(prs: Presentation, tmp_path: Path, name: str = "deck.pptx") -> Path:
    path = tmp_path / name
    prs.save(path)
    return path


def _issue_codes(report: dict) -> list[str]:
    return [issue["code"] for slide in report["slides"] for issue in slide["issues"]]


def test_clean_deck_returns_json_ready_dimensions_and_zero_issue_summary(tmp_path: Path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.7), Inches(0.6), Inches(3), Inches(0.5)).text = "Heading"
    slide.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(4), Inches(1)).text = "Short body text"

    report = validate_layout(_save(prs, tmp_path))

    assert report["slideWidth"] == prs.slide_width
    assert report["slideHeight"] == prs.slide_height
    assert report["slides"] == [{"slideNumber": 1, "issues": []}]
    assert report["summary"] == {
        "slides": 1,
        "issues": 0,
        "errors": 0,
        "warnings": 0,
        "slidesNeedingReview": 0,
    }
    assert "heuristic" in report["limitations"][0].lower()


def test_shape_extending_past_slide_edge_is_reported_as_error(tmp_path: Path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(
        prs.slide_width - Inches(0.4), Inches(1), Inches(1), Inches(1)
    ).text = "Outside"

    report = validate_layout(_save(prs, tmp_path))

    issue = report["slides"][0]["issues"][0]
    assert issue["code"] == "shape_outside_canvas"
    assert issue["severity"] == "error"
    assert issue["shapeIndex"] == 1
    assert "canvas" in issue["reason"].lower()
    assert report["summary"]["errors"] == 1


def test_substantially_overlapping_ordinary_shapes_are_reported(tmp_path: Path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2)).text = "First"
    slide.shapes.add_textbox(Inches(3), Inches(1.5), Inches(4), Inches(2)).text = "Second"

    report = validate_layout(_save(prs, tmp_path))

    issue = next(item for item in report["slides"][0]["issues"] if item["code"] == "shape_overlap")
    assert issue["severity"] == "warning"
    assert issue["shapeIndexes"] == [1, 2]
    assert issue["overlapRatio"] == 0.375
    assert "overlap" in issue["reason"].lower()


def test_full_slide_background_and_spatial_containment_are_not_overlap_issues(tmp_path: Path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height
    )
    slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1), Inches(5), Inches(4)
    )
    slide.shapes.add_textbox(Inches(2), Inches(2), Inches(2), Inches(1)).text = "Inside card"

    report = validate_layout(_save(prs, tmp_path))

    assert "shape_overlap" not in _issue_codes(report)


def test_dense_text_is_a_review_warning_not_a_claim_of_overflow(tmp_path: Path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(2.5))
    box.text = " ".join(["antimicrobial"] * 220)

    report = validate_layout(_save(prs, tmp_path))

    issue = next(item for item in report["slides"][0]["issues"] if item["code"] == "dense_text")
    assert issue["severity"] == "warning"
    assert issue["wordCount"] == 220
    assert "heuristic" in issue["reason"].lower()
    assert "overflow" not in issue["reason"].lower()
    assert report["summary"]["warnings"] == 1
    assert report["summary"]["slidesNeedingReview"] == 1
