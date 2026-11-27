"""Check whether five animal-health briefing prompts retrieve the expected source and original slide in the top five."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from presentation_search.brief_index import build_brief_index
if __package__:
    from .run_public_corpus_demo import ROOT, load_corpus
else:
    from run_public_corpus_demo import ROOT, load_corpus


def _legacy_search(corpus_dir, sectors):
    records, index, failures = load_corpus(corpus_dir, sectors)
    if not records:
        raise ValueError("No verified decks match the selected sectors.")
    if failures:
        raise ValueError(f"{len(failures)} verified sources could not be indexed; refresh the corpus first.")
    indexed_ids = {records[s.deck_name]["id"] for s in index.slides}

    def search(query):
        for hit in index.search(query, limit=5, latest_only=True):
            slide = hit.slide
            record = records[slide.deck_name]
            yield record["id"], record["title"], slide.slide_number, slide.title, record["source_page"]

    return search, indexed_ids, len(index)


def _brief_search(corpus_dir, sectors):
    index = build_brief_index(corpus_dir)
    if index.stats["failures"]:
        raise ValueError("Verified sources could not be indexed; refresh the corpus first.")
    pages = [page for page in index.pages if not sectors or page["sector"] in sectors]
    if not pages:
        raise ValueError("No verified decks match the selected sectors.")

    def search(query):
        for page in index.search(query, limit=5, sectors=sectors):
            yield page["deck_id"], page["deck_title"], page["slide_number"], page["title"], page["source_url"]

    return search, {page["deck_id"] for page in pages}, len(pages)


def score_queries(corpus_dir, queries_path, sectors, language="en", engine="legacy"):
    query_field = {"en": "query", "zh": "query_zh"}[language]
    search, indexed_ids, slide_count = {"legacy": _legacy_search, "brief": _brief_search}[engine](corpus_dir, sectors)
    cases = []
    with queries_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if query_field not in (reader.fieldnames or ()):
            raise ValueError(f"Query file has no {query_field} column for {language}.")
        for case in reader:
            expected = json.loads(case["expected_sources_and_pages"])
            query = case[query_field].strip()
            if not query:
                raise ValueError(f"Missing {language} question for {case['case']}.")
            matches = []
            for rank, (deck_id, deck, number, title, source_page) in enumerate(search(query), 1):
                matches.append({"rank": rank, "deck": deck, "slide": number,
                                "original_slide_title": title, "source_page": source_page,
                                "expected_source": deck_id in expected,
                                "expected_page": number in expected.get(deck_id, [])})
            rank = next((m["rank"] for m in matches if m["expected_source"]), None)
            page_rank = next((m["rank"] for m in matches if m["expected_page"]), None)
            cases.append({"case": case["case"], "query": query, "expected_sources_and_pages": expected,
                          "expected_source_available": bool(expected.keys() & indexed_ids),
                          "first_expected_rank": rank, "first_expected_page_rank": page_rank, "top_five": matches})
    if not cases:
        raise ValueError("The query file contains no evaluation cases.")
    return {"language": language, "engine": engine, "sectors": list(sectors) or ["all"],
            "indexed_decks": len(indexed_ids), "indexed_slides": slide_count, "queries": len(cases),
            "hits_at_five": sum(c["first_expected_rank"] is not None for c in cases),
            "page_hits_at_five": sum(c["first_expected_page_rank"] is not None for c in cases),
            "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "amr")
    parser.add_argument("--queries", type=Path,
                        default=ROOT / "examples" / "public_corpus" / "amr" / "queries.csv")
    parser.add_argument("--all-sectors", action="store_true", help="Include human-health sources in the comparison.")
    parser.add_argument("--language", choices=("en", "zh"), default="en",
                        help="Use the specified prompts with the same labelled source pages.")
    parser.add_argument("--engine", choices=("legacy", "brief"), default="legacy",
                        help="Compare the original search or the local briefing index against the same labels.")
    args = parser.parse_args()
    try:
        results = score_queries(args.corpus_dir, args.queries, () if args.all_sectors else ("animal", "one-health"),
                                args.language, args.engine)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"AMR retrieval check: {exc}\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return int(results["page_hits_at_five"] != results["queries"])


if __name__ == "__main__":
    raise SystemExit(main())
