"""Session-scoped slide retrieval, dialogue, review and versioned export."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from threading import Lock
from unicodedata import normalize

from . import brief_conversation as conversation
from . import studio_model
from .brief_index import build_brief_index, order_story
from .studio_export import publish


DEFAULTS = {"count": 5, "language": "en", "audience": "General audience", "mode": "hybrid",
            "min_year": None, "template": "original", "model": "offline"}
_INDEX_LOCK = Lock()


@dataclass
class StudioSession:
    topic: str = ""
    settings: dict = field(default_factory=lambda: dict(DEFAULTS))
    selected: list = field(default_factory=list)
    excluded: set = field(default_factory=set)
    adaptations: dict = field(default_factory=dict)
    versions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    reply: str = ""
    model_used: bool = False


@lru_cache(maxsize=2)
def _load_index(path, signature):
    return build_brief_index(path)


def _stamp(path):
    stat = path.stat()
    return path.name, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _settings(previous, changes):
    cfg = dict(previous)
    if changes:
        if set(changes) - set(DEFAULTS):
            raise ValueError("The request contains an unknown brief setting.")
        cfg.update(changes)
    for field, options in (("mode", ("hybrid", "compilation", "reconstruction")),
                           ("model", ("offline", "ollama", "openai")), ("template", ("original", "field", "custom"))):
        if cfg[field] not in options:
            raise ValueError(f"Choose a supported {field}.")
    if type(cfg["count"]) is not int or not 1 <= cfg["count"] <= 20:
        raise ValueError("Choose 1–20 slides.")
    if cfg["min_year"] is not None and (type(cfg["min_year"]) is not int or not 1900 <= cfg["min_year"] <= 2099):
        raise ValueError("Enter a publication year between 1900 and 2099.")
    for key, limit in (("audience", 180), ("language", 60)):
        if not isinstance(cfg[key], str) or len(cfg[key].strip()) > limit:
            raise ValueError(f"Please shorten the {key} setting.")
        cfg[key] = cfg[key].strip() or DEFAULTS[key]
    aliases = {"english": "en", "中文": "zh", "chinese": "zh", "简体中文": "zh", "zh-cn": "zh"}
    cfg["language"] = aliases.get(cfg["language"].casefold(), cfg["language"])
    return cfg


def _is_zh(value):
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _note(row, cfg):
    audience = cfg["audience"]
    if cfg["language"].lower().startswith("zh"):
        return (f"向{audience}介绍这页资料。说明证据来自《{row['deck_title']}》，"
                f"请听众讨论这段原文与当前工作有何关联。\n{row['evidence']}")
    return (f"For {audience}: introduce the excerpt from {row['deck_title']}. "
            f"Read the evidence in context, then ask which part applies to the audience’s work.\n{row['evidence']}")


def _evidence_title(row):
    title = row["title"].strip()
    if title and not re.fullmatch(r"(?:slide|page|diapositive)\s*\d+", title, re.I):
        return title
    fragment = row["evidence"].strip().splitlines()[0]
    first = re.split(r"(?<=[.!?。！？])\s+", fragment, maxsplit=1)[0]
    if len(first) <= 100:
        return first
    short = first[:94].rsplit(" ", 1)[0].rstrip(" ,;:，；：")
    return (short or first[:94]) + "…"


def _method(row, settings):
    if settings["mode"] != "hybrid":
        return settings["mode"]
    # Keep source visual context on data-heavy pages. Reflow narrative pages for the intended audience.
    structured = re.search(r"\b(chart|figure|table|graph)\b|\d\s*%|mg/kg", row["body"], re.I)
    return "compilation" if structured else "reconstruction"


class StudioService:
    def __init__(self, corpus_dir, output_dir):
        self.corpus_dir = Path(corpus_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        mapping = self.corpus_dir / "studio-page-map.json"
        self.page_map = json.loads(mapping.read_text(encoding="utf-8")) if mapping.is_file() else {}

        self.digests = {}
        digest_file = Path(__file__).resolve().parents[1] / "studio" / "evidence.json"
        if self.page_map and digest_file.is_file():
            cards = json.loads(digest_file.read_text(encoding="utf-8"))
            self.digests = {("studio-" + c["source_id"], c["page"]): c for c in cards}

    @staticmethod
    def new_session():
        return StudioSession()

    def _index(self):
        manifest = self.corpus_dir / "verified.csv"
        if not manifest.is_file():
            raise ValueError("A prepared corpus with verified.csv and presentations/ is required.")
        signature = (_stamp(manifest), tuple(sorted(_stamp(p) for p in
                                                    (self.corpus_dir / "presentations").glob("*.pptx"))))
        with _INDEX_LOCK:
            return _load_index(self.corpus_dir, signature)

    def _slides(self, state):
        result = []
        for row in state.selected:
            adaptation = state.adaptations.get(row["slide_id"], {})
            original_page = self.page_map.get(row["deck_id"], {}).get(str(row["slide_number"]))
            card = self.digests.get((row["deck_id"], original_page), {})
            in_chinese = state.settings["language"] == "zh"
            title = card.get("title_zh" if in_chinese else "title", _evidence_title(row))
            body = card.get("evidence_zh" if in_chinese else "evidence", row["evidence"])
            method = "reconstruction" if card and state.settings["mode"] == "hybrid" else _method(row, state.settings)
            if method == "compilation":
                title, body = row["title"], row["evidence"]
            else:
                title, body = adaptation.get("title", title), adaptation.get("body", body)
            result.append({
                "title": title, "body": body,
                "evidence": row["evidence"], "source": row["deck_title"], "page": original_page or row["slide_number"],
                "local_page": row["slide_number"], "digest": original_page is not None,
                "url": row["source_url"], "issued": row["issued"], "method": method,
                "notes": adaptation.get("notes", _note(row, state.settings)), "id": row["slide_id"],
                "source_language": state.settings["language"] if card and state.settings["language"] in ("en", "zh") else row.get("language", ""), "reason": row.get("reason", "")})
        return result

    def snapshot(self, state):
        index = self._index()
        warnings = list(state.warnings)
        if 0 <= len(state.selected) < state.settings["count"] and state.topic:
            warnings.append(f"{len(state.selected)} of {state.settings['count']} requested slides have evidence.")
        slides = self._slides(state)
        sources_differ = any(row["source_language"] and state.settings["language"].casefold()
                             not in re.split(r"[/,; ]+", row["source_language"].casefold()) for row in slides)
        if any(s["digest"] and s["method"] == "compilation" for s in slides):
            warnings.append("Compilation uses the local bilingual digest pages; original publisher slides are linked in the source report.")
        if sources_differ and slides:
            if not state.adaptations:
                warnings.append("Offline mode retains the original evidence language. Select Ollama or OpenAI for translated slide prose.")
            if any(row["method"] == "compilation" for row in slides):
                warnings.append("Compiled original slides and visual labels retain the source language.")
        stats = {k: index.stats[k] for k in ("decks", "slides")}
        stats["failed_decks"] = len(index.stats["failures"])
        return {"reply": state.reply, "topic": state.topic, "settings": dict(state.settings), "slides": slides,
                "versions": [{k: v for k, v in version.items() if k != "signature"} for version in state.versions],
                "stats": stats, "model_used": state.model_used, "warnings": list(dict.fromkeys(warnings))}

    def _search(self, state, topic, count, blocked=()):
        pool = self._index().search(topic, min(120, count * 3 + len(blocked) + 10),
                                    min_year=state.settings["min_year"])
        candidates = [r for r in pool if r["slide_id"] not in blocked]
        if state.settings["model"] == "offline":
            language = state.settings["language"].casefold()
            candidates.sort(key=lambda r: language not in re.split(r"[/,; ]+", r.get("language", "").casefold()))
        return order_story(candidates[:count])

    def _edit(self, state, text, zh):
        length = conversation._LENGTH_CHANGE.fullmatch(text) or conversation._COUNT.fullmatch(text)
        if length:
            count = conversation._number(length[1])
            state.settings = _settings(state.settings, {"count": count})
            keep = state.selected[:count]
            if count > len(keep):
                blocked = state.excluded | {r["slide_id"] for r in keep}
                keep.extend(self._search(state, state.topic, count - len(keep), blocked))
            state.selected = keep
            return (f"目标已调整为 {count} 页。" if zh else f"Changed the target to {count} slides."), True

        for action, pattern in (("why", conversation._EXPLAIN), ("move", conversation._MOVE),
                                ("delete", conversation._DELETE), ("replace", conversation._REPLACE)):
            match = pattern.fullmatch(text)
            if not match:
                continue
            pos = conversation._number(match[1]) - 1
            dst = conversation._number(match[2]) - 1 if action == "move" else pos
            if min(pos, dst) < 0 or max(pos, dst) >= len(state.selected):
                return ("请输入当前提纲中的页码。" if zh else "Use a slide number from the current outline."), False
            row = state.selected[pos]
            if action == "why":
                slide = self._slides(state)[pos]
                return (f"{slide['source']} · {slide['page']}\n{slide['evidence']}\n{row['reason']}", False)
            if action == "move":
                state.selected.insert(dst, state.selected.pop(pos))
                return (f"已将第 {pos+1} 页移至第 {dst+1} 页。" if zh else f"Moved slide {pos+1} to {dst+1}."), False
            if action == "delete":
                state.excluded.add(state.selected.pop(pos)["slide_id"])
                state.settings["count"] = max(1, len(state.selected))
                return (f"已移除第 {pos+1} 页。" if zh else f"Removed slide {pos+1}."), False
            query = match[2].strip()
            if not conversation.Features.of(query).places:
                places = conversation.Features.of(state.topic).places
                query = " ".join([*(conversation.COUNTRIES[c].split("|")[0] for c in sorted(places)), query])
            picks = self._search(state, query, 1, state.excluded | {r["slide_id"] for r in state.selected})
            if not picks:
                return ("未找到可替换的证据。" if zh else "No eligible source slide matched that replacement."), False
            state.excluded.add(row["slide_id"])
            state.selected[pos] = picks[0]
            return (f"已替换第 {pos+1} 页。" if zh else f"Replaced slide {pos+1}."), True
        return None

    def _adapt(self, state, reserve, feedback="", all_pages=True):
        if state.settings["model"] == "offline":
            state.adaptations = {}
            return
        pending = [r for r in state.selected if all_pages or r["slide_id"] not in state.adaptations]
        if pending:
            state.adaptations.update(studio_model.adapt_pages(pending, state.topic, state.settings, feedback, reserve))
            state.model_used = True

    def _new_outline(self, state, topic, reserve, zh):
        if not 1 <= len(topic) <= 500:
            raise ValueError("Please enter a topic of 1–500 characters.")
        state.topic = topic
        state.selected = self._search(state, topic, state.settings["count"])
        state.adaptations = {}
        state.excluded = set()
        self._adapt(state, reserve)
        n = len(state.selected)
        if not n:
            return ("未检索到可核验的证据。可以放宽年份或更换主题。" if zh else
                    "No verified slide matched. Broaden the topic or the publication-year filter.")
        return (f"选出 {n} 页资料。可以逐页核对来源、调整页序，然后确认导出。" if zh else
                f"Found {n} evidence-backed slides. Review the sources, revise the order, or generate the deck.")

    def _generate(self, state, template_path, zh):
        if not state.selected:
            return "请先准备有来源的大纲。" if zh else "Prepare an outline with at least one source slide first."
        slides = self._slides(state)
        material = [state.topic, state.settings, slides, [r["source_hash"] for r in state.selected]]
        if template_path and state.settings["template"] == "custom":
            material.append(hashlib.sha256(Path(template_path).read_bytes()).hexdigest())
        signature = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if not state.versions or state.versions[-1]["signature"] != signature:
            if len(state.versions) >= 16:
                raise ValueError("Download your existing versions and start another brief to generate more.")
            warnings = list(self.snapshot(state)["warnings"])
            version = publish(self.corpus_dir, self.output_dir, state.topic, state.selected, slides, state.settings,
                              template_path, warnings, signature, bool(state.adaptations))
            state.versions.append(version)
            state.warnings = warnings
        return (f"第 {len(state.versions)} 版已就绪，可下载 PPT、逐页来源和质量检查报告。" if zh else
                f"Version {len(state.versions)} is ready. Download the PowerPoint, source report and QA report.")

    def turn(self, state, message, settings=None, *, action="chat", reserve_model=None, template_path=None):
        if action not in ("chat", "generate") or not isinstance(message, str) or len(message) > 1600:
            raise ValueError("Use a shorter message or a supported action.")
        candidate = deepcopy(state)
        candidate.settings = _settings(state.settings, settings)
        candidate.model_used = False
        candidate.warnings = []
        text = normalize("NFKC", message).strip().rstrip("。！!？?").strip()
        zh = _is_zh(text) or (not text and candidate.settings["language"] == "zh")
        changed = {k for k, val in candidate.settings.items() if state.settings[k] != val}
        # A form change takes effect on export as well as on chat.
        if state.topic and changed & {"min_year", "count"}:
            if "min_year" in changed:
                candidate.selected = self._search(candidate, candidate.topic, candidate.settings["count"], candidate.excluded)
            else:
                self._edit(candidate, f"change length to {candidate.settings['count']} slides", zh)
            self._adapt(candidate, reserve_model, all_pages=False)
        if state.topic and changed & {"model", "language", "audience"}:
            self._adapt(candidate, reserve_model)

        if action == "generate" or conversation._CONFIRM.fullmatch(text):
            reply = self._generate(candidate, template_path, zh)
        elif not text:
            reply = "设置已更新。" if zh else "Brief settings updated."
        elif not state.topic:
            topic, count = conversation._request(text)
            if count:
                candidate.settings = _settings(candidate.settings, {"count": count})
            reply = self._new_outline(candidate, topic, reserve_model, zh) if topic else (
                "你希望介绍什么主题？" if zh else "What topic should the slides cover?")
        elif conversation._TOPIC_CHANGE.fullmatch(text):
            topic = conversation._TOPIC_CHANGE.fullmatch(text)[1].strip()
            reply = self._new_outline(candidate, topic, reserve_model, zh)
        elif conversation._OVERVIEW.fullmatch(text):
            reply = "\n".join(f"{i}. {s['title']}" for i, s in enumerate(self._slides(candidate), 1))
            reply = reply or ("当前提纲为空。" if zh else "The outline is empty.")
        else:
            edit = self._edit(candidate, text, zh)
            if edit:
                reply, new_pages = edit
                if new_pages:
                    self._adapt(candidate, reserve_model, all_pages=False)
            elif changed and text.lower() in ("apply settings", "update settings", "应用设置"):
                reply = "设置已更新。" if zh else "Brief settings updated."
            elif candidate.settings["model"] in ("ollama", "openai"):
                intent, value = studio_model.interpret(text, state.topic, candidate.selected, reserve_model, candidate.settings["model"])
                candidate.model_used = True
                if intent == "topic":
                    reply = self._new_outline(candidate, value, reserve_model, zh)
                elif intent == "rewrite":
                    self._adapt(candidate, reserve_model, value)
                    reply = "已按要求更新文稿。" if zh else "Revised the slide prose and presenter notes."
                elif intent == "edit":
                    edit = self._edit(candidate, value, zh)
                    reply = edit[0] if edit else ("请指明页码。" if zh else "Please specify a slide number.")
                    if edit and edit[1]:
                        self._adapt(candidate, reserve_model, all_pages=False)
                else:
                    reply = value
            elif conversation._COUNT.search(text) or re.match(r"^(?:create|prepare|build|new brief|制作|准备|做一份)", text, re.I):
                topic, count = conversation._request(text)
                if count:
                    candidate.settings = _settings(candidate.settings, {"count": count})
                reply = self._new_outline(candidate, topic, reserve_model, zh)
            else:
                reply = ("可输入“为什么选第2页”“把第2页移到第1页”“删除第2页”或“主题改为……”。"
                         if zh else "Try “explain slide 2”, “move slide 2 to slide 1”, “remove slide 2” or “topic: …”.")
        candidate.reply = reply
        result = self.snapshot(candidate)
        state.__dict__.update(candidate.__dict__)
        return result
