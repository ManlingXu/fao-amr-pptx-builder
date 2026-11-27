"""Discover native slide attachments from curated public stewardship publishers."""
from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urldefrag, urljoin, urlsplit
from uuid import UUID

GOV = "https://www.gov.uk"
VARSS_COLLECTION = "/government/collections/veterinary-antimicrobial-resistance-and-sales-surveillance"
VARSS_RECORD = re.compile(r"/government/publications/veterinary-antimicrobial-resistance-and-sales-surveillance-\d{4}")
CGSPACE = "https://cgspace.cgiar.org"
DS = CGSPACE + "/server/api"
CG_QUERY = (
    "dcterms.type:Presentation AND (dc.title:antimicrobial OR dc.title:antibiotic "
    "OR dc.title:antimicrobials OR dc.title:antibiotics OR dc.title:AMR OR dc.title:AMU)"
)
CG_PAGE_SIZE = 60
MAX_PAGES = 4
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
RCGP_BOOKS = tuple(
    f"https://elearning.rcgp.org.uk/mod/book/tool/print/index.php?id={book}"
    for book in (12649, 12650, 12651)
)
COMMISSION_RESOURCES = (
    "https://health.ec.europa.eu/home-antimicrobial-resistance-campaign/"
    "resources-antimicrobial-resistance-campaign_en"
)
EBUG_LESSONS = tuple("https://www.e-bug.eu/" + lesson for lesson in (
    "ks2-antibiotics", "ks3-antimicrobial-resistance", "ks3-phse-preventing-infections-vaccination",
    "ks4-phse-preventing-infections-vaccination",
))
# Limit discovery to livestock, food-system and cross-sector policy/education records.
CG_SUBJECTS = re.compile(
    r"livestock|farmers?|animal sector|veterinar|agricultur|aquacultur|one health|"
    r"awareness|stewardship|poultry|antimicrobial resistance hub|gender lens", re.I,
)
CG_OUT_OF_SCOPE = re.compile(
    r"laborator|susceptibility testing|diagnostic|biomarker|biobank|genom|molecular|"
    r"escherichia|salmonella|strains?|foodborne disease|emerging infectious|pandemic", re.I,
)


def _json(fetch, url):
    try:
        data = json.loads(fetch(url))
    except ValueError as exc:
        raise ValueError(f"Invalid JSON from {url}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Invalid metadata object from {url}")
    return data


def _fields(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {name} in publication metadata")
    return value


def _items(value, name):
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Invalid {name} in publication metadata")
    return value


def discover_uk_varss(fetch):
    """Visit annual releases actually linked by the VMD collection and read their file attachments."""
    collection = _json(fetch, GOV + "/api/content" + VARSS_COLLECTION)
    documents = _items(_fields(collection.get("links"), "collection links").get("documents"), "collection documents")
    paths = dict.fromkeys(d["base_path"] for d in documents
                          if isinstance(d.get("base_path"), str) and VARSS_RECORD.fullmatch(d["base_path"]))
    if len(paths) > 50:
        raise ValueError("The VMD collection exceeds the 50-release discovery limit")
    rows = {}
    for path in paths:
        publication = _json(fetch, GOV + "/api/content" + path)
        title = publication.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Missing publication title at {path}")
        details = _fields(publication.get("details"), "publication details")
        attachments = _items(details.get("attachments"), "publication attachments")
        for attachment in attachments:
            url = attachment.get("url")
            if not isinstance(url, str):
                raise ValueError(f"Missing attachment URL at {path}")
            parts = urlsplit(url)
            if (
                attachment.get("attachment_type") != "file"
                or parts.scheme != "https" or parts.netloc != "assets.publishing.service.gov.uk"
                or not unquote(parts.path).lower().endswith(".pptx")
            ):
                continue
            rows[url] = {
                "title": f"{title} — {attachment.get('title') or attachment.get('filename') or 'Presentation'}",
                "source_page": GOV + path, "download_url": url,
                "country": "United Kingdom", "section": "UK VARSS " + path[-4:],
            }
    return list(rows.values())


def _uuid(item):
    try:
        return str(UUID(str(item.get("uuid") or item.get("id"))))
    except ValueError as exc:
        raise ValueError("Invalid CGSpace record identifier") from exc


def _paged(fetch, first, url_for, field, *, search=False):
    """Read bounded HAL pages; an empty result is valid only when its metadata confirms it."""
    page = 0
    while True:
        data = first if page == 0 and first is not None else _json(fetch, url_for(page))
        data = _fields(data, "CGSpace result")
        if search:
            embedded = _fields(data.get("_embedded"), "CGSpace search response")
            data = _fields(embedded.get("searchResult"), "CGSpace search result")
        pagination = _fields(data.get("page"), "CGSpace pagination")
        pages = pagination.get("totalPages")
        if (pagination.get("number") != page or type(pages) is not int or pages < 0
                or pages > MAX_PAGES or (page and page >= pages)):
            raise ValueError(f"Invalid or excessive CGSpace pagination for {field} (limit {MAX_PAGES} pages)")
        entries = _fields(data.get("_embedded", {}), "CGSpace embedded response").get(field)
        if pages == 0 and pagination.get("totalElements") == 0 and entries is None:
            entries = []
        entries = _items(entries, "CGSpace " + field)
        if bool(pages) != bool(entries):
            raise ValueError(f"Incomplete CGSpace page of {field}")
        yield from entries
        page += 1
        if page >= pages:
            return


def _attachment_rows(fetch, item):
    item_id = _uuid(item)
    base = f"{DS}/core/items/{item_id}/bundles"
    bundles = _paged(fetch, None, lambda n: f"{base}?embed=bitstreams&page={n}", "bundles")
    countries = _items(item["metadata"].get("cg.coverage.country", []), "CGSpace country metadata")
    country = " | ".join(dict.fromkeys(c["value"] for c in countries if isinstance(c.get("value"), str)))
    for bundle in bundles:
        if bundle.get("name") != "ORIGINAL":
            continue
        bundle_id = _uuid(bundle)
        first = _fields(bundle.get("_embedded", {}), "CGSpace bundle").get("bitstreams")
        bitstreams = _paged(
            fetch, first, lambda n: f"{DS}/core/bundles/{bundle_id}/bitstreams?page={n}", "bitstreams"
        )
        for file in bitstreams:
            if isinstance(file.get("name"), str) and file["name"].lower().endswith(".pptx"):
                yield {
                    "title": item["name"], "source_page": f"{CGSPACE}/items/{item_id}",
                    "download_url": f"{DS}/core/bitstreams/{_uuid(file)}/content",
                    "country": country, "section": "CGSpace presentations",
                }


def discover_cgiar(fetch):
    """Query presentations by title, inspect public item metadata, and follow ORIGINAL bundles only."""
    def search_url(n):
        return DS + "/discover/search/objects?" + urlencode({"query": CG_QUERY, "size": CG_PAGE_SIZE, "page": n})

    records = _paged(fetch, None, search_url, "objects", search=True)
    rows = {}
    seen = set()
    for result in records:
        item = _fields(result.get("_embedded"), "CGSpace search hit").get("indexableObject")
        if not isinstance(item, dict):
            raise ValueError("Missing item in CGSpace search result")
        title = item.get("name")
        if not isinstance(title, str):
            raise ValueError("Missing title in CGSpace item")
        if (item.get("withdrawn") or not item.get("discoverable") or not CG_SUBJECTS.search(title)
                or CG_OUT_OF_SCOPE.search(title)):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Missing CGSpace item metadata")
        types = _items(metadata.get("dcterms.type", []), "CGSpace item types")
        record_id = _uuid(item)
        if not any(entry.get("value") == "Presentation" for entry in types) or record_id in seen:
            continue
        seen.add(record_id)
        for row in _attachment_rows(fetch, item):
            rows.setdefault(row["download_url"], row)
    return list(rows.values())


class _AttachmentLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            fields = dict(attrs)
            self.href = fields.get("href")
            self.label = fields.get("data-untranslated-label") or ""
            self.text = []

    def handle_data(self, data):
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join((self.label or " ".join(self.text)).split())))
            self.href = None


def _official_attachment_pages(fetch, pages, path_prefix, section, country, *, filename_query=False, static_cdn=None):
    rows = {}
    for page in pages:
        parser = _AttachmentLinks()
        parser.feed(fetch(page))
        parser.close()
        for href, title in parser.links:
            url = urldefrag(urljoin(page, href)).url
            parts = urlsplit(url)
            if (parts.scheme != "https" or parts.netloc != (static_cdn or urlsplit(page).netloc)
                    or not parts.path.startswith(path_prefix)):
                continue
            filename = parse_qs(parts.query).get("filename", [""])[0] if filename_query else unquote(parts.path)
            if not filename.casefold().endswith(".pptx"):
                continue
            if static_cdn:
                # e-Bug's public native files resolve by path; page links also carry expiring signatures.
                url = parts._replace(query="").geturl()
                title = re.sub(r"^(?:Download PPT\b[:\s]*)+", "", title, flags=re.IGNORECASE)
            rows.setdefault(url, {
                "title": title or filename.rsplit("/", 1)[-1], "source_page": page, "download_url": url,
                "country": country, "section": section,
            })
    if not rows:
        raise ValueError(f"No native PPTX attachments found in {section}; inspect the publisher page.")
    return list(rows.values())


def discover_rcgp(fetch):
    return _official_attachment_pages(fetch, RCGP_BOOKS, "/pluginfile.php/", "RCGP TARGET antibiotic toolkit",
                                      "United Kingdom")


def discover_commission(fetch):
    return _official_attachment_pages(fetch, [COMMISSION_RESOURCES], "/document/download/",
                                      "European Commission AMR awareness campaign", "", filename_query=True)


def discover_ebug(fetch):
    return _official_attachment_pages(fetch, EBUG_LESSONS, "/eu-west-2/documents/", "UKHSA e-Bug teaching slides",
                                      "United Kingdom", static_cdn="cdn.e-bug.eu")


def discover_strama(fetch):
    """Search Sweden's national stewardship programme's public media index for topical native decks."""
    rows = {}
    for page in range(MAX_PAGES):
        query = urlencode({"per_page": 100, "offset": page * 100, "mime_type": PPTX_MIME,
                           "orderby": "id", "order": "asc", "_fields": "title,post,link,source_url,mime_type"})
        records = _items(json.loads(fetch("https://strama.se/wp-json/wp/v2/media?" + query)), "Strama files")
        for record in records:
            title = _fields(record.get("title"), "Strama title").get("rendered")
            source = record.get("link")
            url = record.get("source_url")
            if not all(isinstance(value, str) for value in (title, source, url)):
                raise ValueError("Incomplete Strama media record")
            page_url, file_url = urlsplit(source), urlsplit(url)
            if (record.get("mime_type") != PPTX_MIME or not title.strip()
                    or any(p.scheme != "https" or p.netloc != "strama.se" for p in (page_url, file_url))
                    or not file_url.path.startswith("/wp-content/uploads/")
                    or not unquote(file_url.path).lower().endswith(".pptx")
                    or not re.search(r"antibiotika|resistensdata|\bamr\b|app[- ]strama|stewardship",
                                     title, re.IGNORECASE)):
                continue
            # WordPress attachment permalinks often redirect to the raw file. The parent permalink opens the course.
            post = record.get("post")
            source_page = f"https://strama.se/?p={post}" if type(post) is int and post > 0 else source
            rows.setdefault(url, {"title": unescape(title), "source_page": source_page, "download_url": url,
                                  "country": "Sweden", "section": "Strama stewardship and prescribing"})
        if len(records) < 100:
            return list(rows.values())
    raise ValueError("Strama media index reached the discovery page limit; review before increasing it")
