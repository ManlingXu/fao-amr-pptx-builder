import json
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from scripts.amr_discovery_sources import DS, GOV, MAX_PAGES, VARSS_COLLECTION, discover_cgiar, discover_uk_varss
from scripts import discover_amr_training as crawl


def test_varss_follows_collection_years_and_returns_only_official_pptx_attachments():
    path = "/government/publications/veterinary-antimicrobial-resistance-and-sales-surveillance-2030"
    url = "https://assets.publishing.service.gov.uk/media/123/annual%20figures.PPTX"
    requests = []

    def fetch(request):
        requests.append(request)
        if request == GOV + "/api/content" + VARSS_COLLECTION:
            return json.dumps({"links": {"documents": [
                {"base_path": path}, {"base_path": path}, {"base_path": "//other.test/file"},
                {"base_path": path + "/highlights"},
            ]}})
        assert request == GOV + "/api/content" + path
        urls = [url, url, url + ".pdf", "https://other.test/training.pptx", url.replace("https:", "http:")]
        return json.dumps({"title": "Veterinary sales 2030", "details": {"attachments": [
            {"url": link, "title": "Figures", "attachment_type": "file"} for link in urls
        ]}})

    [row] = discover_uk_varss(fetch)
    assert requests == [GOV + "/api/content" + VARSS_COLLECTION, GOV + "/api/content" + path]
    assert row == {"title": "Veterinary sales 2030 — Figures", "source_page": GOV + path, "download_url": url,
                   "country": "United Kingdom", "section": "UK VARSS 2030"}


def uid(n):
    return str(UUID(int=n))


def item(n, title, **overrides):
    fields = {"uuid": uid(n), "name": title, "withdrawn": False, "discoverable": True,
              "metadata": {"dcterms.type": [{"value": "Presentation"}], "cg.coverage.country": [{"value": "Kenya"}]}}
    fields.update(overrides)
    return {"_embedded": {"indexableObject": fields}}


def hal(field, rows, *, page=0, pages=1):
    return {"_embedded": {field: rows}, "page": {"number": page, "totalPages": pages, "totalElements": len(rows)}}


def test_cgspace_uses_public_presentation_records_and_original_bundle_pagination():
    a = item(1, "Veterinary stewardship for farmers")
    excluded = [item(4, "Laboratory testing in farm animals"), item(5, "Stewardship", withdrawn=True),
                item(6, "Stewardship", discoverable=False), item(7, "Stewardship", metadata={})]
    requests = []

    def fetch(url):
        requests.append(url)
        assert url.startswith(DS)
        parts = urlsplit(url)
        n = int(parse_qs(parts.query).get("page", ["0"])[0])
        if parts.path.endswith("/discover/search/objects"):
            page = hal("objects", [a, *excluded] if n == 0 else [a], page=n, pages=2)
            output = {"_embedded": {"searchResult": page}}
        elif parts.path.endswith("/items/" + uid(1) + "/bundles"):
            first = hal("bitstreams", [{"uuid": uid(10), "name": "paper.pdf"}], pages=2)
            output = hal("bundles", [
                {"name": "THUMBNAIL", "uuid": uid(12)},
                {"name": "ORIGINAL", "uuid": uid(11), "_embedded": {"bitstreams": first}},
            ])
        else:
            assert parts.path.endswith("/bundles/" + uid(11) + "/bitstreams") and n == 1
            output = hal("bitstreams", [{"uuid": uid(13), "name": "session.PPTX"}], page=1, pages=2)
        return json.dumps(output)

    [row] = discover_cgiar(fetch)
    assert len(requests) == 4
    assert row["source_page"] == "https://cgspace.cgiar.org/items/" + uid(1)
    assert row["download_url"] == DS + "/core/bitstreams/" + uid(13) + "/content"
    assert row["country"] == "Kenya"


@pytest.mark.parametrize("response", [
    {"_embedded": {"searchResult": {"page": {"number": 0, "totalPages": MAX_PAGES + 1}}}},
    {"_embedded": {"searchResult": {"page": {"number": 1, "totalPages": 1}}}},
    {"_embedded": {"searchResult": {"page": {"number": 0, "totalPages": 1}}}},
    {"_embedded": {"searchResult": hal("objects", [{}])}},
])
def test_malformed_or_excessive_search_is_not_reported_as_empty(response):
    with pytest.raises(ValueError):
        discover_cgiar(lambda _: json.dumps(response))


def test_confirmed_empty_result_is_allowed():
    metadata = {"number": 0, "size": 60, "totalElements": 0, "totalPages": 0}
    assert discover_cgiar(lambda _: json.dumps({"_embedded": {"searchResult": {"page": metadata}}})) == []
    assert discover_uk_varss(lambda _: json.dumps({"links": {"documents": []}})) == []


def run_publisher(monkeypatch, source, fetch, listed=None):
    monkeypatch.setattr(crawl, "read_page", lambda opener, url, stats: fetch(url))
    return crawl.scan_source(source, listed or {}, {"pages_requested": 0, "request_attempts": 0})


def test_commission_query_filename_must_be_native_pptx_on_its_download_route(monkeypatch):
    good = "/document/download/123_en?filename=AMR%20Education.pptx"
    html = f"""
        <a href="{good}#a" data-untranslated-label="One Health teaching materials">Download</a>
        <a href="{good}#b">Download</a><a href="/article?filename=something.pptx">News</a>
        <a href="https://external.invalid/document/download/123_en?filename=x.pptx">External</a>
        <a href="/document/download/456_en?filename=report.pdf">Report</a>
    """
    [row] = run_publisher(monkeypatch, "eu-awareness", lambda _: html)
    assert row["title"] == "One Health teaching materials"
    assert row["download_url"] == "https://health.ec.europa.eu" + good
    assert row["source_page"].endswith("resources-antimicrobial-resistance-campaign_en")
    assert row["status"] == "candidate_unreviewed"


def test_rcgp_deduplicates_training_attachments_and_keeps_original_landing_page(monkeypatch):
    file = "https://elearning.rcgp.org.uk/pluginfile.php/123/mod_book/chapter/456/workshop%20slides.pptx"
    pages = []
    def fetch(url):
        pages.append(url)
        return f"""<a href="{file}">TARGET <strong>stewardship</strong> workshop</a>
        <a href="/misc/whitepaper.pptx">Unrelated</a>
        <a href="//outside.test/pluginfile.php/123/mod_book/chapter/456/slide.pptx">External</a>"""
    [row] = run_publisher(monkeypatch, "rcgp-target", fetch, {file: "existing"})
    assert len(set(pages)) == 3 and all(page.startswith("https://elearning.rcgp.org.uk/") for page in pages)
    assert (row["title"], row["source_page"], row["download_url"], row["status"]) == (
        "TARGET stewardship workshop", pages[0], file, "listed")


def test_strama_uses_agency_media_metadata_and_filters_irrelevant_attachments(monkeypatch):
    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    def record(title, filename, host="strama.se"):
        return {"title": {"rendered": title}, "link": "https://strama.se/meetings/record/", "post": 527,
                "mime_type": mime, "source_url": f"https://{host}/wp-content/uploads/2026/{filename}"}
    rows = [record("Antibiotika &amp; stewardship", "briefing.pptx"), record("Conference programme", "schedule.pptx"),
            record("Antibiotika", "briefing.pptx", "cdn.invalid"), record("Antibiotika", "slides.pdf")]
    def fetch(url):
        assert url.startswith("https://strama.se/wp-json/wp/v2/media?")
        return json.dumps(rows)
    [candidate] = run_publisher(monkeypatch, "strama", fetch)
    assert candidate["title"] == "Antibiotika & stewardship"
    assert candidate["source_page"] == "https://strama.se/?p=527"
    assert candidate["status"] == "candidate_unreviewed"


def test_ebug_uses_only_native_teaching_assets_and_stable_public_cdn_paths(monkeypatch):
    url = "https://cdn.e-bug.eu/eu-west-2/documents/teaching.pptx"
    pages = []
    def fetch(page):
        pages.append(page)
        return f"""<a href="{url}?signature=transient"><span>Download PPT</span> Download PPT: KS2 antibiotics</a>
        <a href="{url}?signature=other">Download PPT</a>
        <a href="https://cdn.other.org/eu-west-2/documents/other.pptx">Other</a>
        <a href="https://cdn.e-bug.eu/eu-west-2/documents/teacher.pdf">Guide</a>"""
    [row] = run_publisher(monkeypatch, "ukhsa-ebug", fetch)
    assert len(set(pages)) == 4
    assert row["download_url"] == url
    assert row["source_page"].startswith("https://www.e-bug.eu/")
    assert row["title"] == "KS2 antibiotics"
