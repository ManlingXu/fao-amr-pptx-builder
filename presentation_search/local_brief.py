"""Create a source-backed local brief from a topic, a length and a verified corpus."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from pptx import Presentation

from .brief_export import export_brief
from .brief_index import build_brief_index, order_story
from .local_model import rerank_candidates
from .templates import MAX_TEMPLATE_BYTES
from .templating import apply_template


def _check_template(template):
    if template is None:
        return
    path = Path(template)
    if path.suffix.lower() not in {".pptx", ".potx"} or not path.is_file():
        raise ValueError("Choose an existing .pptx or .potx template.")
    if not 0 < path.stat().st_size <= MAX_TEMPLATE_BYTES:
        raise ValueError("The template must contain 1 byte to 16 MiB.")


def build_brief(corpus_dir, output_root, *, topic, pages, sectors=(), model=None, template=None, reflow=False):
    topic = topic.strip()
    if not 1 <= len(topic) <= 500:
        raise ValueError("Enter a topic between 1 and 500 characters.")
    if type(pages) is not int or not 1 <= pages <= 20:
        raise ValueError("Choose between 1 and 20 slides.")
    if set(sectors) - {"animal", "one-health", "human"}:
        raise ValueError("Choose animal, one-health or human.")
    _check_template(template)
    corpus = Path(corpus_dir).resolve()
    root = Path(output_root).resolve()
    if root.is_relative_to(corpus):
        raise ValueError("Choose an output directory outside the source corpus.")

    index = build_brief_index(corpus)
    pool = index.search(topic, min(40, max(12, pages * 2)), sectors=sectors)
    used_model = False
    if model and pool:
        evidence = [{"slide_id": row["slide_id"], "title": row["title"],
                     "snippet": "\n".join((row["evidence"], row["body"], row["notes"])),
                     "source": row["deck_title"]} for row in pool]
        choices = rerank_candidates(topic, evidence, model=model, limit=min(pages, len(pool)))
        by_id = {row["slide_id"]: row for row in pool}
        chosen = [dict(by_id[choice["slide_id"]], evidence=choice["evidence"], model_evidence=choice["evidence"])
                  for choice in choices]
        used_model = True
    else:
        chosen = pool[:pages]
    selected = order_story(chosen)

    root.mkdir(parents=True, exist_ok=True)
    run = root / ("brief-" + uuid4().hex[:16])
    with tempfile.TemporaryDirectory(prefix=".building-", dir=root) as directory:
        stage = Path(directory)
        exports = export_brief(corpus, stage, topic, selected, template=template, reflow=reflow) if selected else {}
        report = {
            "topic": topic, "requested_pages": pages, "selected_pages": len(selected),
            "status": ("completed" if len(selected) == pages else "partial" if selected else "no_evidence"),
            "unfilled_pages": pages - len(selected), "sectors": list(sectors),
            "index": index.stats, "shortlisted": len(pool), "model_requested": model,
            "llm_called": used_model, "model_used": model if used_model else None,
            "output_directory": str(run),
            "outputs": {key: Path(exports[key]).name for key in ("draft", "styled", "source_map") if key in exports},
            "reflow_requested": reflow, "assembly_mode": exports.get("assembly_mode"),
            "warnings": exports.get("warnings", []),
            "selected": [{k: row[k] for k in (
                "slide_id", "deck_id", "deck_title", "slide_number", "title", "evidence", "source_url",
                "source_hash", "publisher", "author", "sector", "stage", "score", "reason", "model_evidence",
            ) if k in row} for row in selected],
        }
        (stage / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        stage.rename(run)
    return report


def restyle_brief(draft_path, template_path, destination_path):
    """Apply a new master to an existing brief without repeating retrieval."""
    draft, template, output = map(Path, (draft_path, template_path, destination_path))
    _check_template(template)
    if output.suffix.lower() != ".pptx" or output.exists() or output.is_symlink():
        raise ValueError("Choose a new .pptx filename for the template version.")
    if not draft.is_file():
        raise ValueError("The draft was not found.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        staged = Path(folder) / "styled.pptx"
        result = apply_template(draft, template, staged)
        def notes(path):
            return [s.notes_slide.notes_text_frame.text if s.has_notes_slide else ""
                    for s in Presentation(path).slides]
        if notes(draft) != notes(staged):
            raise ValueError("Template change did not preserve the source notes for each slide.")
        # Exclusive creation also protects callers that choose the same name concurrently.
        with staged.open("rb") as source, output.open("xb") as target:
            try:
                shutil.copyfileobj(source, target)
            except OSError:
                target.close()
                output.unlink(missing_ok=True)
                raise
    return result
