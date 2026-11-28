"""Publish a reviewed Studio outline, source ledger and measured layout checks atomically."""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pptx import Presentation

from .assembly import P, assemble_slides
from .brief_export import _add_source_notes, _demo_template, _evidence_deck, _verify
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
        qa = {"topic": topic, "requested_slides": settings["count"], "actual_slides": len(deck.slides),
              "coverage_gap": max(0, settings["count"] - len(deck.slides)),
              "distinct_sources": source_count, "source_hashes_and_excerpts_verified": True,
              "source_links_and_speaker_notes_present": notes_verified,
              "method_counts": dict(Counter(record["assemblyMode"] for record in records)),
              "requested_language": settings["language"], "model_used_for_draft": model_used,
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
