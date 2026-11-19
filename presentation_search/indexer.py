from __future__ import annotations

import logging

from .pptx_parser import parse_presentation
from .providers.base import KnowledgeProvider, SourceFailure
from .search import SearchIndex

logger = logging.getLogger(__name__)


def rebuild_index(provider: KnowledgeProvider, index: SearchIndex) -> dict[str, object]:
    slides = []
    failures = []
    count = 0
    for source in provider.materialize_presentations():
        count += 1
        if isinstance(source, SourceFailure):
            logger.warning("Skipped unsupported presentation")
            failures.append({"file": source.name, "error": source.error})
            continue
        try:
            deck = parse_presentation(
                source.path,
                source_url=source.url,
                source_key=source.key,
                name=source.name,
                folder=source.folder,
            )
        except Exception as exc:
            logger.warning("Skipped unreadable presentation (%s)", type(exc).__name__)
            failures.append(
                {"file": source.name, "error": "Unreadable, unsupported, or oversized presentation"}
            )
            continue
        slides.extend(deck.slides)
        if len(slides) > 25000:
            raise ValueError("Approved library exceeds the pilot slide limit")
    index.replace(slides)
    return {"files_seen": count, "slides_indexed": len(slides), "failures": failures}
