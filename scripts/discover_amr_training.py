"""Discover native PowerPoint links at public AMR publishers for editorial review."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from . import amr_discovery_sources as publishers
else:  # python scripts/discover_amr_training.py
    import amr_discovery_sources as publishers

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_URL = "https://www.amrfvtraining.eu/library/"
HOST = "www.amrfvtraining.eu"
OUTPUT = ROOT / ".local" / "amr-training-candidates.csv"
FIELDS = ("status", "catalog_id", "title", "country", "section", "source_page", "download_url")
SOURCE_HOSTS = {
    "eu-training": {"www.amrfvtraining.eu", "amrfvtraining.eu"},
    "uk-varss": {"www.gov.uk"},
    "cgiar": {"cgspace.cgiar.org"},
    "strama": {"strama.se"},
    "rcgp-target": {"elearning.rcgp.org.uk"},
    "eu-awareness": {"health.ec.europa.eu"},
    "ukhsa-ebug": {"www.e-bug.eu"},
}
MAX_REQUESTS = 300
MAX_PAGE_BYTES = 8 * 1024 * 1024
COUNTRIES = set(
    "Austria|Belgium|Bulgaria|Croatia|Cyprus|Czech Republic|Czechia|Denmark|Estonia|Finland|"
    "France|Germany|Greece|Hungary|Ireland|Italy|Latvia|Lithuania|Luxembourg|Malta|"
    "Netherlands|The Netherlands|Poland|Portugal|Romania|Slovakia|Slovenia|Spain|Sweden".split("|")
)


def presentation_url(href: str) -> str | None:
    """Resolve only this publisher's PowerPoint files, including same-site file links in query strings."""
    href = href.strip()
    if re.match(r"^(?:https?%3a|%2f)", href, flags=re.IGNORECASE):
        href = unquote(href)
    try:
        target = urljoin(LIBRARY_URL, href)
    except ValueError:
        return None
    for depth in range(2):
        try:
            parts = urlsplit(target)
            if (
                parts.scheme not in {"http", "https"}
                or parts.hostname not in {HOST, "amrfvtraining.eu"}
                or parts.username is not None
                or parts.port not in {None, 80 if parts.scheme == "http" else 443}
            ):
                return None
        except ValueError:
            return None
        if unquote(parts.path).lower().endswith(".pptx"):
            path = quote(unquote(parts.path), safe="/!$&'()*+,;=:@-._~")
            return urlunsplit(("https", HOST, path, parts.query, ""))
        if depth == 0:
            for key, value in parse_qsl(parts.query):
                if key in {"file", "url", "download"} and value:
                    target = urljoin(target, value)
                    break
            else:
                return None
    return None


def file_key(url: str) -> str:
    # On this library page the files are static uploads. Tracking/download queries
    # and fragments do not identify additional presentations.
    return urlsplit(url).path


class LibraryLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.div_depth = 0
        self.sections: dict[int, str] = {}
        self.anchor: tuple[str | None, bool] | None = None
        self.label: list[str] = []
        self.files: dict[str, dict] = {}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        classes = (fields.get("class") or "").split()
        if tag == "div":
            self.div_depth += 1
            if "elementor-accordion-item" in classes:
                self.sections[self.div_depth] = ""
        elif tag == "a":
            self.anchor = (fields.get("href"), "elementor-accordion-title" in classes)
            self.label = []

    def handle_data(self, data):
        if self.anchor is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self.div_depth:
            self.sections.pop(self.div_depth, None)
            self.div_depth -= 1
        elif tag == "a" and self.anchor is not None:
            href, is_heading = self.anchor
            label = " ".join("".join(self.label).split())
            self.anchor = None
            depth = next(reversed(self.sections), None)
            if is_heading and depth is not None:
                self.sections[depth] = label.lstrip("• ").strip()
            elif href and (url := presentation_url(href)):
                row = self.files.setdefault(file_key(url), {
                    "title": "", "sections": [], "download_url": url,
                })
                if not row["title"] and label.lstrip("• ").casefold() not in {"presentation", "download", "pptx"}:
                    row["title"] = label
                section = self.sections[depth] if depth is not None else ""
                if section and section not in row["sections"]:
                    row["sections"].append(section)


def eu_training_links(html: str) -> list[dict[str, str]]:
    parser = LibraryLinks()
    parser.feed(html)
    parser.close()
    if not parser.files:
        raise ValueError("The library page contained no same-site PPTX links. Check the page before retrying.")
    rows = []
    for key, link in parser.files.items():
        sections = link["sections"]
        countries = [re.sub(r"\s+\d{4}$", "", section) for section in sections]
        rows.append({
            "title": link["title"] or unquote(key.rsplit("/", 1)[-1]),
            "country": " | ".join(dict.fromkeys(c for c in countries if c in COUNTRIES)),
            "section": " | ".join(sections),
            "source_page": LIBRARY_URL,
            "download_url": link["download_url"],
        })
    return rows


def file_identity(url: str) -> str:
    # This library's file aliases and tracking queries all resolve to a static path.
    # Other publishers can use query values to identify distinct downloads.
    if normalized := presentation_url(url):
        return "https://" + HOST + file_key(normalized)
    parts = urlsplit(url)
    if parts.netloc == "health.ec.europa.eu" and parts.path.startswith("/document/download/"):
        return urlunsplit(parts._replace(query=urlencode(parse_qsl(parts.query, keep_blank_values=True)), fragment=""))
    return url.partition("#")[0]


def load_catalog(path: Path) -> tuple[dict[str, str], str]:
    content = path.read_bytes()
    reader = csv.DictReader(StringIO(content.decode("utf-8-sig"), newline=""))
    if not {"id", "download_url"}.issubset(reader.fieldnames or ()):
        raise ValueError("The catalog must include id and download_url columns.")
    listed = {file_identity(row["download_url"]): row["id"] for row in reader if not row.get("zip_member")}
    return listed, hashlib.sha256(content).hexdigest()


def label_rows(links, listed):
    rows = {}
    for link in links:
        key = file_identity(link["download_url"])
        if key not in rows:
            catalog_id = listed.get(key, "")
            rows[key] = {**link, "status": "listed" if catalog_id else "candidate_unreviewed", "catalog_id": catalog_id}
    return list(rows.values())


def discovery_rows(html: str, catalog: Path) -> list[dict[str, str]]:
    listed, _ = load_catalog(catalog)
    return label_rows(eu_training_links(html), listed)


def allowed_page(url, hosts):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in hosts and parts.username is None and parts.port in (None, 443)


class PublisherRedirects(HTTPRedirectHandler):
    def __init__(self, hosts):
        super().__init__()
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_page(newurl, self.hosts):
            raise ValueError("Redirect left the selected publisher's HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_page(opener, url, stats):
    request = Request(url, headers={"User-Agent": "PPT-Builder-AMR-discovery/2.0"})
    for attempt in range(2):
        stats["request_attempts"] += 1
        try:
            with opener.open(request, timeout=30) as response:
                body = response.read(MAX_PAGE_BYTES + 1)
                if len(body) > MAX_PAGE_BYTES:
                    raise ValueError("Publisher page exceeded the 8 MiB discovery limit")
                return body.decode(response.headers.get_content_charset() or "utf-8")
        except HTTPError as exc:
            retry = exc.headers.get("Retry-After", "1") if exc.headers else "1"
            # Leave longer or date-based publisher backoff to a subsequent scan.
            if attempt or exc.code not in {429, 500, 502, 503, 504} or not retry.isdecimal() or int(retry) > 5:
                raise
            exc.close()
            time.sleep(int(retry))
        except (TimeoutError, URLError):
            if attempt:
                raise
            time.sleep(1)


def scan_source(source, listed, stats):
    hosts = SOURCE_HOSTS[source]
    opener = build_opener(PublisherRedirects(hosts))

    def fetch(url):
        if not allowed_page(url, hosts) or stats["pages_requested"] >= MAX_REQUESTS:
            raise ValueError("Page address or request count outside this source's allowed scope")
        stats["pages_requested"] += 1
        return read_page(opener, url, stats)

    if source == "eu-training":
        links = eu_training_links(fetch(LIBRARY_URL))
    else:
        discover = {"uk-varss": publishers.discover_uk_varss, "cgiar": publishers.discover_cgiar,
                    "rcgp-target": publishers.discover_rcgp, "strama": publishers.discover_strama,
                    "eu-awareness": publishers.discover_commission, "ukhsa-ebug": publishers.discover_ebug}
        links = discover[source](fetch)
    return label_rows(links, listed)


def write_csv(path, rows, fields):
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        temporary = Path(directory) / "rows.csv"
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)


def write_report(path, report):
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        temporary = Path(directory) / "report.json"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


def scan(catalog, sources, run_root, resume):
    listed, checksum = load_catalog(catalog)
    previous = {}
    if resume is not None:
        previous = json.loads((resume / "report.json").read_text(encoding="utf-8"))
        if previous["catalog_sha256"] != checksum:
            raise ValueError("The catalog changed since the saved scan. Start a new scan.")
        if sources is not None and set(sources) != set(previous["requested_sources"]):
            raise ValueError("Requested sources differ from the saved scan")
        sources = previous["requested_sources"]
    sources = sources or ["eu-training"]
    if not sources or any(source not in SOURCE_HOSTS for source in sources):
        raise ValueError("Unknown source in saved scan")
    if sources == ["eu-training"] and catalog.resolve() == OUTPUT.resolve():
        raise ValueError("Choose a catalog distinct from the discovery output")
    run_root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=run_root))
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "catalog_sha256": checksum,
              "requested_sources": sources, "complete": False, "sources": {}}
    print(f"Discovery scan: {run}", flush=True)
    write_report(run / "report.json", report)
    combined = []
    for source in sources:
        stats = {"status": "running", "pages_requested": 0, "request_attempts": 0}
        report["sources"][source] = stats
        write_report(run / "report.json", report)
        cached = previous.get("sources", {}).get(source, {})
        try:
            rows = None
            if cached.get("status") in {"ok", "empty"}:
                snapshot = resume / f"{source}.csv"
                data = snapshot.read_bytes() if snapshot.is_file() else b""
                if data and hashlib.sha256(data).hexdigest() == cached.get("snapshot_sha256"):
                    rows = list(csv.DictReader(StringIO(data.decode("utf-8"))))
                    stats["reused_from"] = str(resume)
            if rows is None:
                rows = scan_source(source, listed, stats)
            snapshot = run / f"{source}.csv"
            write_csv(snapshot, rows, FIELDS)
            count = sum(row["status"] == "listed" for row in rows)
            stats.update(status="ok" if rows else "empty", listed=count, unreviewed=len(rows) - count,
                         snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
            print(f"{source}: {len(rows)} links ({count} listed, {len(rows) - count} unreviewed).", flush=True)
            combined.extend({"source": source, **row} for row in rows)
        except (OSError, HTTPException, ValueError) as exc:
            stats.update(status="failed", error=str(exc))
            print(f"{source}: failed ({exc}).", flush=True)
        write_report(run / "report.json", report)
    if all(state["status"] in {"ok", "empty"} for state in report["sources"].values()):
        write_csv(run / "candidates.csv", combined, ("source", *FIELDS))
        if sources == ["eu-training"]:
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            write_csv(OUTPUT, [{key: row[key] for key in FIELDS} for row in combined], FIELDS)
        report["complete"] = True
        write_report(run / "report.json", report)
    return run, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "examples" / "public_corpus" / "amr" / "catalog.csv")
    parser.add_argument("--source", action="append", choices=["all", *SOURCE_HOSTS],
                        help="Repeat to select publishers, or use all. Defaults to eu-training.")
    parser.add_argument("--output-dir", type=Path, help="Parent directory for distinct run snapshots.")
    parser.add_argument("--resume", type=Path, help="Reuse completed source snapshots from this run.")
    args = parser.parse_args(argv)
    sources = None if not args.source else list(dict.fromkeys(args.source))
    if sources and "all" in sources:
        sources = list(SOURCE_HOSTS)
    try:
        run, report = scan(args.catalog, sources, args.output_dir or OUTPUT.parent / "amr-discovery", args.resume)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Discovery failed: {exc}\n")
    if not report["complete"]:
        parser.exit(1, f"Incomplete scan. Inspect {run / 'report.json'} and retry with --resume {run}\n")
    print(f"Review candidates in {run / 'candidates.csv'}")
    if report["requested_sources"] == ["eu-training"]:
        print(f"EU training CSV: {OUTPUT}")


if __name__ == "__main__":
    main()
