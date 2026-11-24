"""Download selected discovery candidates and compare their original PPTX bytes with the AMR catalogue."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import urlopen

if __package__:
    from .fetch_public_corpus import FIELDS, ROOT, fetch_catalog, read_catalog
else:  # python scripts/review_amr_candidates.py
    from fetch_public_corpus import FIELDS, ROOT, fetch_catalog, read_catalog

MAX_SELECTION = 20
DEFAULT_CATALOG = ROOT / "examples" / "public_corpus" / "amr" / "catalog.csv"


def select_rows(candidates, urls):
    if not 1 <= len(urls) <= MAX_SELECTION or len(set(urls)) != len(urls):
        raise ValueError(f"Select 1 to {MAX_SELECTION} different download URLs from the candidates CSV.")
    wanted = set(urls)
    selected = {}
    with candidates.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"title", "source_page", "download_url"}.issubset(reader.fieldnames or ()):
            raise ValueError("Candidates CSV must include title, source_page and download_url.")
        for row in reader:
            url = row["download_url"]
            if url in wanted:
                if row.get("zip_member"):
                    raise ValueError("Review supports direct PPTX candidates from the discovery command.")
                selected.setdefault(url, row)
    missing = [url for url in urls if url not in selected]
    if missing:
        raise ValueError("URL absent from the candidates CSV: " + missing[0])
    return [
        {**selected[url], "id": "candidate-" + hashlib.sha256(url.encode()).hexdigest()}
        for url in urls
    ]


def review(candidates, urls, catalog, output_dir, *, opener=urlopen):
    selected = select_rows(candidates, urls)
    catalog_hash = hashlib.sha256(catalog.read_bytes()).hexdigest()
    frozen = read_catalog(catalog)
    if catalog_hash != hashlib.sha256(catalog.read_bytes()).hexdigest():
        raise ValueError("The comparison catalogue changed while being read. Please retry.")
    if any(not row["sha256"] for row in frozen):
        raise ValueError("A full SHA-256 is required for each comparison catalogue record.")
    by_hash = {row["sha256"]: row["id"] for row in frozen}
    output_dir.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=output_dir))
    selection = run / "selection.csv"
    with selection.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)
    # A fresh staging folder keeps these unreviewed files outside the searchable corpus
    # and observes current bytes even when a previously listed URL has changed.
    staging = run / "downloads"
    result = fetch_catalog(selection, staging, workers=min(3, len(selected)), opener=opener)
    with (staging / "verified.csv").open(encoding="utf-8", newline="") as stream:
        verified = {row["id"]: row for row in csv.DictReader(stream)}
    duplicates = {row["id"]: row["duplicate_of"] for row in result["duplicates"]}
    failures = {row["id"]: row["error"] for row in result["failed"]}
    records = []
    for row in selected:
        key = row["id"]
        record = {field: row[field] for field in FIELDS}
        record["discovery_status"] = row.get("status", "")
        if key in failures:
            record.update(status="failed", error=failures[key])
        else:
            original = verified[duplicates.get(key, key)]
            sha = original["sha256"]
            record.update(sha256=sha, slide_count=int(original["slide_count"]), catalog_id=by_hash.get(sha))
            if key in duplicates:
                record.update(status="duplicate_within_batch", duplicate_of=duplicates[key])
            elif sha in by_hash:
                record["status"] = "duplicate_of_catalog"
            else:
                record["status"] = "distinct_bytes"
        records.append(record)
    report = {"catalog_sha256": catalog_hash,
              "requested": len(records), "records": records}
    temporary = run / "review.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(run / "review.json")
    return run, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True, help="Candidates CSV produced by discovery.")
    parser.add_argument("--url", action="append", required=True, help="Exact download_url to review. Repeat for up to 20 URLs.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local" / "amr-candidate-review",
                        help="Parent directory for isolated review runs.")
    args = parser.parse_args(argv)
    try:
        run, report = review(args.candidates, args.url, args.catalog, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Candidate review failed: {exc}\n")
    for row in report["records"]:
        print(f"{row['status']}: {row['title']}")
    print(f"See {run / 'review.json'}")
    return int(any(row["status"] == "failed" for row in report["records"]))


if __name__ == "__main__":
    raise SystemExit(main())
