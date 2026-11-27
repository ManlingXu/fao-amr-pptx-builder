"""Export verified selections to an editable draft and a separately styled copy."""
from __future__ import annotations

import json
import re
import math
import shutil
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from lxml import etree as ET
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN
from pptx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from pptx.parts.chart import ChartPart
from pptx.util import Inches, Pt
from xlsxwriter import Workbook
from xlsxwriter.utility import xl_rowcol_to_cell

from .assembly import P, assemble_slides
from .brief_index import read_verified_manifest
from .pptx_parser import parse_presentation
from .providers.base import read_bounded
from .templates import MAX_TEMPLATE_BYTES
from .templating import apply_template


def _verify(corpus, selections, snapshots):
    rows = {r["id"]: r for r in read_verified_manifest(corpus / "verified.csv")}
    parsed, seen, records, paths = {}, set(), [], []
    for order, pick in enumerate(selections, 1):
        key = pick["deck_id"]
        if key not in rows:
            raise ValueError(f"Unknown verified deck: {key!r}")
        row = rows[key]
        path = corpus / "presentations" / (key + ".pptx")
        if path.is_symlink() or path.resolve().parent != (corpus / "presentations").resolve():
            raise ValueError("The selected file must be inside the verified corpus.")
        snapshot = snapshots / path.name
        if key not in parsed:
            snapshot.write_bytes(read_bounded(path))
            parsed[key] = parse_presentation(snapshot, source_url=row["source_page"], source_key=path.name)
        number = pick["slide_number"]
        pages = parsed[key].slides
        if type(number) is not int or not 1 <= number <= len(pages):
            raise ValueError(f"Original slide {number!r} is out of range for {key}.")
        page = pages[number - 1]
        if page.source_hash != row["sha256"] or pick["source_hash"] != page.source_hash:
            raise ValueError(f"Source hash changed for {key}. Refresh the index.")
        if (page.source_hash, number) in seen:
            raise ValueError(f"Duplicate original slide {number} of {key}.")
        seen.add((page.source_hash, number))
        evidence = pick["evidence"].strip()
        if not evidence or not any(evidence in part for part in [page.title, page.text, page.notes]):
            raise ValueError(f"Evidence is absent from original slide {number} of {key}.")
        records.append({
            "outputSlide": order, "deckId": key, "deckName": path.name, "deckTitle": row["title"],
            "slideId": page.id, "slideNumber": number, "title": page.title, "sourcePage": row["source_page"],
            "downloadUrl": row.get("download_url", ""), "sourceHash": page.source_hash,
            "author": row.get("author", ""), "publisher": row.get("publisher", ""),
            "issued": row.get("issued", ""), "license": row.get("license", ""),
            "evidence": evidence, "selectionReason": pick.get("reason", ""), "stage": pick.get("stage", ""),
        })
        paths.append((snapshot, number))
    return paths, records, parsed


def _add_source_notes(slide, record):
    frame = slide.notes_slide.notes_text_frame
    if frame is None:
        raise ValueError("The source notes master lacks an editable notes body.")
    for line in [
        "", f"{record['deckTitle']} · Original slide {record['slideNumber']}",
        " · ".join(filter(None, [record["author"], record["publisher"], record["issued"]])),
        record["sourcePage"], record["license"], "SHA-256 " + record["sourceHash"],
        "Selected passage", record["evidence"],
    ]:
        para = frame.add_paragraph()
        para.text = line
        if line == record["sourcePage"]:
            para.runs[0].hyperlink.address = line


def _master_shape(master, shape):
    element = deepcopy(shape._element)
    ids = [int(item.get("id")) for item in master._element.iter(P + "cNvPr")]
    element.find(".//" + P + "cNvPr").set("id", str(max(ids) + 1))
    master.shapes._spTree.insert_element_before(element, "p:extLst")


def _textbox(slide, text, x, y, w, h, size, color, *, bold=False):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_top = frame.margin_bottom = 0
    frame.margin_left = frame.margin_right = 0
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.name, paragraph.font.size = "Aptos", Pt(size)
    paragraph.font.bold, paragraph.font.color.rgb = bold, RGBColor.from_string(color)
    return shape


def _demo_template(path):
    """A widescreen training master with a running header and a generous text area."""
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    sample = deck.slides.add_slide(deck.slide_layouts[6])
    master = deck.slide_master
    master.background.fill.solid()
    master.background.fill.fore_color.rgb = RGBColor.from_string("EFF5F2")
    stripe = sample.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.16), deck.slide_height)
    stripe.line.fill.background()
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = RGBColor.from_string("176655")
    _master_shape(master, stripe)
    _master_shape(master, _textbox(sample, "AMR    /    FIELD BRIEFING", .72, .22, 8, .24, 11, "176655", bold=True))
    for layout in deck.slide_layouts:
        objects = [s for s in layout.placeholders if s.placeholder_format.type in
                   (PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.SUBTITLE)]
        for placeholder in layout.placeholders:
            kind = placeholder.placeholder_format.type
            if kind in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                box = (.7, .58, 11.92, 1.2 if kind == PP_PLACEHOLDER.TITLE else 2.65)
            elif kind in (PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.SUBTITLE):
                n = len(objects)
                i = next(i for i, shape in enumerate(objects) if shape.shape_id == placeholder.shape_id)
                top = 3.5 if kind == PP_PLACEHOLDER.SUBTITLE else 1.9
                box = (.7 + i * 12 / n, top, 12 / n - .15, 7.03 - top)
            else:
                continue
            placeholder.left, placeholder.top, placeholder.width, placeholder.height = map(Inches, box)
    deck.save(path)


def _source_paragraphs(slide):
    """Select readable slide text, keeping the original paragraphs and their order."""
    blocks = []
    def visit(shapes):
        for shape in shapes:
            if shape._element.tag == P + "grpSp":
                visit(shape.shapes)
            if not shape.has_text_frame:
                continue
            if shape.is_placeholder and shape.placeholder_format.type in (
                PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.DATE,
                PP_PLACEHOLDER.FOOTER, PP_PLACEHOLDER.SLIDE_NUMBER,
            ):
                continue
            for paragraph in shape.text_frame.paragraphs:
                text = ' '.join(paragraph.text.split())
                if text and not re.match(r"^(?:\d{1,4}$|©|https?://|(?:source|sources|reference)\s*:|(?:UK[- ]?)?VARSS REPORT\b)", text, re.I):
                    blocks.append(text)
    visit(slide.shapes)
    return list(dict.fromkeys(blocks))


def _dominant_image(slide, deck):
    """Find a substantial authored figure, retaining its displayed proportions and crop."""
    images = []
    for shape in slide.shapes:
        if shape._element.tag != P + "pic" or shape.rotation or not shape.height:
            continue
        area = (shape.width / deck.slide_width) * (shape.height / deck.slide_height)
        # Some publishers embed an entire single-row annual data table as a wide
        # picture. Thin header strips and logos should not displace the figure.
        wide_figure = (shape.width / deck.slide_width >= .7 and
                       2 <= shape.width / shape.height <= 14 and area >= .065)
        if area < .18 and not wide_figure:
            continue
        crop = (shape.crop_left, shape.crop_right, shape.crop_top, shape.crop_bottom)
        if any(value < 0 for value in crop) or crop[0] + crop[1] >= 1 or crop[2] + crop[3] >= 1:
            continue
        image = shape.image
        if image.content_type in {"image/jpeg", "image/png"}:
            images.append((shape.width * shape.height, shape))
    return max(images, key=lambda item: item[0])[1] if images else None


def _excerpt_heading(page, slide, parts, record):
    # Many publishers draw a heading in a regular shape named “Title” without a
    # title placeholder. Its text is stronger evidence than a synthetic Slide N.
    title = page.title
    if not title or re.fullmatch(r"Slide \d+", title):
        named = [s.text.strip() for s in slide.shapes if s.has_text_frame and
                 re.match(r"(?:title|标题)\b", s.name, re.I) and s.text.strip()]
        title = next(iter(named), "")
    if not title:
        title = next((p for p in parts if 4 < len(p) < 100), record["deckTitle"])
    return ' '.join(title.split())


def _specific_heading(title, parts, evidence):
    """Use a brief, intact quantitative statement or caption from the source."""
    if len(title) > 52:
        return title
    fragments = [' '.join(line.split()) for line in evidence.splitlines() if len(line.strip()) >= 12]
    for paragraph in parts:
        if not any(f in paragraph or paragraph in f for f in fragments):
            continue
        # A parenthesized figure qualifier stays in the caption and in the notes.
        subject = paragraph.split(" (", 1)[0].strip()
        if (28 <= len(subject) <= 125 and re.search(r"\b(?:19|20)\d{2}\b", subject)
                and (len(subject) < len(paragraph) or re.search(r"\b\d[\d,.]*\s*(?:%|tonnes?\b|kg\b|mg\b)", subject))):
            return subject
    return title


def _excerpt_text(page, parts, evidence, heading, limit):
    fragments = [' '.join(line.split()) for line in evidence.splitlines() if line.strip()]
    evidence = ' '.join(evidence.split())
    parts = [p for p in parts if p != heading]
    # The selected phrase may lie in the middle of a sentence. Prefer its full
    # paragraph from the actual source, including any qualifier or population.
    matches = [(min(len(f), len(p)), p) for p in parts for f in fragments if f in p or p in f]
    first = max(matches, key=lambda match: match[0])[1] if matches else evidence
    if first not in parts and first != heading:
        note = next((' '.join(p.split()) for p in page.notes.splitlines() if evidence in ' '.join(p.split())), '')
        first = note or first
    caution = re.compile(r"\b(?:should not|not (?:directly )?comparable|cannot|subject to|caution|biased|biases)\b|不宜|不能|不可|偏倚", re.I)
    caveats = [s for p in parts for s in re.split(r'(?<=[.!?。！？])\s+', p) if caution.search(s)]
    candidates = [first, *caveats, *parts]
    included = []
    for p in candidates:
        if not p or p == heading or any(p in current for current in included):
            continue
        if len(p) > limit and not included:
            # Preserve the evidence and complete sentences wherever possible. The
            # full original text and notes remain in the slide's speaker notes.
            sentences = re.split(r'(?<=[.!?。！？])\s+', p)
            match = next((s for s in sentences if evidence in s), p)
            if len(match) > limit:
                # Select the containing excerpt from a long paragraph, avoiding
                # any impression that the visibly abbreviated text is complete.
                start = max(0, match.find(evidence))
                snippet = match[start:start + limit - 2]
                if ' ' in snippet and start + len(snippet) < len(match):
                    snippet = snippet.rsplit(' ', 1)[0]
                match = ('…' if start else '') + snippet + ('…' if start + len(snippet) < len(match) else '')
            p = match
        if sum(map(len, included)) + len(p) <= limit:
            included.append(p)
        if len(included) >= 4:
            break
    while included and (included[-1].endswith((':', '：')) or
                        included[-1].casefold() in {'key findings', 'findings', 'results', 'summary'}):
        included.pop()
    return '\n\n'.join(included)


def _source_table(slide, evidence):
    for shape in slide.shapes:
        if not shape.has_table:
            continue
        table = shape.table
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        if any(evidence in text for row in rows for text in row):
            # Preserve the full small table with column headings, units and row context.
            # A cropped numeric cell or a truncated row could change its meaning.
            if (len(rows) <= 8 and len(rows[0]) <= 6 and all(len(cell) <= 100 for row in rows for cell in row)
                    and not any(c.is_merge_origin or c.is_spanned for c in table.iter_cells())):
                return rows
            return []
    return None


_CHART = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_DRAW = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_COMPAT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def _chart_workbook(space):
    """Rebuild only the cached chart cells and replace every original range reference."""
    formulas = space.xpath(".//c:f")
    if not 1 <= len(formulas) <= 120:
        raise ValueError("Unsupported number of cached ranges")
    stream = BytesIO()
    with Workbook(stream, {"in_memory": True}) as workbook:
        sheet = workbook.add_worksheet("Data")
        column = 0
        for formula in formulas:
            reference = formula.getparent()
            kind = ET.QName(reference).localname
            caches = {"strRef": "strCache", "numRef": "numCache", "multiLvlStrRef": "multiLvlStrCache"}
            cache = reference.find(_CHART + caches[kind])
            if cache is None:
                raise ValueError("A source range has no cached data")
            count_part = cache.find(_CHART + "ptCount")
            count = int(count_part.get("val")) if count_part is not None else 0
            levels = list(reversed(cache.findall(_CHART + "lvl"))) if kind == "multiLvlStrRef" else [cache]
            if not 1 <= count <= 1000 or not 1 <= len(levels) <= 8:
                raise ValueError("Unsupported chart range dimensions")
            first = xl_rowcol_to_cell(1, column, row_abs=True, col_abs=True)
            field = ET.QName(reference.getparent()).localname
            header = {"cat": "Category", "val": "Value", "tx": "Label"}.get(field, field)
            for level in levels:
                sheet.write_string(0, column, header)
                seen = set()
                for point in level.findall(_CHART + "pt"):
                    index = int(point.get("idx"))
                    value = point.findtext(_CHART + "v")
                    if not 0 <= index < count or index in seen or value is None or len(value) > 32767:
                        raise ValueError("Invalid cached chart point")
                    seen.add(index)
                    if kind == "numRef":
                        number = float(value)
                        if not math.isfinite(number):
                            raise ValueError("Invalid cached number")
                        sheet.write_number(index + 1, column, number)
                    else:
                        sheet.write_string(index + 1, column, value)
                column += 1
            last = xl_rowcol_to_cell(count, column - 1, row_abs=True, col_abs=True)
            formula.text = "Data!" + (first if first == last else f"{first}:{last}")
    return stream.getvalue()


def _add_cached_chart(target, slide, x, y, w, h):
    """Copy a single bar/line plot, its axes and labels, using only published cached data."""
    charts = [shape.chart for shape in slide.shapes if shape.has_chart]
    if len(charts) != 1:
        return False
    space = deepcopy(charts[0]._chartSpace)
    plots = space.xpath(".//c:plotArea/*[c:ser]")
    if not plots or any(p.tag not in {_CHART + "barChart", _CHART + "lineChart"} for p in plots):
        return False
    # Chart relationships can reference workbooks, custom drawings or images. Never
    # carry those from the source. Plain cached chart XML describes the entire figure.
    for part in space.xpath("./c:externalData | .//c:extLst | .//a:extLst"):
        part.getparent().remove(part)
    for option in list(space.iter(_COMPAT + "AlternateContent")):
        fallback = option.find(_COMPAT + "Fallback")
        if option.getparent() is not space or fallback is None or len(fallback) != 1 or fallback[0].tag != _CHART + "style":
            return False
        option.getparent().replace(option, fallback[0])
    for part in space.iter():
        if (not isinstance(part.tag, str) or not part.tag.startswith((_CHART, _DRAW))
                or part.tag.startswith(_DRAW + "hlink")
                or part.tag in {_DRAW + "blip", _CHART + "pivotSource", _CHART + "userShapes"}
                or any("relationships" in key for key in part.attrib)):
            return False
    for series in space.xpath(".//c:ser"):
        if not series.xpath("c:cat/*/c:f") or not series.xpath("c:val/c:numRef/c:f"):
            return False
    try:
        data = _chart_workbook(space)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    package = target.part.package
    chart = ChartPart.load(package.next_partname(ChartPart.partname_template), CT.DML_CHART,
                           package, ET.tostring(space))
    chart.chart_workbook.update_from_xlsx_blob(data)
    relation = target.part.relate_to(chart, RT.CHART)
    target.shapes._add_chart_graphicFrame(relation, *map(Inches, (x, y, w, h)))
    return True


def _draw_table(target, rows):
    table = target.shapes.add_table(len(rows), len(rows[0]), Inches(.8), Inches(1.9),
                                    Inches(11.75), Inches(min(4.4, .66 * len(rows)))).table
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.text = value
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(14 if len(row) > 4 or len(value) > 40 else 18)


def _evidence_deck(paths, records, parsed, topic, output):
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    deck.core_properties.title = topic
    # Only one selected source package is open at a time.
    for (path, number), record in zip(paths, records):
        original = Presentation(path)
        slide = original.slides[number - 1]
        page = parsed[record["deckId"]].slides[number - 1]
        target = deck.slides.add_slide(deck.slide_layouts[5])
        parts = _source_paragraphs(slide)
        content_title = _excerpt_heading(page, slide, parts, record)
        title = _specific_heading(content_title, parts, record["evidence"])
        edition = re.search(r"\(([A-Z][A-Z0-9-]{2,15})\)\s+((?:19|20)\d{2})\s*$", record["deckTitle"], re.I)
        caption = record["evidence"]
        if edition and title == content_title and len(title) < 48:
            edition_text = " ".join(edition.groups())
            if edition_text.casefold() not in title.casefold():
                title = f"{title}  ·  {edition_text}"
        record["displayTitle"] = title
        heading = target.shapes.title
        heading.left, heading.top, heading.width, heading.height = map(Inches, (.7, .23, 11.9, 1.17))
        heading.text = title
        heading.text_frame.word_wrap = True
        for paragraph in heading.text_frame.paragraphs:
            paragraph.alignment = PP_ALIGN.LEFT
            paragraph.font.name = "Aptos Display"
            paragraph.font.size = Pt(23 if len(title) > 85 else 31)
            paragraph.font.bold = True

        rows = _source_table(slide, caption)
        has_chart = rows is None and _add_cached_chart(target, slide, .83, 2.62, 11.66, 3.9)
        picture = _dominant_image(slide, original) if rows is None and not has_chart else None
        visual = bool(has_chart or picture)
        record.update(excerptChart=has_chart, excerptImage=bool(picture), excerptTable=bool(rows))
        if rows:
            _draw_table(target, rows)
            body = ""
        elif rows is not None:
            body = "Open the source slide below to read the full table with its column headings and units."
        else:
            body = _excerpt_text(page, parts, caption, content_title, 300 if visual else 700)
            if title != content_title and body.startswith(title):
                body = body[len(title):].strip()
        if picture:
            # The original aspect ratio is preserved. A photo without a separate
            # caption can use the entire content area below the title.
            y, height = (2.62, 3.9) if body else (1.47, 5.0)
            width, h = picture.width, picture.height
            scale = min(11.65 / width, height / h)
            w, h = width * scale, h * scale
            copied = target.shapes.add_picture(BytesIO(picture.image.blob), Inches(.84 + (11.65 - w) / 2),
                                               Inches(y + (height - h) / 2), Inches(w), Inches(h))
            copied.crop_left, copied.crop_right = picture.crop_left, picture.crop_right
            copied.crop_top, copied.crop_bottom = picture.crop_top, picture.crop_bottom
        if body:
            if visual:
                # One compact caption leaves space for the readable graph.
                body = body.replace("\n\n", " ")
            shape = _textbox(target, body, .84, 1.47, 11.66, 1.14 if visual else 4.88,
                             (15 if len(body) > 196 else 18) if visual else (18 if len(body) > 365 else 23),
                             "243537")
            for paragraph in shape.text_frame.paragraphs:
                paragraph.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
        credit = record["publisher"] or record["author"] or record["deckTitle"]
        label = f"{credit[:95]}   ·   Original slide {number}"
        footer = _textbox(target, label, .85, 6.79, 11.6, .38, 11, "355C6F")
        footer.text_frame.paragraphs[0].runs[0].hyperlink.address = record["sourcePage"]
        frame = target.notes_slide.notes_text_frame
        frame.text = page.notes
        if page.text:
            frame.add_paragraph().text = "Original slide text"
            frame.add_paragraph().text = page.text
        _add_source_notes(target, record)
    deck.save(output)


def _write_outputs(corpus, stage, snapshots, topic, selected, template, reflow):
    paths, records, parsed = _verify(corpus, selected, snapshots)
    draft, styled = stage / "draft.pptx", stage / "styled.pptx"
    if template is None:
        template = stage / "field-briefing-template.pptx"
        _demo_template(template)
    if template.suffix.lower() not in {".pptx", ".potx"} or template.stat().st_size > MAX_TEMPLATE_BYTES:
        raise ValueError("Supply a PPTX or POTX template up to 16 MiB.")
    warnings = []
    mode = "evidence_excerpts" if reflow else "native"
    if mode == "native":
        try:
            assembled = assemble_slides(paths, draft)
            warnings.extend(assembled["warnings"])
            deck = Presentation(draft)
            deck.core_properties.title = topic
            for slide, record in zip(deck.slides, records):
                _add_source_notes(slide, record)
            deck.save(draft)
            report = apply_template(draft, template, styled)
        except ValueError as exc:
            # Retain the approved set when original objects/masters cannot be combined.
            mode = "evidence_excerpts"
            warnings.append(f"Used editable source excerpts for this selection: {exc}")
    if mode == "evidence_excerpts":
        _evidence_deck(paths, records, parsed, topic, draft)
        report = apply_template(draft, template, styled)
    for item in records:
        item["assemblyMode"] = mode
    (stage / "source_map.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return mode, warnings + report["warnings"], report["template"]["appliedLayouts"]


def export_brief(corpus_dir: Path, output_dir: Path, topic: str, slides: list[dict], *,
                 template: Path | None = None, reflow: bool = False) -> dict:
    """Validate source bytes and quotes, generate the complete set, then publish new files only."""
    corpus = Path(corpus_dir).resolve()
    output = Path(output_dir).resolve()
    if output.is_relative_to(corpus / "presentations"):
        raise ValueError("Choose a draft output directory outside the source presentations.")
    if not topic.strip() or not slides:
        raise ValueError("Supply a topic and at least one selected source slide.")
    template = Path(template).resolve() if template else None
    names = ["draft.pptx", "styled.pptx", "source_map.json"]
    if template is None:
        names.append("field-briefing-template.pptx")
    if any((output / name).exists() for name in names):
        raise FileExistsError("The output already contains a brief. Choose another output directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".amr-export-", dir=output.parent) as temp:
        stage = Path(temp)
        with TemporaryDirectory(prefix=".amr-sources-", dir=output.parent) as snapshots:
            mode, warnings, layouts = _write_outputs(corpus, stage, Path(snapshots), topic, slides, template, reflow)
        if not output.exists():
            # rename only onto a new directory; no pre-existing folder is deleted.
            stage.rename(output)
        else:
            created = []
            try:
                for name in names:
                    destination = output / name
                    with destination.open("xb") as write, (stage / name).open("rb") as read:
                        created.append(destination)
                        shutil.copyfileobj(read, write)
            except OSError:
                for path in created:
                    path.unlink(missing_ok=True)
                raise
    return {"draft": str(output / names[0]), "styled": str(output / names[1]),
            "source_map": str(output / names[2]), "template": str(template or output / names[3]),
            "assembly_mode": mode, "warnings": warnings, "applied_layouts": layouts}
