from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from presentation_search.slide_analysis import analyze_slides


def _analysis_deck(path: Path) -> Path:
    deck = Presentation()

    title_slide = deck.slides.add_slide(deck.slide_layouts[5])
    title_slide.shapes.title.text = "AMR briefing"

    rich_slide = deck.slides.add_slide(deck.slide_layouts[6])
    title = rich_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(8), Inches(0.5))
    title.text = "Surveillance findings"
    body = rich_slide.shapes.add_textbox(Inches(0.5), Inches(1), Inches(5), Inches(2))
    body.text = " ".join(f"finding{index}" for index in range(90))

    table = rich_slide.shapes.add_table(1, 2, Inches(0.5), Inches(3.2), Inches(4), Inches(0.8))
    table.table.cell(0, 0).text = "Country"
    table.table.cell(0, 1).text = "Zambia"

    chart_data = CategoryChartData()
    chart_data.categories = ["2024", "2025"]
    chart_data.add_series("Isolates", [12, 18])
    rich_slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(5.8),
        Inches(1),
        Inches(3),
        Inches(2),
        chart_data,
    )

    picture = io.BytesIO()
    Image.new("RGB", (20, 20), (20, 100, 140)).save(picture, format="PNG")
    rich_slide.shapes.add_picture(io.BytesIO(picture.getvalue()), Inches(5.8), Inches(3.3), width=Inches(1))

    group = rich_slide.shapes.add_group_shape()
    group_text = group.shapes.add_textbox(Inches(7), Inches(3.3), Inches(2), Inches(0.5))
    group_text.text = "Grouped evidence"

    final_slide = deck.slides.add_slide(deck.slide_layouts[5])
    final_slide.shapes.title.text = "Recommendations"
    deck.save(path)
    return path


def test_analyze_slides_reports_structure_and_layout_hints(tmp_path: Path):
    path = _analysis_deck(tmp_path / "analysis.pptx")

    title, rich = analyze_slides(path, [1, 2])

    assert title == {
        "slide_number": 1,
        "shape_counts": {
            "text_boxes": 1,
            "pictures": 0,
            "tables": 0,
            "charts": 0,
            "groups": 0,
        },
        "word_count": 2,
        "occupancy_ratio": title["occupancy_ratio"],
        "content_type": "title",
        "density": "low",
        "recommended_layout_action": "reuse",
    }
    assert 0 < title["occupancy_ratio"] < 1

    assert rich["slide_number"] == 2
    assert rich["shape_counts"] == {
        "text_boxes": 3,
        "pictures": 1,
        "tables": 1,
        "charts": 1,
        "groups": 1,
    }
    assert rich["word_count"] == 96
    assert 0 < rich["occupancy_ratio"] <= 1
    assert rich["content_type"] == "mixed"
    assert rich["density"] == "high"
    assert rich["recommended_layout_action"] == "review"
    json.dumps([title, rich])


def test_analyze_slides_preserves_requested_order(tmp_path: Path):
    path = _analysis_deck(tmp_path / "ordered.pptx")

    analyses = analyze_slides(path, [3, 1])

    assert [analysis["slide_number"] for analysis in analyses] == [3, 1]
    assert [analysis["content_type"] for analysis in analyses] == ["title", "title"]


@pytest.mark.parametrize(
    ("slide_numbers", "message"),
    [
        ([0], "must be 1-based"),
        ([4], "out of range"),
    ],
)
def test_analyze_slides_rejects_invalid_slide_numbers(
    tmp_path: Path, slide_numbers: list[int], message: str
):
    path = _analysis_deck(tmp_path / "invalid.pptx")

    with pytest.raises(ValueError, match=message):
        analyze_slides(path, slide_numbers)
