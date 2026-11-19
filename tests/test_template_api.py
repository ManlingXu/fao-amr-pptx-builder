"""Exercise uploaded templates through authenticated draft creation and revision."""
import base64
import io
import json
import time
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches

from presentation_search.api import ApplyTemplateRequest, TemplateUploadRequest, create_app
from presentation_search.auth import Identity
from presentation_search.config import Settings
from presentation_search.templates import MAX_TEMPLATE_BASE64, MAX_TEMPLATE_BYTES, TemplateStore
from scripts.export_connector import specification


def presentation_bytes(*, template=False):
    ppt = Presentation()
    if template:
        ppt.slide_width = Inches(12)
        ppt.slide_height = Inches(6.75)
        ppt.slide_master.background.fill.solid()
        ppt.slide_master.background.fill.fore_color.rgb = RGBColor(220, 238, 250)
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Template example" if template else "Surveillance"
    slide.placeholders[1].text = "Private template example" if template else "Source body unchanged"
    slide.notes_slide.notes_text_frame.text = "Keep these speaker notes verbatim"
    output = io.BytesIO()
    ppt.save(output)
    return output.getvalue()


def repackage(content, transform):
    output = io.BytesIO()
    with ZipFile(io.BytesIO(content)) as source, ZipFile(output, "w", ZIP_DEFLATED) as destination:
        for item in source.infolist():
            destination.writestr(item, transform(item.filename, source.read(item.filename)))
    return output.getvalue()


def template_payload(file_name="Brand.pptx", content=None):
    return {
        "file_name": file_name,
        "content_base64": base64.b64encode(content or presentation_bytes(template=True)).decode(),
    }


@pytest.fixture
def setup_app(tmp_path, monkeypatch):
    # Authentication parsing already has real Entra coverage in test_delivery.
    # Use two explicit principals here to cover object ownership independently.
    def principal(self, request: Request):
        return request.headers.get("X-Test-Owner", "alice")

    monkeypatch.setattr(Identity, "principal", principal)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "Source.pptx").write_bytes(presentation_bytes())
    settings = Settings(
        _env_file=None, auth_mode="local_demo", local_presentation_path=inputs,
        drafts_path=tmp_path / "jobs",
    )
    return settings, create_app(settings=settings)


def wait_for_draft(client, response, owner="alice"):
    assert response.status_code == 202, response.text
    for _ in range(250):
        result = client.get(response.json()["statusUrl"], headers={"X-Test-Owner": owner}).json()
        if result["status"] in {"completed", "failed"}:
            assert result["status"] == "completed", result
            return result
        time.sleep(0.02)
    pytest.fail("Draft job did not finish")


def draft_request(client, **extra):
    slide = client.post("/api/search", json={"query": "Surveillance"}).json()["results"][0]
    return {"title": "Brief", "slide_ids": [slide["slideId"]], "confirmed": True, **extra}


def shape_text(shapes):
    values = []
    for shape in shapes:
        if shape.has_text_frame:
            values.append(shape.text)
        if hasattr(shape, "shapes"):
            values.extend(shape_text(shape.shapes))
    return values


@pytest.mark.parametrize("extension", ["pptx", "potx"])
def test_upload_template_is_private_validated_and_not_indexed(setup_app, extension):
    settings, app = setup_app
    content = presentation_bytes(template=True)
    if extension == "potx":
        content = repackage(content, lambda name, value: value.replace(
            b"presentationml.presentation.main+xml", b"presentationml.template.main+xml"
        ) if name == "[Content_Types].xml" else value)
    with TestClient(app) as client:
        before = client.get("/health").json()["slides"]
        upload = client.post("/api/templates", json=template_payload("Brand." + extension, content))
        assert upload.status_code == 201, upload.text
        metadata = upload.json()
        assert metadata["fileName"] == "Brand." + extension
        assert metadata["slideWidth"] == Inches(12)
        assert metadata["slideHeight"] == Inches(6.75)
        assert metadata["layoutNames"]
        assert "owner" not in metadata and str(settings.drafts_path) not in json.dumps(metadata)
        assert client.get("/api/templates/" + metadata["templateId"]).json() == metadata
        assert client.get("/health").json()["slides"] == before
        hits = client.post("/api/search", json={"query": "Private template example"}).json()["results"]
        assert hits == []
        assert len(list((settings.drafts_path / "templates").glob("*/metadata.json"))) == 1


@pytest.mark.parametrize("file_name,encoded", [
    ("../Brand.pptx", "VALID"), ("folder\\Brand.pptx", "VALID"),
    ("Brand.pptm", "VALID"), ("Brand.ppt", "VALID"), ("Brand.pptx", "not base64!"),
    ("Brand.pptx", base64.b64encode(b"not a PowerPoint package").decode()),
])
def test_bad_uploads_leave_no_usable_template(setup_app, file_name, encoded):
    settings, app = setup_app
    payload = template_payload(file_name)
    if encoded != "VALID":
        payload["content_base64"] = encoded
    with TestClient(app) as client:
        assert client.post("/api/templates", json=payload).status_code == 422
    assert not list((settings.drafts_path / "templates").glob("*/metadata.json"))


def test_macros_and_decoded_size_limit_rejected(setup_app):
    settings, app = setup_app
    content = repackage(presentation_bytes(template=True), lambda name, value: value.replace(
        b"presentationml.presentation.main+xml", b"presentationml.presentation.macroEnabled.main+xml"
    ) if name == "[Content_Types].xml" else value)
    with TestClient(app) as client:
        assert client.post("/api/templates", json=template_payload(content=content)).status_code == 422
    # MAX+1 bytes can still fit the maximum base64 string length: enforce both limits.
    oversized = base64.b64encode(b"x" * (MAX_TEMPLATE_BYTES + 1)).decode()
    assert len(oversized) == MAX_TEMPLATE_BASE64
    store = TemplateStore(settings.drafts_path / "templates")
    with pytest.raises(ValueError, match="16 MiB"):
        store.create("alice", "Brand.pptx", oversized)
    assert not list((settings.drafts_path / "templates").glob("*/metadata.json"))


def test_create_with_template_and_retheme_completed_draft_keep_original(setup_app):
    settings, app = setup_app
    with TestClient(app) as client:
        metadata = client.post("/api/templates", json=template_payload()).json()
        original = wait_for_draft(client, client.post("/api/drafts", json=draft_request(client)))
        original_bytes = client.get(original["downloadUrl"]).content
        selected = wait_for_draft(client, client.post(
            "/api/drafts", json=draft_request(client, template_id=metadata["templateId"]),
        ))
        assert selected["template"] == metadata
        selected_ppt = Presentation(io.BytesIO(client.get(selected["downloadUrl"]).content))
        assert selected_ppt.slide_width == metadata["slideWidth"]
        assert len(selected_ppt.slides) == 1
        title = original["title"]
        revised = wait_for_draft(client, client.post(
            original["statusUrl"] + "/template",
            json={"template_id": metadata["templateId"], "confirmed": True},
        ))
        assert revised["jobId"] != original["jobId"]
        assert revised["title"] == title
        assert revised["sourceJobId"] == original["jobId"]
        assert revised["sourceMap"] == original["sourceMap"]
        assert revised["template"] == metadata
        assert client.get(original["downloadUrl"]).content == original_bytes
        revised_bytes = client.get(revised["downloadUrl"]).content
        assert revised_bytes != original_bytes
        ppt = Presentation(io.BytesIO(revised_bytes))
        assert ppt.slide_width == Inches(12) and ppt.slide_height == Inches(6.75)
        assert len(ppt.slides) == 1  # The template's demonstration page is excluded.
        text = "\n".join(shape_text(ppt.slides[0].shapes))
        assert "Surveillance" in text and "Source body unchanged" in text
        assert "Private template example" not in text
        assert ppt.slides[0].notes_slide.notes_text_frame.text == "Keep these speaker notes verbatim"
    # A restart preserves the uploaded template reference and the independent output.
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/templates/" + metadata["templateId"]).status_code == 200
        assert client.get(revised["downloadUrl"]).content == revised_bytes


def test_templates_and_template_changes_enforce_owner_and_confirmation(setup_app):
    _, app = setup_app
    bob = {"X-Test-Owner": "bob"}
    with TestClient(app) as client:
        template = client.post("/api/templates", json=template_payload()).json()
        template_id = template["templateId"]
        original = wait_for_draft(client, client.post("/api/drafts", json=draft_request(client)))
        request = {"template_id": template_id, "confirmed": True}
        assert client.get("/api/templates/" + template_id, headers=bob).status_code == 404
        assert client.post("/api/drafts", json=draft_request(client, template_id=template_id), headers=bob).status_code == 404
        assert client.post(original["statusUrl"] + "/template", json=request, headers=bob).status_code == 404
        for confirmation in [False, "true", 1]:
            assert client.post(original["statusUrl"] + "/template", json={
                **request, "confirmed": confirmation,
            }).status_code == 422
        assert client.post(original["statusUrl"] + "/template", json={
            **request, "template_id": "0" * 32,
        }).status_code == 404
        # Bob's own job still cannot use Alice's uploaded template.
        own = wait_for_draft(client, client.post("/api/drafts", json=draft_request(client), headers=bob), "bob")
        assert client.post(own["statusUrl"] + "/template", json=request, headers=bob).status_code == 404


def test_corrupted_saved_template_is_not_reused(setup_app):
    settings, app = setup_app
    with TestClient(app) as client:
        template = client.post("/api/templates", json=template_payload()).json()
        saved = settings.drafts_path / "templates" / template["templateId"] / "template.pptx"
        saved.write_bytes(b"changed")
        assert client.get("/api/templates/" + template["templateId"]).status_code == 404
        assert client.post("/api/drafts", json=draft_request(client, template_id=template["templateId"])).status_code == 404


@pytest.mark.parametrize("auth", ["api-key", "entra"])
@pytest.mark.parametrize("path,model", [
    ("/api/templates", TemplateUploadRequest),
    ("/api/drafts/{job_id}/template", ApplyTemplateRequest),
])
def test_template_connector_requests_match_api(auth, path, model):
    spec = specification(
        "https://approved.example.invalid", auth,
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
    )
    imported = next(p["schema"] for p in spec["paths"][path]["post"]["parameters"] if p["in"] == "body")
    actual = model.model_json_schema()
    assert set(imported["required"]) == set(actual["required"])
    assert set(imported["properties"]) == set(actual["properties"])
    for name, field in actual["properties"].items():
        for constraint in ("minLength", "maxLength", "pattern"):
            if constraint in field:
                assert imported["properties"][name][constraint] == field[constraint]
