import io
import re

from fastapi.testclient import TestClient
from pptx import Presentation


def test_demo_shows_sources_and_restyles_the_displayed_draft(tmp_path):
    from scripts.serve_amr_brief import create_demo_app

    built = []
    styled = []
    draft = io.BytesIO()
    Presentation().save(draft)
    blob = draft.getvalue()

    def build(corpus, output, *, topic, pages, sectors, model, template, reflow):
        assert not reflow
        built.append((topic, pages, sectors, model, template.read_bytes()))
        run = output / "unique-run"
        run.mkdir(parents=True)
        (run / "draft.pptx").write_bytes(blob)
        (run / "styled.pptx").write_bytes(blob)
        (run / "source_map.json").write_text("[]")
        return {"status": "partial", "output_directory": str(run), "requested_pages": 3,
                "selected_pages": 1, "selected": [{"slide_number": 8, "deck_title": "Zambia",
                "title": "Outreach", "source_url": "https://example.org/original",
                "evidence": "Farmer engagement"}]}

    def restyle(original, template, result):
        styled.append((original, template.read_bytes()))
        result.write_bytes(blob)

    app = create_demo_app(tmp_path / "corpus", tmp_path / "out", build=build, restyle=restyle)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        page = client.get("/")
        token = re.search(r'<meta name="demo-token" content="([^"]+)"', page.text)[1]
        headers = {"X-Demo-Token": token}
        upload = {"template": ("../private.pptx", blob)}
        response = client.post("/briefs", headers=headers, files=upload, data={
            "topic": "赞比亚养殖户培训", "pages": 3, "sectors": "animal", "model": "qwen3:4b"})
        assert response.status_code == 200, response.text
        record = response.json()
        assert record["status"] == "partial"
        assert record["selected"][0]["source_url"] == "https://example.org/original"
        assert built == [("赞比亚养殖户培训", 3, ["animal"], "qwen3:4b", blob)]
        assert client.get(record["downloads"]["draft"]).content == blob
        assert client.get(record["downloads"]["sources"]).json() == []
        revised = client.post(record["template_url"], headers=headers, files=upload)
        assert revised.status_code == 200, revised.text
        assert client.get(revised.json()["download"]).content == blob
        assert len(built) == 1
        assert styled == [(tmp_path / "out" / "unique-run" / "draft.pptx", blob)]
        assert not (tmp_path / "private.pptx").exists()


def test_browser_must_use_local_host_and_same_origin_for_writes(tmp_path):
    from scripts.serve_amr_brief import create_demo_app

    app = create_demo_app(tmp_path, tmp_path / "out")
    with TestClient(app, base_url="http://localhost:8765") as client:
        assert client.get("/", headers={"Host":"untrusted.example"}).status_code == 400
        assert client.post("/briefs", data={"topic":"hello", "pages":1}).status_code == 403
        token = re.search(r'<meta name="demo-token" content="([^"]+)"', client.get("/").text)[1]
        assert client.post("/briefs", headers={"X-Demo-Token": token,
            "Origin": "https://untrusted.example"}, data={"topic":"hello", "pages":1}).status_code == 403
        assert client.get("/briefs/old-run/files/draft").status_code == 404
        assert client.post("/briefs", headers={"X-Demo-Token":token}, data={"topic":"x", "pages":1},
            files={"template":("wrong.txt", b"not PPTX")}).status_code == 400


def test_evidence_reflow_requires_an_explicit_choice(tmp_path):
    from scripts.serve_amr_brief import create_demo_app

    options = []

    def build(corpus, output, **settings):
        options.append(settings.get("reflow", False))
        run = output / f"brief-{len(options)}"
        run.mkdir(parents=True)
        return {"status": "no_evidence", "output_directory": str(run), "requested_pages": 1,
                "selected_pages": 0, "selected": []}

    app = create_demo_app(tmp_path / "corpus", tmp_path / "out", build=build)
    with TestClient(app, base_url="http://localhost:8765") as client:
        page = client.get("/").text
        checkbox = re.search(r'<input[^>]+name="reflow"[^>]*>', page)
        assert checkbox and "checked" not in checkbox[0]
        token = re.search(r'<meta name="demo-token" content="([^"]+)"', page)[1]
        for choice in ({}, {"reflow": "on"}):
            assert client.post("/briefs", headers={"X-Demo-Token": token},
                               data={"topic": "农户培训", "pages": 1, **choice}).status_code == 200
    assert options == [False, True]
