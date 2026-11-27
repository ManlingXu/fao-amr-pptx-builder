from io import BytesIO
from zipfile import ZipFile

from lxml import etree as ET
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches


def source_chart():
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    data = CategoryChartData()
    data.categories = ["2019", "2020", "2021"]
    data.add_series("Recorded sales", [3.5, None, 0])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, 0, 0, Inches(8), Inches(4), data).chart
    chart.chart_title.text_frame.text = "Recorded UK veterinary sales"
    chart.value_axis.axis_title.text_frame.text = "Sales (mg/kg)"
    chart.category_axis.axis_title.text_frame.text = "Report year"
    return slide, chart


def test_cached_chart_keeps_units_labels_missing_values_and_fresh_workbook(tmp_path):
    from presentation_search.brief_export import _add_cached_chart
    source, original = source_chart()
    # Changing the cached source formula does not alter its published observations.
    for formula in original._chartSpace.xpath(".//c:f"):
        formula.text = formula.text.replace("Sheet1!", "OriginalSheet!")
    original_book = original.part.chart_workbook.xlsx_part.blob
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    assert _add_cached_chart(slide, source, 1, 1, 10, 4)
    result = tmp_path / "new.pptx"
    deck.save(result)
    chart = Presentation(result).slides[0].shapes[0].chart
    assert chart.chart_title.text_frame.text == "Recorded UK veterinary sales"
    assert chart.value_axis.axis_title.text_frame.text == "Sales (mg/kg)"
    assert chart.category_axis.axis_title.text_frame.text == "Report year"
    assert [str(c) for c in chart.plots[0].categories] == ["2019", "2020", "2021"]
    assert chart.series[0].name == "Recorded sales"
    assert chart.series[0].values == (3.5, None, 0.0)
    assert all(f.text.startswith("Data!") for f in chart._chartSpace.xpath(".//c:f"))
    book = chart.part.chart_workbook.xlsx_part.blob
    assert book != original_book
    with ZipFile(BytesIO(book)) as parts:
        sheet = ET.fromstring(parts.read("xl/worksheets/sheet1.xml"))
        assert not sheet.xpath("//*[local-name()='f']")
        assert not any("external" in path.lower() for path in parts.namelist())


def test_absent_cache_leaves_no_incomplete_chart():
    from presentation_search.brief_export import _add_cached_chart
    source, original = source_chart()
    cache = original._chartSpace.xpath(".//c:numCache")[0]
    cache.getparent().remove(cache)
    deck = Presentation()
    target = deck.slides.add_slide(deck.slide_layouts[6])
    assert not _add_cached_chart(target, source, 1, 1, 10, 4)
    assert len(target.shapes) == 0


def test_multilevel_categories_survive_a_template_change(tmp_path):
    from presentation_search.brief_export import _add_cached_chart
    from presentation_search.templating import apply_template

    source = Presentation()
    original = source.slides.add_slide(source.slide_layouts[6])
    data = CategoryChartData()
    region = data.add_category("District A")
    region.add_sub_category("2019")
    region.add_sub_category("2020")
    data.add_category("District B").add_sub_category("2020")
    data.add_series("Reported sales (kg)", [7.5, 4.2, 0])
    original.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, 0, 0, Inches(8), Inches(4), data)
    draft = Presentation()
    output = draft.slides.add_slide(draft.slide_layouts[6])
    assert _add_cached_chart(output, original, 1, 1, 8, 4)
    draft.save(tmp_path / "draft.pptx")
    Presentation().save(tmp_path / "template.pptx")
    styled = tmp_path / "styled.pptx"
    apply_template(tmp_path / "draft.pptx", tmp_path / "template.pptx", styled)
    shapes = Presentation(styled).slides[0].shapes
    chart = next(sh.chart for group in shapes if hasattr(group, "shapes") for sh in group.shapes if sh.has_chart)
    assert chart.plots[0].categories.flattened_labels == (
        ("District A", "2019"), ("District A", "2020"), ("District B", "2020"))
    assert chart.series[0].values == (7.5, 4.2, 0.0)
