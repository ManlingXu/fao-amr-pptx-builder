"""Evaluate offline slide retrieval, partial coverage and released PowerPoint files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from presentation_search.studio_service import StudioService

FIELDS = (
    "case",
    "partition",
    "suite",
    "language",
    "prompt",
    "expected",
    "status",
    "actual",
    "page_hit",
    "deck_hit",
    "first_accepted_rank",
    "traceable",
    "returned",
    "seconds",
    "issue",
    "observed_utc",
    "model",
    "indexed_decks",
    "indexed_slides",
    "interface_page_hit",
    "interface_returned",
)
QUESTION_BANK = ROOT / "docs/studio/evaluation-questions.csv"


def check_questions(service, cases):
    index = service._index()
    by_id = {page["slide_id"]: page for page in index.pages}
    for case in cases:
        start = perf_counter()
        target = json.loads(case["accepted_source_pages"])
        kind, prompt = case["kind"], case["prompt"]
        min_year = int(case["min_year"]) if case["min_year"] else None
        hits = index.search(prompt, 5, min_year=min_year)
        ranks = [
            i
            for i, h in enumerate(hits, 1)
            if h["slide_number"] in target.get(h["deck_id"], [])
        ]
        deck_hit = any(h["deck_id"] in target for h in hits)
        service_state = service.new_session()
        visible = service.turn(
            service_state,
            prompt,
            {"count": 5, "language": case["language"], "min_year": min_year},
        )
        visible_ids = [by_id[slide["id"]] for slide in visible["slides"]]
        interface_hit = any(
            row["slide_number"] in target.get(row["deck_id"], []) for row in visible_ids
        )
        actual = " | ".join(f"{h['deck_id']} p{h['slide_number']}" for h in hits)
        traceable = sum(
            bool(
                h["source_url"].startswith(("http://", "https://"))
                and h["source_hash"]
                and h["evidence"]
                and h["slide_id"] in by_id
                and " ".join(h["evidence"].split())
                in " ".join(
                    " ".join(
                        str(by_id[h["slide_id"]].get(k, ""))
                        for k in ("title", "body", "notes")
                    ).split()
                )
            )
            for h in hits
        )
        issue = ""
        if kind == "negative":
            passed = not hits and not visible_ids
            issue = "" if passed else "Unexpected matches on a no-evidence query."
            expected = "Return zero candidates."
        elif kind == "partial":
            # The independent missing-concept criterion checks what the requester actually sees.
            shown = " ".join([visible["reply"], *visible["warnings"]]).casefold()
            gap = ("budget" in shown or "预算" in shown) and any(
                x in shown
                for x in (
                    "missing",
                    "unavailable",
                    "unsupported",
                    "no evidence",
                    "无证据",
                    "缺少",
                    "未找到",
                    "无法",
                )
            )
            passed = interface_hit and gap
            actual += f" | budget gap explicitly disclosed={gap}"
            expected = target.__str__() + "; disclose missing 2099 budget evidence."
            if not passed:
                issue = (
                    "Mixed request: budget coverage needs explicit review."
                    if interface_hit
                    else "Supported clause missed; partial-coverage answer needs manual review."
                )
        else:
            passed = bool(ranks) and interface_hit
            issue = (
                ""
                if passed
                else (
                    "Accepted original page absent from visible outline."
                    if interface_hit
                    else "Accepted original page absent from first five retrieval results."
                )
            )
            expected = json.dumps(target, ensure_ascii=False, separators=(",", ":"))
        if traceable != len(hits):
            passed = False
            issue += (
                " Returned excerpt could not be matched to the indexed original page."
            )
        yield dict(
            case=case["case"],
            partition=case["partition"],
            suite=kind,
            language=case["language"],
            prompt=prompt,
            expected=expected,
            status="PASS" if passed else "REVIEW",
            actual=actual or "No matches",
            page_hit=int(bool(ranks)) if target else "",
            deck_hit=int(deck_hit) if target else "",
            first_accepted_rank=ranks[0] if ranks else "",
            traceable=traceable,
            returned=len(hits),
            seconds=round(perf_counter() - start, 3),
            issue=issue.strip(),
            interface_page_hit=int(interface_hit) if target else "",
            interface_returned=len(visible_ids),
        )


def check_exports(service):
    for mode, template in (
        ("compilation", "original"),
        ("reconstruction", "field"),
        ("hybrid", "original"),
    ):
        start = perf_counter()
        prompt = "How did Zambia reach farmers and traditional leaders about prudent antibiotic use?"
        row = dict(
            case="export-" + mode,
            partition="artifact",
            suite="export",
            language="en",
            prompt=prompt,
            expected="Open PPTX, confirm every original hash/page/URL and speaker note, match edited order, validate QA and idempotent re-export.",
        )
        try:
            state = service.new_session()
            initial = service.turn(
                state, prompt, {"count": 2, "mode": mode, "template": template}
            )
            original = initial["slides"]
            assert len(original) == 2, "Two supported slides required."
            edited = service.turn(state, "move slide 2 to slide 1")
            edited_ids = [p["id"] for p in edited["slides"]]
            assert edited_ids == [
                original[1]["id"],
                original[0]["id"],
            ], "Move did not preserve selected identities."
            generated = service.turn(state, "", action="generate")
            v = generated["versions"][-1]
            again = service.turn(state, "", action="generate")
            assert (
                len(again["versions"]) == 1 and again["versions"][-1]["id"] == v["id"]
            ), "Identical export duplicated."
            directory = service.output_dir / v["id"]
            deck = Presentation(directory / v["files"]["pptx"])
            records = json.loads((directory / v["files"]["sources"]).read_text())
            qa = json.loads((directory / v["files"]["qa"]).read_text())
            assert (
                len(records) == len(deck.slides) == 2
            ), "PPTX/source report count mismatch."
            assert (
                qa["coverage_gap"] == 0 and qa["actual_slides"] == 2
            ), "QA summary count mismatch."
            assert [
                record["slideId"] for record in records
            ] == edited_ids, "Export order mismatch."
            linked = 0
            for page, record in zip(deck.slides, records, strict=True):
                path = service.corpus_dir / "presentations" / record["deckName"]
                assert (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    == record["sourceHash"]
                ), "SHA-256 disagrees with original."
                assert (
                    1 <= record["slideNumber"] <= len(Presentation(path).slides)
                ), "Original page out of range."
                notes = page.notes_slide.notes_text_frame.text
                assert (
                    record["sourcePage"] in notes and record["presenterNote"].strip()
                ), "Missing note or source URL."
                linked += 1
            if mode == "compilation" and qa["method_counts"].get(
                "compilation", 0
            ) != len(records):
                assert any(
                    "rebuilt" in warning.lower() or "excerpt" in warning.lower()
                    for warning in qa["warnings"]
                ), "Reconstruction fallback was not disclosed."
            row.update(
                status="PASS",
                returned=len(records),
                traceable=linked,
                actual=f"2 slides; methods={qa['method_counts']}; template={v['template']}; layout={qa['layout']['summary']}; unchanged export reused version.",
                issue="",
            )
        except (ValueError, AssertionError, KeyError, OSError) as exc:
            row.update(
                status="REVIEW",
                actual=type(exc).__name__ + ": " + str(exc),
                issue="Inspect the current export, reports and saved version.",
            )
        row["seconds"] = round(perf_counter() - start, 3)
        yield row


def check_native_and_restyle(service):
    prompt = "UK food-producing animals sales veterinary antibiotics mg/kg"
    state = service.new_session()
    start = perf_counter()
    base = dict(
        case="native-and-restyle",
        partition="artifact",
        suite="version",
        language="en",
        prompt=prompt,
        expected="Compile one original page; restyle it into a distinct version while preserving the first PPTX, evidence and speaker notes.",
    )
    try:
        service.turn(
            state, prompt, {"count": 1, "mode": "compilation", "min_year": 2026}
        )
        first = service.turn(state, "", action="generate")["versions"][-1]
        path = service.output_dir / first["id"] / first["files"]["pptx"]
        original = path.read_bytes()
        records = json.loads((path.parent / first["files"]["sources"]).read_text())
        qa = json.loads((path.parent / first["files"]["qa"]).read_text())
        assert qa["method_counts"] == {
            "compilation": 1
        }, "The requested publisher slide was rebuilt."
        assert (
            records[0]["deckId"] == "vmd-uk-varss-2025"
            and records[0]["slideNumber"] == 3
        ), "Unexpected original slide."
        styled = service.turn(state, "", {"template": "field"}, action="generate")[
            "versions"
        ]
        assert (
            len(styled) == 2
            and styled[0]["id"] == first["id"]
            and styled[1]["id"] != first["id"]
        ), "Restyling replaced an existing version."
        second = service.output_dir / styled[1]["id"] / styled[1]["files"]["pptx"]
        assert (
            original == path.read_bytes() and original != second.read_bytes()
        ), "Immutable bytes or restyled output check failed."
        original_notes = Presentation(path).slides[0].notes_slide.notes_text_frame.text
        new_notes = Presentation(second).slides[0].notes_slide.notes_text_frame.text
        assert (
            original_notes == new_notes and records[0]["sourcePage"] in new_notes
        ), "Source notes changed during restyling."
        base.update(
            status="PASS",
            actual="Original UK-VARSS 2025 p3 compiled and restyled into a second immutable version; original notes and URL preserved.",
            returned=2,
            traceable=2,
            issue="",
        )
    except (ValueError, AssertionError, KeyError, OSError) as exc:
        base.update(
            status="REVIEW",
            actual=str(exc),
            issue="Review native assembly and restyling.",
        )
    base["seconds"] = round(perf_counter() - start, 3)
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "docs/studio/evaluation.csv")
    parser.add_argument(
        "--artifacts", type=Path, help="Keep generated files in this directory."
    )
    args = parser.parse_args()
    with QUESTION_BANK.open(encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    with tempfile.TemporaryDirectory() as tmp:
        service = StudioService(args.corpus, args.artifacts or Path(tmp))
        stats = service._index().stats
        observations = [
            *check_questions(service, cases),
            *check_exports(service),
            check_native_and_restyle(service),
        ]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        out = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        out.writeheader()
        for obs in observations:
            out.writerow(
                dict(
                    obs,
                    observed_utc=stamp,
                    model="offline",
                    indexed_decks=stats["decks"],
                    indexed_slides=stats["slides"],
                )
            )
    print(
        f"{sum(o['status']=='PASS' for o in observations)}/{len(observations)} checks passed. Full outcomes: {args.out}"
    )


if __name__ == "__main__":
    main()
