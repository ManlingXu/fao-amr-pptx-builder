"""Ollama HTTP boundary and extractive selection, without CI model downloads."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@pytest.fixture
def ollama():
    state = {
        "show": {"details": {"format": "gguf"}, "model_info": {"general.architecture": "qwen3"},
                 "capabilities": ["completion", "thinking"]},
        "picks": [{"slide_id": "zm10", "evidence_index": 1}],
        "requests": [],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, body))
            if self.path == "/api/show":
                data = state["show"]
            elif self.path == "/api/chat":
                if state.get("redirect"):
                    self.send_response(307)
                    self.send_header("Location", "/other")
                    self.end_headers()
                    return
                data = {"model": body["model"], "done": True,
                        "message": {"content": json.dumps({"selections": state["picks"]})},
                        **state.get("generation_metadata", {})}
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        try:
            yield state, f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(2)


CANDIDATES = [
    {"slide_id": "zm11", "title": "Training", "snippet": "Veterinary training session."},
    {"slide_id": "zm10", "title": "Outreach", "snippet": "Farmers attended community meetings."},
]


def select(ollama, **kwargs):
    from presentation_search.local_model import rerank_candidates
    _, url = ollama
    return rerank_candidates("赞比亚农户宣传", CANDIDATES, model="qwen3:4b", limit=2,
                             endpoint=url, **kwargs)


def test_ranked_evidence_resolves_from_its_page_and_model_is_local(ollama):
    assert select(ollama) == [{"slide_id": "zm10", "evidence": "Farmers attended community meetings."}]
    reqs = ollama[0]["requests"]
    assert [path for path, _ in reqs] == ["/api/show", "/api/chat"]
    assert "Farmers" not in json.dumps(reqs[0][1])
    assert reqs[1][1]["think"] is False


@pytest.mark.parametrize("picks", [
    [{"slide_id": "not-a-candidate", "evidence_index": 0}],
    [{"slide_id": "zm10", "evidence_index": 2}],
    [{"slide_id": "zm10", "evidence_index": True}],
    [{"slide_id": "zm10", "evidence_index": 1}, {"slide_id": "zm10", "evidence_index": 0}],
    [{"slide_id": "zm10", "evidence_index": 0, "evidence": "Invented quotation."}],
])
def test_hallucinated_or_duplicate_choice_fails_the_whole_rerank(ollama, picks):
    from presentation_search.local_model import LocalModelError
    ollama[0]["picks"] = picks
    with pytest.raises(LocalModelError):
        select(ollama)


def test_cloud_alias_never_receives_slide_text(ollama):
    from presentation_search.local_model import LocalModelError
    ollama[0]["show"]["remote_host"] = "https://ollama.com"
    with pytest.raises(LocalModelError, match="local"):
        select(ollama)
    assert [path for path, _ in ollama[0]["requests"]] == ["/api/show"]


def test_generation_which_reports_a_remote_model_cannot_be_labeled_local(ollama):
    from presentation_search.local_model import LocalModelError
    ollama[0]["generation_metadata"] = {"remote_model": "other", "remote_host": "https://ollama.com"}
    with pytest.raises(LocalModelError, match="remote") as error:
        select(ollama)
    assert error.value.chat_requested is True


def test_daemon_redirect_is_not_followed(ollama):
    from presentation_search.local_model import LocalModelError
    ollama[0]["redirect"] = True
    with pytest.raises(LocalModelError):
        select(ollama)
    assert [path for path, _ in ollama[0]["requests"]] == ["/api/show", "/api/chat"]


@pytest.mark.parametrize("endpoint", ["https://ollama.com", "http://192.168.1.42",
                                      "http://localhost:11434@outside.invalid", "http://localhost/api"])
def test_endpoint_accepts_only_local_daemon_roots(endpoint):
    from presentation_search.local_model import LocalModelError, rerank_candidates
    with pytest.raises(LocalModelError, match="loopback"):
        rerank_candidates("AMR", CANDIDATES, model="qwen3:4b", limit=2, endpoint=endpoint)


def test_model_can_abstain(ollama):
    ollama[0]["picks"] = []
    assert select(ollama) == []
