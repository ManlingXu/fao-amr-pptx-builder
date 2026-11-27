"""Build a traceable 10-slide Zambia AMR deck and apply two templates."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import secrets
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER

from presentation_search.api import create_app
from presentation_search.assembly import P
from presentation_search.config import Settings
from presentation_search.pptx_parser import parse_presentation
from presentation_search.search import SearchIndex
from presentation_search.templates import MAX_TEMPLATE_BYTES
from scripts.run_public_corpus_demo import public_source
from scripts.run_template_demo import synthetic_template

DEFAULT_DECK_ID = "amr-antimicrobial-resistance-and-antimicrobial-stewardship-in-th-ed21ba02"
DEFAULT_SLIDE_NUMBERS = (1, 2, 3, 5, 8, 10, 11, 15, 17, 19)
DEFAULT_TITLE = "Veterinary stewardship in Zambia"
OUTPUTS = {
    "original": "AMR_10_Slide_Original.pptx",
    "blue": "AMR_10_Slide_Blue.pptx",
    "green": "AMR_10_Slide_Green.pptx",
}
STORY_ROLES = {
    1: "Opening: AMR and antimicrobial stewardship in Zambia",
    2: "Challenge: reported antimicrobial resistance in Zambia",
    3: "Response principle: why antimicrobial stewardship matters",
    5: "National response: the action plan and its five objectives",
    8: "Implementation: awareness, biosecurity and early disease reporting",
    10: "Outreach: radio, meetings and stakeholder engagement",
    11: "Training: prudent use of antibiotics",
    15: "Policy: legislation and species-specific treatment guidance",
    17: "Surveillance: protocols for poultry, pigs and aquaculture",
    19: "Capacity: laboratory infrastructure and staff development",
}


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_slide_numbers(value: str) -> tuple[int, ...]:
    try:
        numbers = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("Invalid slide number; use ten comma-separated integers.") from exc
    if len(numbers) != 10:
        raise ValueError("The showcase requires exactly 10 slide numbers.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("The 10 slide numbers must be unique.")
    if any(number < 1 for number in numbers):
        raise ValueError("Slide numbers are 1-based and must be positive.")
    return numbers


def response_json(response):
    if response.is_error:
        try:
            detail = response.json().get("detail", response.reason_phrase)
        except (ValueError, AttributeError):
            detail = response.reason_phrase
        raise ValueError(f"{response.request.url.path}: {detail}")
    return response.json()


def wait_job(client: TestClient, response, timeout: float = 180) -> dict:
    job = response_json(response)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = response_json(client.get(job["statusUrl"]))
        if status["status"] == "completed":
            return status
        if status["status"] == "failed":
            raise ValueError(status["error"] or "Draft generation failed.")
        time.sleep(0.05)
    raise ValueError("The 10-slide showcase timed out.")


def _load_verified_deck(corpus: Path, deck_id: str):
    if not deck_id or Path(deck_id).name != deck_id or "\\" in deck_id:
        raise ValueError("Invalid deck ID.")
    manifest = corpus / "verified.csv"
    if not manifest.is_file():
        raise ValueError("verified.csv was not found; download the AMR corpus first.")
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "title", "source_page", "download_url", "sha256"}
        if not required <= set(reader.fieldnames or ()):
            raise ValueError("verified.csv is missing required catalogue columns.")
        matches = [row for row in reader if row["id"] == deck_id]
    if len(matches) != 1:
        raise ValueError(f"Verified AMR deck not found: {deck_id}")
    row = matches[0]
    filename = deck_id + ".pptx"
    path = corpus / "presentations" / filename
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Verified source file is missing: presentations/{filename}")
    deck = parse_presentation(path, source_url=row["source_page"], source_key=filename)
    if not deck.slides or deck.slides[0].source_hash != row["sha256"]:
        raise ValueError("The local source differs from the SHA-256 in verified.csv.")
    for slide in deck.slides:
        slide.deck_title = row["title"]
    return row, path, deck


def _validate_selection(slide_numbers, slide_count: int) -> tuple[int, ...]:
    numbers = tuple(slide_numbers)
    if len(numbers) != 10:
        raise ValueError("The showcase requires exactly 10 slide numbers.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("The 10 slide numbers must be unique.")
    if any(not isinstance(number, int) or isinstance(number, bool) or number < 1 for number in numbers):
        raise ValueError("Slide numbers are 1-based positive integers.")
    invalid = [number for number in numbers if number > slide_count]
    if invalid:
        raise ValueError(f"Slide number out of range for the verified source: {invalid[0]}")
    return numbers


def _template_bytes(path: Path) -> bytes:
    path = Path(path)
    if path.suffix.lower() not in {".pptx", ".potx"} or not path.is_file() or path.is_symlink():
        raise ValueError(f"Template must be a local PPTX or POTX file: {path}")
    with path.open("rb") as handle:
        content = handle.read(MAX_TEMPLATE_BYTES + 1)
    if len(content) > MAX_TEMPLATE_BYTES:
        raise ValueError("Template exceeds the 16 MiB upload limit.")
    return content


def _upload_template(client: TestClient, path: Path) -> dict:
    return response_json(client.post("/api/templates", json={
        "file_name": path.name,
        "content_base64": base64.b64encode(_template_bytes(path)).decode("ascii"),
    }))


def _unique_layout(layout_names: list[str], candidates: list[str]) -> str | None:
    counts = Counter(layout_names)
    by_lower = {name.lower(): name for name in layout_names if counts[name] == 1}
    for candidate in candidates:
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    for candidate in candidates:
        matches = [name for name in layout_names
                   if counts[name] == 1 and candidate.lower() in name.lower()]
        if len(matches) == 1:
            return matches[0]
    return None


def choose_layouts(layout_names: list[str], analysis: list[dict]) -> tuple[list[dict], list[dict]]:
    overrides = []
    decisions = []
    for output_slide, item in enumerate(analysis, 1):
        if output_slide == 1:
            candidates = ["Title Slide", "Cover", "Title"]
        elif item["contentType"] == "image":
            candidates = ["Two Content", "Picture with Caption", "Title and Content", "Title Only"]
        else:
            candidates = ["Title and Content", "Content", "Title Only"]
        selected = _unique_layout(layout_names, candidates)
        if selected:
            overrides.append({"output_slide": output_slide, "layout_name": selected})
        decisions.append({
            "outputSlide": output_slide,
            "sourceSlide": item["slideNumber"],
            "title": item["title"],
            "contentType": item["contentType"],
            "density": item["density"],
            "recommendedLayoutAction": item["recommendedLayoutAction"],
            "requestedLayout": selected,
            "fallbackToAutomatic": selected is None,
        })
    return overrides, decisions


def _slide_texts(presentation: Presentation) -> list[list[str]]:
    def collect(shapes):
        texts = []
        for shape in shapes:
            if (shape.is_placeholder
                    and shape.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER):
                continue
            if shape.has_text_frame and shape.text.strip():
                texts.append(shape.text)
            if shape.has_table:
                texts.extend(
                    cell.text
                    for row in shape.table.rows
                    for cell in row.cells
                    if cell.text.strip()
                )
            if hasattr(shape, "shapes"):
                texts.extend(collect(shape.shapes))
        return texts

    return [sorted(collect(slide.shapes)) for slide in presentation.slides]


def _slide_notes(presentation: Presentation) -> list[str]:
    return [slide.notes_slide.notes_text_frame.text for slide in presentation.slides]


def _picture_counts(presentation: Presentation) -> list[int]:
    def count(shapes):
        return sum(
            (1 if shape._element.tag == P + "pic" else 0)
            + (count(shape.shapes) if hasattr(shape, "shapes") else 0)
            for shape in shapes
        )

    return [count(slide.shapes) for slide in presentation.slides]


def _download(client: TestClient, job: dict, path: Path) -> None:
    response = client.get(job["downloadUrl"])
    response.raise_for_status()
    path.write_bytes(response.content)


def _build_showcase(
    corpus_dir: Path,
    output_dir: Path,
    *,
    deck_id: str = DEFAULT_DECK_ID,
    slide_numbers: tuple[int, ...] = DEFAULT_SLIDE_NUMBERS,
    title: str = DEFAULT_TITLE,
    template_a: Path | None = None,
    template_b: Path | None = None,
    reported_output_dir: Path | None = None,
) -> dict:
    corpus = Path(corpus_dir).resolve()
    output = Path(output_dir).resolve()
    presentations = (corpus / "presentations").resolve()
    if output.is_relative_to(presentations):
        raise ValueError("Choose an output directory outside the source presentations.")
    row, _, deck = _load_verified_deck(corpus, deck_id)
    numbers = _validate_selection(slide_numbers, len(deck.slides))
    if not title.strip() or len(title) > 120:
        raise ValueError("Supply a presentation title of up to 120 characters.")
    if template_a is not None:
        _template_bytes(template_a)
    if template_b is not None:
        _template_bytes(template_b)

    by_number = {slide.slide_number: slide for slide in deck.slides}
    selected = [by_number[number] for number in numbers]
    output.mkdir(parents=True, exist_ok=True)
    generated_a = template_a is None
    generated_b = template_b is None
    if generated_a:
        template_a = output / "Template_Blue.pptx"
        synthetic_template(template_a, "DDEBF7", "BLUE")
    if generated_b:
        template_b = output / "Template_Green.pptx"
        synthetic_template(template_b, "E2F0D9", "GREEN")

    original_path = output / OUTPUTS["original"]
    blue_path = output / OUTPUTS["blue"]
    green_path = output / OUTPUTS["green"]
    with tempfile.TemporaryDirectory(prefix="amr-ten-slide-") as directory:
        work = Path(directory)
        key = secrets.token_urlsafe(32)
        settings = Settings(
            _env_file=None,
            auth_mode="api_key",
            copilot_api_key=key,
            knowledge_provider="local",
            local_presentation_path=presentations,
            drafts_path=work / "drafts",
        )
        index = SearchIndex(deck.slides)
        with TestClient(create_app(index=index, settings=settings), headers={"X-API-Key": key}) as client:
            slide_ids = [slide.id for slide in selected]
            analysis = response_json(client.post("/api/slides/analyze", json={"slide_ids": slide_ids}))
            original = wait_job(client, client.post("/api/drafts", json={
                "title": title,
                "slide_ids": slide_ids,
                "confirmed": True,
            }))
            _download(client, original, original_path)

            template_a_metadata = _upload_template(client, Path(template_a))
            template_b_metadata = _upload_template(client, Path(template_b))
            overrides_a, decisions_a = choose_layouts(
                template_a_metadata["layoutNames"], analysis["slides"]
            )
            overrides_b, decisions_b = choose_layouts(
                template_b_metadata["layoutNames"], analysis["slides"]
            )
            blue = wait_job(client, client.post(
                f"/api/drafts/{original['jobId']}/template",
                json={
                    "template_id": template_a_metadata["templateId"],
                    "confirmed": True,
                    "layout_overrides": overrides_a,
                },
            ))
            green = wait_job(client, client.post(
                f"/api/drafts/{original['jobId']}/template",
                json={
                    "template_id": template_b_metadata["templateId"],
                    "confirmed": True,
                    "layout_overrides": overrides_b,
                },
            ))
            _download(client, blue, blue_path)
            _download(client, green, green_path)
            layout_blue = response_json(client.get(f"/api/drafts/{blue['jobId']}/layout-report"))
            layout_green = response_json(client.get(f"/api/drafts/{green['jobId']}/layout-report"))

    if original["sourceMap"] != blue["sourceMap"] or original["sourceMap"] != green["sourceMap"]:
        raise RuntimeError("Template versions do not preserve the original source map.")
    decks = [Presentation(path) for path in (original_path, blue_path, green_path)]
    if any(len(deck.slides) != 10 for deck in decks):
        raise RuntimeError("A showcase output does not contain exactly 10 slides.")
    notes_preserved = _slide_notes(decks[0]) == _slide_notes(decks[1]) == _slide_notes(decks[2])
    text_preserved = _slide_texts(decks[0]) == _slide_texts(decks[1]) == _slide_texts(decks[2])
    pictures_preserved = (
        _picture_counts(decks[0]) == _picture_counts(decks[1]) == _picture_counts(decks[2])
    )
    if not notes_preserved or not text_preserved or not pictures_preserved:
        raise RuntimeError("Template application changed source text, pictures or speaker notes.")
    if len({path.read_bytes() for path in (original_path, blue_path, green_path)}) != 3:
        raise RuntimeError("The template versions are not distinct PowerPoint files.")

    rows = {deck_id + ".pptx": row}
    source_map = [public_source(item, rows) for item in original["sourceMap"]]
    storyline = [
        {
            "outputSlide": position,
            "sourceSlide": number,
            "title": selected[position - 1].title,
            "storyRole": (
                STORY_ROLES.get(number, f"Curated source page {number}")
                if deck_id == DEFAULT_DECK_ID
                else f"Curated source page {number}"
            ),
        }
        for position, number in enumerate(numbers, 1)
    ]
    decisions = []
    for item_a, item_b, applied_a, applied_b in zip(
        decisions_a, decisions_b, blue["appliedLayouts"], green["appliedLayouts"]
    ):
        decisions.append({
            **item_a,
            "templateA": {
                "requestedLayout": item_a["requestedLayout"],
                "appliedLayout": applied_a,
                "fallbackToAutomatic": item_a["fallbackToAutomatic"],
            },
            "templateB": {
                "requestedLayout": item_b["requestedLayout"],
                "appliedLayout": applied_b,
                "fallbackToAutomatic": item_b["fallbackToAutomatic"],
            },
        })
        decisions[-1].pop("requestedLayout")
        decisions[-1].pop("fallbackToAutomatic")

    save_json(output / "storyline.json", storyline)
    save_json(output / "source_map.json", source_map)
    save_json(output / "slide_analysis.json", analysis)
    save_json(output / "layout_decisions.json", decisions)
    save_json(output / "layout_report_blue.json", layout_blue)
    save_json(output / "layout_report_green.json", layout_green)
    summary = {
        "status": "completed",
        "output_directory": str((reported_output_dir or output).resolve()),
        "source_deck": deck_id,
        "source_hash": selected[0].source_hash,
        "source_slide_numbers": list(numbers),
        "slides": 10,
        "template_switches": 2,
        "outputs": OUTPUTS,
        "template_a": template_a_metadata["fileName"],
        "template_b": template_b_metadata["fileName"],
        "generated_demo_templates": {"template_a": generated_a, "template_b": generated_b},
        "source_map_preserved": True,
        "notes_preserved": notes_preserved,
        "slide_text_preserved": text_preserved,
        "pictures_preserved": pictures_preserved,
        "blue_layout_review": layout_blue["summary"],
        "green_layout_review": layout_green["summary"],
        "warnings": {"blue": blue["warnings"], "green": green["warnings"]},
        "selection_mode": "curated deterministic showcase",
        "llm_called": False,
        "microsoft_services_called": False,
        "limitations": [
            "The local showcase uses a fixed, source-backed 10-slide storyline.",
            "Structural analysis does not interpret picture meaning.",
            "Template application preserves source content but may still require visual review in PowerPoint.",
        ],
    }
    save_json(output / "summary.json", summary)
    return summary


def _publish_showcase(stage: Path, output: Path) -> None:
    """Swap a fully validated directory into place, restoring the old one on failure."""
    stage, output = Path(stage), Path(output)
    if not stage.is_dir():
        raise ValueError("The staged showcase directory is missing.")
    if output.exists() and not output.is_dir():
        raise ValueError("The showcase output path must be a directory.")
    if not output.exists():
        os.replace(stage, output)
        return
    generated = set(OUTPUTS.values()) | {
        "Template_Blue.pptx", "Template_Green.pptx", "storyline.json", "source_map.json",
        "slide_analysis.json", "layout_decisions.json", "layout_report_blue.json",
        "layout_report_green.json", "summary.json",
    }
    if any(entry.name not in generated or entry.is_symlink() or not entry.is_file()
           for entry in output.iterdir()):
        raise ValueError("Choose a new output directory to preserve the other files here.")
    backup = output.parent / f".{output.name}.backup-{secrets.token_hex(8)}"
    os.replace(output, backup)
    try:
        os.replace(stage, output)
    except BaseException:
        try:
            os.replace(backup, output)
        except OSError as restore_error:
            raise RuntimeError(
                f"Could not restore the previous showcase from {backup}."
            ) from restore_error
        raise
    try:
        shutil.rmtree(backup)
    except OSError:
        # Publication succeeded. A locked old file can leave a hidden recovery
        # directory, which is safer than failing after the new set is complete.
        pass


def run_showcase(
    corpus_dir: Path,
    output_dir: Path,
    *,
    deck_id: str = DEFAULT_DECK_ID,
    slide_numbers: tuple[int, ...] = DEFAULT_SLIDE_NUMBERS,
    title: str = DEFAULT_TITLE,
    template_a: Path | None = None,
    template_b: Path | None = None,
) -> dict:
    """Build and validate every artifact before replacing the visible showcase."""
    corpus = Path(corpus_dir).resolve()
    output = Path(output_dir).resolve()
    presentations = (corpus / "presentations").resolve()
    if output.is_relative_to(presentations):
        raise ValueError("Choose an output directory outside the source presentations.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".amr-ten-slide-stage-",
        dir=output.parent,
    ) as directory:
        stage = Path(directory)
        summary = _build_showcase(
            corpus,
            stage,
            deck_id=deck_id,
            slide_numbers=slide_numbers,
            title=title,
            template_a=template_a,
            template_b=template_b,
            reported_output_dir=output,
        )
        _publish_showcase(stage, output)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "amr")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "amr-ten-slide-showcase")
    parser.add_argument("--deck-id", default=DEFAULT_DECK_ID)
    parser.add_argument("--slides", default=",".join(map(str, DEFAULT_SLIDE_NUMBERS)))
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--template-a", type=Path)
    parser.add_argument("--template-b", type=Path)
    args = parser.parse_args()
    try:
        summary = run_showcase(
            args.corpus_dir,
            args.output_dir,
            deck_id=args.deck_id,
            slide_numbers=parse_slide_numbers(args.slides),
            title=args.title,
            template_a=args.template_a,
            template_b=args.template_b,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"AMR 10-slide showcase: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
