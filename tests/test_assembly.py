"""Integration fixtures built from real, editable PowerPoint objects."""
import io
import posixpath
from zipfile import ZipFile

import pytest
from lxml import etree as ET
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from presentation_search.assembly import assemble_slides as assemble

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def modify_zip(path, replacements):
    with ZipFile(path) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    for name, update in replacements.items():
        parts[name] = update(parts[name]) if callable(update) else update
    with ZipFile(path, "w") as target:
        for name, data in parts.items():
            target.writestr(name, data)


def source_deck(path, label, width=10):
    deck = Presentation()
    deck.slide_width = Inches(width)
    private = deck.slides.add_slide(deck.slide_layouts[0])
    private.shapes.title.text = "CONFIDENTIAL_UNUSED_" + label
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = label
    slide.shapes.title.text_frame.paragraphs[0].runs[0].font.name = "Fixture Sans"
    slide.notes_slide.notes_text_frame.text = "Speaker notes for " + label
    data = CategoryChartData()
    data.categories = ["Jan", "Feb"]
    data.add_series(label, [11, 23])
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(4), Inches(3), data)
    picture = io.BytesIO()
    Image.new("RGB", (8, 8), (45, 80, 95)).save(picture, format="PNG")
    slide.shapes.add_picture(io.BytesIO(picture.getvalue()), Inches(6), Inches(2))
    slide.shapes.add_table(1, 1, Inches(6), Inches(3), Inches(2), Inches(1)).table.cell(0, 0).text = label
    jump = slide.shapes.add_textbox(Inches(0), Inches(6), Inches(1), Inches(.5))
    jump.text = "Other slide"
    jump.click_action.target_slide = private
    deck.save(path)
    return picture.getvalue()


def test_order_native_objects_dependencies_and_exclusions(tmp_path):
    first, second, out = [tmp_path / f"{n}.pptx" for n in ("first", "second", "out")]
    picture = source_deck(first, "Alpha")
    source_deck(second, "Beta")
    report = assemble([(second, 2), (first, 2)], out)
    assert report["slide_count"] == 2
    assert any("link" in warning.lower() for warning in report["warnings"])
    result = Presentation(out)
    assert [s.shapes.title.text for s in result.slides] == ["Beta", "Alpha"]
    assert len(result.slide_masters) == 2
    for slide in result.slides:
        label = slide.shapes.title.text
        assert slide.notes_slide.notes_text_frame.text == "Speaker notes for " + label
        assert slide.slide_layout.name == "Title and Content"
        assert len(slide.slide_layout.slide_master.slide_layouts) == 1
        assert slide.shapes.title.text_frame.paragraphs[0].runs[0].font.name == "Fixture Sans"
        chart = next(s.chart for s in slide.shapes if s.has_chart)
        assert chart.series[0].values == (11.0, 23.0)
        with ZipFile(io.BytesIO(chart.part.chart_workbook.xlsx_part.blob)) as workbook:
            assert b"<v>23</v>" in workbook.read("xl/worksheets/sheet1.xml")
        assert next(s.table for s in slide.shapes if s.has_table).cell(0, 0).text == label
        assert any(hasattr(s, "image") and s.image.blob == picture for s in slide.shapes)
        assert slide.shapes[-1].click_action.target_slide is None
    with ZipFile(out) as z:
        assert z.testzip() is None
        files = set(z.namelist())
        for name in files:
            if name.endswith(".xml"):
                assert b"CONFIDENTIAL_UNUSED" not in z.read(name)
            if name.endswith(".rels"):
                base = posixpath.dirname(posixpath.dirname(name))
                for rel in ET.fromstring(z.read(name)):
                    if rel.get("TargetMode") != "External":
                        assert posixpath.normpath(posixpath.join(base, rel.get("Target"))) in files


def test_selected_slide_jump_survives_reordering(tmp_path):
    path, out = tmp_path / "source.pptx", tmp_path / "draft.pptx"
    source_deck(path, "Linked")
    assemble([(path, 2), (path, 1)], out)
    result = Presentation(out)
    assert result.slides[0].shapes[-1].click_action.target_slide == result.slides[1]


def test_embedded_font_and_theme_are_preserved(tmp_path):
    path, out = tmp_path / "source.pptx", tmp_path / "draft.pptx"
    source_deck(path, "Font")
    with ZipFile(path) as z:
        original_theme = z.read("ppt/theme/theme1.xml")
    def font_list(data):
        root = ET.fromstring(data)
        root.set("embedTrueTypeFonts", "1")
        group = ET.Element(f"{{{P}}}embeddedFontLst")
        font = ET.SubElement(group, f"{{{P}}}embeddedFont")
        ET.SubElement(font, f"{{{P}}}font", typeface="Fixture Sans")
        ET.SubElement(font, f"{{{P}}}regular", {f"{{{R}}}id": "rIdFont"})
        root.insert(root.index(root.find(f"{{{P}}}notesSz")) + 1, group)
        return ET.tostring(root)
    def add_font_rel(data):
        root = ET.fromstring(data)
        ET.SubElement(root, f"{{{REL}}}Relationship", Id="rIdFont", Type=R+"/font", Target="fonts/font1.fntdata")
        return ET.tostring(root)
    def font_type(data):
        root = ET.fromstring(data)
        ET.SubElement(root, f"{{{CT}}}Default", Extension="fntdata", ContentType="application/x-fontdata")
        return ET.tostring(root)
    modify_zip(path, {"ppt/presentation.xml": font_list, "ppt/_rels/presentation.xml.rels": add_font_rel,
                      "[Content_Types].xml": font_type, "ppt/fonts/font1.fntdata": b"fixture font bytes"})
    assemble([(path, 2)], out)
    with ZipFile(out) as z:
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        assert pres.find(f".//{{{P}}}font").get("typeface") == "Fixture Sans"
        rid = pres.find(f".//{{{P}}}regular").get(f"{{{R}}}id")
        rel = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
        target = next(x.get("Target") for x in rel if x.get("Id") == rid)
        assert z.read("ppt/" + target) == b"fixture font bytes"
        assert original_theme in [z.read(n) for n in z.namelist() if "/theme" in n and n.endswith(".xml")]


@pytest.mark.parametrize("error", ["mixed", "empty", "duplicate", "invalid_number", "out_of_bounds",
                                   "corrupt", "macro", "traversal", "doctype", "missing_target", "ole"])
def test_rejects_invalid_or_unsafe_source_without_replacing_existing_output(tmp_path, error):
    first, second, out = [tmp_path / f"{n}.pptx" for n in ("first", "second", "out")]
    source_deck(first, "Alpha")
    picks = [(first, 2)]
    if error == "mixed":
        source_deck(second, "Beta", width=12)
        picks.append((second, 2))
    elif error == "empty":
        picks = []
    elif error == "duplicate":
        picks *= 2
    elif error == "invalid_number":
        picks = [(first, True)]
    elif error == "out_of_bounds":
        picks = [(first, 3)]
    elif error == "corrupt":
        first.write_bytes(b"this is not a ZIP file")
    elif error == "ole":
        first.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + bytes(32))
    elif error == "macro":
        modify_zip(first, {"ppt/vbaProject.bin": b"fake macro"})
    elif error == "traversal":
        modify_zip(first, {"../outside.xml": b"x"})
    elif error == "doctype":
        modify_zip(first, {"ppt/slides/slide2.xml": lambda b: b.replace(b"<p:sld ", b"<!DOCTYPE sld [<!ENTITY x 'x'>]><p:sld ", 1)})
    elif error == "missing_target":
        modify_zip(first, {"ppt/slides/_rels/slide2.xml.rels": lambda b: b.replace(b"../charts/chart1.xml", b"../charts/missing.xml")})
    out.write_bytes(b"previous artifact")
    with pytest.raises(ValueError):
        assemble(picks, out)
    assert out.read_bytes() == b"previous artifact"

@pytest.mark.parametrize("fault", ["missing_root", "wrong_media_type", "unsupported_extension", "invalid_destination"])
def test_invalid_package_identity_or_type_is_rejected(tmp_path, fault):
    path = tmp_path / "deck.pptx"
    out = tmp_path / "output.pptx"
    source_deck(path, "Sample")
    if fault == "missing_root":
        modify_zip(path, {"_rels/.rels": lambda data: data.replace(b"relationships/officeDocument", b"relationships/customXml")})
    elif fault == "wrong_media_type":
        modify_zip(path, {"[Content_Types].xml": lambda data: data.replace(b"image/png", b"application/octet-stream")})
    elif fault == "unsupported_extension":
        moved = path.with_suffix(".pptm")
        path.rename(moved)
        path = moved
    else:
        out = None
    with pytest.raises(ValueError):
        assemble([(path, 2)], out)


@pytest.mark.parametrize("feature", ["externalLink", "package", "connections", "queryTable",
                                     "external_target", "missing_target", "xml_dtd"])
def test_chart_workbook_with_unsupported_dependencies_is_rejected(tmp_path, feature):
    path, out, sheet = (tmp_path / name for name in ("source.pptx", "draft.pptx", "data.xlsx"))
    source_deck(path, "Quarterly totals")
    with ZipFile(path) as slides:
        xlsx_part = next(name for name in slides.namelist() if name.endswith(".xlsx"))
        sheet.write_bytes(slides.read(xlsx_part))
    s = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    def add_rel(data, rid, kind, target, external=False):
        root = ET.fromstring(data)
        rel = ET.SubElement(root, f"{{{REL}}}Relationship", Id=rid, Type=R+"/"+kind, Target=target)
        if external:
            rel.set("TargetMode", "External")
        return ET.tostring(root)

    def override(data, target, mime):
        root = ET.fromstring(data)
        ET.SubElement(root, f"{{{CT}}}Override", PartName="/xl/"+target, ContentType=mime)
        return ET.tostring(root)

    relfile = "xl/_rels/workbook.xml.rels"
    if feature == "externalLink":
        reference = f'<externalReferences xmlns="{s}" xmlns:r="{R}"><externalReference r:id="rIdOtherBook"/></externalReferences>'
        book = f'<externalLink xmlns="{s}" xmlns:r="{R}"><externalBook r:id="rIdFile"><sheetNames><sheetName val="Totals"/></sheetNames></externalBook></externalLink>'
        target = "externalLinks/externalLink1.xml"
        modify_zip(sheet, {
            "xl/workbook.xml": lambda b: b.replace(b"</sheets>", b"</sheets>" + reference.encode()),
            relfile: lambda b: add_rel(b, "rIdOtherBook", "externalLink", target),
            "xl/"+target: book.encode(),
            "xl/externalLinks/_rels/externalLink1.xml.rels": add_rel(
                ET.tostring(ET.Element(f"{{{REL}}}Relationships")), "rIdFile",
                "externalLinkPath", "https://example.invalid/totals.xlsx", True),
            "[Content_Types].xml": lambda b: override(b, target, "application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml"),
        })
    elif feature in {"package", "connections", "queryTable"}:
        kind = feature
        target, mime, data = {
            "package": ("embeddings/attachment.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", sheet.read_bytes()),
            "connections": ("connections.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.connections+xml", f'<connections xmlns="{s}"/>'.encode()),
            "queryTable": ("queryTables/queryTable1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.queryTable+xml", f'<queryTable xmlns="{s}" name="Source" connectionId="1"/>'.encode()),
        }[feature]
        modify_zip(sheet, {relfile: lambda b: add_rel(b, "rIdExtra", kind, target),
                           "xl/"+target: data, "[Content_Types].xml": lambda b: override(b, target, mime)})
    elif feature == "external_target":
        modify_zip(sheet, {relfile: lambda b: add_rel(b, "rIdHyperlink", "hyperlink", "https://example.invalid", True)})
    elif feature == "missing_target":
        modify_zip(sheet, {relfile: lambda b: b.replace(b"worksheets/sheet1.xml", b"worksheets/missing.xml")})
    else:
        modify_zip(sheet, {"xl/styles.xml": lambda b: b.replace(b"<styleSheet ", b"<!DOCTYPE styleSheet><styleSheet ", 1)})
    modify_zip(path, {xlsx_part: sheet.read_bytes()})
    with pytest.raises(ValueError):
        assemble([(path, 2)], out)
    assert not out.exists()
