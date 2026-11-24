"""Check whether five animal-health briefing prompts retrieve the expected source and original slide in the top five."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from run_public_corpus_demo import ROOT, load_corpus


def score_queries(corpus_dir, queries_path, sectors, language="en"):
    query_field = {"en": "query", "zh": "query_zh"}[language]
    records, index, failures = load_corpus(corpus_dir, sectors)
    if not records:
        raise ValueError("No verified decks match the selected sectors.")
    if failures:
        raise ValueError(f"{len(failures)} verified sources could not be indexed; refresh the corpus first.")
    indexed_ids = {records[s.deck_name]["id"] for s in index.slides}
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
            for rank, hit in enumerate(index.search(query, limit=5, latest_only=True), 1):
                slide = hit.slide
                record = records[slide.deck_name]
                matches.append({"rank": rank, "deck": record["title"], "slide": slide.slide_number,
                                "original_slide_title": slide.title, "source_page": record["source_page"],
                                "expected_source": record["id"] in expected,
                                "expected_page": slide.slide_number in expected.get(record["id"], [])})
            rank = next((m["rank"] for m in matches if m["expected_source"]), None)
            page_rank = next((m["rank"] for m in matches if m["expected_page"]), None)
            cases.append({"case": case["case"], "query": query, "expected_sources_and_pages": expected,
                          "expected_source_available": bool(expected.keys() & indexed_ids),
                          "first_expected_rank": rank, "first_expected_page_rank": page_rank, "top_five": matches})
    if not cases:
        raise ValueError("The query file contains no evaluation cases.")
    return {"language": language, "sectors": list(sectors) or ["all"], "indexed_decks": len(indexed_ids), "indexed_slides": len(index), "queries": len(cases),
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
    args = parser.parse_args()
    try:
        results = score_queries(args.corpus_dir, args.queries, () if args.all_sectors else ("animal", "one-health"),
                                args.language)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"AMR retrieval check: {exc}\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return int(results["page_hits_at_five"] != results["queries"])


if __name__ == "__main__":
    raise SystemExit(main())
