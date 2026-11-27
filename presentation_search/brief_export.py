"""Export verified selections to an editable draft and a separately styled copy."""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.util import Inches, Pt

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
    """Keep authored paragraphs together. Do not turn isolated table cells into claims."""
    blocks = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape != slide.shapes.title:
            if shape.is_placeholder and shape.placeholder_format.type in (
                PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.DATE,
                PP_PLACEHOLDER.FOOTER, PP_PLACEHOLDER.SLIDE_NUMBER,
            ):
                continue
            blocks.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
    return list(dict.fromkeys(blocks))


def _dominant_image(slide, deck):
    """A large, uncropped, unrotated JPEG/PNG on the selected page can accompany its excerpt."""
    images = []
    for shape in slide.shapes:
        if shape._element.tag != P + "pic" or shape.rotation or shape.width * shape.height < deck.slide_width * deck.slide_height * .18:
            continue
        if any(abs(v) > .001 for v in (shape.crop_left, shape.crop_right, shape.crop_top, shape.crop_bottom)):
            continue
        image = shape.image
        if image.content_type in {"image/jpeg", "image/png"}:
            images.append((shape.width * shape.height, image))
    return max(images, key=lambda item: item[0])[1] if images else None


def _excerpt_text(page, slide, evidence, limit):
    parts = _source_paragraphs(slide)
    normalized = " ".join(evidence.split())
    matches = [i for i, text in enumerate(parts) if normalized in " ".join(text.split())]
    start = matches[0] if matches else 0
    selected = []
    if normalized not in " ".join(" ".join(parts).split()) and evidence != page.title:
        selected.append(evidence)
    for part in parts[start:start + 5]:
        if sum(len(s) for s in selected) + len(part) > limit and selected:
            break
        selected.append(part)
    if not selected:
        selected.append(evidence)
    result = "\n\n".join(selected)
    if len(result) > limit:
        # A literal continuation mark distinguishes an excerpt from a full source claim.
        shortened = result[:limit].rsplit(" ", 1)[0]
        result = shortened.rstrip() + "…"
    return result


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
        title = page.title if page.title != f"Slide {number}" else record["deckTitle"]
        heading = target.shapes.title
        heading.left, heading.top, heading.width, heading.height = map(Inches, (.66, .32, 12, 1.28))
        heading.text = title
        heading.text_frame.word_wrap = True
        for paragraph in heading.text_frame.paragraphs:
            paragraph.font.name = "Aptos Display"
            paragraph.font.size = Pt(26 if len(title) > 85 else 32)
            paragraph.font.bold = True
        rows = _source_table(slide, record["evidence"])
        image = _dominant_image(slide, original) if rows is None else None
        record["excerptImage"] = bool(image)
        record["excerptTable"] = bool(rows)
        if rows:
            _draw_table(target, rows)
            body = ""
        elif rows is not None:
            body = "Open the source slide below to read the full table with its column headings and units."
        else:
            body = _excerpt_text(page, slide, record["evidence"], 410 if image else 650)
            if image and body == title:
                body = ""
        if image:
            w, h = image.size
            scale = min(4.7 / w, 3.85 / h)
            target.shapes.add_picture(BytesIO(image.blob), Inches(7.95 + (4.7 - w * scale) / 2),
                                      Inches(1.97 + (3.85 - h * scale) / 2), Inches(w * scale), Inches(h * scale))
        if body:
            shape = _textbox(target, body, .8, 1.84, 6.95 if image else 11.78, 4.4,
                             18 if len(body) > 340 else 22, "243537")
            for paragraph in shape.text_frame.paragraphs:
                paragraph.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
        credit = record["publisher"] or record["author"] or record["deckTitle"]
        label = f"{credit[:105]}   ·   Original slide {number}"
        footer = _textbox(target, label, .8, 6.68, 11.7, .45, 12, "355C6F")
        footer.text_frame.paragraphs[0].runs[0].hyperlink.address = record["sourcePage"]
        target.notes_slide.notes_text_frame.text = page.notes
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
