import csv
import hashlib
import io
import json
from pathlib import Path

from scripts.prepare_amr_corpus import describe_corpus, prepare_corpus

FIXTURES = Path(__file__).parents[1] / "data" / "presentations"


class Response(io.BytesIO):
    headers = {}


def test_default_expands_old_subset_and_reopens_offline(tmp_path):
    first = (FIXTURES / "One_Health_Methodology.pptx").read_bytes()
    second = (FIXTURES / "AMR_Global_Update_2026.pptx").read_bytes()
    third = (FIXTURES / "RENOFARM_Regional_2026.pptx").read_bytes()
    catalog = tmp_path / "catalog.csv"
    source = tmp_path / "old"
    dest = tmp_path / "full"
    (source / "presentations").mkdir(parents=True)
    (source / "presentations" / "one.pptx").write_bytes(first)
    (source / "presentations" / "two.pptx").write_bytes(b"unverified")
    (source / "private-notes.txt").write_text("keep", encoding="utf-8")
    rows = []
    for name, data in (("one", first), ("two", second), ("three", third)):
        rows.append(dict(id=name, title=name, source_page="https://example.org/" + name,
                         download_url="https://example.org/" + name + ".pptx",
                         sha256=hashlib.sha256(data).hexdigest()))
    with catalog.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    requests = []
    def online(request, *, timeout):
        url = request.full_url
        requests.append(url)
        if url.endswith("/two.pptx"):
            return Response(second)
        raise OSError("publisher unavailable")
    result = prepare_corpus(catalog, dest, reuse_dirs=(source,), opener=online)
    assert result["requested"] == 3 and result["verified"] == 2
    assert sorted(requests) == [rows[2]["download_url"], rows[1]["download_url"]]
    assert (source / "presentations" / "two.pptx").read_bytes() == b"unverified"
    assert (source / "private-notes.txt").read_text() == "keep"
    assert (dest / "presentations" / "two.pptx").read_bytes() == second
    assert describe_corpus(dest, catalog)["full_catalog_attempted"]
    assert not describe_corpus(source, catalog)["full_catalog_attempted"]
    requests.clear()
    again = prepare_corpus(catalog, dest, opener=online)
    assert requests == [] and again["verified"] == 2
    result = prepare_corpus(catalog, dest, refresh=True, opener=lambda request, timeout: Response(third))
    assert result["verified"] == 3 and not result["failed"]
    (dest / "presentations" / "one.pptx").unlink()
    scope = describe_corpus(dest, catalog)
    assert scope["verified_decks"] == 2 and not scope["full_catalog_attempted"]
    result = prepare_corpus(catalog, dest, opener=online)
    assert result["verified"] == 3 and not requests


def test_subset_manifest_must_not_be_called_full(tmp_path):
    official = Path(__file__).parents[1] / "examples/public_corpus/amr/catalog.csv"
    first = next(csv.DictReader(official.open(encoding="utf-8-sig")))
    catalog_size = sum(1 for _ in csv.DictReader(official.open(encoding="utf-8-sig")))
    (tmp_path / "presentations").mkdir()
    (tmp_path / "presentations" / (first["id"] + ".pptx")).write_bytes(b"placeholder")
    with (tmp_path / "verified.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=first)
        writer.writeheader()
        writer.writerow(first)
    (tmp_path / "report.json").write_text(json.dumps({"requested": 1, "verified": 1, "failed": [], "duplicates": []}))
    scope = describe_corpus(tmp_path)
    assert scope["catalog_decks"] == catalog_size
    assert scope["reviewed_decks"] == scope["verified_decks"] == 1
    assert not scope["full_catalog_attempted"]


def test_short_network_transfer_is_retried_once(tmp_path, monkeypatch):
    from scripts.fetch_public_corpus import _fetch_bytes
    from urllib.request import Request
    calls = []
    def opener(request, *, timeout):
        calls.append(request.full_url)
        response = Response(b"short" if len(calls) == 1 else b"complete")
        response.headers = {"Content-Length": "8"}
        return response
    monkeypatch.setattr("scripts.fetch_public_corpus.time.sleep", lambda seconds: None)
    path = tmp_path / "received"
    _fetch_bytes(path, Request("https://example.org/deck"), opener)
    assert path.read_bytes() == b"complete" and len(calls) == 2
