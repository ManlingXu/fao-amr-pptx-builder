"""Prepare every approved AMR source for an offline-capable workbench launch."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from presentation_search.brief_index import read_verified_manifest
from scripts.fetch_public_corpus import digest, fetch_catalog, read_catalog

CATALOG = ROOT / "examples" / "public_corpus" / "amr" / "catalog.csv"


def _report(directory):
    try:
        value = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def describe_corpus(corpus_dir, catalog=CATALOG):
    """Summarise the active manifest, without downloading or building an index."""
    directory = Path(corpus_dir)
    approved = {row["id"]: row["sha256"] for row in read_catalog(Path(catalog))}
    try:
        rows = read_verified_manifest(directory / "verified.csv")
    except (OSError, ValueError, TypeError):
        rows = []
    present = []
    for row in rows:
        path = directory / "presentations" / (row["id"] + ".pptx")
        if path.is_file() and not path.is_symlink():
            present.append(row)
    matched = {r["id"] for r in present if approved.get(r["id"]) == r["sha256"]}
    counts = (r.get("slide_count") or "" for r in present)
    slides = sum(int(count) for count in counts if count.isascii() and count.isdigit() and len(count) < 9)
    report = _report(directory)
    unavailable = {item["id"] for field in ("failed", "duplicates")
                   if isinstance(report.get(field), list) for item in report[field]
                   if isinstance(item, dict) and isinstance(item.get("id"), str)}
    report_hash = report.get("catalog_sha256")
    accounted = (report.get("requested") == len(approved) and report.get("verified") == len(rows)
                 and len(rows) == len(present) == len(matched) and matched | unavailable == set(approved)
                 and (report_hash is None or report_hash == digest(Path(catalog))))
    return {"catalog_decks": len(approved), "verified_decks": len(present), "verified_slides": slides,
            "reviewed_decks": len(matched), "full_catalog_attempted": accounted,
            "is_reviewed_corpus": bool(present) and len(matched) == len(present)}


def prepare_corpus(catalog, corpus_dir, *, reuse_dirs=(), refresh=False, opener=urlopen, progress=None):
    catalog, directory = Path(catalog), Path(corpus_dir)
    summary = describe_corpus(directory, catalog)
    if summary["full_catalog_attempted"] and summary["verified_decks"] and not refresh:
        rows = read_verified_manifest(directory / "verified.csv")
        if all(digest(directory / "presentations" / (r["id"] + ".pptx")) == r["sha256"] for r in rows):
            return _report(directory)
    sources = tuple(dict.fromkeys([directory, *(Path(p) for p in reuse_dirs)]))
    return fetch_catalog(catalog, directory, workers=4, opener=opener, reuse_dirs=sources, progress=progress)


def default_directory(project=ROOT):
    """Use a separate directory if previous work occupies a default location."""
    base = project / ".local"
    expected = {row["id"]: row["sha256"] for row in read_catalog(CATALOG)}
    suffix = 0
    while True:
        name = "amr" if not suffix else ("amr-reviewed" if suffix == 1 else f"amr-reviewed-{suffix}")
        candidate = base / name
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        if candidate.is_dir() and not candidate.is_symlink():
            manifest = candidate / "verified.csv"
            if manifest.is_file():
                try:
                    rows = read_verified_manifest(manifest)
                    if all(expected.get(row["id"]) == row["sha256"] for row in rows):
                        return candidate
                except (OSError, ValueError, TypeError):
                    pass
            elif not any(candidate.iterdir()) or (candidate / ".cache" / "download.lock").is_file():
                # A download interrupted before publication may have receipts but no manifest.
                return candidate
        suffix += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Retry publishers unavailable on the last run")
    parser.add_argument("--serve", action="store_true", help="Open the local workbench when ready")
    args = parser.parse_args()
    directory = default_directory()
    downloads = Path.home() / "Downloads"
    reuse = (ROOT / ".local" / "amr", ROOT.parent / "UK_Example",
             downloads / "fao-amr-pptx-builder-main" / ".local" / "amr",
             downloads / "AMR_Local_Demo" / "amr-workbench" / ".local" / "amr",
             downloads / "AMR_Local_Demo" / "UK_Example")
    print(f"Preparing all {len(read_catalog(CATALOG))} approved AMR sources in {directory}", flush=True)

    def progress(done, total):
        if done == 1 or done % 10 == 0 or done == total:
            print(f"Checked {done}/{total} sources", flush=True)

    try:
        result = prepare_corpus(CATALOG, directory, reuse_dirs=reuse,
                                refresh=args.refresh, progress=progress)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Ready: {result['verified']} verified decks of {result['requested']} approved sources, "
          f"{result['slides']} original slides.", flush=True)
    if result["failed"]:
        print(f"Missing {len(result['failed'])} source(s). See {directory / 'report.json'}. "
              "Run start-amr.cmd --refresh to retry.", flush=True)
    if not result["verified"]:
        parser.exit(1, "No verified slides are available yet. Check your connection and retry.\n")
    if args.serve:
        return subprocess.call([sys.executable, str(ROOT / "scripts" / "serve_amr_brief.py"),
                                "--corpus-dir", str(directory), "--open-browser"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
