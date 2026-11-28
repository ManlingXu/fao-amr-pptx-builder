"""Prepare the offline, attributed starter corpus from the bundled page digests."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "studio" / "evidence.json"
SAMPLE_FORMAT = b"evidence-digest-v1"
FIELDS = (
    "id",
    "title",
    "source_page",
    "download_url",
    "publisher",
    "author",
    "license",
    "issued",
    "sector",
    "topic",
    "language",
    "training_country",
    "sha256",
    "slide_count",
)


def _make_deck(records, target):
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    deck.core_properties.title = "Evidence digest — " + records[0]["source"]
    deck.core_properties.author = "PPT Builder demonstration"
    for record in records:
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        title = slide.shapes.title
        title.left, title.top, title.width, title.height = (
            Inches(0.65),
            Inches(0.48),
            Inches(12),
            Inches(1.05),
        )
        title.text = record["title"]
        title.text_frame.paragraphs[0].font.size = Pt(33)
        box = slide.shapes.add_textbox(
            Inches(0.75), Inches(1.65), Inches(11.7), Inches(4.8)
        )
        frame = box.text_frame
        frame.word_wrap = True
        for i, (text, size) in enumerate(
            (
                (record["evidence"], 24),
                (record["title_zh"], 21),
                (record["evidence_zh"], 21),
            )
        ):
            paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            paragraph.text = text
            paragraph.font.size = Pt(size)
            paragraph.space_after = Pt(18)
        credit = slide.shapes.add_textbox(
            Inches(0.75), Inches(6.28), Inches(11.7), Inches(0.85)
        )
        credit.text_frame.word_wrap = True
        run = credit.text_frame.paragraphs[0].add_run()
        run.text = f"Evidence digest · {record['author'] or record['publisher']} · Original slide {record['page']}"
        run.font.size = Pt(15)
        run.font.color.rgb = RGBColor.from_string("3C5187")
        run.hyperlink.address = record["url"]
        slide.notes_slide.notes_text_frame.text = (
            f"Original bilingual summary of {record['source']}, slide {record['page']}.\n"
            f"Credit: {record['author']} · {record['publisher']}\n{record['url']}\n"
            f"Source publication date: {record['issued'] or 'not stated'}."
        )
    deck.save(target)


def prepare_sample(directory: Path) -> Path:
    """Publish a complete generation atomically; concurrent starters use the same one."""
    source = EVIDENCE.read_bytes()
    revision = hashlib.sha256(SAMPLE_FORMAT + source).hexdigest()[:16]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / revision
    if (target / "verified.csv").is_file():
        return target
    grouped = defaultdict(list)
    for record in json.loads(source):
        grouped[record["source_id"]].append(record)
    tmp = Path(tempfile.mkdtemp(prefix="prepare-", dir=directory))
    try:
        (tmp / "presentations").mkdir()
        page_map = {}
        with (tmp / "verified.csv").open("w", newline="", encoding="utf-8") as stream:
            manifest = csv.DictWriter(stream, fieldnames=FIELDS)
            manifest.writeheader()
            for source_id, records in grouped.items():
                first = records[0]
                deck_id = "studio-" + source_id
                filename = tmp / "presentations" / (deck_id + ".pptx")
                _make_deck(records, filename)
                page_map[deck_id] = {
                    str(i): r["page"] for i, r in enumerate(records, 1)
                }
                manifest.writerow(
                    dict(
                        id=deck_id,
                        title="Evidence digest — " + first["source"],
                        source_page=first["url"],
                        download_url=first["download_url"],
                        publisher=first["publisher"],
                        author=first["author"],
                        license=first["license"],
                        issued=first["issued"],
                        sector="animal",
                        topic=first["source"],
                        language="en/zh",
                        training_country=first["country"],
                        sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
                        slide_count=len(records),
                    )
                )
        (tmp / "studio-page-map.json").write_text(
            json.dumps(page_map), encoding="utf-8"
        )
        try:
            tmp.rename(target)
        except OSError:
            if not (target / "verified.csv").is_file():
                raise
        return target
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    print(prepare_sample(ROOT / ".local" / "studio-sample"))
