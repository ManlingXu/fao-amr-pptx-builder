"""Download and verify a catalogue of public, slide-searchable PowerPoint files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

from presentation_search.pptx_parser import parse_presentation
from presentation_search.providers.base import MAX_FILE_BYTES, write_bounded

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("id", "title", "source_page", "download_url")
CREDIT_FIELDS = ("author", "license", "issued", "publisher", "sector", "topic", "series", "language", "training_country", "evidence_slide")
VERIFIED_FIELDS = (*FIELDS, *CREDIT_FIELDS, "zip_member", "sha256", "slide_count")
SHA256 = re.compile(r"[0-9a-f]{64}")


def read_catalog(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or ()):
            raise ValueError("Catalogue requires columns " + ", ".join(FIELDS))
        rows = []
        ids = set()
        for number, raw in enumerate(reader, 2):
            row = {key: (raw.get(key) or "").strip() for key in (*FIELDS, *CREDIT_FIELDS, "sha256")}
            member = raw.get("zip_member") or ""
            if member and (
                not member.lower().endswith(".pptx")
                or "\\" in member
                or PureWindowsPath(member).drive
                or any(part in {"", ".", ".."} for part in member.split("/"))
                or any(ord(char) < 32 for char in member)
            ):
                raise ValueError(f"Line {number}: invalid relative PPTX zip_member {member!r}")
            row["zip_member"] = member
            identifier = row["id"]
            if (
                not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}", identifier)
                or identifier.endswith(".")
                or PureWindowsPath(identifier).is_reserved()
                or identifier.casefold() in ids
            ):
                raise ValueError(f"Line {number}: invalid or repeated deck id {identifier!r}")
            ids.add(identifier.casefold())
            if not row["title"]:
                raise ValueError(f"Line {number}: missing title")
            for key in ("download_url", "source_page"):
                url = urlsplit(row[key])
                if url.scheme not in {"https", "http"} or not url.hostname or url.username is not None:
                    raise ValueError(f"Line {number}: invalid HTTP(S) {key}")
            row["sha256"] = row["sha256"].lower()
            if row["sha256"] and not SHA256.fullmatch(row["sha256"]):
                raise ValueError(f"Line {number}: invalid sha256")
            rows.append(row)
        if not rows:
            raise ValueError("Catalogue is empty")
        return rows


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_deck(row, opener, cache, temporary):
    url = row["download_url"]
    member = row["zip_member"]
    # Keep the URL-only key for receipts written by older direct-download runs.
    key = url if not member else "\0" + url + "\0" + member
    receipt = cache / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    # The URL receipt is stored separately from the current selection, so an
    # interrupted or smaller run can reuse its verified files on a later run.
    if receipt.is_file():
        try:
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            checksum = saved["sha256"]
            if SHA256.fullmatch(checksum) and (not row["sha256"] or row["sha256"] == checksum):
                blob = cache / (checksum + ".pptx")
                count = int(saved["slide_count"])
                if count > 0 and blob.is_file() and blob.stat().st_size <= MAX_FILE_BYTES and digest(blob) == checksum:
                    return checksum, count
        except (OSError, ValueError, TypeError, KeyError):
            pass

    path = temporary / (row["id"] + ".download")
    url = quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    request = Request(url, headers={"User-Agent": "PPTBuilder-PublicCorpus/1.0"})
    with opener(request, timeout=30) as response:
        length = response.headers.get("Content-Length", "")
        if length.isdigit() and int(length) > MAX_FILE_BYTES:
            raise ValueError("A source deck exceeds the 64 MiB limit")
        write_bounded(path, iter(lambda: response.read(64 * 1024), b""))
    if member:
        extracted = temporary / (row["id"] + ".member")
        try:
            with ZipFile(path) as archive:
                matches = [info for info in archive.infolist() if info.filename == member]
                if len(matches) != 1:
                    raise ValueError("Publisher ZIP must contain exactly one entry named " + repr(member))
                entry = matches[0]
                if entry.file_size > MAX_FILE_BYTES:
                    raise ValueError("The selected PowerPoint exceeds the 64 MiB limit")
                with archive.open(entry) as stream:
                    write_bounded(extracted, iter(lambda: stream.read(64 * 1024), b""))
        finally:
            path.unlink(missing_ok=True)
        path = extracted
    checksum = digest(path)
    if row["sha256"] and row["sha256"] != checksum:
        raise ValueError("Downloaded SHA-256 differs from the catalogue")
    deck = parse_presentation(path, source_url=row["source_page"], name=row["title"])
    count = len(deck.slides)
    if not count:
        raise ValueError("PowerPoint has no slides")
    path.replace(cache / (checksum + ".pptx"))
    new_receipt = temporary / (row["id"] + ".receipt")
    new_receipt.write_text(json.dumps({"sha256": checksum, "slide_count": count}), encoding="utf-8")
    new_receipt.replace(receipt)
    return checksum, count


@contextmanager
def publisher_lock(cache):
    # Closing the handle releases both OS locks, including after a process exit.
    with (cache / "download.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Cannot acquire download lock; another fetch may be running in this corpus directory") from exc
        yield


def fetch_catalog(catalog, corpus_dir, *, limit=None, workers=3, opener=urlopen):
    if limit is not None and limit < 1:
        raise ValueError("--limit must be positive")
    if not 1 <= workers <= 12:
        raise ValueError("--workers must be between 1 and 12")
    rows = read_catalog(catalog)[:limit]
    cache = corpus_dir / ".cache"
    presentations = corpus_dir / "presentations"
    for directory in (cache, presentations):
        if directory.is_symlink():
            raise ValueError(f"Output directory cannot be a symlink: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

    verified = []
    seen = {}
    failed = []
    duplicates = []
    with publisher_lock(cache), tempfile.TemporaryDirectory(dir=corpus_dir, prefix=".fetch-") as working:
        temporary = Path(working)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            def attempt(row):
                try:
                    return download_deck(row, opener, cache, temporary), None
                except Exception as exc:
                    # Public hosts and third-party decks fail independently.
                    return None, f"{type(exc).__name__}: {exc}"

            for row, (result, error) in zip(rows, executor.map(attempt, rows)):
                if error is not None:
                    failure = {"id": row["id"], "download_url": row["download_url"], "error": error}
                    if row["zip_member"]:
                        failure["zip_member"] = row["zip_member"]
                    failed.append(failure)
                    continue
                checksum, count = result
                if checksum in seen:
                    duplicates.append({"id": row["id"], "duplicate_of": seen[checksum]})
                    continue
                seen[checksum] = row["id"]
                target = temporary / (row["id"] + ".pptx")
                blob = cache / (checksum + ".pptx")
                try:
                    os.link(blob, target)
                except OSError:
                    shutil.copyfile(blob, target)
                target.replace(presentations / target.name)
                verified.append({**row, "sha256": checksum, "slide_count": count})

        report = {
            "requested": len(rows), "verified": len(verified),
            "slides": sum(item["slide_count"] for item in verified),
            "duplicates": duplicates, "failed": failed,
        }
        archive_members = [
            {key: row[key] for key in ("id", "download_url", "zip_member")}
            for row in rows if row["zip_member"]
        ]
        if archive_members:
            report["archive_members"] = archive_members
        with (temporary / "verified.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=VERIFIED_FIELDS)
            writer.writeheader()
            writer.writerows(verified)
        (temporary / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for name in ("verified.csv", "report.json"):
            (temporary / name).replace(corpus_dir / name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "examples" / "public_corpus" / "catalog.csv")
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "public-corpus")
    parser.add_argument("--limit", type=int, help="Fetch only the first N catalogue rows")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent downloads (default 3)")
    args = parser.parse_args()
    try:
        report = fetch_catalog(args.catalog, args.corpus_dir, limit=args.limit, workers=args.workers)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    print(
        f"{report['verified']} unique verified presentations, {report['slides']} slides, "
        f"{len(report['duplicates'])} duplicates, {len(report['failed'])} failures. "
        f"See {args.corpus_dir / 'report.json'}."
    )
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
