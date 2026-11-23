"""Owner-scoped, revisioned presentation storylines with grounded slide IDs.

The conversational LLM proposes section titles and search terms. This store
persists only slide IDs actually found in the approved source index. Each edit
is a full, optimistic revision; generation requires approval of that revision.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import uuid4

from .search import SearchIndex
from .jobs import provenance
from .templates import TemplateStore


_ID = re.compile(r"[0-9a-f]{32}\Z")


class PlanConflict(Exception):
    """The caller holds an outdated plan revision."""


class PlanStore:
    def __init__(self, root: Path, index: SearchIndex, templates: TemplateStore):
        self.root = Path(root)
        self.index = index
        self.templates = templates
        self._lock = RLock()

    def start(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, plan_id: str) -> Path:
        if not _ID.fullmatch(plan_id):
            raise KeyError("Plan not found")
        return self.root / f"{plan_id}.json"

    def _get(self, plan_id: str, owner: str) -> dict:
        try:
            data = json.loads(self._path(plan_id).read_text(encoding="utf-8"))
        except (ValueError, FileNotFoundError):
            raise KeyError("Plan not found") from None
        if data.get("owner") != owner:
            raise KeyError("Plan not found")
        return data

    @staticmethod
    def _public(data: dict) -> dict:
        return {k: v for k, v in data.items() if k != "owner"}

    def _write(self, data: dict):
        target = self._path(data["planId"])
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                prefix=".plan-", delete=False) as f:
            tmp = Path(f.name)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def _validate_slides(self, sections: list[dict]):
        ids = [sid for section in sections for sid in section.get("slideIds", [])]
        if len(ids) > 20 or len(ids) != len(set(ids)):
            raise ValueError("A plan allows at most 20 unique selected slides")
        try:
            slides = self.index.lookup(ids)
        except KeyError:
            raise ValueError("A selected slide no longer exists. Search again.") from None
        return [provenance(slide) for slide in slides]

    def create(self, owner: str, title: str, audience: str, purpose: str,
               sections: list[dict], template_id: str | None = None) -> dict:
        if template_id is not None:
            self.templates.get(template_id, owner)
        with self._lock:
            used: set[str] = set()
            selected = []
            for section in sections:
                chosen = []
                # The index supplies evidence; Copilot supplies the storyline.
                for result in self.index.search(section["query"], limit=15, latest_only=True):
                    sid = result.slide.id
                    if sid in used:
                        continue
                    if len(chosen) >= section["slideCount"] or len(used) >= 20:
                        break
                    chosen.append(sid)
                    used.add(sid)
                selected.append({
                    "title": section["title"], "query": section["query"],
                    "notes": section.get("notes", ""),
                    "slideIds": chosen,
                    "gap": len(chosen) < section["slideCount"],
                    "requestedSlides": section["slideCount"],
                })
            sources = self._validate_slides(selected)
            plan = {
                "planId": uuid4().hex, "owner": owner, "revision": 1,
                "title": title, "audience": audience, "purpose": purpose,
                "templateId": template_id, "sections": selected,
                "sourceMap": sources,
                "needsReview": any(s["gap"] for s in selected),
                "requiresUserConfirmation": True,
                "isReadyForDraft": bool(sources) and not any(s["gap"] for s in selected),
            }
            self._write(plan)
            return self._public(plan)

    def get(self, owner: str, plan_id: str) -> dict:
        with self._lock:
            return self._public(self._get(plan_id, owner))

    def revise(self, owner: str, plan_id: str, expected_revision: int,
               sections: list[dict], template_id: str | None,
               template_provided: bool = False) -> dict:
        with self._lock:
            old = self._get(plan_id, owner)
            if not template_provided:
                template_id = old["templateId"]
            if template_id is not None:
                self.templates.get(template_id, owner)
            if old["revision"] != expected_revision:
                raise PlanConflict("Plan changed. Retrieve the latest revision and confirm again.")
            sources = self._validate_slides(sections)
            revised_sections = [
                {
                    "title": s["title"], "query": s["query"],
                    "notes": s.get("notes", ""), "slideIds": s["slideIds"],
                    "requestedSlides": len(s["slideIds"]), "gap": not bool(s["slideIds"]),
                }
                for s in sections
            ]
            updated = {
                **old, "revision": old["revision"] + 1,
                "sections": revised_sections, "templateId": template_id,
                "sourceMap": sources,
                "needsReview": any(not s["slideIds"] for s in revised_sections),
                "isReadyForDraft": bool(sources) and all(s["slideIds"] for s in revised_sections),
            }
            self._write(updated)
            return self._public(updated)

    def submit_draft(self, owner: str, plan_id: str, revision: int, submit):
        """Validate and enqueue under one lock; edits cannot race confirmation."""
        with self._lock:
            plan = self._get(plan_id, owner)
            if plan["revision"] != revision:
                raise PlanConflict("The plan revision changed. Review and confirm again.")
            if not plan["isReadyForDraft"]:
                raise ValueError("Plan has empty or underfilled sections; review before drafting")
            ids = [sid for section in plan["sections"] for sid in section["slideIds"]]
            try:
                slides = self.index.lookup(ids)
            except KeyError:
                raise ValueError("A selected source was removed from the index") from None
            return submit(self._public(plan), slides)
