from pathlib import Path

import httpx
import pytest
from pptx import Presentation

from presentation_search.config import Settings
from presentation_search.indexer import rebuild_index
from presentation_search.providers import base, sharepoint
from presentation_search.providers.sharepoint import SharePointKnowledgeProvider
from presentation_search.search import SearchIndex


def test_sharepoint_provider_requires_credentials_and_folder_identifiers(tmp_path: Path):
    settings = Settings(
        knowledge_provider="sharepoint",
        sharepoint_cache_path=tmp_path,
        azure_tenant_id="",
        azure_client_id="",
        azure_client_secret="",
        sharepoint_drive_id="",
        sharepoint_folder_item_id="",
    )

    with pytest.raises(ValueError, match="Missing SharePoint configuration"):
        SharePointKnowledgeProvider(settings)


def test_graph_pages_and_membership_refresh_and_existing_permission_upload(tmp_path, monkeypatch):
    file = tmp_path / "sample.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = "Existing sources"
    prs.save(file)
    blob = file.read_bytes()
    state = {"present": True, "uploaded": b"", "name": "Report June.pptx"}

    def graph(request):
        path = request.url.path
        if request.url.host == "download.example":
            assert "Authorization" not in request.headers
            return httpx.Response(200, content=blob)
        assert request.headers["Authorization"] == "Bearer testtoken"
        if path.endswith("/approved/children"):
            return httpx.Response(
                200, json={"value": [], "@odata.nextLink": "https://graph.microsoft.com/v1.0/test-page"}
            )
        if path.endswith("/test-page"):
            return httpx.Response(200, json={"value": [{"id": "f1", "name": "Reports", "folder": {}}]})
        if path.endswith("/f1/children"):
            item = {
                "id": "i1",
                "name": state["name"],
                "webUrl": "https://tenant.sharepoint.com/report",
                "file": {},
            }
            return httpx.Response(200, json={"value": [item] if state["present"] else []})
        if path.endswith("/i1/content"):
            return httpx.Response(302, headers={"location": "https://download.example/document"})
        if path == "/v1.0/drives/dst/items/out:/job.pptx:/content" and request.method == "PUT":
            state["uploaded"] = request.read()
            return httpx.Response(201, json={"webUrl": "https://tenant.sharepoint.com/output"})
        return httpx.Response(404)

    settings = Settings(
        azure_tenant_id="tenant",
        azure_client_id="client",
        azure_client_secret="secret",
        sharepoint_drive_id="src",
        sharepoint_folder_item_id="approved",
        sharepoint_output_drive_id="dst",
        sharepoint_output_folder_item_id="out",
        sharepoint_cache_path=tmp_path / "cache",
    )
    provider = SharePointKnowledgeProvider(settings)
    monkeypatch.setattr(provider, "_token", lambda: "testtoken")
    monkeypatch.setattr(provider, "_client", lambda: httpx.Client(transport=httpx.MockTransport(graph)))
    index = SearchIndex()
    assert rebuild_index(provider, index)["slides_indexed"] == 1
    slide = index.slides[0]
    assert slide.deck_name == "Report June.pptx"
    assert provider.publish(file, "job.pptx") == "https://tenant.sharepoint.com/output"
    assert state["uploaded"] == blob
    state["name"] = "Renamed source.pptx"
    with pytest.raises(ValueError, match="source"):
        provider.snapshot([slide], tmp_path / "snap")
    assert rebuild_index(provider, index)["slides_indexed"] == 1
    assert index.slides[0].id != slide.id
    state["present"] = False
    with pytest.raises(ValueError, match="source"):
        provider.snapshot([slide], tmp_path / "snap")


@pytest.fixture
def source_blob(tmp_path):
    path = tmp_path / "source.pptx"
    presentation = Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[5]).shapes.title.text = "Surveillance"
    presentation.save(path)
    return path.read_bytes()


def mock_sharepoint(tmp_path, monkeypatch, graph):
    settings = Settings(
        _env_file=None,
        azure_tenant_id="tenant",
        azure_client_id="client",
        azure_client_secret="secret",
        sharepoint_drive_id="src",
        sharepoint_folder_item_id="approved",
        sharepoint_output_drive_id="dst",
        sharepoint_output_folder_item_id="out",
        sharepoint_cache_path=tmp_path / "cache",
    )
    provider = SharePointKnowledgeProvider(settings)
    monkeypatch.setattr(provider, "_token", lambda: "testtoken")
    monkeypatch.setattr(provider, "_client", lambda: httpx.Client(transport=httpx.MockTransport(graph)))
    return provider


def source_item(key, size):
    return {
        "id": key,
        "name": key + ".pptx",
        "webUrl": "https://tenant.sharepoint.com/" + key,
        "file": {},
        "size": size,
    }


class OversizedStream(httpx.SyncByteStream):
    def __init__(self, limit):
        self.limit = limit

    def __iter__(self):
        yield b"x" * self.limit
        yield b"x"


@pytest.mark.parametrize("oversize_at", ["metadata", "stream"])
def test_reindex_skips_and_reports_oversized_sharepoint_source(
    tmp_path, monkeypatch, source_blob, oversize_at
):
    limit = len(source_blob) * 2
    monkeypatch.setattr(base, "MAX_FILE_BYTES", limit)
    monkeypatch.setattr(sharepoint, "MAX_FILE_BYTES", limit)
    items = [
        source_item("before", len(source_blob)),
        source_item("oversized", limit + 1 if oversize_at == "metadata" else 1),
        source_item("after", len(source_blob)),
    ]

    def graph(request):
        if request.url.path.endswith("/approved/children"):
            return httpx.Response(200, json={"value": items})
        if request.url.path.endswith("/oversized/content"):
            assert oversize_at == "stream", "Metadata rejection must avoid downloading the source"
            return httpx.Response(200, stream=OversizedStream(limit))
        if request.url.path.endswith(("/before/content", "/after/content")):
            return httpx.Response(200, content=source_blob)
        return httpx.Response(404)

    provider = mock_sharepoint(tmp_path, monkeypatch, graph)
    index = SearchIndex()
    result = rebuild_index(provider, index)

    assert result["files_seen"] == 3
    assert result["slides_indexed"] == 2
    assert [slide.deck_name for slide in index.slides] == ["before.pptx", "after.pptx"]
    assert len(result["failures"]) == 1
    assert result["failures"][0]["file"] == "oversized.pptx"
    assert "limit" in result["failures"][0]["error"]
    assert list(provider.cache_dir.iterdir()) == []


@pytest.mark.parametrize("oversize_at", ["metadata", "stream"])
def test_selected_sharepoint_source_fails_closed_when_it_becomes_oversized(
    tmp_path, monkeypatch, source_blob, oversize_at
):
    limit = len(source_blob) * 2
    monkeypatch.setattr(base, "MAX_FILE_BYTES", limit)
    monkeypatch.setattr(sharepoint, "MAX_FILE_BYTES", limit)
    state = {"oversized": False}

    def graph(request):
        if request.url.path.endswith("/approved/children"):
            size = limit + 1 if state["oversized"] and oversize_at == "metadata" else len(source_blob)
            return httpx.Response(200, json={"value": [source_item("selected", size)]})
        if request.url.path.endswith("/selected/content"):
            if state["oversized"]:
                assert oversize_at == "stream", "Metadata rejection must avoid downloading the source"
                return httpx.Response(200, stream=OversizedStream(limit))
            return httpx.Response(200, content=source_blob)
        return httpx.Response(404)

    provider = mock_sharepoint(tmp_path, monkeypatch, graph)
    index = SearchIndex()
    rebuild_index(provider, index)
    state["oversized"] = True

    with pytest.raises(ValueError, match="64 MiB limit"):
        provider.snapshot(index.slides, tmp_path / "snapshot")
    assert list((tmp_path / "snapshot").iterdir()) == []
    assert list(provider.cache_dir.iterdir()) == []


@pytest.mark.parametrize("failure", ["authentication", "authorization", "service", "traversal", "redirect"])
def test_failed_sharepoint_scan_preserves_previous_index(tmp_path, monkeypatch, source_blob, failure):
    state = {"fail": False}

    def graph(request):
        path = request.url.path
        if path.endswith("/approved/children"):
            if state["fail"] and failure == "authorization":
                return httpx.Response(403)
            item = source_item("replacement" if state["fail"] else "original", len(source_blob))
            result = {"value": [item]}
            if state["fail"] and failure == "traversal":
                result["@odata.nextLink"] = str(request.url)
            return httpx.Response(200, json=result)
        if path.endswith("/replacement/content") and failure == "service":
            return httpx.Response(503, headers={"Retry-After": "0"})
        if path.endswith("/replacement/content") and failure == "redirect":
            return httpx.Response(302, headers={"location": "http://untrusted.example/document"})
        if path.endswith(("/original/content", "/replacement/content")):
            return httpx.Response(200, content=source_blob)
        return httpx.Response(404)

    provider = mock_sharepoint(tmp_path, monkeypatch, graph)
    index = SearchIndex()
    rebuild_index(provider, index)
    original = list(index.slides)
    state["fail"] = True
    if failure == "authentication":
        def denied_token():
            raise RuntimeError("Microsoft Graph authentication failed")

        monkeypatch.setattr(provider, "_token", denied_token)

    with pytest.raises((RuntimeError, ValueError), match="Microsoft Graph|traversal"):
        rebuild_index(provider, index)
    assert index.slides == original
    assert index.search("Surveillance")[0].slide.deck_name == "original.pptx"
