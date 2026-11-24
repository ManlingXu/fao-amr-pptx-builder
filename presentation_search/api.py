from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

from .auth import Identity, key_matches
from .config import Settings, get_settings
from .indexer import rebuild_index
from .jobs import MIME, DraftJobs, provenance, safe_title
from .plans import PlanStore, PlanConflict
from .providers.local import LocalKnowledgeProvider
from .providers.sharepoint import SharePointKnowledgeProvider
from .search import SearchIndex
from .slide_analysis import analyze_slides
from .layout_validation import validate_layout
from .templates import MAX_TEMPLATE_BASE64, TemplateStore

TemplateId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$", min_length=32, max_length=32)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class TemplateUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
    content_base64: Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEMPLATE_BASE64)]


class AnalyzeSlidesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=20
    )

    @field_validator("slide_ids")
    @classmethod
    def validate_ids(cls, ids):
        if len(ids) != len(set(ids)):
            raise ValueError("Slide IDs must be unique")
        return ids


class SlideLayoutOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_slide: int = Field(ge=1, le=20)
    layout_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ApplyTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: TemplateId
    title: Title | None = None
    confirmed: StrictBool
    layout_overrides: list[SlideLayoutOverride] = Field(default_factory=list, max_length=20)

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value):
        if not value:
            raise ValueError("Explicit confirmation is required")
        return value

    @field_validator("layout_overrides")
    @classmethod
    def validate_layout_overrides(cls, overrides):
        slides = [item.output_slide for item in overrides]
        if len(slides) != len(set(slides)):
            raise ValueError("A slide can have only one template layout override")
        return overrides



class PlanSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    slide_count: int = Field(ge=1, le=8)
    notes: str = Field(default="", max_length=600)


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    audience: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    purpose: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    sections: list[PlanSectionRequest] = Field(min_length=1, max_length=8)
    template_id: TemplateId | None = None


class PlanRevisionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    slide_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = Field(
        default_factory=list, max_length=20
    )
    notes: str = Field(default="", max_length=600)


class PlanRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    sections: list[PlanRevisionSection] = Field(min_length=1, max_length=8)
    template_id: TemplateId | None = None


class PlanFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value):
        if not value:
            raise ValueError("Confirm the exact current plan revision before generating a draft")
        return value


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    limit: int = Field(default=15, ge=1, le=15)
    latest_only: bool = True


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    slide_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=20
    )
    confirmed: StrictBool
    template_id: TemplateId | None = None

    @field_validator("slide_ids")
    @classmethod
    def validate_ids(cls, ids):
        if len(ids) != len(set(ids)):
            raise ValueError("Slide IDs must be unique")
        return ids

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value):
        if not value:
            raise ValueError("Explicit confirmation is required")
        return value


def _serialize_result(result) -> dict:
    return {
        **provenance(result.slide),
        "snippet": result.slide.text[:1200],
        "freshness": result.freshness_status,
        "relatedVersions": result.related_versions,
        "relevanceScore": result.relevance_score,
        "freshnessScore": result.freshness_score,
        "finalScore": result.final_score,
        "explanation": result.explanation,
    }


def _copilot_result(result) -> dict[str, str]:
    slide = result.slide
    source = f"Source: {slide.deck_name}, slide {slide.slide_number}."
    period = slide.report_date or slide.effective_year or "unknown"
    body = " ".join(slide.text.split())[:950]
    return {
        "title": f"{slide.deck_name} — Slide {slide.slide_number} — {slide.title}",
        "snippet": f"{body}\n\n{source} Report period: {period}. {result.freshness_status}.",
        "url": slide.source_url,
    }


def create_app(index: SearchIndex | None = None, settings: Settings | None = None) -> FastAPI:
    active_index = index if index is not None else SearchIndex()
    settings = settings or get_settings()
    provider = (
        SharePointKnowledgeProvider(settings)
        if settings.knowledge_provider == "sharepoint"
        else LocalKnowledgeProvider(settings.local_presentation_path)
    )
    identity = Identity(settings)
    jobs = DraftJobs(settings.drafts_path, provider)
    templates = TemplateStore(settings.drafts_path / "templates")
    plans = PlanStore(settings.drafts_path / "plans", active_index, templates)
    indexing = Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        identity.validate()
        source_root = settings.local_presentation_path.resolve()
        output_root = settings.drafts_path.resolve()
        if settings.knowledge_provider == "local" and output_root.is_relative_to(source_root):
            raise ValueError("Place DRAFTS_PATH outside the approved source directory")
        if index is None:
            rebuild_index(provider, active_index)
        jobs.start()
        plans.start()
        try:
            yield
        finally:
            jobs.stop()

    app = FastAPI(title="Teams Presentation Assistant", version="1.3.0", lifespan=lifespan)
    app.state.index = active_index
    app.state.provider = provider
    app.state.settings = settings
    app.state.plans = plans
    auth = Depends(identity.principal)

    @app.get("/health")
    def health():
        return {"status": "ok", "slides": len(active_index), "provider": settings.knowledge_provider}

    @app.get("/api/copilot/search", dependencies=[auth])
    def copilot_search(q: str = Query(min_length=1, max_length=1000), limit: int = Query(default=15, ge=1)):
        return {"query": q, "results": [_copilot_result(r) for r in active_index.search(q, min(limit, 15))]}

    @app.post("/api/search", dependencies=[auth])
    def search(request: SearchRequest):
        results = active_index.search(request.query, request.limit, request.latest_only)
        return {"query": request.query, "results": [_serialize_result(result) for result in results]}

    @app.post("/api/slides/analyze", dependencies=[auth])
    def analyze_selected_slides(request: AnalyzeSlidesRequest):
        try:
            slides = active_index.lookup(request.slide_ids)
        except KeyError:
            raise HTTPException(
                409, "A selected slide is no longer indexed. Search and select it again."
            ) from None
        try:
            with TemporaryDirectory() as directory:
                paths = provider.snapshot(slides, Path(directory))
                by_source: dict[str, list] = {}
                for slide in slides:
                    by_source.setdefault(slide.source_key, []).append(slide)
                analyzed = {}
                for source_key, source_slides in by_source.items():
                    results = analyze_slides(
                        paths[source_key], [slide.slide_number for slide in source_slides]
                    )
                    analyzed.update(zip((slide.id for slide in source_slides), results))
        except (ValueError, FileNotFoundError):
            raise HTTPException(
                409, "A selected source changed or is unavailable. Refresh the index and search again."
            ) from None

        response = []
        for slide in slides:
            analysis = analyzed[slide.id]
            counts = analysis["shape_counts"]
            response.append(
                {
                    **provenance(slide),
                    "wordCount": analysis["word_count"],
                    "occupancyRatio": analysis["occupancy_ratio"],
                    "textShapeCount": counts["text_boxes"],
                    "pictureCount": counts["pictures"],
                    "tableCount": counts["tables"],
                    "chartCount": counts["charts"],
                    "groupCount": counts["groups"],
                    "contentType": analysis["content_type"],
                    "density": analysis["density"],
                    "recommendedLayoutAction": analysis["recommended_layout_action"],
                }
            )
        return {
            "slides": response,
            "limitations": [
                "This is structural PowerPoint analysis; it does not interpret picture meaning."
            ],
        }

    @app.get("/api/slides/{slide_id}/versions", dependencies=[auth])
    def versions(slide_id: str):
        try:
            matched = active_index.versions(slide_id)
        except KeyError:
            raise HTTPException(404, "Slide not found") from None
        return {"slideId": slide_id, "versions": [provenance(s) for s in matched]}

    @app.post("/api/plans", status_code=201)
    def create_plan(request: PlanCreateRequest, owner: str = auth):
        sections = [{"title": s.title, "query": s.query,
                     "slideCount": s.slide_count, "notes": s.notes}
                    for s in request.sections]
        try:
            return plans.create(owner, request.title, request.audience, request.purpose,
                                sections, request.template_id)
        except KeyError:
            raise HTTPException(404, "Template not found for this user") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str, owner: str = auth):
        try:
            return plans.get(owner, plan_id)
        except KeyError:
            raise HTTPException(404, "Plan not found") from None

    @app.put("/api/plans/{plan_id}")
    def revise_plan(plan_id: str, request: PlanRevisionRequest, owner: str = auth):
        sections = [{"title": s.title, "query": s.query,
                     "slideIds": s.slide_ids, "notes": s.notes}
                    for s in request.sections]
        try:
            return plans.revise(owner, plan_id, request.expected_revision,
                                sections, request.template_id,
                                template_provided=("template_id" in request.model_fields_set))
        except KeyError:
            raise HTTPException(404, "Plan or template not found for this user") from None
        except PlanConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/api/plans/{plan_id}/draft", status_code=202)
    def create_plan_draft(plan_id: str, request: PlanFinalizeRequest, owner: str = auth):
        def submit(plan, slides):
            template = owned_template(plan["templateId"], owner) if plan["templateId"] else None
            return jobs.submit(owner, plan["title"], slides, template)

        try:
            return plans.submit_draft(owner, plan_id, request.expected_revision, submit)
        except KeyError:
            raise HTTPException(404, "Plan or template not found") from None
        except PlanConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except OverflowError:
            raise HTTPException(429, "Draft queue is busy. Try again shortly.") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/slides/{slide_id}/source", dependencies=[auth])
    def local_source(slide_id: str):
        if settings.knowledge_provider != "local":
            raise HTTPException(404, "Use the SharePoint document URL")
        try:
            (slide,) = active_index.lookup([slide_id])
            with TemporaryDirectory() as directory:
                paths = provider.snapshot([slide], Path(directory))
                content = paths[slide.source_key].read_bytes()
        except KeyError:
            raise HTTPException(404, "Slide not found") from None
        except (ValueError, FileNotFoundError):
            raise HTTPException(409, "Source changed. Refresh the index and search again.") from None
        return Response(
            content, media_type=MIME, headers={"Content-Disposition": 'attachment; filename="source.pptx"'}
        )

    @app.post("/api/drafts", status_code=202)
    def create_draft(request: DraftRequest, owner: str = auth):
        try:
            slides = active_index.lookup(request.slide_ids)
        except KeyError:
            raise HTTPException(
                409, "A selected slide is no longer indexed. Search and confirm again."
            ) from None
        template = owned_template(request.template_id, owner) if request.template_id else None
        try:
            return jobs.submit(owner, request.title, slides, template)
        except OverflowError:
            raise HTTPException(429, "Draft queue is busy. Try again shortly.") from None

    @app.post("/api/templates", status_code=201)
    def upload_template(request: TemplateUploadRequest, owner: str = auth):
        try:
            return templates.create(owner, request.file_name, request.content_base64)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    def owned_template(template_id: str, owner: str):
        try:
            return templates.get(template_id, owner)
        except KeyError:
            raise HTTPException(404, "Template not found. Upload the template again.") from None

    @app.get("/api/templates/{template_id}")
    def template_metadata(template_id: str, owner: str = auth):
        metadata, _ = owned_template(template_id, owner)
        return metadata

    @app.post("/api/drafts/{job_id}/template", status_code=202)
    def replace_template(job_id: str, request: ApplyTemplateRequest, owner: str = auth):
        source = owned_job(job_id, owner)
        if source["status"] != "completed":
            raise HTTPException(409, "The source draft is not ready for a template change.")
        template = owned_template(request.template_id, owner)
        layout_names = template[0]["layoutNames"]
        slide_count = len(source["sourceMap"])
        layout_overrides = {}
        for override in request.layout_overrides:
            if override.output_slide > slide_count:
                raise HTTPException(
                    422, f"Output slide {override.output_slide} does not exist in this draft."
                )
            occurrences = layout_names.count(override.layout_name)
            if occurrences == 0:
                raise HTTPException(
                    422, f"Template layout '{override.layout_name}' does not exist in this template."
                )
            if occurrences > 1:
                raise HTTPException(
                    422, f"Template layout '{override.layout_name}' is ambiguous in this template."
                )
            layout_overrides[override.output_slide] = override.layout_name
        try:
            return jobs.submit_template(
                owner,
                source,
                request.title or source["title"],
                template,
                layout_overrides=layout_overrides,
            )
        except OverflowError:
            raise HTTPException(429, "Draft queue is busy. Try again shortly.") from None

    def owned_job(job_id: str, owner: str = auth):
        try:
            return jobs.get(job_id, owner)
        except KeyError:
            raise HTTPException(404, "Draft not found") from None

    @app.get("/api/drafts/{job_id}")
    def get_draft(job=Depends(owned_job)):
        return job

    @app.get("/api/drafts/{job_id}/layout-report")
    def get_layout_report(job=Depends(owned_job)):
        if job["status"] != "completed":
            raise HTTPException(409, "The draft is not ready for layout review")
        try:
            report = validate_layout(settings.drafts_path / job["jobId"] / "draft.pptx")
        except (OSError, ValueError, KeyError):
            raise HTTPException(409, "The completed draft could not be inspected") from None
        return {"jobId": job["jobId"], "slideCount": report["summary"]["slides"], **report}

    @app.get("/api/drafts/{job_id}/file")
    def download(job=Depends(owned_job)):
        if job["status"] != "completed":
            raise HTTPException(409, "The draft is not ready for download")
        return FileResponse(
            settings.drafts_path / job["jobId"] / "draft.pptx",
            media_type=MIME,
            filename=safe_title(job["title"]) + ".pptx",
        )

    @app.post("/api/admin/reindex")
    def reindex(x_admin_key: str = Header(default="")):
        if not settings.admin_api_key.strip():
            raise HTTPException(403, "Administrative reindexing is disabled")
        if not key_matches(x_admin_key, settings.admin_api_key):
            raise HTTPException(401, "Invalid admin key")
        if not indexing.acquire(blocking=False):
            raise HTTPException(409, "An index refresh is already running")
        try:
            report = rebuild_index(provider, active_index)
        except Exception:
            raise HTTPException(503, "Unable to refresh the approved library") from None
        finally:
            indexing.release()
        return {"status": "ok", **report}

    return app


app = create_app()
