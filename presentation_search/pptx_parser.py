from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from pptx import Presentation
from pptx.shapes.group import GroupShape

from .freshness import extract_date_signals, normalize_family_key
from .models import DeckDocument, SlideDocument
from .providers.base import read_bounded


def _shape_text(shape) -> list[str]:
    values: list[str] = []
    if getattr(shape, "has_text_frame", False):
        text = shape.text_frame.text.strip()
        if text:
            values.append(text)
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                value = cell.text.strip()
                if value:
                    values.append(value)
    if getattr(shape, "has_chart", False):
        # Read the labels already embedded in the chart. Numeric series in
        # isolation cannot describe their units or support a factual sentence.
        chart = shape.chart._chartSpace
        labels = chart.xpath(
            ".//c:title//a:t | .//c:title//c:strCache/c:pt/c:v | "
            ".//c:ser/c:tx//c:v | .//c:ser/c:cat//c:strCache/c:pt/c:v | "
            ".//c:ser/c:cat//c:strLit/c:pt/c:v | .//c:ser/c:cat//c:lvl/c:pt/c:v"
        )
        values.extend(dict.fromkeys(n.text.strip() for n in labels if n.text and n.text.strip()))
    if isinstance(shape, GroupShape):
        for child in shape.shapes:
            values.extend(_shape_text(child))
    return values


def _content_type(text: str) -> str:
    lowered = text.lower()
    if any(
        term in lowered
        for term in ("data through", "as of", "trend", "incidence", "prevalence", "number of")
    ):
        return "current_data"
    if any(term in lowered for term in ("project update", "progress", "milestone", "activity")):
        return "project_update"
    if any(term in lowered for term in ("methodology", "method", "calculation", "model")):
        return "methodology"
    if any(term in lowered for term in ("definition", "means", "is defined as")):
        return "definition"
    if any(term in lowered for term in ("recommendation", "priority", "next step")):
        return "recommendation"
    return "unknown"


def parse_presentation(
    path: Path, source_url: str = "", *, source_key: str = "", name: str = "", folder: str = ""
) -> DeckDocument:
    path = Path(path)
    stat = path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    name = name or path.name
    source_key = source_key or str(path.resolve())
    deck_id = hashlib.sha256(source_key.encode()).hexdigest()[:24]
    content = read_bounded(path)
    digest = hashlib.sha256(content).hexdigest()
    with ZipFile(BytesIO(content)) as archive:
        members = archive.infolist()
        if len(members) > 10000 or sum(m.file_size for m in members) > 256 * 1024 * 1024:
            raise ValueError("Presentation exceeds package limits")
    prs = Presentation(BytesIO(content))
    if len(prs.slides) > 1000:
        raise ValueError("Presentation exceeds slide limit")
    family_occurrences = Counter()
    deck = DeckDocument(
        id=deck_id,
        filename=name,
        path=path,
        source_url=source_url,
        modified_at=modified_at,
    )

    for index, slide in enumerate(prs.slides, start=1):
        title = ""
        if slide.shapes.title is not None:
            title = slide.shapes.title.text.strip()
        text_parts: list[str] = []
        for shape in slide.shapes:
            text_parts.extend(_shape_text(shape))
        text = "\n".join(dict.fromkeys(part for part in text_parts if part))
        notes = ""
        try:
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
        except (AttributeError, ValueError):
            notes = ""

        signal = extract_date_signals(
            text="\n".join(filter(None, [title, text, notes])),
            filename=name,
            modified_at=modified_at,
        )
        basis = title or text[:160] or path.stem
        family_key = f"{folder}:{normalize_family_key(Path(name).stem)}:{normalize_family_key(basis)}"
        family_occurrences[family_key] += 1
        family_key += f":{family_occurrences[family_key]}"
        slide_id = hashlib.sha256(
            f"{deck_id}:{digest}:{name}:{source_url}:{index}".encode("utf-8")
        ).hexdigest()[:24]
        deck.slides.append(
            SlideDocument(
                id=slide_id,
                deck_id=deck_id,
                deck_name=name,
                slide_number=index,
                title=title or f"Slide {index}",
                text=text,
                notes=notes,
                source_url=source_url or f"/api/slides/{slide_id}/source",
                source_hash=digest,
                source_key=source_key,
                report_date=signal.report_date,
                modified_at=modified_at,
                effective_year=signal.effective_year,
                date_confidence=signal.confidence,
                date_reason=signal.reason,
                family_key=family_key or f"{deck_id}-{index}",
                content_type=_content_type("\n".join([title, text, notes])),
            )
        )
    return deck
