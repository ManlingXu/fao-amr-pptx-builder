from pathlib import Path

from fastapi.testclient import TestClient

from scripts.serve_studio import Budget, StudioHost, create_app


class ExampleService:
    def __init__(self, corpus, folder):
        self.folder = folder

    def new_session(self):
        return {"versions": [], "stats": {"decks": 2, "slides": 5}}

    def snapshot(self, state):
        return state

    def turn(self, state, message, settings, *, action, **kwargs):
        if action == "generate":
            out = self.folder / "v1"
            out.mkdir(exist_ok=True)
            (out / "sources.json").write_text('{"demo": true}')
            state["versions"] = [{"id": "v1", "files": {"sources": "sources.json"}}]
        return state


def make_host(tmp_path, monkeypatch, *, tunnel=True):
    monkeypatch.setenv("PPT_STUDIO_ADMIN_PASSWORD", "example-dev-phrase")
    monkeypatch.setenv("PPT_STUDIO_USER_PASSWORD", "example-user-phrase")
    monkeypatch.delenv("PPT_STUDIO_ENABLE_OPENAI", raising=False)
    return StudioHost(Path("example"), tmp_path / "sessions", tmp_path / "host",
                      tunnel=tunnel, service_factory=ExampleService)


def test_roles_sessions_files_reset_and_monitor(tmp_path, monkeypatch):
    host = make_host(tmp_path, monkeypatch)
    app = create_app(host)
    def client():
        return TestClient(app, base_url="http://127.0.0.1")
    with client() as first, client() as second:
        assert first.get("/api/session").json()["requiresLogin"]
        assert first.get("/api/developer").status_code == 401
        for visitor in [first, second]:
            assert visitor.post("/api/login", json={"password": "example-user-phrase"}).status_code == 200
        assert first.get("/api/developer").status_code == 403
        assert first.get("/studio-config.json").status_code == 403
        assert first.post("/api/chat", json={"settings": {"model": "openai"}}).status_code == 403
        result = first.post("/api/export", json={}).json()
        file_url = result["versions"][0]["files"]["sources"]
        assert first.get(file_url).json() == {"demo": True}
        assert second.get(file_url).status_code == 404
        upgrade = first.post("/api/login", json={"role": "developer", "password": "example-dev-phrase"})
        assert upgrade.json()["sessionId"] == result["sessionId"]
        assert first.get(file_url).json() == {"demo": True}
        assert first.get("/api/developer").status_code == 200
        assert first.post("/api/reset", json={}).json()["sessionId"] != result["sessionId"]
        assert first.get(file_url).status_code == 404
        assert first.post("/api/login", json={"role": "developer", "password": "example-dev-phrase"}).status_code == 200
        monitor = first.get("/api/developer").json()
        assert monitor["runtime"]["decks"] == 2
        assert monitor["usage"]["model_calls"] == 0
        assert monitor["deployment"]["teams"] == "not_connected"
        assert first.post("/api/logout", json={}).status_code == 200
        assert first.get("/api/history").status_code == 401


def test_local_auto_user_and_paid_caps(tmp_path, monkeypatch):
    monkeypatch.delenv("PPT_STUDIO_USER_PASSWORD", raising=False)
    monkeypatch.setenv("PPT_STUDIO_MAX_CALLS", "1")
    host = StudioHost(Path("example"), tmp_path / "visitors", tmp_path / "ledger",
                      service_factory=ExampleService)
    with TestClient(create_app(host), base_url="http://localhost") as local:
        assert local.get("/api/session").json()["role"] == "user"
        assert local.get("/api/developer").status_code == 403
    assert host.budget.reserve("hello", 300)
    reboot = Budget(tmp_path / "ledger" / "budget.sqlite3")
    assert reboot.usage()["model_calls"] == 1
    import pytest
    with pytest.raises(ValueError, match="allowance"):
        reboot.reserve("another request", 300)


def test_limits_template_content_and_remote_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("PPT_STUDIO_RPM", "2")
    host = make_host(tmp_path, monkeypatch)
    host.remote_host = "ppt-builder-test.trycloudflare.com"
    with TestClient(create_app(host), base_url="https://" + host.remote_host) as guest:
        reply = guest.post("/api/login", json={"password": "example-user-phrase"})
        assert "secure" in reply.headers["set-cookie"].lower()
        bad = guest.post("/api/template", content=b"example", headers={"content-type": "application/octet-stream"})
        assert bad.status_code == 400
        assert guest.post("/api/chat", json={"message": "test"}).status_code == 200
        assert guest.post("/api/chat", json={"message": "test"}).status_code == 429
