"""Review full-corpus evidence in a local conversation before publishing a deck."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from itertools import groupby

from .brief_index import COUNTRIES, Features, build_brief_index
from .local_brief import save_brief_selection, select_brief_pages


@dataclass
class Conversation:
    topic: str = ""
    pages: int = 0
    model: str = ""
    phase: str = "clarify"
    selected: list[dict] = field(default_factory=list)
    excluded: frozenset = frozenset()
    stats: dict = field(default_factory=dict)
    shortlisted: int = 0
    used_model: bool = False
    report: dict | None = None
    interpretation_model_called: bool = False


_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}
_NUMBER = r"(-?\d+|[零一二两三四五六七八九十]+)"
_COUNT = re.compile(_NUMBER + r"\s*(?:张(?:幻灯片)?|页|[- ]?(?:slides?|pages?)\b)", re.I)
_SLOT = r"(?:第\s*|(?:slide|page)\s*)" + _NUMBER + r"\s*(?:页|张)?"
_EXPLAIN = re.compile(r"(?:请问|请|能否|能不能)?\s*(?:为什么(?:要)?(?:选(?:择|了|中)?)?|解释(?:一下)?|介绍(?:一下)?|why(?: did you (?:choose|select))?|explain)\s*" + _SLOT, re.I)
_MOVE = re.compile(r"(?:请)?(?:把|将|move\s+)?\s*" + _SLOT + r"\s*(?:移(?:动)?到|调(?:整)?到|放到|挪到|放在|to)\s*" + _SLOT, re.I)
_DELETE = re.compile(r"(?:请)?\s*(?:删除|删掉|去掉|移除|remove|delete|drop)\s*" + _SLOT, re.I)
_REPLACE = re.compile(r"(?:请)?\s*(?:把|将|replace\s+)?\s*" + _SLOT + r"\s*(?:替换为|替换成|换成|换为|改成|改为|with)\s*(.+)", re.I)
_TOPIC_CHANGE = re.compile(r"(?:请)?\s*(?:把)?(?:主题|topic)\s*(?:改为|换成|改成|改到|[:：]|to\s+)\s*(.+)", re.I)
_LENGTH_CHANGE = re.compile(r"(?:请)?\s*(?:(?:把)?(?:页数|长度|PPT))?(?:改成|改为|调整为|缩(?:短)?到|扩(?:展)?到|make it|change (?:it|length) to|resize to)\s*" + _COUNT.pattern, re.I)
_CONFIRM = re.compile(
    r"(?:(?:好的?|可以)[,，]?\s*)?(?:就?按(?:这个|这份|当前|上面)(?:大纲|提纲|方案|顺序))?"
    r"(?:请|帮我)?(?:确认(?:生成|导出|输出|制作)?|同意生成|可以(?:生成|导出)|导出|生成初稿|生成|生成吧)"
    r"(?:这份|这个)?(?:可编辑的)?(?:PPT|PowerPoint|演示文稿|幻灯片|初稿)?(?:了|吧)?"
    r"|confirm(?: (?:and )?(?:generate|export))?|export(?: (?:the )?(?:deck|ppt|powerpoint))?|yes", re.I)
_OVERVIEW = re.compile(
    r"(?:请|先|帮我|给我|再|我想|可以|能不能|让我|你)?(?:给我|先|再)?(?:看(?:看|一下)?|显示|展示|介绍|概括|总结)"
    r"(?:一下)?(?:这份|这个|当前|整个)?(?:PPT的?|演示文稿的?)?(?:大纲|提纲|方案|内容)?(?:吗)?"
    r"|(?:这份|这个)?(?:PPT|演示文稿)(?:会|要)?讲(?:什么|哪些内容)|"
    r"(?:show(?: me)?|summari[sz]e) (?:the |this )?(?:outline|plan|presentation)", re.I)
_ACTIONS = "你可以问“为什么选第2页”，也可以输入“把第3页移到第1页”“把第2页换成农户培训”或“确认生成”。"


def _number(text):
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if "十" in text:
        tens, units = text.split("十", maxsplit=1)
        return _DIGITS.get(tens or "一", 99) * 10 + _DIGITS.get(units or "零", 99)
    return _DIGITS.get(text, 99)


def _request(text):
    matches = list(_COUNT.finditer(text))
    pages = _number(matches[0][1]) if matches else 0
    if matches and (not 1 <= pages <= 20 or len(matches) > 1):
        raise ValueError("请给一个明确页数，范围为 1–20 页。")
    if re.fullmatch(_NUMBER, text):
        pages = _number(text)
        if not 1 <= pages <= 20:
            raise ValueError("请输入 1–20 之间的页数。")
        return "", pages
    topic = _COUNT.sub(" ", text)
    marker = re.search(r"(?:主题(?:是|为|[:：])|主题为|关于|topic(?: is|[:：])|\babout\b|\bon\b)", topic, re.I)
    if marker:
        topic = topic[marker.end():]
    else:
        # Remove conversational framing only at the edges; keep policy and agency names intact.
        prefix = (r"^(?:(?:从|在)(?:全部|整个|所有)(?:资料库|课件库|资料|课件)(?:里|中)?|请|我想要|我想|我要|"
                  r"帮我|给我|做(?:一份|一个)?|准备(?:一份|一个)?|制作(?:一份|一个)?|生成(?:一份|一个)?|"
                  r"关于|介绍|讲讲|讲|\s|[,，。:：、]|(?:make|create|prepare|build|a|an|please)\b)+")
        topic = re.sub(prefix, "", topic, flags=re.I)
        topic = re.sub(r"^(?:的?(?:ppt|幻灯片|演示文稿|powerpoint|presentation))[\s,，:：、]*(?:关于|介绍|讲)?", "", topic, flags=re.I)
    topic = topic.rstrip(" \t。，,、：:！？!?")
    topic = re.sub(r"(?:的?\s*(?:ppt|幻灯片|演示文稿|powerpoint|presentation))\s*$", "", topic, flags=re.I)
    return topic.strip(" \t。，,、：:！？!?"), pages


def _initial_or_revise(state, text, corpus, *, retain_pages=True):
    try:
        topic, n = _request(text)
    except ValueError as exc:
        return state, str(exc)
    topic = topic or state.topic
    n = n or (state.pages if retain_pages else 0)
    if not topic or not n:
        next_state = replace(state, topic=topic, pages=n, phase="clarify", report=None)
        if not topic and not n:
            return next_state, "你想给谁介绍什么主题，预计做几页？例如“赞比亚兽医抗菌药物管理，10页”。"
        if not topic:
            return next_state, f"记下了，目标是 {n} 页。你希望介绍什么主题？"
        return next_state, f"主题是“{topic}”。你希望做几页？可以选择 1–20 页。"
    index = build_brief_index(corpus)
    selected, shortlisted, called = select_brief_pages(index, topic, n, model=state.model)
    new = replace(state, topic=topic, pages=n, stats=index.stats, selected=selected,
                  shortlisted=shortlisted, used_model=called, excluded=frozenset(), phase="preview", report=None)
    source_count = len({row["deck_id"] for row in selected})
    reply = (f"我在本地已索引的 {index.stats['decks']} 份课件、{index.stats['slides']:,} 页中检索了“{topic}”。"
             f"草案有 {len(selected)} 页，来自 {source_count} 份原始课件。")
    if selected:
        sections = []
        for stage, group in groupby(enumerate(selected, 1), key=lambda pair: pair[1]["stage"]):
            positions = [i for i, _ in group]
            span = str(positions[0]) if len(positions) == 1 else f"{positions[0]}–{positions[-1]}"
            label = {"Context": "背景", "Policy": "政策", "Implementation": "实践",
                     "Monitoring": "监测", "Next steps": "后续行动"}.get(stage, stage)
            sections.append(f"第 {span} 页讲{label}")
        if len(sections) <= 5:
            reply += " 提纲安排为" + "、".join(sections) + "。"
    if len(selected) < n:
        reply += f"距离目标还缺 {n-len(selected)} 页。"
    if selected:
        return new, reply + " 你可以逐页核对下面的提纲和出处。" + _ACTIONS
    return new, reply + " 可以输入“主题改为……”扩大范围。"


def _search_edit(state, criterion, limit, corpus, *, keep_place=False):
    if keep_place and not Features.of(criterion).places:
        countries = Features.of(state.topic).places
        criterion = " ".join([*(COUNTRIES[c].split("|")[0] for c in sorted(countries)), criterion])
    index = build_brief_index(corpus)
    unavailable = state.excluded | {r["slide_id"] for r in state.selected}
    rows, shortlisted, called = select_brief_pages(index, criterion, limit, model=state.model, excluded=unavailable)
    return rows, index.stats, shortlisted, called


def _edit(state, text, corpus):
    """Return None when the input needs clarification or optional language interpretation."""
    text = re.sub(r"最后一页|末页", f"第{len(state.selected)}页", text)
    change = _TOPIC_CHANGE.fullmatch(text)
    if change:
        return _initial_or_revise(state, change[1], corpus)
    length = _LENGTH_CHANGE.fullmatch(text) or _COUNT.fullmatch(text)
    if length:
        n = _number(length[1])
        if not 1 <= n <= 20:
            return state, "请输入 1–20 之间的页数。"
        selected = state.selected[:n]
        stats, shortlisted, called = state.stats, state.shortlisted, False
        if n > len(selected):
            extras, stats, shortlisted, called = _search_edit(state, state.topic, n-len(selected), corpus)
            selected += extras
        new = replace(state, pages=n, selected=selected, stats=stats, shortlisted=shortlisted, phase="preview",
                      used_model=state.used_model or called, report=None)
        return new, f"目标调整为 {n} 页，当前有 {len(selected)} 页可核验的材料。请查看更新后的提纲。"

    for intent, pattern in (("why", _EXPLAIN), ("move", _MOVE), ("delete", _DELETE), ("replace", _REPLACE)):
        match = pattern.fullmatch(text)
        if not match:
            continue
        position = _number(match[1])
        destination = _number(match[2]) if intent == "move" else position
        if not (1 <= position <= len(state.selected) and 1 <= destination <= len(state.selected)):
            return state, f"当前提纲有 {len(state.selected)} 页，请使用已有页码。"
        row = state.selected[position - 1]
        if intent == "why":
            return state, (f"第 {position} 页选自《{row['deck_title']}》原第 {row['slide_number']} 页。"
                           f"它与主题匹配的证据是“{row['evidence']}”。\n{row['reason']}")
        selected = list(state.selected)
        new = replace(state, selected=selected, phase="preview", report=None)
        if intent == "move":
            selected.insert(destination - 1, selected.pop(position - 1))
            return new, f"已把原来的第 {position} 页移到第 {destination} 页。下面是新的顺序。"
        if intent == "delete":
            selected.pop(position - 1)
            return replace(new, pages=max(1, len(selected)), excluded=state.excluded | {row["slide_id"]}), (
                f"已删除第 {position} 页。当前草案共 {len(selected)} 页。")
        focus = re.sub(r"(?:的)?(?:案例|例子)$", "", match[2]).strip()
        if not focus:
            return state, "希望这一页换成哪方面的资料？例如“把第2页换成农户培训”。"
        replacements, stats, shortlisted, called = _search_edit(state, focus, 1, corpus, keep_place=True)
        if not replacements:
            return state, f"没有找到关于“{focus}”的其他可核验页面，已保留原第 {position} 页。"
        source = selected[position - 1] = replacements[0]
        return replace(new, stats=stats, shortlisted=shortlisted, used_model=state.used_model or called,
                       excluded=state.excluded | {row["slide_id"]}), (
            f"已替换第 {position} 页，采用《{source['deck_title']}》原第 {source['slide_number']} 页。")


def _overview(rows):
    if not rows:
        return "当前提纲还没有匹配的证据页，可以输入“主题改为……”重新检索。"
    # Select examples from distinct stages first, then keep the displayed deck order.
    positions = []
    stages = set()
    for i, row in enumerate(rows):
        if row["stage"] not in stages:
            positions.append(i)
            stages.add(row["stage"])
        if len(positions) == 3:
            break
    for i in range(len(rows)):
        if len(positions) == min(3, len(rows)):
            break
        if i not in positions:
            positions.append(i)
    lines = ["这份简报共 " + str(len(rows)) + " 页。以下是提纲中的原文要点。"]
    for i in sorted(positions):
        row = rows[i]
        quote = row["evidence"].strip()
        if len(quote) > 200:
            quote = quote[:200].rsplit(" ", 1)[0].rstrip() + "…"
        lines.append(f"第 {i+1} 页《{row['title']}》：“{quote}”（原第 {row['slide_number']} 页）")
    return "\n".join(lines)


def answer(state, message, corpus, output_root):
    text = unicodedata.normalize("NFKC", message).strip().rstrip("。！!？?").strip()
    state = replace(state, interpretation_model_called=False)
    if not text:
        return state, "请输入主题和目标页数，或告诉我想修改哪一页。"
    if re.search(r"(?:暂时|先)?(?:不要|别|不想|取消|暂缓).{0,6}(?:确认|导出|生成|输出)|"
                 r"(?:do not|don['’]t|not yet).{0,10}(?:export|confirm|generate)", text, re.I):
        return state, "好的，当前提纲已保留。你可以继续看大纲或修改某一页。"
    if _OVERVIEW.fullmatch(text) and state.phase != "clarify":
        return state, _overview(state.selected)
    if _CONFIRM.fullmatch(text):
        if not state.selected:
            return state, "还没有可导出的证据页。请提供主题和页数，或输入“主题改为……”重新检索。"
        if state.report is None:
            report = save_brief_selection(corpus, output_root, topic=state.topic, pages=state.pages,
                                          selected=state.selected, stats=state.stats, shortlisted=state.shortlisted,
                                          model=state.model or None, used_model=state.used_model, reflow=True)
            state = replace(state, phase="exported", report=report)
        return state, (f"已按刚确认的顺序生成 {len(state.selected)} 页可编辑的初稿。"
                       "可下载 PowerPoint 和逐页来源清单，也可以上传自己的模板。")
    if state.phase == "clarify":
        return _initial_or_revise(state, text, corpus)
    result = _edit(state, text, corpus)
    if result:
        return result
    if state.model:
        from .dialog_model import interpret_message
        command = interpret_message(text, model=state.model, selected=state.selected,
                                    topic=state.topic, requested_pages=state.pages)
        state = replace(state, interpretation_model_called=True)
        if command:
            result = _edit(state, command, corpus)
            if result:
                return result
    return state, "请指出要调整的页码或新的主题。" + _ACTIONS
