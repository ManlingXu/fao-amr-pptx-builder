"""Template application keeps native evidence while changing the design graph."""
import io
import posixpath
from copy import deepcopy
from zipfile import ZipFile

import pytest
from lxml import etree as ET
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from presentation_search.assembly import A, P, PRES, R, REL, _parse, _xml
from presentation_search.templating import POTX_MAIN, apply_template, inspect_template


def rewrite(path, edits):
    with ZipFile(path) as archive:
        parts = {n: archive.read(n) for n in archive.namelist()}
    for name, edit in edits.items():
        parts[name] = edit(parts.get(name, b"")) if callable(edit) else edit
    with ZipFile(path, "w") as archive:
        for name, blob in parts.items():
            archive.writestr(name, blob)


def sources(tmp_path):
    source, template, output = [tmp_path / f"{name}.pptx" for name in ("source", "template", "output")]
    deck = Presentation()
    deck.slide_width = Inches(10)
    deck.slide_height = Inches(7.5)
    for label in ("Evidence one", "Evidence two"):
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = label
        slide.placeholders[1].text = "Unchanged body words"
        slide.notes_slide.notes_text_frame.text = "Unchanged speaker notes: " + label
    slide = deck.slides[0]
    data = CategoryChartData()
    data.categories = ["A", "B"]
    data.add_series("Recorded", [5, 11])
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(3), Inches(3), Inches(2), data)
    slide.shapes.add_table(1, 1, Inches(5), Inches(3), Inches(3), Inches(1)).table.cell(0, 0).text = "Native table"
    picture = io.BytesIO()
    Image.new("RGB", (20, 10), (30, 80, 100)).save(picture, format="PNG")
    picture_blob = picture.getvalue()
    slide.shapes.add_picture(io.BytesIO(picture_blob), Inches(5), Inches(5), width=Inches(2))
    deck.save(source)
    design = Presentation()
    design.slide_width = Inches(13.333333)
    design.slide_height = Inches(7.5)
    example = design.slides.add_slide(design.slide_layouts[1])
    example.shapes.title.text = "TEMPLATE EXAMPLE MUST NOT LEAK"
    branding = example.shapes.add_textbox(Inches(.2), Inches(7), Inches(4), Inches(.3))
    branding.text = "TEMPLATE MASTER BRAND"
    master = design.slide_masters[0]._element
    branding_copy = deepcopy(branding._element)
    next_id = max(int(n.get("id")) for n in master.iter(P + "cNvPr")) + 1
    branding_copy.find(P + "nvSpPr/" + P + "cNvPr").set("id", str(next_id))
    master.find(P + "cSld/" + P + "spTree").append(branding_copy)
    design.save(template)
    def background(blob):
        node = _parse(blob)
        common = node.find(P + "cSld")
        old = common.find(P + "bg")
        if old is not None:
            common.remove(old)
        bg = ET.Element(P + "bg")
        props = ET.SubElement(bg, P + "bgPr")
        solid = ET.SubElement(props, A + "solidFill")
        ET.SubElement(solid, A + "srgbClr", val="EAF4F8")
        ET.SubElement(props, A + "effectLst")
        common.insert(0, bg)
        return _xml(node)
    rewrite(template, {"ppt/slideMasters/slideMaster1.xml": background})
    return source, template, output, picture_blob


def all_shapes(shapes):
    for shape in shapes:
        yield shape
        if hasattr(shape, "shapes"):
            yield from all_shapes(shape.shapes)


def test_applies_master_layout_page_size_without_example_slides_and_preserves_evidence(tmp_path):
    source, template, output, picture_blob = sources(tmp_path)
    report = apply_template(source, template, output)
    assert report["slide_count"] == 2
    result = Presentation(output)
    assert result.slide_width == Presentation(template).slide_width
    assert result.slide_height == Presentation(template).slide_height
    assert len(result.slides) == 2
    assert [s.shapes.title.text for s in result.slides] == ["Evidence one", "Evidence two"]
    assert len(result.slide_masters) == 1
    master = result.slide_masters[0]._element
    assert "TEMPLATE MASTER BRAND" in " ".join(master.itertext())
    assert master.find(P + "cSld/" + P + "bg/" + P + "bgPr/" + A + "solidFill/" + A + "srgbClr").get("val") == "EAF4F8"
    for slide in result.slides:
        assert slide.notes_slide.notes_text_frame.text == "Unchanged speaker notes: " + slide.shapes.title.text
        assert slide.slide_layout.name == "Title and Content"
        assert any(getattr(s, "text", "") == "Unchanged body words" for s in all_shapes(slide.shapes))
        # Source content is uniformly scaled. The group preserves all object ratios.
        group = next(s for s in slide.shapes if hasattr(s, "shapes"))
        xfrm = group._element.find(P + "grpSpPr/" + A + "xfrm")
        ext, child = xfrm.find(A + "ext"), xfrm.find(A + "chExt")
        assert abs(int(ext.get("cx")) / int(child.get("cx")) - int(ext.get("cy")) / int(child.get("cy"))) < 1e-6
    shapes = list(all_shapes(result.slides[0].shapes))
    assert next(s.chart for s in shapes if s.has_chart).series[0].values == (5.0, 11.0)
    assert next(s.table for s in shapes if s.has_table).cell(0, 0).text == "Native table"
    assert next(s.image.blob for s in shapes if hasattr(s, "image")) == picture_blob
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert archive.testzip() is None
        for name in names:
            if name.endswith(".xml"):
                assert b"TEMPLATE EXAMPLE MUST NOT LEAK" not in archive.read(name)
            if name.endswith(".rels"):
                base = posixpath.dirname(posixpath.dirname(name))
                for rel in _parse(archive.read(name)):
                    if rel.get("TargetMode") != "External":
                        assert posixpath.normpath(posixpath.join(base, rel.get("Target"))) in names


def test_accepts_real_potx_template_and_reports_layouts(tmp_path):
    source, template, output, _ = sources(tmp_path)
    template = template.rename(template.with_suffix(".potx"))
    rewrite(template, {"[Content_Types].xml": lambda b: b.replace(
        b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml", POTX_MAIN.encode())})
    metadata = inspect_template(template)
    assert metadata["slideWidth"] == 12191999
    assert "Title and Content" in metadata["layoutNames"]
    assert metadata["warnings"]
    apply_template(source, template, output)
    assert len(Presentation(output).slides) == 2


@pytest.mark.parametrize("fault", ["macro", "traversal", "missing_design_part", "dtd", "corrupt", "animations"])
def test_unsupported_inputs_fail_atomically(tmp_path, fault):
    source, template, output, _ = sources(tmp_path)
    if fault == "macro":
        rewrite(template, {"ppt/vbaProject.bin": b"unsafe"})
    elif fault == "traversal":
        rewrite(template, {"../outside.xml": b"unsafe"})
    elif fault == "missing_design_part":
        rewrite(template, {"ppt/slideMasters/_rels/slideMaster1.xml.rels": lambda b: b.replace(
            b"../theme/theme1.xml", b"../theme/absent.xml")})
    elif fault == "dtd":
        rewrite(template, {"ppt/slideMasters/slideMaster1.xml": lambda b: b.replace(
            b"<p:sldMaster ", b"<!DOCTYPE sldMaster [<!ENTITY x 'x'>]><p:sldMaster ", 1)})
    elif fault == "corrupt":
        template.write_bytes(b"invalid ZIP")
    else:
        rewrite(source, {"ppt/slides/slide1.xml": lambda b: b.replace(b"</p:sld>", b"<p:timing/></p:sld>")})
    output.write_bytes(b"previous output")
    with pytest.raises(ValueError):
        apply_template(source, template, output)
    assert output.read_bytes() == b"previous output"


def test_source_and_template_are_never_overwritten(tmp_path):
    source, template, _, _ = sources(tmp_path)
    original = source.read_bytes()
    with pytest.raises(ValueError):
        apply_template(source, template, source)
    assert source.read_bytes() == original


def test_filled_picture_chart_and_table_placeholders_keep_native_objects(tmp_path):
    source, template, output, picture_blob = sources(tmp_path)
    def placeholders(blob):
        slide = _parse(blob)
        for shape in slide.find(P + "cSld/" + P + "spTree"):
            if shape.tag in {P + "pic", P + "graphicFrame"}:
                nv = next(n for n in shape if ET.QName(n).localname.startswith("nv"))
                ET.SubElement(nv.find(P + "nvPr"), P + "ph", type="pic", idx="77")
        return _xml(slide)
    rewrite(source, {"ppt/slides/slide1.xml": placeholders})
    apply_template(source, template, output)
    shapes = list(all_shapes(Presentation(output).slides[0].shapes))
    assert next(s.image.blob for s in shapes if hasattr(s, "image")) == picture_blob
    assert next(s.chart for s in shapes if s.has_chart).series[0].values == (5.0, 11.0)
    assert next(s.table for s in shapes if s.has_table).cell(0, 0).text == "Native table"


def test_absolute_template_relationships_remain_inside_template_graph(tmp_path):
    source, template, output, _ = sources(tmp_path)
    with ZipFile(template) as archive:
        edits = {}
        for name in archive.namelist():
            if not name.endswith(".rels"):
                continue
            node = _parse(archive.read(name))
            base = posixpath.dirname(posixpath.dirname(name))
            for rel in node:
                if rel.get("TargetMode") != "External":
                    rel.set("Target", "/" + posixpath.normpath(posixpath.join(base, rel.get("Target"))))
            edits[name] = _xml(node)
        edits["ppt/theme/theme1.xml"] = archive.read("ppt/theme/theme1.xml").replace(b"4F81BD", b"ABCDEF")
    rewrite(template, edits)
    apply_template(source, template, output)
    result = Presentation(output)
    layout = result.slides[0].slide_layout
    theme = next(rel.target_part for rel in layout.slide_master.part.rels.values() if rel.reltype == R + "/theme")
    assert b"ABCDEF" in theme.blob
    assert b"TEMPLATE MASTER BRAND" in layout.slide_master.part.blob


def test_existing_templated_draft_can_change_templates_again(tmp_path):
    source, template, first, _ = sources(tmp_path)
    apply_template(source, template, first)
    replacement = tmp_path / "replacement.pptx"
    replacement.write_bytes(template.read_bytes())
    rewrite(replacement, {"ppt/slideMasters/slideMaster1.xml": lambda b: b.replace(
        b"TEMPLATE MASTER BRAND", b"SECOND TEMPLATE BRAND").replace(b"EAF4F8", b"DDEEAA")})
    output = tmp_path / "second.pptx"
    first_bytes = first.read_bytes()
    apply_template(first, replacement, output)
    assert first.read_bytes() == first_bytes
    result = Presentation(output)
    assert len(result.slides) == 2
    assert [s.shapes.title.text for s in result.slides] == ["Evidence one", "Evidence two"]
    assert b"SECOND TEMPLATE BRAND" in result.slide_masters[0].part.blob
    assert b"TEMPLATE MASTER BRAND" not in result.slide_masters[0].part.blob
    assert b"DDEEAA" in result.slide_masters[0].part.blob
    shapes = list(all_shapes(result.slides[0].shapes))
    assert next(s.chart for s in shapes if s.has_chart).series[0].values == (5.0, 11.0)
    assert result.slides[0].notes_slide.notes_text_frame.text == "Unchanged speaker notes: Evidence one"
