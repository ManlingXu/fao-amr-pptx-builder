import csv
import hashlib
import json
from io import BytesIO

import pytest

from scripts.fetch_public_corpus import FIELDS, ROOT
from scripts.review_amr_candidates import MAX_SELECTION, review


class Response(BytesIO):
    headers = {}


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def sources(tmp_path):
    data = ROOT / "data" / "presentations"
    pinned = (data / "One_Health_Methodology.pptx").read_bytes()
    other = (data / "RENOFARM_Regional_2026.pptx").read_bytes()
    site = "https://example.org/"
    payloads = {
        site + "first.pptx": pinned,
        site + "unique.pptx": other,
        site + "alias.pptx": pinned,
        site + "broken.pptx": b"not a PowerPoint",
    }
    catalog = tmp_path / "official.csv"
    write_csv(catalog, (*FIELDS, "sha256"), [{
        "id": "existing-slide-deck", "title": "Existing title", "source_page": site,
        "download_url": site + "original-distribution.pptx", "sha256": hashlib.sha256(pinned).hexdigest(),
    }])
    candidates = tmp_path / "candidates.csv"
    write_csv(candidates, ("title", "source_page", "download_url", "status"),
              [{"title": "A title", "source_page": site, "download_url": url, "status": "candidate_unreviewed"}
               for url in payloads])
    return catalog, candidates, payloads


def test_reviews_only_requested_urls_and_compares_against_all_catalog_bytes(tmp_path):
    catalog, candidates, payloads = sources(tmp_path)
    originals = (catalog.read_bytes(), candidates.read_bytes())
    requested = list(payloads)
    calls = []

    def serve(request, *, timeout):
        calls.append(request.full_url)
        return Response(payloads[request.full_url])

    run, report = review(candidates, requested, catalog, tmp_path, opener=serve)
    assert report == json.loads((run / "review.json").read_text())
    assert sorted(calls) == sorted(requested)
    same, different, alias, broken = report["records"]
    assert same["status"] == "duplicate_of_catalog" and same["catalog_id"] == "existing-slide-deck"
    assert different["status"] == "distinct_bytes" and different["catalog_id"] is None
    assert alias["status"] == "duplicate_within_batch" and alias["duplicate_of"] == same["id"]
    assert alias["sha256"] == same["sha256"] and alias["slide_count"] == same["slide_count"] > 0
    assert alias["catalog_id"] == same["catalog_id"]
    assert broken["status"] == "failed" and broken["error"]
    assert originals == (catalog.read_bytes(), candidates.read_bytes())

    # A separate run can observe replacement files and never overwrites the prior review.
    calls.clear()
    second_run, second_report = review(candidates, requested[:1], catalog, tmp_path, opener=serve)
    assert second_run != run and calls == requested[:1]
    assert second_report["records"][0] == same
    assert report == json.loads((run / "review.json").read_text())


@pytest.mark.parametrize("selection", [[], ["unknown"], ["same", "same"], list(map(str, range(MAX_SELECTION + 1)))])
def test_rejects_invalid_selection_before_fetch_or_output(tmp_path, selection):
    catalog, candidates, _ = sources(tmp_path)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="absent|different download URLs"):
        review(candidates, selection, catalog, output,
               opener=lambda *args, **kwargs: pytest.fail("Invalid review attempted a download"))
    assert not output.exists()
