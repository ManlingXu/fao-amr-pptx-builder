import csv
import json
from email.message import Message
from io import BytesIO
from types import SimpleNamespace

import pytest

from scripts import discover_amr_training as discovery


# The live page uses Elementor country accordions, a training-material table
# and a separate set of links outside the accordions.
def session(name, links):
    return f"""
    <div class="elementor-accordion-item">
      <div class="elementor-tab-title" role="button">
        <a class="elementor-accordion-title"><span>•</span> {name}</a>
      </div>
      <div class="elementor-tab-content elementor-clearfix" role="region">
        <table class="training-material"><tbody><tr><td>{links}</td></tr></tbody></table>
      </div>
    </div>"""


def test_discovers_distinct_links_preserving_session_and_review_status(tmp_path):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "id,download_url\nknown,https://amrfvtraining.eu/wp-content/Deck%20A.pptx#start\n",
        encoding="utf-8",
    )
    html = session("Austria", """
      <a href="../wp-content/Deck%20A.pptx?download=1&amp;v=2">L1 – <strong>AMR</strong> in practice</a>
      <a href="/wp-content/Deck A.pptx">L1 – same file</a>
      <a href="/download?file=%2Fwp-content%2Ftraining.PPTX">A second course</a>
      <a href="/article?text=training.pptx">Not a file</a>
      <a href="https://other.org/foreign.pptx">External</a>
      <a href="/download?file=https%3A%2F%2Fother.org%2Fforeign.pptx">External wrapper</a>
      <a href="https%3A%2F%2Fother.org%2Fforeign.pptx">Encoded external URL</a>
      <a href="http://amrfvtraining.eu@other.org/a.pptx">Wrong host</a>
      <a href="/old.ppt">Legacy format</a><a href="/notes.pdf">Notes</a>
    """) + session("Bulgaria 2024", '<a href="/wp-content/Deck%20A.pptx#slide2">Same file</a>')
    html += '<a href="/wp-content/standalone.pptx">Additional project</a>'
    original = catalog.read_bytes()
    rows = discovery.discovery_rows(html, catalog)
    assert len(rows) == 3
    assert rows[0] == {
        "status": "listed",
        "catalog_id": "known",
        "title": "L1 – AMR in practice",
        "country": "Austria | Bulgaria",
        "section": "Austria | Bulgaria 2024",
        "source_page": discovery.LIBRARY_URL,
        "download_url": "https://www.amrfvtraining.eu/wp-content/Deck%20A.pptx?download=1&v=2",
    }
    assert rows[1]["status"] == "candidate_unreviewed"
    assert rows[1]["download_url"] == "https://www.amrfvtraining.eu/wp-content/training.PPTX"
    assert rows[2]["section"] == rows[2]["country"] == rows[2]["catalog_id"] == ""
    assert catalog.read_bytes() == original


def test_command_only_fetches_source_page_and_preserves_last_output_on_failure(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("id,download_url\n", encoding="utf-8")
    output = tmp_path / ".local" / "amr-training-candidates.csv"
    monkeypatch.setattr(discovery, "OUTPUT", output)
    responses = [b'<a href="https%3A%2F%2Famrfvtraining.eu%2Fdeck.pptx">Deck</a>', b"<html></html>"]
    urls = []

    def open_page(request, timeout):
        urls.append(request.full_url)
        response = BytesIO(responses.pop(0))
        response.headers = Message()
        return response

    monkeypatch.setattr(discovery, "build_opener", lambda handler: SimpleNamespace(open=open_page))
    discovery.main(["--catalog", str(catalog)])
    with output.open(newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["status"] == "candidate_unreviewed"
    previous = output.read_bytes()
    with pytest.raises(SystemExit):
        discovery.main(["--catalog", str(catalog)])
    assert output.read_bytes() == previous
    assert urls == [discovery.LIBRARY_URL, discovery.LIBRARY_URL]


def test_partial_scan_preserves_snapshots_and_resumes_only_failed_sources(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("id,download_url\n", encoding="utf-8")
    runs = tmp_path / "scans"
    calls = []

    def scan_source(source, listed, stats):
        calls.append(source)
        stats["pages_requested"] += 1
        if source == "uk-varss" and calls.count(source) == 1:
            raise TimeoutError("publisher timed out")
        if source == "cgiar":
            return []
        return [{"status": "candidate_unreviewed", "catalog_id": "", "country": "", "section": "",
                 "title": source, "source_page": f"https://example.org/{source}",
                 "download_url": f"https://example.org/files/{source}.pptx"}]

    monkeypatch.setattr(discovery, "scan_source", scan_source)
    options = ["--catalog", str(catalog), "--output-dir", str(runs)]
    with pytest.raises(SystemExit):
        discovery.main([*options, "--source", "eu-training", "--source", "uk-varss", "--source", "cgiar"])
    [incomplete] = runs.iterdir()
    report = json.loads((incomplete / "report.json").read_text())
    assert not report["complete"] and not (incomplete / "candidates.csv").exists()
    assert [report["sources"][s]["status"] for s in report["requested_sources"]] == ["ok", "failed", "empty"]
    assert "timed out" in report["sources"]["uk-varss"]["error"]
    assert (incomplete / "cgiar.csv").read_text().count("\n") == 1

    discovery.main([*options, "--resume", str(incomplete)])
    [finished] = set(runs.iterdir()) - {incomplete}
    assert calls == ["eu-training", "uk-varss", "cgiar", "uk-varss"]
    report = json.loads((finished / "report.json").read_text())
    assert report["complete"] and report["sources"]["eu-training"]["pages_requested"] == 0
    with (finished / "candidates.csv").open(newline="") as stream:
        assert [row["source"] for row in csv.DictReader(stream)] == ["eu-training", "uk-varss"]
    (finished / "uk-varss.csv").write_text("damaged snapshot")
    discovery.main([*options, "--resume", str(finished)])
    assert calls.count("uk-varss") == 3
    assert calls.count("eu-training") == calls.count("cgiar") == 1
    catalog.write_text("id,download_url\nnew,https://example.org/x.pptx\n", encoding="utf-8")
    with pytest.raises(ValueError, match="catalog changed"):
        discovery.scan(catalog, None, runs, incomplete)


def test_source_matching_uses_file_identity_and_keeps_distinct_api_queries(tmp_path):
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("id,download_url,zip_member\n"
                       "first,https://example.org/dl?id=1,\n"
                       "archived,https://example.org/collection.zip,file.pptx\n", encoding="utf-8")
    candidates = [{"title": "same", "download_url": url} for url in [
        "https://example.org/dl?id=1#s1", "https://example.org/dl?id=1#s2", "https://example.org/dl?id=2",
    ]]
    listed, _ = discovery.load_catalog(catalog)
    result = discovery.label_rows(candidates, listed)
    assert [(r["status"], r["catalog_id"]) for r in result] == [("listed", "first"), ("candidate_unreviewed", "")]
    assert "https://example.org/collection.zip" not in listed


def test_commission_document_reuses_catalog_entry_for_two_encodings_of_a_space():
    base = "https://health.ec.europa.eu/document/download/123_en?filename="
    key = discovery.file_identity(base + "AMR+Teaching.pptx")
    assert discovery.file_identity(base + "AMR%20Teaching.pptx") == key
    assert discovery.file_identity(base + "AMR%2BTeaching.pptx") != key


def test_publisher_redirects_cannot_cross_source_boundaries():
    handler = discovery.PublisherRedirects({"cgspace.cgiar.org"})
    for url in ("https://external.example/", "https://cgspace.cgiar.org@example.org/",
                "http://cgspace.cgiar.org/items", "https://cgspace.cgiar.org:444/items"):
        with pytest.raises(ValueError, match="Redirect"):
            handler.redirect_request(None, None, 302, "", None, url)


def test_page_fetch_retries_temporary_errors_and_respects_publisher_backoff(monkeypatch):
    waits = []
    monkeypatch.setattr(discovery.time, "sleep", waits.append)
    headers = Message()
    headers["Retry-After"] = "2"
    response = BytesIO(b"success")
    response.headers = Message()
    results = [discovery.HTTPError("https://example.org", 503, "busy", headers, None), response]

    def next_page(request, timeout):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    opener = SimpleNamespace(open=next_page)
    stats = {"request_attempts": 0}
    assert discovery.read_page(opener, "https://example.org", stats) == "success"
    assert stats["request_attempts"] == 2 and waits == [2]
    headers.replace_header("Retry-After", "120")
    results.append(discovery.HTTPError("https://example.org", 429, "wait", headers, None))
    with pytest.raises(discovery.HTTPError):
        discovery.read_page(opener, "https://example.org", stats)
    assert stats["request_attempts"] == 3 and waits == [2]
