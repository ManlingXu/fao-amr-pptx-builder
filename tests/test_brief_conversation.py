import json
from pathlib import Path

import pytest

from test_local_brief_workflow import corpus_fixture
from presentation_search.brief_conversation import Conversation, answer


def say(state, message, corpus, out):
    return answer(state, message, corpus, out)


def test_conversation_collects_requirements_and_exports_the_confirmed_revision(tmp_path):
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    s, first = say(Conversation(), "我要做一个PPT", corpus, out)
    assert s.phase == "clarify" and "主题" in first and not out.exists()
    s, reply = say(s, "两页，讲赞比亚兽医抗菌药物管理，重点是农户培训和宣传。", corpus, out)
    assert s.pages == 2 and s.phase == "preview" and len(s.selected) == 2
    assert "2 份" in reply and "1 份" in reply and not out.exists()
    original = [x["slide_id"] for x in s.selected]
    s, why = say(s, "为什么选第2页？", corpus, out)
    assert s.selected[1]["evidence"] in why and "原第" in why and not out.exists()
    s, _ = say(s, "把第2页移到第1页", corpus, out)
    assert [r["slide_id"] for r in s.selected] == original[::-1]
    s, _ = say(s, "确认生成", corpus, out)
    run = Path(s.report["output_directory"])
    assert s.phase == "exported" and (run / "draft.pptx").is_file()
    assert [r["slideId"] for r in json.loads((run / "source_map.json").read_text())] == original[::-1]
    s2, _ = say(s, "确认生成", corpus, out)
    assert s2.report == s.report and len(list(out.iterdir())) == 1
    s3, _ = say(s2, "删除第2页", corpus, out)
    assert s3.phase == "preview" and s3.report is None and len(s3.selected) == 1


def test_requests_wait_for_topic_and_pages_and_report_gaps(tmp_path):
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    s, _ = say(Conversation(), "10页", corpus, out)
    assert s.phase == "clarify" and s.pages == 10 and not s.topic
    s, reply = say(s, "做一份关于 medieval harpsichord tuning 的PPT", corpus, out)
    assert s.phase == "preview" and s.pages == 10 and s.selected == [] and "0 页" in reply
    s, reply = say(s, "确认生成", corpus, out)
    assert s.report is None and not out.exists()
    s, reply = say(s, "主题改为赞比亚兽医抗菌药物管理", corpus, out)
    assert s.pages == 10 and 0 < len(s.selected) <= 2 and "缺" in reply
    s, reply = say(s, "确认生成", corpus, out)
    assert s.report and s.report["status"] == "partial"


def test_replacement_uses_a_distinct_grounded_page_and_preserves_geography(tmp_path):
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    s, _ = say(Conversation(), "Make a 1-slide presentation about Zambia veterinary antibiotic stewardship", corpus, out)
    actual = s.selected[0]["slide_number"]
    focus = "农户培训" if actual != 1 else "广播宣传"
    s, _ = say(s, f"把第1页换成{focus}的例子", corpus, out)
    assert s.selected[0]["slide_number"] != actual and s.selected[0]["deck_id"] == "zambia"
    before = s.selected
    s, no_match = say(s, "把第1页换成medieval harpsichord tuning", corpus, out)
    assert s.selected == before and "保留" in no_match
    s, _ = say(s, "请把备注改得幽默一些", corpus, out)
    assert s.selected == before and not out.exists()
    s, _ = say(s, "不要确认生成", corpus, out)
    assert not out.exists()


def test_topic_only_and_invalid_counts_do_not_truncate(tmp_path):
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    s, _ = say(Conversation(), "赞比亚兽医抗菌药物管理", corpus, out)
    assert s.phase == "clarify" and s.topic == "赞比亚兽医抗菌药物管理"
    s2, reply = say(s, "200页", corpus, out)
    assert not s2.pages and "20" in reply
    s, _ = say(s2, "两页", corpus, out)
    assert s.pages == 2
    original = s.selected
    s, reply = say(s, "把第0页移到第1页", corpus, out)
    assert s.selected == original and "页码" in reply


def test_http_stale_and_duplicate_requests_cannot_export_an_old_plan(tmp_path):
    import re
    from fastapi.testclient import TestClient
    from scripts.serve_amr_brief import create_demo_app

    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    with TestClient(create_demo_app(corpus, out), base_url="http://127.0.0.1:8765") as client:
        token = re.search(r'<meta name="demo-token" content="([^"]+)"', client.get("/").text)[1]

        def post(message, previous=None):
            data = {"message": message}
            if previous:
                data.update(session_id=previous["session_id"], revision=previous["revision"])
            return client.post("/conversation", json=data, headers={"x-demo-token": token})

        r = post("做2页关于赞比亚兽医抗菌药物管理的PPT").json()
        assert r["phase"] == "preview" and r["source_decks"] == 1 and r["index"] == {"decks": 2, "slides": 3}
        edited = post("把第2页移到第1页", r).json()
        assert post("确认生成", r).status_code == 409 and not out.exists()
        final = post("确认生成", edited).json()
        assert final["phase"] == "exported" and post("确认生成", edited).status_code == 409
        again = post("确认生成", final).json()
        assert again["downloads"] == final["downloads"]
        mapped = client.get(again["downloads"]["sources"]).json()
        assert [row["slideId"] for row in mapped] == [row["slide_id"] for row in edited["selected"]]
        assert client.get(again["downloads"]["draft"]).content[:2] == b"PK"
        assert len(list(out.iterdir())) == 1


@pytest.mark.parametrize("command", ["确认生成", "删除第99页", "nonsense"])
def test_optional_model_cannot_confirm_or_modify_an_unknown_slide(tmp_path, monkeypatch, command):
    from presentation_search import dialog_model, local_brief
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    monkeypatch.setattr(local_brief, "rerank_candidates", lambda topic, cards, *, model, limit:
                        [{"slide_id": c["slide_id"], "evidence": c["title"]} for c in cards[:limit]])
    monkeypatch.setattr(dialog_model, "interpret_message", lambda *a, **k: command)
    s, _ = say(Conversation(model="test"), "赞比亚兽医管理，2页", corpus, out)
    initial = s.selected
    s, _ = say(s, "要改改看", corpus, out)
    assert s.interpretation_model_called and s.selected == initial
    assert s.phase == "preview" and not out.exists()


def test_recordable_natural_followups_and_no_early_export(tmp_path):
    corpus, out = corpus_fixture(tmp_path), tmp_path / "out"
    s, _ = say(Conversation(), "我想做两页关于赞比亚兽医抗菌药物管理的PPT", corpus, out)
    assert len(s.selected) == 2
    for prompt in ["这份PPT会讲什么？", "先给我看看大纲", "概括一下", "请给我看看大纲"]:
        s, text = say(s, prompt, corpus, out)
        assert "原第" in text and "第 1 页" in text and s.selected[0]["evidence"] in text and not out.exists()
    for msg in ["先别导出", "不要确认生成", "暂时不想生成PPT"]:
        s, _ = say(s, msg, corpus, out)
        assert s.phase == "preview" and not out.exists()
    last = s.selected[-1]["slide_id"]
    s, _ = say(s, "把最后一页移到第一页", corpus, out)
    assert s.selected[0]["slide_id"] == last
    s, _ = say(s, "好的，就按这个大纲生成PPT吧", corpus, out)
    assert s.phase == "exported" and len(list(out.iterdir())) == 1
    s, _ = say(s, "帮我导出这份PPT", corpus, out)
    assert s.phase == "exported" and len(list(out.iterdir())) == 1
