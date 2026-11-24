"""Offline integrity checks for the published, slide-verified AMR catalogue."""
import csv
import ipaddress
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from scripts.fetch_public_corpus import read_catalog


PUBLIC_CORPUS = Path(__file__).resolve().parents[1] / "examples" / "public_corpus"
AMR_CATALOG = PUBLIC_CORPUS / "amr" / "catalog.csv"


def test_amr_catalog_has_distinct_pinned_decks_and_slide_evidence():
    # Run the actual fetcher's validation as well as checking catalogue-only columns.
    parsed = read_catalog(AMR_CATALOG)
    with AMR_CATALOG.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        expected_fields = {
            "id", "title", "author", "publisher", "sector", "language", "issued", "series",
            "source_page", "download_url", "zip_member", "license", "sha256", "evidence_slide",
            "slide_count", "topic",
        }
        assert expected_fields.issubset(reader.fieldnames or ())
        rows = list(reader)

    assert [r["id"] for r in parsed] == [r["id"] for r in rows]
    assert len({r["id"].casefold() for r in parsed}) == len(parsed) >= 100
    assert len({r["sha256"] for r in parsed}) == len(rows)
    assert len({(r["download_url"], r["zip_member"]) for r in parsed}) == len(rows)
    assert len({r["sector"].casefold() for r in parsed}) >= 2

    for record, row in zip(parsed, rows):
        for field in ("sha256", "publisher", "sector", "language", "topic", "evidence_slide"):
            assert record[field] == row[field].strip() and record[field], (row["id"], field)
        slide_count = int(row["slide_count"])
        assert slide_count >= 2, row["id"]
        assert 1 <= int(record["evidence_slide"]) <= slide_count, row["id"]


def test_amr_catalog_reuses_existing_ids_for_shared_source_decks():
    previous = read_catalog(PUBLIC_CORPUS / "catalog.csv")
    frozen_ids = {r["sha256"]: r["id"] for r in previous}
    current_ids = {r["sha256"]: r["id"] for r in read_catalog(AMR_CATALOG)}
    shared_hashes = frozen_ids.keys() & current_ids.keys()
    assert shared_hashes
    for checksum in shared_hashes:
        assert current_ids[checksum] == frozen_ids[checksum], checksum


def test_amr_catalog_uses_public_source_and_download_addresses():
    # Availability and file hashes are verified at acquisition. These checks catch
    # credentials, short-lived signatures and local addresses without a network call.
    private_query_keys = {
        "access_token", "authkey", "expires", "key-pair-id", "private_link", "sig",
        "signature", "token", "x-amz-credential", "x-amz-signature", "x-goog-signature",
    }
    for row in read_catalog(AMR_CATALOG):
        for field in ("source_page", "download_url"):
            url = urlsplit(row[field])
            host = url.hostname or ""
            assert url.scheme in {"http", "https"} and host and url.username is None, row["id"]
            assert host != "localhost" and not host.endswith((".localhost", ".local", ".internal")), row["id"]
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                assert "." in host, row["id"]
            else:
                assert address.is_global, row["id"]
            query_keys = {k.casefold() for k, _ in parse_qsl(url.query, keep_blank_values=True)}
            assert private_query_keys.isdisjoint(query_keys), (row["id"], field)
