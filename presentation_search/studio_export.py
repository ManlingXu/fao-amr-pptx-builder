"""Publish a reviewed Studio outline, source ledger and measured layout checks atomically."""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .assembly import P, assemble_slides
from .brief_export import _add_source_notes, _demo_template, _evidence_deck, _textbox, _verify
from .layout_validation import validate_layout
from .local_brief import _check_template
from .templating import apply_template


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _canvas(deck):
    return tuple(tuple(int(deck._element.find(P + tag).get(k)) for k in ("cx", "cy"))
                 for tag in ("sldSz", "notesSz"))


def _fit_rebuilt(path, canvas):
    """Fit rebuilt shapes into an original deck's canvas without stretching images."""
    deck = Presentation(path)
    if _canvas(deck) == canvas:
        return
    (width, height), (note_width, note_height) = canvas
    scale = min(width / deck.slide_width, height / deck.slide_height)
    dx, dy = (width - deck.slide_width * scale) / 2, (height - deck.slide_height * scale) / 2
    for slide in deck.slides:
        for shape in slide.shapes:
            x, y, w, h = shape.left, shape.top, shape.width, shape.height
            shape.left, shape.top = round(dx + x * scale), round(dy + y * scale)
            shape.width, shape.height = round(w * scale), round(h * scale)
            for prop in shape._element.xpath(".//a:rPr | .//a:defRPr | .//a:endParaRPr"):
                if prop.get("sz"):
                    prop.set("sz", str(max(100, round(int(prop.get("sz")) * scale))))
    deck.slide_width, deck.slide_height = width, height
    note = deck._element.find(P + "notesSz")
    note.set("cx", str(note_width))
    note.set("cy", str(note_height))
    deck.save(path)


def _format_digests(path, indices, slides, records):
    """Lay out the author's concise bilingual source digests as editable teaching slides."""
    deck = Presentation(path)
    for page, idx in zip(deck.slides, indices, strict=True):
        card, record = slides[idx], records[idx]
        if not card["digest"]:
            continue
        zh = card["display_language"] == "zh"
        page.background.fill.solid()
        page.background.fill.fore_color.rgb = RGBColor.from_string("F8F8F3")
        title = page.shapes.title
        for shape in list(page.shapes):
            if shape.shape_id != title.shape_id:
                shape._element.getparent().remove(shape._element)
        title.left, title.top, title.width, title.height = map(Inches, (.76, 1.09, 11.75, 1.25))
        title.text = card["title"]
        for para in title.text_frame.paragraphs:
            para.font.name = "Aptos Display"
            para.font.color.rgb = RGBColor.from_string("153F3F")
            para.font.bold, para.font.size = True, Pt(32 if len(card["title"]) > 65 else 39)
        label = ("兽医培训简报" if zh else "VETERINARY TRAINING BRIEF") + "    /    " + card["country"].upper()
        _textbox(page, label, .77, .42, 9.8, .33, 13, "24685D", bold=True)
        _textbox(page, f"{idx+1:02d} / {len(slides):02d}", 11.50, .42, 1.20, .33, 13, "37615A", bold=True)
        _textbox(page, card["body"], .78, 2.49, 8.0, 1.91, 22 if len(card["body"]) > 220 else 25, "243B38")
        _textbox(page, "原始资料页码" if zh else "PUBLISHER SLIDE", 9.35, 2.51, 3.04, .34, 13, "24685D", bold=True)
        _textbox(page, str(card["page"]), 9.30, 2.94, 2.7, 1.03, 49, "24685D", bold=True)
        _textbox(page, str(card["issued"] or ""), 9.36, 4.05, 2.93, .4, 15, "3C5750")
        _textbox(page, "讨论" if zh else "DISCUSSION", .78, 4.74, 8.0, .35, 13, "24685D", bold=True)
        _textbox(page, card["discussion"], .78, 5.21, 11.60, .89, 19, "243B38")
        label = ("资料来源  ·  " if zh else "Source   ·   ") + record["deckTitle"].removeprefix("Evidence digest — ")
        credit = _textbox(page, label, .78, 6.64, 11.80, .62, 12, "37615A")
        credit.text_frame.paragraphs[0].runs[0].hyperlink.address = record["sourcePage"]
    deck.save(path)


def _assemble(corpus, stage, work, topic, rows, slides, warnings):
    paths, records, parsed = _verify(corpus, rows, work)
    for record, card in zip(records, slides):
        if card["digest"]:
            record["digestSlideNumber"] = record["slideNumber"]
            record["originalPublisherSlide"] = card["page"]
            record["evidenceKind"] = "Bilingual editorial digest of the cited publisher slide"
            record["hashScope"] = "Local digest PowerPoint file"
            record["digestSHA256"] = record["sourceHash"]
    methods = [slide["method"] for slide in slides]
    canvas, dims = None, {}
    for i, (path, _) in enumerate(paths):
        if methods[i] == "compilation":
            if path not in dims:
                dims[path] = _canvas(Presentation(path))
            canvas = canvas or dims[path]
            if canvas != dims[path]:
                methods[i] = "reconstruction"
                warnings.append(f"Slide {i+1} was rebuilt to fit the presentation canvas.")
    adapted = {row["slide_id"]: {"title": slide["title"], "body": slide["body"]}
               for row, slide in zip(rows, slides)}
    draft = work / "content.pptx"

    def rebuild(indices):
        path = work / "excerpts.pptx"
        _evidence_deck([paths[i] for i in indices], [records[i] for i in indices],
                       parsed, topic, path, adaptations=adapted)
        if any(slides[i]["digest"] for i in indices):
            _format_digests(path, indices, slides, records)
        return path

    native = [i for i, mode in enumerate(methods) if mode == "compilation"]
    rebuilt = [i for i, mode in enumerate(methods) if mode == "reconstruction"]
    if native:
        picks = list(paths)
        if rebuilt:
            excerpts = rebuild(rebuilt)
            _fit_rebuilt(excerpts, canvas)
            for n, idx in enumerate(rebuilt, 1):
                picks[idx] = excerpts, n
        try:
            warnings.extend(assemble_slides(picks, draft)["warnings"])
        except ValueError:
            warnings.append("The original Office objects could not be combined. Verified editable excerpts were used.")
            methods = ["reconstruction"] * len(rows)
            draft = rebuild(list(range(len(rows))))
    else:
        draft = rebuild(rebuilt)
    deck = Presentation(draft)
    deck.core_properties.title = topic
    for number, (slide, record, card, mode) in enumerate(zip(deck.slides, records, slides, methods), 1):
        if mode == "compilation":
            _add_source_notes(slide, record)
        notes = slide.notes_slide.notes_text_frame
        notes.add_paragraph().text = card["notes"]
        if card["digest"]:
            notes.add_paragraph().text = f"Evidence digest page {card['local_page']} · Original publisher slide {card['page']}"
        record.update(outputSlide=number, assemblyMode=mode, presenterNote=card["notes"])
        if card["digest"]:
            record["slideNumber"] = card["page"]
    deck.save(stage / "brief.pptx")
    return records


def publish(corpus, output, topic, rows, slides, settings, template_path, warnings, signature, model_used):
    output.mkdir(parents=True, exist_ok=True)
    if output.resolve().is_relative_to(corpus.resolve()):
        raise ValueError("Session outputs must be outside the corpus.")
    if settings["template"] == "custom":
        if not template_path:
            raise ValueError("Upload a PowerPoint template for the custom theme.")
        _check_template(template_path)
    version_id = "v-" + uuid4().hex[:14]
    with tempfile.TemporaryDirectory(dir=output, prefix=".studio-") as temp:
        root = Path(temp)
        stage, work = root / "release", root / "work"
        stage.mkdir()
        work.mkdir()
        records = _assemble(corpus, stage, work, topic, rows, slides, warnings)
        deck_path = stage / "brief.pptx"
        if settings["template"] != "original":
            if settings["template"] == "field":
                template_path = work / "field.pptx"
                _demo_template(template_path)
            styled = work / "styled.pptx"
            warnings.extend(apply_template(deck_path, Path(template_path), styled)["warnings"])
            os.replace(styled, deck_path)
        deck = Presentation(deck_path)
        notes_verified = all(
            record["sourcePage"] in slide.notes_slide.notes_text_frame.text
            and " ".join(record["presenterNote"].split()) in " ".join(slide.notes_slide.notes_text_frame.text.split())
            for slide, record in zip(deck.slides, records, strict=True))
        if not notes_verified:
            raise ValueError("A source citation or presenter note was lost during generation.")
        layout = validate_layout(deck_path)
        source_count = len({r["sourceHash"] for r in records})
        numeric_review = []
        if model_used:
            for i, (row, card) in enumerate(zip(rows, slides, strict=True), 1):
                def numbers(value):
                    return set(re.findall(r"\d+(?:[.,]\d+)*", value))
                source_numbers = numbers(row["title"] + " " + row["evidence"])
                new_numbers = numbers(card["title"] + " " + card["body"] + " " + card["notes"]) - source_numbers
                if new_numbers:
                    numeric_review.append({"slide": i, "figures_to_check": sorted(new_numbers)})
            if numeric_review:
                warnings.append("Some generated figures do not match the source excerpt verbatim. Review the numeric checks.")

        qa = {"topic": topic, "requested_slides": settings["count"], "actual_slides": len(deck.slides),
              "coverage_gap": max(0, settings["count"] - len(deck.slides)),
              "distinct_sources": source_count, "source_hashes_and_excerpts_verified": True,
              "verified_material": "Locally generated editorial digest files and their embedded excerpts"
                  if all(s["digest"] for s in slides) else "Locally indexed presentation files and their embedded excerpts",
              "source_links_and_speaker_notes_present": notes_verified,
              "method_counts": dict(Counter(record["assemblyMode"] for record in records)),
              "requested_language": settings["language"], "model_used_for_draft": model_used,
              "generated_figures_needing_review": numeric_review,
              "warnings": list(dict.fromkeys(warnings)), "layout": layout,
              "manual_review": ["Check projected text and chart legibility in PowerPoint.",
                                "Review source licence exceptions and any third-party visuals.",
                                "Review translated or rewritten claims before presentation."]}
        files = {"pptx": deck_path.name, "sources": "source-report.json", "qa": "qa-report.json"}
        _write(stage / files["sources"], records)
        _write(stage / files["qa"], qa)
        version = {"id": version_id, "slide_count": len(records), "files": files, "mode": settings["mode"],
                   "template": settings["template"], "language": settings["language"], "topic": topic,
                   "created_at": datetime.now(timezone.utc).isoformat(), "source_count": source_count,
                   "qa_summary": layout["summary"], "signature": signature}
        stage.rename(output / version_id)
    return version
