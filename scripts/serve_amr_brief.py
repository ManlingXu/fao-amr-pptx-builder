"""Run the single-user AMR presentation workbench on the loopback interface."""
from __future__ import annotations

import argparse
import html
import re
import secrets
import sys
import webbrowser
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from presentation_search.templates import MAX_TEMPLATE_BYTES
from scripts.amr_conversation_routes import register_conversation_routes
from scripts.prepare_amr_corpus import describe_corpus

CHAT = Path(__file__).with_name("amr_conversation.html")
CLASSIC = Path(__file__).with_name("amr_workbench.html")
FILES = {"draft": "draft.pptx", "styled": "styled.pptx", "sources": "source_map.json"}
PUBLIC_FIELDS = ("deck_title", "title", "slide_number", "source_url", "evidence", "model_evidence",
                 "reason", "publisher", "author", "stage")


def _upload(upload: UploadFile | None, folder: Path) -> Path | None:
    if upload is None or not upload.filename:
        return None
    ext = Path(upload.filename).suffix.lower()
    if ext not in {".pptx", ".potx"}:
        raise HTTPException(400, "请上传 .pptx 或 .potx 模板文件。")
    contents = upload.file.read(MAX_TEMPLATE_BYTES + 1)
    if not contents or len(contents) > MAX_TEMPLATE_BYTES:
        raise HTTPException(400, "模板大小应为 1 字节至 16 MiB。")
    path = folder / ("design" + ext)
    path.write_bytes(contents)
    return path


def create_demo_app(corpus_dir: Path, output_dir: Path, *, build=None, restyle=None) -> FastAPI:
    """Only opaque IDs from this launch can be used to access generated files."""
    corpus_dir, output_dir = Path(corpus_dir).resolve(), Path(output_dir).resolve()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    token = secrets.token_urlsafe(32)
    app.state.launch_id = secrets.token_hex(12)
    runs: dict[str, dict[str, Path]] = {}

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            origin_ok = not origin or origin == str(request.base_url).rstrip("/")
            if not origin_ok or not secrets.compare_digest(
                request.headers.get("x-demo-token", "").encode(), token.encode()
            ):
                return JSONResponse({"detail": "请刷新本地演示页面后重试。"}, 403)
            length = request.headers.get("content-length", "")
            if not length.isascii() or not length.isdigit():
                return JSONResponse({"detail": "需要提供文件大小。"}, 411)
            if len(length) > 9 or int(length) > MAX_TEMPLATE_BYTES + 65536:
                return JSONResponse({"detail": "模板大小上限为 16 MiB。"}, 413)
        response = await call_next(request)
        if request.url.path == "/":
            response.headers["X-AMR-Launch"] = app.state.launch_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; script-src 'nonce-{token}'; style-src 'unsafe-inline'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    def render_page(source: Path):
        coverage = describe_corpus(corpus_dir)
        verified = coverage["verified_decks"]
        slides = coverage["verified_slides"]
        reviewed = coverage["reviewed_decks"]
        catalog = coverage["catalog_decks"]
        if not verified:
            scope = "本地资料库尚未就绪"
            note = "请用 start-amr.cmd 从正式目录下载并校验课件，然后刷新页面。"
        elif coverage["full_catalog_attempted"] and coverage["is_reviewed_corpus"]:
            scope = f"正式目录 {catalog} 份 · 本地核验 {verified} 份 · {slides:,} 页"
            note = "已尝试下载完整目录。默认跨全部本地已核验课件和所有领域检索，逐页出处见大纲。"
        elif reviewed == verified and reviewed < catalog:
            scope = f"当前子集 {reviewed} / {catalog} 份 · {slides:,} 页"
            note = "当前启动目录只含部分正式课件。双击 start-amr.cmd 可切换到完整正式目录。"
        else:
            scope = f"当前资料库 {verified} 份 · {slides:,} 页"
            note = f"已挂载的课件中有 {reviewed} 份匹配正式目录。默认检索这个目录里的全部已核验课件。"
        values = {"TOKEN": token, "SCOPE": scope, "SCOPE_NOTE": note, "CORPUS_DIR": str(corpus_dir),
                  "CORPUS": scope}
        return re.sub(r"\{\{(TOKEN|SCOPE|SCOPE_NOTE|CORPUS_DIR|CORPUS)\}\}",
                      lambda m: html.escape(values[m[1]]), source.read_text(encoding="utf-8"))

    @app.get("/", response_class=HTMLResponse)
    def workspace():
        return render_page(CHAT)

    @app.get("/classic", response_class=HTMLResponse)
    def classic():
        return render_page(CLASSIC)

    @app.post("/briefs")
    def create_brief(topic: str = Form(..., min_length=1, max_length=500),
                     pages: int = Form(..., ge=1, le=20), sectors: list[str] = Form(default=[]),
                     model: str = Form(default="", max_length=120), reflow: bool = Form(default=False),
                     template: UploadFile | None = File(default=None)):
        if set(sectors) - {"animal", "one-health", "human"}:
            raise HTTPException(400, "请选择界面列出的领域。")
        if model and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}", model):
            raise HTTPException(400, "请填写 ollama list 列出的模型名称。")
        with TemporaryDirectory(prefix="amr-ui-") as tmp:
            uploaded = _upload(template, Path(tmp))
            try:
                build_fn = build
                if build_fn is None:
                    from presentation_search.local_brief import build_brief as build_fn
                report = build_fn(corpus_dir, output_dir, topic=topic.strip(), pages=pages,
                                  sectors=sectors, model=model.strip() or None,
                                  template=uploaded, reflow=reflow)
            except (ValueError, OSError, RuntimeError) as error:
                raise HTTPException(400, str(error)) from error
        return publish_run({**report, "topic": topic.strip()})

    def publish_run(report):
        run_dir = Path(report["output_directory"]).resolve()
        if not run_dir.is_relative_to(output_dir) or run_dir == output_dir:
            raise RuntimeError("Output directory is outside this session's workspace")
        key = secrets.token_urlsafe(18)
        allowed = {name: run_dir / filename for name, filename in FILES.items()
                   if (run_dir / filename).is_file()}
        runs[key] = allowed
        sources = [{field: row.get(field) for field in PUBLIC_FIELDS}
                   for row in report["selected"]]
        return {"topic": report["topic"], "status": report["status"], "requested_pages": report["requested_pages"],
                "selected_pages": report["selected_pages"], "selected": sources,
                "model": report.get("model_used", "") if report.get("llm_called") else "",
                "downloads": {name: f"/briefs/{key}/files/{name}" for name in allowed},
                "template_url": f"/briefs/{key}/template" if "draft" in allowed else None}

    register_conversation_routes(app, corpus_dir, output_dir, publish_run)

    @app.post("/briefs/{key}/template")
    def apply_design(key: str, template: UploadFile = File(...)):
        files = runs.get(key, {})
        if "draft" not in files:
            raise HTTPException(404, "请先生成初稿。")
        with TemporaryDirectory(prefix="amr-design-") as tmp:
            uploaded = _upload(template, Path(tmp))
            if uploaded is None:
                raise HTTPException(400, "请先选择模板文件。")
            revision = "restyled-" + secrets.token_hex(6)
            target = files["draft"].parent / (revision + ".pptx")
            try:
                restyle_fn = restyle
                if restyle_fn is None:
                    from presentation_search.local_brief import restyle_brief as restyle_fn
                restyle_fn(files["draft"], uploaded, target)
            except (OSError, ValueError, RuntimeError) as error:
                raise HTTPException(400, str(error)) from error
            files[revision] = target
        return {"download": f"/briefs/{key}/files/{revision}"}

    @app.get("/briefs/{key}/files/{kind}")
    def download(key: str, kind: str):
        path = runs.get(key, {}).get(kind)
        if path is None or not path.is_file():
            raise HTTPException(404, "这次会话中没有该文件。")
        return FileResponse(path, filename=path.name)

    return app


def _open_when_ready(port: int, launch_id: str):
    url = f"http://127.0.0.1:{port}/"
    deadline = monotonic() + 20
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200 and response.headers.get("X-AMR-Launch") == launch_id:
                    webbrowser.open(url)
                return  # Another process may still own this port.
        except (URLError, OSError):
            sleep(.25)


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "amr")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "amr-briefs")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true", help="Open the workbench when it is ready.")
    args = parser.parse_args()
    app = create_demo_app(args.corpus_dir, args.output_dir)
    if args.open_browser:
        Thread(target=_open_when_ready, args=(args.port, app.state.launch_id), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1",
                port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
