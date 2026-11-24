"""List public AMR farmer/veterinarian training PPTX links for editorial review."""
from __future__ import annotations

import argparse
import csv
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_URL = "https://www.amrfvtraining.eu/library/"
HOST = "www.amrfvtraining.eu"
OUTPUT = ROOT / ".local" / "amr-training-candidates.csv"
FIELDS = ("status", "catalog_id", "title", "country", "section", "source_page", "download_url")
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


def discovery_rows(html: str, catalog: Path) -> list[dict[str, str]]:
    parser = LibraryLinks()
    parser.feed(html)
    parser.close()
    if not parser.files:
        raise ValueError("The library page contained no same-site PPTX links. Check the page before retrying.")
    with catalog.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"id", "download_url"}.issubset(reader.fieldnames or []):
            raise ValueError("The catalog must include id and download_url columns.")
        listed = {}
        for record in reader:
            if url := presentation_url(record["download_url"] or ""):
                listed[file_key(url)] = record["id"]
    rows = []
    for key, link in parser.files.items():
        sections = link["sections"]
        countries = [re.sub(r"\s+\d{4}$", "", section) for section in sections]
        rows.append({
            "status": "listed" if key in listed else "candidate_unreviewed",
            "catalog_id": listed.get(key, ""),
            "title": link["title"] or unquote(key.rsplit("/", 1)[-1]),
            "country": " | ".join(dict.fromkeys(c for c in countries if c in COUNTRIES)),
            "section": " | ".join(sections),
            "source_page": LIBRARY_URL,
            "download_url": link["download_url"],
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "examples" / "public_corpus" / "amr" / "catalog.csv")
    args = parser.parse_args(argv)
    try:
        if args.catalog.resolve() == OUTPUT.resolve():
            raise ValueError("Choose a catalog distinct from the discovery output.")
        request = Request(LIBRARY_URL, headers={"User-Agent": "PPT-Builder-AMR-discovery/1.0"})
        with urlopen(request, timeout=45) as response:
            html = response.read().decode(response.headers.get_content_charset() or "utf-8")
        rows = discovery_rows(html, args.catalog)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUTPUT.parent) as directory:
            temporary = Path(directory) / "discovery.csv"
            with temporary.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            temporary.replace(OUTPUT)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Discovery failed: {exc}\n")
    listed = sum(row["status"] == "listed" for row in rows)
    print(f"{len(rows)} distinct PPTX links: {listed} listed, {len(rows) - listed} unreviewed. {OUTPUT}")


if __name__ == "__main__":
    main()
