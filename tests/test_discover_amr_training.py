import csv
from email.message import Message
from io import BytesIO

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

    monkeypatch.setattr(discovery, "urlopen", open_page)
    discovery.main(["--catalog", str(catalog)])
    with output.open(newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["status"] == "candidate_unreviewed"
    previous = output.read_bytes()
    with pytest.raises(SystemExit):
        discovery.main(["--catalog", str(catalog)])
    assert output.read_bytes() == previous
    assert urls == [discovery.LIBRARY_URL, discovery.LIBRARY_URL]
