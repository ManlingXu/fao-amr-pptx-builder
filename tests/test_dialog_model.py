"""An optional model may interpret an edit, but cannot confirm or invent evidence."""
import pytest


def interpret(monkeypatch, message, action, page=0, dest=0, query="", **extra):
    from presentation_search import dialog_model
    rows = [{"title": heading} for heading in ("Introduction", "Guidelines", "Surveillance")]
    fake = {"action": action, "page": page, "destination": dest, "query": query, **extra}
    monkeypatch.setattr(dialog_model, "request_local_json", lambda *a, **kw: fake)
    return dialog_model.interpret_message(message, model="qwen3:4b", selected=rows)


def test_flexible_feedback_becomes_specific_existing_commands(monkeypatch):
    assert interpret(monkeypatch, "请把最后一张放到最前面，内容不用加", "move", 3, 1) == "把第3页移到第1页"
    assert interpret(monkeypatch, "最后一张跟主题有关吗？", "explain", 3) == "为什么选第3页"
    assert interpret(monkeypatch, "三页太多了，能弄成两页吗", "pages", 2) == "改成2页"
    assert interpret(monkeypatch, "我更希望第二张聚焦在农户培训上", "replace", 2,
                     query="农户培训") == "把第2页换成农户培训"
    assert interpret(monkeypatch, "这次改做家禽监测", "topic", query="家禽监测") == "主题改为家禽监测"
    assert interpret(monkeypatch, "第二张可以删了", "remove", 2) == "删除第2页"
    assert interpret(monkeypatch, "需要说明", "clarify") is None


@pytest.mark.parametrize("action,page,dest,query,extra", [
    ("export", 0, 0, "", {}), ("remove", 4, 0, "", {}), ("move", 2, 4, "", {}),
    ("pages", 21, 0, "", {}), ("remove", True, 0, "", {}),
    ("topic", 0, 0, "模型臆造主题", {}), ("replace", 2, 0, "", {}),
    ("clarify", 0, 0, "", {"confirmation": True}),
])
def test_invalid_model_actions_cannot_reach_editor(monkeypatch, action, page, dest, query, extra):
    from presentation_search.local_model import LocalModelError
    with pytest.raises(LocalModelError):
        interpret(monkeypatch, "最后一张放到前面", action, page, dest, query, **extra)


def test_conversational_interpretation_changes_only_preview(tmp_path, monkeypatch):
    from presentation_search import dialog_model
    from presentation_search.brief_conversation import Conversation, answer

    rows = [{"slide_id": slide_id, "title": slide_id} for slide_id in ("one", "two", "three")]
    state = Conversation(model="qwen3:4b", topic="Zambia", pages=3, phase="preview", selected=rows)
    out = tmp_path / "out"
    monkeypatch.setattr(dialog_model, "request_local_json", lambda *args, **kwargs: {
        "action": "move", "page": 3, "destination": 1, "query": "",
    })
    updated, reply = answer(state, "计划给农业部做汇报，请把最后一张放到最前面", tmp_path, out)
    assert updated.interpretation_model_called and "第 1 页" in reply
    assert [row["slide_id"] for row in updated.selected] == ["three", "one", "two"]
    assert updated.phase == "preview" and updated.report is None and not out.exists()
