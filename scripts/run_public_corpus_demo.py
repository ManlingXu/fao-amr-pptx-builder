"""Search verified public PPTX files, revise a source-backed plan and export it locally."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import secrets
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from pptx import Presentation

from presentation_search.api import create_app
from presentation_search.assembly import assemble_slides
from presentation_search.config import Settings
from presentation_search.pptx_parser import parse_presentation
from presentation_search.providers.base import MAX_LIBRARY_FILES
from presentation_search.search import SearchIndex
from presentation_search.templates import MAX_TEMPLATE_BYTES

ROOT = Path(__file__).resolve().parents[1]


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_corpus(root):
    """Index only the current verification manifest, even if other decks remain cached."""
    rows = {}
    slides = []
    failures = []
    with (root / "verified.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"id", "title", "source_page", "download_url"} <= set(reader.fieldnames or ()):
            raise ValueError("verified.csv is missing required catalogue columns.")
        for row in reader:
            deck_id = row["id"]
            if not deck_id or Path(deck_id).name != deck_id or "\\" in deck_id:
                raise ValueError("Invalid deck ID in verified.csv.")
            filename = deck_id + ".pptx"
            if filename in rows:
                raise ValueError(f"Duplicate ID in verified.csv: {deck_id}")
            rows[filename] = row
            if len(rows) > MAX_LIBRARY_FILES:
                raise ValueError("Verified corpus exceeds the pilot file limit.")
            path = root / "presentations" / filename
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Missing local file or symlink.")
                deck = parse_presentation(path, source_url=row["source_page"], source_key=filename)
                if not deck.slides:
                    raise ValueError("Presentation contains no slides.")
                if row.get("sha256") and row["sha256"] != deck.slides[0].source_hash:
                    raise ValueError("Local file differs from the verified download.")
            except Exception as exc:
                failures.append({"id": deck_id, "reason": str(exc)})
                continue
            slides.extend(deck.slides)
            if len(slides) > 25_000:
                raise ValueError("Verified corpus exceeds the pilot slide limit.")
    return rows, SearchIndex(slides), failures


def public_source(item, rows):
    record = rows[item["deckName"]]
    attribution = {k: record[k] for k in ("author", "license", "issued") if record.get(k)}
    return {**item, "deckTitle": record["title"], "sourcePage": record["source_page"],
            "downloadUrl": record["download_url"], **attribution}


def response_json(response):
    if response.is_error:
        raise ValueError(f"{response.request.url.path}: {response.json().get('detail', response.reason_phrase)}")
    return response.json()


def compatible_selection(searches, presentations, work, per_section):
    """Try ranked candidates first, then up to eight other leads if coverage can improve."""
    checked = {}
    candidates = [search["results"] for search in searches]
    lead_section = next((i for i, hits in enumerate(candidates) if hits), 0)

    def attempt(lead_rank):
        picks = []
        ordered_ids = []
        used = set()
        sections = []
        skipped = []
        for i, search in enumerate(searches):
            hits = candidates[i]
            if i == lead_section and lead_rank > 1:
                pos = lead_rank - 1
                hits = [hits[pos], *hits[:pos], *hits[pos + 1:]]
            ids = []
            for hit in hits:
                sid = hit["slideId"]
                if sid in used:
                    continue
                pick = (presentations / hit["deckName"], hit["slideNumber"])
                key = (*ordered_ids, sid)
                if key not in checked:
                    try:
                        assemble_slides([*picks, pick], work / "compatibility.pptx")
                        checked[key] = None
                    except ValueError as exc:
                        checked[key] = str(exc)
                if checked[key] is not None:
                    skipped.append({"query": search["query"], "slideId": sid, "deckName": hit["deckName"],
                                    "slideNumber": pick[1], "reason": checked[key]})
                    continue
                used.add(sid)
                ordered_ids.append(sid)
                picks.append(pick)
                ids.append(sid)
                if len(ids) == per_section:
                    break
            sections.append({"title": search["query"][:120], "query": search["query"], "slide_ids": ids})
        coverage = (sum(len(s["slide_ids"]) == per_section for s in sections), len(ordered_ids))
        return coverage, sections, skipped

    upper_bound = (sum(len(hits) >= per_section for hits in candidates),
                   sum(min(per_section, len(hits)) for hits in candidates))
    # A missing query can never be filled by changing a different section.
    leads_to_try = min(9, len(candidates[lead_section])) if sum(bool(h) for h in candidates) > 1 else 1
    attempts = []
    best = None
    for lead_rank in range(1, max(1, leads_to_try) + 1):
        coverage, sections, skipped = attempt(lead_rank)
        attempts.append({"lead_query": searches[lead_section]["query"], "lead_candidate_rank": lead_rank,
                         "filled_sections": coverage[0], "selected_slides": coverage[1]})
        if best is None or coverage > best[0]:
            best = coverage, sections, skipped, len(attempts) - 1
        if best[0] == upper_bound:
            break
    _, sections, skipped, chosen = best
    attempts[chosen]["selected"] = True
    return sections, skipped, attempts


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def source_label(slide):
    # Keep public source text on one terminal line, including titles with line breaks.
    label = f"{slide['deckTitle']} · original slide {slide['slideNumber']} · {slide['title']}"
    return " ".join("".join(ch if ch.isprintable() else " " for ch in label).split())


def review_candidates(searches, sections, presentations, work):
    selected = []
    used_ids = set()
    rejected = []
    finished = True
    for search, section in zip(searches, sections):
        hits = search["results"]
        suggestions = [str(rank) for rank, hit in enumerate(hits, 1) if hit["slideId"] in section["slide_ids"]]
        section["slide_ids"] = []
        if not finished:
            continue
        print(f"\nSection: {search['query']}")
        for rank, hit in enumerate(hits, 1):
            print(f"  {rank}. {source_label(hit)}")
        if not hits:
            print("  No matches.")
            continue
        suggested = ",".join(suggestions) or "none"
        while True:
            answer = ask(f"Ranks in output order [suggested: {suggested}], 'none', or 'preview': ")
            if answer is None or answer.lower() == "preview":
                finished = False
                break
            answer = answer or suggested
            if answer.lower() == "none":
                break
            try:
                ranks = [int(v) for v in answer.replace(",", " ").split()]
                if not ranks or any(not 1 <= rank <= len(hits) for rank in ranks):
                    raise ValueError("Enter ranks shown for this section.")
                chosen = [hits[rank - 1] for rank in ranks]
                ids = [item["slideId"] for item in chosen]
                if len(set(ids)) != len(ids) or used_ids.intersection(ids):
                    raise ValueError("Each selected slide may appear once in the presentation.")
                if len(ids) > 8 or len(used_ids) + len(ids) > 20:
                    raise ValueError("Choose up to 8 slides per section and 20 slides overall.")
                picks = [(presentations / hit["deckName"], hit["slideNumber"]) for hit in chosen]
                assemble_slides(selected + picks, work / "compatibility.pptx")
            except ValueError as exc:
                print(f"Selection rejected: {exc} Choose other ranks or enter 'preview'.")
                rejected.append({"query": search["query"], "input": answer, "reason": str(exc)})
                continue
            section["slide_ids"] = ids
            used_ids.update(ids)
            selected.extend(picks)
            break
    return finished, rejected

def run_demo(corpus, out, queries, *, slides_per_query=1, reverse_sections=False,
             confirm=False, title="Public source briefing", template=None, interactive=False):
    corpus, out = Path(corpus).resolve(), Path(out).resolve()
    presentations = corpus / "presentations"
    if interactive and confirm:
        raise ValueError("Choose either interactive review or scripted confirmation.")
    if out.is_relative_to(presentations.resolve()):
        raise ValueError("Choose an output directory outside the source presentations.")
    if not 1 <= len(queries) <= 8 or any(not q.strip() or len(q) > 400 for q in queries):
        raise ValueError("Supply one to eight nonempty section queries of up to 400 characters.")
    if not 1 <= slides_per_query <= 8 or len(queries) * slides_per_query > 20:
        raise ValueError("Choose 1–8 slides per section and at most 20 slides in total.")
    if not title.strip() or len(title) > 120:
        raise ValueError("Supply a presentation title of up to 120 characters.")
    rows, index, failures = load_corpus(corpus)
    if not index.slides:
        raise ValueError("No verified presentations could be indexed. Run the corpus downloader first.")
    out.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=out))
    summary = {"output_directory": str(run), "verified_decks": len(rows),
               "indexed_decks": len({slide.deck_id for slide in index.slides}),
               "indexed_slides": len(index), "index_failures": failures,
               "queries": queries, "requested_slides": len(queries) * slides_per_query,
               "llm_called": False, "microsoft_services_called": False}
    with tempfile.TemporaryDirectory(prefix="public-ppt-demo-") as directory:
        work = Path(directory)
        key = secrets.token_urlsafe(32)
        settings = Settings(_env_file=None, auth_mode="api_key", copilot_api_key=key,
                            knowledge_provider="local", local_presentation_path=presentations,
                            drafts_path=work / "drafts")
        with TestClient(create_app(index=index, settings=settings), headers={"X-API-Key": key}) as client:
            searches = []
            versions = []
            for query in queries:
                result = response_json(client.post("/api/search", json={"query": query, "limit": 15}))
                searches.append({"query": query, "results": [public_source(r, rows) for r in result["results"]]})
                hits = result["results"]
                first_id = hits[0]["slideId"] if hits else None
                related = []
                if first_id:
                    group = response_json(client.get(f"/api/slides/{first_id}/versions"))
                    related = [public_source(version, rows) for version in group["versions"]]
                versions.append({"query": query, "firstHitSlideId": first_id, "versions": related})
            save_json(run / "search_results.json", searches)
            save_json(run / "versions.json", versions)
            template_id = None
            if template is not None:
                template = Path(template)
                with template.open("rb") as handle:
                    payload = handle.read(MAX_TEMPLATE_BYTES + 1)
                if len(payload) > MAX_TEMPLATE_BYTES:
                    raise ValueError("Template exceeds the 16 MiB upload limit.")
                uploaded = response_json(client.post("/api/templates", json={
                    "file_name": template.name, "content_base64": base64.b64encode(payload).decode("ascii"),
                }))
                template_id = uploaded["templateId"]
                summary["template"] = uploaded["fileName"]
            initial = response_json(client.post("/api/plans", json={
                "title": title, "audience": "Briefing participants", "template_id": template_id,
                "purpose": "Prepare a briefing using traceable public slides",
                "sections": [{"title": q[:120], "query": q, "slide_count": slides_per_query} for q in queries],
            }))
            initial["sourceMap"] = [public_source(s, rows) for s in initial["sourceMap"]]
            save_json(run / "initial_plan.json", initial)
            if reverse_sections:
                searches.reverse()
            sections, skipped, attempts = compatible_selection(searches, presentations, work, slides_per_query)
            finished = True
            if interactive:
                finished, summary["interactive_rejections"] = review_candidates(searches, sections, presentations, work)
            plan_path = f"/api/plans/{initial['planId']}"
            plan = response_json(client.put(plan_path, json={
                "expected_revision": initial["revision"], "sections": sections,
            }))
            plan["sourceMap"] = [public_source(s, rows) for s in plan["sourceMap"]]
            save_json(run / "revised_plan.json", plan)
            summary.update(revision=plan["revision"], selected_slides=len(plan["sourceMap"]),
                           skipped_incompatible=skipped, selection_attempts=attempts,
                           underfilled_sections=[s["query"] for s in sections
                                                 if len(s["slide_ids"]) < (1 if interactive else slides_per_query)])
            if interactive:
                print(f"\nRevision {plan['revision']} · {title}")
                for number, item in enumerate(plan["sourceMap"], 1):
                    print(f"  {number}. {source_label(item)}")
                if finished and not summary["underfilled_sections"]:
                    confirm = (ask("Export this revision as an editable PowerPoint? [yes/no, default no]: ") or "").lower() == "yes"
            if not finished:
                summary["status"] = "preview"
            elif summary["underfilled_sections"]:
                summary["status"] = "incomplete_plan"
            elif not confirm:
                summary["status"] = "preview"
            else:
                job = response_json(client.post(plan_path + "/draft", json={
                    "expected_revision": plan["revision"], "confirmed": True,
                }))
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    job_status = response_json(client.get(job["statusUrl"]))
                    if job_status["status"] in {"completed", "failed"}:
                        break
                    time.sleep(.1)
                else:
                    job_status = {"status": "failed", "error": "Draft job timed out."}
                summary["status"] = job_status["status"]
                if job_status["status"] == "completed":
                    response = client.get(job_status["downloadUrl"])
                    response.raise_for_status()
                    draft = run / "editable_draft.pptx"
                    draft.write_bytes(response.content)
                    source_map = [public_source(s, rows) for s in job_status["sourceMap"]]
                    if len(Presentation(draft).slides) != len(source_map):
                        raise RuntimeError("Generated slide count and source map differ.")
                    save_json(run / "source_map.json", source_map)
                    summary.update(source_decks=len({s["deckName"] for s in source_map}),
                                   warnings=job_status["warnings"])
                else:
                    summary["error"] = job_status["error"]
    save_json(run / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "public-corpus")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "public-corpus-demo")
    parser.add_argument("--query", action="append", help="Search text for a section; repeat for multiple sections.")
    parser.add_argument("--title", default="Public source briefing")
    parser.add_argument("--template", type=Path, help="Apply a local .pptx or .potx design to the confirmed draft.")
    parser.add_argument("--slides-per-query", type=int, default=1)
    parser.add_argument("--reverse-sections", action="store_true", help="Reverse the section order on revision.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--confirm", action="store_true", help="Approve the scripted revision for local draft export.")
    mode.add_argument("--interactive", action="store_true", help="Select candidate ranks in order and review before exporting.")
    args = parser.parse_args()
    try:
        summary = run_demo(args.corpus_dir, args.output_dir,
                           args.query or ["antimicrobial resistance", "One Health"],
                           title=args.title, slides_per_query=args.slides_per_query,
                           reverse_sections=args.reverse_sections, confirm=args.confirm, template=args.template,
                           interactive=args.interactive)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Public corpus demo: {exc}\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] in {"preview", "completed"} else 1


if __name__ == "__main__":
    sys.exit(main())
