"""HTTP boundary for this launch's local, revisioned briefing conversations."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from presentation_search.brief_conversation import Conversation, answer


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=100)
    revision: int | None = Field(default=None, ge=0)
    model: str = Field(default="", max_length=120, pattern=r"^(?:[A-Za-z0-9][A-Za-z0-9._:/-]*)?$")


@dataclass
class Session:
    state: Conversation
    revision: int = 0
    files: dict = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)


def register_conversation_routes(app, corpus_dir, output_dir, publish_run):
    sessions = {}
    registry_lock = Lock()

    @app.post("/conversation")
    def converse(turn: Message):
        key = turn.session_id
        with registry_lock:
            if key is None:
                if turn.revision not in (None, 0):
                    raise HTTPException(409, "新对话须从第一条消息开始。")
                key = secrets.token_urlsafe(18)
                session = Session(Conversation(model=turn.model))
            elif key not in sessions:
                raise HTTPException(404, "该对话已过期，请开启新对话。")
            else:
                session = sessions[key]
        with session.lock:
            if turn.session_id is not None and turn.revision != session.revision:
                raise HTTPException(409, "提纲已更新，请使用对话的最新版本。")
            # Changing the model mid-preview would silently mix two selection methods.
            if turn.model and turn.model != session.state.model:
                raise HTTPException(400, "如要更换模型，请开启新对话。")
            try:
                state, reply = answer(session.state, turn.message, corpus_dir, output_dir)
                if state.report is None:
                    files = {}
                elif state.report is session.state.report:
                    files = session.files
                else:
                    files = publish_run(state.report)
            except (OSError, ValueError, RuntimeError) as exc:
                raise HTTPException(400, str(exc)) from exc
            session.state, session.files = state, files
            session.revision += 1
            if not turn.session_id:
                with registry_lock:
                    sessions[key] = session
            public = ("slide_id", "deck_title", "title", "slide_number", "source_url", "evidence", "reason",
                      "publisher", "author", "stage")
            selected = [{k: row.get(k) for k in public} for row in state.selected]
            return {
                "session_id": key, "revision": session.revision, "phase": state.phase, "reply": reply,
                "topic": state.topic, "requested_pages": state.pages, "selected_pages": len(selected),
                "source_decks": len({row["deck_id"] for row in state.selected}),
                "index": {k: state.stats.get(k, 0) for k in ("decks", "slides")},
                "selected": selected, "model": state.model if state.used_model else "",
                "interpretation_model_called": state.interpretation_model_called,
                "downloads": files.get("downloads", {}), "template_url": files.get("template_url"),
            }
