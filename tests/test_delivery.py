import hashlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pptx import Presentation

from presentation_search.api import create_app
from presentation_search.config import Settings

TENANT = "9bc84df1-b63e-4765-85b6-e0387823c421"
LOOPBACK = {"base_url": "http://localhost", "client": ("127.0.0.1", 41321)}


def deck(path, body, title="Surveillance"):
    ppt = Presentation()
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = title
    slide.placeholders[1].text = body
    ppt.save(path)


def config(tmp_path, **kwargs):
    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    return Settings(
        _env_file=None,
        local_presentation_path=inputs,
        drafts_path=tmp_path / "jobs",
        **{"auth_mode": "local_demo", **kwargs},
    )


def search(client, **kw):
    return client.post("/api/search", json={"query": "surveillance", **kw}).json()["results"]


def test_newest_report_month_wins_and_unknown_has_no_filesystem_date(tmp_path):
    settings = config(tmp_path)
    root = settings.local_presentation_path
    deck(root / "Status_2025.pptx", "Data through 2025-01-14. surveillance surveillance")
    deck(root / "Status_2026.pptx", "Data through 2025-08-10.")
    deck(root / "Method.pptx", "Field method", title="Surveillance protocol")
    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        results = search(client)
        assert len(results) == 2
        latest = next(r for r in results if r["deckName"].startswith("Status"))
        assert latest["deckName"] == "Status_2026.pptx"
        assert latest["reportDate"] == "2025-08-10"
        assert latest["sourceHash"] == hashlib.sha256((root / latest["deckName"]).read_bytes()).hexdigest()
        assert latest["dateConfidence"] > 0
        assert client.get(latest["url"]).content == (root / latest["deckName"]).read_bytes()
        assert str(tmp_path) not in json.dumps(results)
        method = next(r for r in results if r["deckName"] == "Method.pptx")
        assert method["effectiveYear"] is None
        assert len(search(client, latest_only=False)) == 3
        versions = client.get("/api/slides/" + latest["slideId"] + "/versions").json()["versions"]
        assert [v["reportDate"] for v in versions] == ["2025-08-10", "2025-01-14"]


def test_latest_search_uses_written_reporting_date_before_target_year(tmp_path):
    settings = config(tmp_path)
    root = settings.local_presentation_path
    deck(root / "Status_2025.pptx", "Data as of 30 September 2025. Target 2030.")
    deck(root / "Status_2026.pptx", "Data through September 30, 2026. Target 2030.")

    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        hits = search(client)
        assert len(hits) == 1
        assert hits[0]["deckName"] == "Status_2026.pptx"
        assert hits[0]["reportDate"] == "2026-09-30"
        versions = client.get("/api/slides/" + hits[0]["slideId"] + "/versions").json()["versions"]
        assert [version["reportDate"] for version in versions] == ["2026-09-30", "2025-09-30"]


def test_default_credentials_fail_closed_and_local_requires_loopback(tmp_path):
    with pytest.raises(ValueError, match="COPILOT_API_KEY"):
        with TestClient(
            create_app(settings=config(tmp_path, auth_mode="api_key", copilot_api_key=" ")), **LOOPBACK
        ):
            pass
    app = create_app(settings=config(tmp_path))
    with TestClient(app, base_url="http://localhost", client=("192.0.2.10", 8000)) as client:
        assert client.post("/api/search", json={"query": "x"}).status_code == 403
    with TestClient(app, base_url="http://outside.example", client=("127.0.0.1", 8000)) as client:
        assert client.post("/api/search", json={"query": "x"}).status_code == 403
    with TestClient(app, **LOOPBACK) as client:
        assert client.post("/api/admin/reindex").status_code == 403


def poll(client, url, headers=None):
    for _ in range(300):
        result = client.get(url, headers=headers or {}).json()
        if result["status"] in ("completed", "failed"):
            return result
        time.sleep(0.02)
    pytest.fail("Draft did not finish")


def test_stale_sources_and_reindexed_ids_cannot_build(tmp_path):
    settings = config(tmp_path, admin_api_key="admin")
    path = settings.local_presentation_path / "Status.pptx"
    deck(path, "First.")
    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        slide_id = search(client)[0]["slideId"]
        body = {"title": "Brief", "confirmed": True, "slide_ids": [slide_id]}
        assert client.post("/api/drafts", json={**body, "confirmed": False}).status_code == 422
        assert (
            client.post("/api/drafts", json={**body, "slide_ids": [slide_id, slide_id]}).status_code == 422
        )
        deck(path, "Second.")
        job = client.post("/api/drafts", json=body)
        assert job.status_code == 202
        result = poll(client, job.json()["statusUrl"])
        assert result["status"] == "failed" and "source" in result["error"].lower()
        assert client.get(result["statusUrl"] + "/file").status_code == 409
        assert client.post("/api/admin/reindex", headers={"X-Admin-Key": "admin"}).status_code == 200
        assert search(client)[0]["slideId"] != slide_id
        assert client.post("/api/drafts", json=body).status_code == 409


def test_entra_tokens_job_ownership_order_and_persistence(tmp_path, monkeypatch):
    settings = config(
        tmp_path,
        auth_mode="entra",
        azure_tenant_id=TENANT,
        entra_audience="tool",
        entra_allowed_roles="Presenter",
    )
    for subject in ["Bird", "Cow"]:
        deck(
            settings.local_presentation_path / f"{subject}.pptx",
            subject + " data through 2024",
            title=subject + " surveillance",
        )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jj = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    monkeypatch.setattr(
        jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [{**jj, "kid": "unit", "use": "sig"}]}
    )
    now = int(time.time())

    def bearer(oid, **extra):
        data = {
            "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "aud": "tool",
            "tid": TENANT,
            "iat": now,
            "nbf": now - 5,
            "exp": now + 300,
            "oid": oid,
            "sub": oid,
            "scp": "access_as_user",
            "roles": ["Presenter"],
            **extra,
        }
        token = jwt.encode(data, key, algorithm="RS256", headers={"kid": "unit"})
        return {"Authorization": "Bearer " + token}

    alice, bob = bearer("alice"), bearer("bob")
    with TestClient(create_app(settings=settings)) as client:
        for headers, status in [
            (bearer("alice", exp=now - 100), 401),
            (bearer("alice", aud="other"), 401),
            (bearer("alice", iss="other"), 401),
            (bearer("alice", roles=[]), 403),
            (bearer("alice", scp=""), 403),
            ({"X-User-Id": "alice"}, 401),
        ]:
            assert (
                client.post("/api/search", json={"query": "surveillance"}, headers=headers).status_code
                == status
            )
        hits = client.post("/api/search", json={"query": "surveillance"}, headers=alice).json()["results"]
        expected = list(reversed(hits))
        body = {"title": "Brief", "confirmed": True, "slide_ids": [s["slideId"] for s in expected]}
        job = client.post("/api/drafts", json=body, headers=alice)
        assert job.status_code == 202
        url = job.json()["statusUrl"]
        assert client.get(url, headers={**bob, "X-User-Id": "alice"}).status_code == 404
        status = poll(client, url, alice)
        assert status["status"] == "completed", status
        assert [v["slideId"] for v in status["sourceMap"]] == body["slide_ids"]
        assert [v["outputSlide"] for v in status["sourceMap"]] == [1, 2]
        assert client.get(status["downloadUrl"], headers=bob).status_code == 404
    with TestClient(create_app(settings=settings)) as client:
        file = client.get(url + "/file", headers=alice)
        assert file.status_code == 200 and file.content.startswith(b"PK")
        assert client.get(url, headers=alice).json()["sourceMap"] == status["sourceMap"]


def test_identical_source_bytes_in_distinct_decks_keep_both_selected_pages(tmp_path):
    settings = config(tmp_path)
    root = settings.local_presentation_path
    deck(root / "North.pptx", "Data through 2025.")
    (root / "South.pptx").write_bytes((root / "North.pptx").read_bytes())
    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        hits = search(client)
        assert len(hits) == 2
        response = client.post(
            "/api/drafts",
            json={"title": "Combined", "confirmed": True, "slide_ids": [s["slideId"] for s in hits]},
        )
        job = poll(client, response.json()["statusUrl"])
        assert job["status"] == "completed", job["error"]
        assert [s["deckName"] for s in job["sourceMap"]] == [s["deckName"] for s in hits]


def test_slide_year_outranks_newer_filename_only_date(tmp_path):
    settings = config(tmp_path)
    root = settings.local_presentation_path
    deck(root / "Status_2024.pptx", "Surveillance report for 2024")
    deck(root / "Status_2026.pptx", "An undated copy")
    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        assert search(client)[0]["deckName"] == "Status_2024.pptx"


def test_same_deck_and_title_in_distinct_region_folders_are_not_versions(tmp_path):
    settings = config(tmp_path)
    for region, year in [("North", "2024"), ("South", "2025")]:
        folder = settings.local_presentation_path / region
        folder.mkdir()
        deck(folder / "Report.pptx", f"{region} data through {year}.")
    with TestClient(create_app(settings=settings), **LOOPBACK) as client:
        hits = search(client)
        assert sorted(s["reportDate"] for s in hits) == ["2024", "2025"]
        assert all(s["relatedVersions"] == 1 for s in hits)
