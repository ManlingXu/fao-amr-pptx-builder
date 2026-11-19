from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import BoundedSemaphore
from uuid import uuid4

from .models import SlideDocument
from .providers.base import STALE, KnowledgeProvider
from .search import period

logger = logging.getLogger(__name__)
MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def provenance(slide: SlideDocument) -> dict:
    return {
        "slideId": slide.id,
        "deckName": slide.deck_name,
        "slideNumber": slide.slide_number,
        "title": slide.title,
        "url": slide.source_url,
        "reportDate": period(slide) or None,
        "effectiveYear": slide.effective_year,
        "dateConfidence": slide.date_confidence,
        "dateReason": slide.date_reason,
        "sourceHash": slide.source_hash,
    }


class DraftJobs:
    """One process, bounded queue, atomic JSON status and private immutable inputs per job."""

    def __init__(self, root: Path, provider: KnowledgeProvider):
        self.root = root
        self.provider = provider
        self.pool = None
        self.slots = BoundedSemaphore(12)

    def start(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for status in self.root.glob("*/status.json"):
            record = json.loads(status.read_text(encoding="utf-8"))
            if record["status"] in {"running", "queued"}:
                self._write(
                    {
                        **record,
                        "status": "failed",
                        "error": "The service restarted. Confirm and submit a new draft.",
                    }
                )
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="draft")

    def stop(self):
        if self.pool is not None:
            self.pool.shutdown(wait=True)
            self.pool = None

    def _write(self, record):
        folder = self.root / record["jobId"]
        with NamedTemporaryFile(mode="w", dir=folder, encoding="utf-8", delete=False) as output:
            json.dump(record, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(output.name, folder / "status.json")

    def submit(self, owner: str, title: str, slides: list[SlideDocument]) -> dict:
        if self.pool is None or not self.slots.acquire(blocking=False):
            raise OverflowError("Draft queue is busy. Try again shortly.")
        try:
            job_id = uuid4().hex
            folder = self.root / job_id
            folder.mkdir(mode=0o700)
            record = {
                "jobId": job_id,
                "status": "queued",
                "statusUrl": f"/api/drafts/{job_id}",
                "title": title,
                "owner": owner,
                "warnings": [],
                "sourceMap": [],
                "webUrl": None,
                "downloadUrl": None,
                "error": None,
            }
            self._write(record)
            self.pool.submit(self._build, record.copy(), slides)
            return {key: record[key] for key in ("jobId", "status", "statusUrl")}
        except Exception:
            self.slots.release()
            raise

    def _build(self, record, slides):
        job_id = record["jobId"]
        folder = self.root / job_id
        try:
            record["status"] = "running"
            self._write(record)
            with TemporaryDirectory(dir=folder) as scratch:
                work = Path(scratch)
                paths = self.provider.snapshot(slides, work / "sources")
                selections = [(paths[s.source_key], s.slide_number) for s in slides]
                from .assembly import assemble_slides

                output = work / "assembled.pptx"
                report = assemble_slides(selections, output)
                if output.stat().st_size > 128 * 1024 * 1024:
                    raise ValueError("Draft exceeds the 128 MiB limit.")
                filename = f"{safe_title(record['title'])}-{job_id}.pptx"
                url = self.provider.publish(output, filename)
                os.replace(output, folder / "draft.pptx")
            record.update(
                status="completed",
                webUrl=url,
                downloadUrl=f"/api/drafts/{job_id}/file",
                warnings=report.get("warnings", []),
                sourceMap=[{"outputSlide": n, **provenance(s)} for n, s in enumerate(slides, 1)],
            )
        except Exception as exc:
            logger.warning("Draft %s failed (%s)", job_id, type(exc).__name__)
            record["status"] = "failed"
            record["error"] = _safe_error(exc)
        finally:
            try:
                self._write(record)
            finally:
                self.slots.release()

    def get(self, job_id: str, owner: str) -> dict:
        if not re.fullmatch("[0-9a-f]{32}", job_id):
            raise KeyError(job_id)
        try:
            record = json.loads((self.root / job_id / "status.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(job_id) from None
        if record.pop("owner") != owner:
            raise KeyError(job_id)
        return record


def safe_title(title: str) -> str:
    return re.sub(r"[^\w -]", "_", title).strip(" .")[:64] or "Draft"


def _safe_error(exc: Exception) -> str:
    msg = str(exc)
    if msg == STALE or isinstance(exc, FileNotFoundError):
        return STALE
    if "limit" in msg.lower() or "exceed" in msg.lower():
        return "The selection exceeds the pilot package or size limits."
    if any(word in msg.lower() for word in ("canvas", "dimension", "slide size", "aspect ratio")):
        return "The selected source slides use different slide sizes."
    if isinstance(exc, ValueError):
        return "The slide selection contains an unsupported or invalid PowerPoint feature. Select different slides."
    return "Unable to assemble or publish the draft. Check source access and output permissions."
