import csv
import hashlib
import json
from io import BytesIO
from pathlib import Path

from urllib.error import HTTPError
from urllib.parse import urlsplit
import pytest

from scripts.fetch_public_corpus import FIELDS, fetch_catalog, publisher_lock

FIXTURES = Path(__file__).parents[1] / "data" / "presentations"


class Response(BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}


def write_catalog(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(*FIELDS, "author", "license", "issued", "sha256"))
        writer.writeheader()
        for identifier, url, checksum in rows:
            writer.writerow({
                "id": identifier, "title": identifier, "source_page": "https://example.org/teaching",
                "download_url": "https://example.org/" + url, "sha256": checksum,
                "author": "Example author", "license": "CC BY 4.0", "issued": "2025",
            })


def test_verified_selection_deduplicates_and_resumes_offline(tmp_path):
    data = (FIXTURES / "One_Health_Methodology.pptx").read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    catalog = tmp_path / "catalog.csv"
    corpus = tmp_path / "corpus"
    write_catalog(catalog, [("first", "deck", checksum), ("second", "alias", ""), ("bad", "html", "")])
    urls = []

    def serve(request, *, timeout):
        path = urlsplit(request.full_url).path
        urls.append(path)
        return Response(b"<html>" if path == "/html" else data)

    result = fetch_catalog(catalog, corpus, opener=serve)
    assert result["verified"] == result["slides"] == 1
    assert result["duplicates"] == [{"id": "second", "duplicate_of": "first"}]
    assert [item["id"] for item in result["failed"]] == ["bad"]
    assert json.loads((corpus / "report.json").read_text()) == result
    with (corpus / "verified.csv").open() as stream:
        verified = list(csv.DictReader(stream))
    assert len(verified) == 1
    assert verified[0]["sha256"] == checksum
    assert [verified[0][key] for key in ("author", "license", "issued")] == ["Example author", "CC BY 4.0", "2025"]
    assert (corpus / "presentations" / "first.pptx").read_bytes() == data
    assert not (corpus / "presentations" / "second.pptx").exists()

    urls.clear()
    write_catalog(catalog, [("moved", "deck", checksum), ("second", "alias", "")])
    result = fetch_catalog(catalog, corpus, limit=1, opener=serve)
    assert result["requested"] == result["verified"] == 1
    assert urls == []
    with (corpus / "verified.csv").open() as stream:
        assert [row["id"] for row in csv.DictReader(stream)] == ["moved"]


def test_changed_url_bad_checksum_and_transport_errors(tmp_path):
    old = (FIXTURES / "One_Health_Methodology.pptx").read_bytes()
    new = (FIXTURES / "AMR_Global_Update_2026.pptx").read_bytes()
    catalog = tmp_path / "catalog.csv"
    corpus = tmp_path / "corpus"
    write_catalog(catalog, [("example", "old", "")])

    def serve(request, *, timeout):
        path = urlsplit(request.full_url).path
        if path == "/gone":
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        if path == "/large":
            return Response(b"", {"Content-Length": str(65 * 1024 ** 2)})
        return Response(old if path == "/old" else new)

    fetch_catalog(catalog, corpus, opener=serve)
    write_catalog(catalog, [
        ("example", "replacement", ""), ("mismatch", "new", "0" * 64),
        ("removed", "gone", ""), ("oversized", "large", ""),
    ])
    result = fetch_catalog(catalog, corpus, opener=serve)
    assert result["verified"] == 1 and result["slides"] == 2
    assert (corpus / "presentations" / "example.pptx").read_bytes() == new
    assert [item["id"] for item in result["failed"]] == ["mismatch", "removed", "oversized"]


@pytest.mark.parametrize("ids", [["../bad"], ["/tmp/example"], ["CON"], ["ok", "OK"]])
def test_invalid_identifiers_do_not_write_output(tmp_path, ids):
    catalog = tmp_path / "catalog.csv"
    write_catalog(catalog, [(identifier, "url", "") for identifier in ids])
    corpus = tmp_path / "corpus"
    with pytest.raises(ValueError, match="invalid or repeated"):
        fetch_catalog(catalog, corpus)
    assert not corpus.exists()


def test_busy_corpus_cannot_publish_and_lock_releases(tmp_path):
    with publisher_lock(tmp_path):
        with pytest.raises(ValueError, match="download lock"):
            with publisher_lock(tmp_path):
                pytest.fail("Second publisher acquired the active lock")
    with publisher_lock(tmp_path):
        pass
