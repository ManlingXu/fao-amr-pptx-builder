"""Run the PPT Builder dual-mode web app with isolated, temporary workspaces."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request as URLRequest, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from presentation_search.templates import MAX_TEMPLATE_BYTES

COOKIE = "ppt_studio_session"
LOCAL = {"localhost", "127.0.0.1", "::1"}
TTL = 4 * 3600


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def positive_env(name, default, minimum=0):
    value = int(os.environ.get(name, default))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


class Budget:
    """Reserve before network I/O. Failed/incomplete requests keep their reservation."""

    def __init__(self, path):
        self.path = path
        self.calls = positive_env("PPT_STUDIO_MAX_CALLS", 12)
        self.tokens = positive_env("PPT_STUDIO_TOKEN_BUDGET", 60000)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY, calls INTEGER, tokens INTEGER)")
            db.execute("INSERT OR IGNORE INTO ledger VALUES (1, 0, 0)")

    def reserve(self, prompt, max_output_tokens):
        if not isinstance(prompt, str) or not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("Invalid model reservation.")
        # UTF-8 byte length conservatively bounds ordinary text token counts.
        amount = len(prompt.encode("utf-8")) + max_output_tokens + 256
        with sqlite3.connect(self.path) as db:
            changed = db.execute(
                "UPDATE ledger SET calls=calls+1, tokens=tokens+? WHERE id=1 AND calls<? AND tokens+?<=?",
                (amount, self.calls, amount, self.tokens),
            ).rowcount
        if not changed:
            raise ValueError("OpenAI request declined. The host's call or token allowance is exhausted.")
        return True

    def usage(self):
        with sqlite3.connect(self.path) as db:
            calls, tokens = db.execute("SELECT calls,tokens FROM ledger WHERE id=1").fetchone()
        return {"model_calls": calls, "tokens_reserved": tokens}


@dataclass
class Session:
    role: str
    folder: Path
    service: object
    state: object
    session_id: str = field(default_factory=lambda: secrets.token_hex(10))
    lock: object = field(default_factory=threading.RLock)
    touched: float = field(default_factory=time.monotonic)
    files: dict = field(default_factory=dict)
    retired: bool = False


class StudioHost:
    def __init__(self, corpus, workspace, ledger_dir, *, tunnel=False, service_factory=None):
        self.corpus = Path(corpus)
        self.workspace = Path(workspace)
        self.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.budget = Budget(ledger_dir / "budget.sqlite3")
        self.passwords = {}
        self.local_auto = not tunnel and not os.environ.get("PPT_STUDIO_USER_PASSWORD")
        for role, key in (("user", "PPT_STUDIO_USER_PASSWORD"), ("developer", "PPT_STUDIO_ADMIN_PASSWORD")):
            value = os.environ.get(key) or secrets.token_urlsafe(20)
            if len(value) < 12:
                raise ValueError(f"{key} needs at least 12 characters.")
            self.passwords[role] = value
        if self.passwords["user"] == self.passwords["developer"]:
            raise ValueError("Set different user and developer passwords.")
        self.tunnel = tunnel
        self.remote_host = None
        self.service_factory = service_factory
        self.lock = threading.RLock()
        self.sessions = {}
        self.events = deque(maxlen=80)
        self.timestamps = {}
        self.rpm = positive_env("PPT_STUDIO_RPM", 30, 1)
        self.started = time.monotonic()
        self.stats = {"decks": None, "slides": None}
        self.stop_token = secrets.token_urlsafe(36)
        self.shutdown = lambda: None

    def enabled(self, role):
        return bool(os.getenv("PPT_STUDIO_ENABLE_OPENAI") == "1" and os.getenv("OPENAI_API_KEY")
                    and (role == "developer" or role == "user" and os.getenv("PPT_STUDIO_GUEST_OPENAI") == "1"))

    def release(self, s):
        # A file or turn already in progress may finish before its directory is reclaimed.
        with s.lock:
            s.retired = True
            shutil.rmtree(s.folder, ignore_errors=True)

    def new(self, role):
        now = time.monotonic()
        with self.lock:
            for key, prev in list(self.sessions.items()):
                if prev.touched + TTL < now and prev.lock.acquire(blocking=False):
                    try:
                        self.sessions.pop(key)
                        self.release(prev)
                    finally:
                        prev.lock.release()
            if len(self.sessions) >= 64:
                raise HTTPException(429, "The host has reached its active-session limit.")
            folder = Path(tempfile.mkdtemp(dir=self.workspace, prefix="brief-"))
            try:
                factory = self.service_factory
                if factory is None:
                    from presentation_search.studio_service import StudioService
                    factory = StudioService
                service = factory(self.corpus, folder)
                s = Session(role, folder, service, service.new_session())
            except Exception:
                shutil.rmtree(folder, ignore_errors=True)
                raise
            token = secrets.token_urlsafe(32)
            self.sessions[token] = s
            return token, s

    def lookup(self, request, required=True):
        with self.lock:
            s = self.sessions.get(request.cookies.get(COOKIE))
            if s and s.touched + TTL >= time.monotonic():
                s.touched = time.monotonic()
                return s
        if required:
            raise HTTPException(401, "Sign in to this local host.")
        return None

    def sign_in(self, request, role):
        # Changing mode should keep the conversation and its downloads. Rotate the
        # authentication cookie after successful password verification.
        previous = request.cookies.get(COOKIE)
        with self.lock:
            s = self.sessions.get(previous)
        if s is not None:
            with s.lock, self.lock:
                if self.sessions.get(previous) is s and s.touched + TTL >= time.monotonic():
                    del self.sessions[previous]
                    token = secrets.token_urlsafe(32)
                    s.role = role
                    s.touched = time.monotonic()
                    self.sessions[token] = s
                    return token, s
        return self.new(role)

    def remove(self, request):
        with self.lock:
            old = self.sessions.pop(request.cookies.get(COOKIE), None)
        if old:
            self.release(old)

    def limit(self, request, bucket, ceiling):
        ip = request.client.host if request.client else "local"
        if self.remote_host and request.url.hostname == self.remote_host:
            ip = request.headers.get("cf-connecting-ip", ip)
        key = (bucket, ip)
        now = time.monotonic()
        with self.lock:
            # Discard expired windows even when a visitor never comes back.
            for stale in [k for k, q in self.timestamps.items() if q[-1] <= now - 60]:
                del self.timestamps[stale]
            q = self.timestamps.setdefault(key, deque())
            while q and q[0] <= now - 60:
                q.popleft()
            if len(q) >= ceiling:
                raise HTTPException(429, "Too many requests. Try again in one minute.")
            q.append(now)

    def record(self, action, outcome):
        with self.lock:
            self.events.appendleft({"time": utc(), "action": action, "outcome": outcome})

    def status(self, s):
        role = s.role if s else None
        return {"authenticated": bool(s), "role": role, "sessionId": s.session_id if s else None,
                "requiresLogin": not bool(s), "modelAvailable": self.enabled(role),
                "runtime": "local", "tunnelEnabled": self.tunnel}

    def present(self, s, result):
        versions = []
        for version in result.get("versions", []):
            vid = str(version["id"])
            links = {}
            for kind, name in version["files"].items():
                # Only files explicitly returned by the exporter are ever served.
                name = str(name)
                if vid != Path(vid).name or name != Path(name).name:
                    raise ValueError("The exporter returned an unexpected filename.")
                path = (s.folder / vid / name).resolve()
                if not path.is_relative_to(s.folder.resolve()) or not path.is_file():
                    raise ValueError("The exporter returned an unavailable file.")
                s.files[(vid, name)] = path
                links[kind] = f"/api/files/{quote(vid, safe='')}/{quote(name, safe='')}"
            versions.append({**version, "files": links})
        stats = result.get("stats", {})
        with self.lock:
            self.stats.update({k: stats[k] for k in ("decks", "slides") if k in stats})
        return {**result, "versions": versions, "sessionId": s.session_id}


async def bounded_body(request, limit):
    data = bytearray()
    async for part in request.stream():
        if len(data) + len(part) > limit:
            raise HTTPException(413, "File or message exceeds the size limit.")
        data.extend(part)
    return bytes(data)


async def payload(request):
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Send a JSON object.")
    try:
        value = json.loads(await bounded_body(request, 65536))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON.")
    if not isinstance(value, dict):
        raise HTTPException(400, "Expected a JSON object.")
    return value


def create_app(host: StudioHost):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def boundary(req, next_handler):
        hostname = req.url.hostname
        if hostname not in LOCAL and (not host.remote_host or hostname != host.remote_host):
            return JSONResponse({"detail": "Unrecognized host."}, 403)
        if req.method == "POST":
            origin = req.headers.get("origin")
            expected = ("https" if hostname not in LOCAL else "http") + "://" + req.headers.get("host", "")
            if (origin and origin != expected) or req.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Same-origin requests are required."}, 403)
        response = await next_handler(req)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if req.url.path.startswith("/api/") or req.url.path.endswith("studio-config.json"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    def signed(req, token, s):
        response = JSONResponse(host.status(s))
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, samesite="strict",
                            secure=req.url.hostname not in LOCAL, path="/")
        return response

    @app.get("/api/status")
    @app.get("/api/session")
    def status(req: Request):
        s = host.lookup(req, False)
        if s is None and host.local_auto:
            host.limit(req, "sessions", 20)
            token, s = host.new("user")
            return signed(req, token, s)
        return host.status(s)

    @app.post("/api/login")
    async def login(req: Request):
        host.limit(req, "login", 12)
        body = await payload(req)
        role, password = body.get("role", "user"), body.get("password")
        if role not in ("developer", "user") or not isinstance(password, str) or not hmac.compare_digest(
                host.passwords[role].encode(), password.encode()):
            host.record("Sign in", "Declined")
            raise HTTPException(401, "Check the role and password.")
        token, s = await run_in_threadpool(host.sign_in, req, role)
        host.record("Sign in", "Accepted")
        return signed(req, token, s)

    @app.post("/api/logout")
    async def logout(req: Request):
        await payload(req)
        await run_in_threadpool(host.remove, req)
        response = JSONResponse(host.status(None))
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return response

    @app.post("/api/reset")
    async def reset(req: Request):
        s = host.lookup(req)
        host.limit(req, "sessions", 20)
        await payload(req)
        await run_in_threadpool(host.remove, req)
        token, s = await run_in_threadpool(host.new, s.role)
        return signed(req, token, s)

    def present_turn(s, action, message, settings):
        with s.lock:
            if s.retired:
                raise HTTPException(401, "This session has ended.")
            if settings.get("model") == "openai" and not host.enabled(s.role):
                raise HTTPException(403, "OpenAI is disabled for this role.")
            custom = s.folder / "template.pptx"
            def authorize_model(prompt, max_output_tokens):
                if not host.enabled(s.role):
                    raise ValueError("OpenAI is disabled for this role.")
                return host.budget.reserve(prompt, max_output_tokens)
            try:
                if action == "history":
                    data = s.service.snapshot(s.state)
                else:
                    data = s.service.turn(s.state, message, settings, action=action, reserve_model=authorize_model,
                                          template_path=custom if custom.is_file() else None)
                response = host.present(s, data)
            except ValueError as exc:
                host.record(action, "Declined")
                raise HTTPException(400, str(exc))
            except (OSError, RuntimeError) as exc:
                host.record(action, "Failed")
                raise HTTPException(503, "The local engine could not finish this operation. Check the source files or model configuration.") from exc
            if action != "history":
                host.record(action, "Completed")
            return response

    @app.get("/api/history")
    def history(req: Request):
        return present_turn(host.lookup(req), "history", "", {})

    @app.post("/api/export")
    @app.post("/api/chat")
    async def chat(req: Request):
        s = host.lookup(req)
        host.limit(req, "agent", host.rpm)
        body = await payload(req)
        action = "generate" if req.url.path == "/api/export" else body.get("action", "chat")
        msg, settings = body.get("message", ""), body.get("settings", {})
        if action not in ("generate", "chat") or not isinstance(msg, str) or len(msg) > 5000 or not isinstance(settings, dict):
            raise HTTPException(400, "Check the message, settings and action.")
        if "template" in body:
            settings["template"] = body["template"]
        return await run_in_threadpool(present_turn, s, action, msg.strip(), settings)

    @app.get("/api/files/{version}/{name}")
    def download(req: Request, version: str, name: str):
        s = host.lookup(req)
        with s.lock:
            path = s.files.get((version, name))
            if s.retired or path is None or not path.is_file():
                raise HTTPException(404, "File unavailable in this session.")
            stream = path.open("rb")
            length = path.stat().st_size
        def chunks():
            with stream:
                while block := stream.read(131072):
                    yield block
        media = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if name.endswith(".pptx") else "application/json" if name.endswith(".json") else "application/octet-stream"
        return StreamingResponse(chunks(), media_type=media, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}", "Content-Length": str(length)})

    @app.post("/api/template")
    async def upload(req: Request):
        s = host.lookup(req)
        host.limit(req, "agent", host.rpm)
        if req.headers.get("content-type", "").split(";")[0] not in (
                "application/octet-stream", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.openxmlformats-officedocument.presentationml.template"):
            raise HTTPException(415, "Upload the PowerPoint file body.")
        data = await bounded_body(req, MAX_TEMPLATE_BYTES)
        def save_template():
            from presentation_search.templating import inspect_template
            with s.lock:
                if s.retired:
                    raise HTTPException(401, "This session has ended.")
                tmp = s.folder / "upload.pptx"
                try:
                    tmp.write_bytes(data)
                    details = inspect_template(tmp)
                    tmp.replace(s.folder / "template.pptx")
                    return {"uploaded": True, "layoutNames": details["layoutNames"]}
                except (OSError, ValueError) as exc:
                    raise HTTPException(400, "The template must be a supported PowerPoint file.") from exc
                finally:
                    tmp.unlink(missing_ok=True)
        return await run_in_threadpool(save_template)

    def developer(req):
        s = host.lookup(req)
        if s.role != "developer":
            raise HTTPException(403, "Sign in with the developer password.")
        return s

    @app.get("/api/developer")
    def monitor(req: Request):
        s = developer(req)
        present_turn(s, "history", "", {})
        with host.lock:
            runtime = {"mode": "tunnel" if host.tunnel else "local", "provider": "openai-available" if host.enabled(s.role) else "offline",
                       "model": os.getenv("PPT_STUDIO_OPENAI_MODEL", "gpt-4.1-mini") if host.enabled(s.role) else None,
                       "corpus": host.corpus.name, **host.stats, "uptime_seconds": int(time.monotonic()-host.started),
                       "sessions": len(host.sessions)}
            events = list(host.events)
        return {"role": s.role, "runtime": runtime, "limits": {"requests_per_minute": host.rpm,
                "model_calls": host.budget.calls, "token_budget": host.budget.tokens}, "usage": host.budget.usage(),
                "events": events, "deployment": {"teams": "not_connected", "tunnel_enabled": host.tunnel}}

    @app.get("/studio-config.json")
    def developer_config(req: Request):
        developer(req)
        return FileResponse(ROOT / "studio" / "studio-config.json")

    @app.post("/api/shutdown")
    async def shutdown(req: Request):
        if req.url.hostname not in LOCAL or req.client is None or req.client.host not in LOCAL:
            raise HTTPException(403, "Local host only.")
        body = await payload(req)
        if not hmac.compare_digest(str(body.get("token", "")).encode(), host.stop_token.encode()):
            raise HTTPException(403, "This launch token is required.")
        host.shutdown()
        return {"stopping": True}

    @app.api_route("/api/{unknown:path}", methods=["GET", "POST"])
    def missing(unknown: str):
        raise HTTPException(404, "Unknown Studio API route.")

    class PublicAssets(StaticFiles):
        async def get_response(self, path, scope):
            if Path(path).name.casefold() == "studio-config.json":
                raise HTTPException(403, "Sign in with the developer password.")
            return await super().get_response(path, scope)
    app.mount("/", PublicAssets(directory=ROOT / "studio", html=True), name="studio")
    return app


def select_corpus(explicit):
    if explicit:
        directory = Path(explicit).expanduser().resolve()
        if not (directory / "verified.csv").is_file():
            raise ValueError("--corpus needs a directory containing verified.csv and presentations/.")
        return directory
    from scripts.prepare_amr_corpus import default_directory
    approved = default_directory()
    if (approved / "verified.csv").is_file():
        return approved
    from scripts.prepare_studio_sample import prepare_sample
    return prepare_sample(ROOT / ".local" / "studio-sample")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=os.getenv("PPT_STUDIO_CORPUS"))
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--tunnel", action="store_true", help="Start a password-protected Cloudflare Quick Tunnel")
    parser.add_argument("--stop", action="store_true", help="Stop this project's server and its tunnel")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Choose a port from 1 to 65535.")
    base = ROOT / ".local" / "studio"
    run_file = base / f"run-{args.port}.json"
    local_url = f"http://127.0.0.1:{args.port}"
    if args.stop:
        try:
            data = run_file.read_bytes()
            req = URLRequest(local_url + "/api/shutdown", data=data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=5) as reply:
                print("Stopping PPT Builder." if reply.status == 200 else "Check the running host.")
        except (OSError, ValueError) as exc:
            parser.exit(1, f"Unable to stop Studio on port {args.port}: {exc}\n")
        return
    if args.tunnel and not shutil.which("cloudflared"):
        parser.exit(1, "Install Cloudflare's cloudflared on PATH first, then rerun with --tunnel.\n")
    import uvicorn
    try:
        corpus = select_corpus(args.corpus)
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener, tempfile.TemporaryDirectory(dir=base) as workspace:
        # Binding before creating the shutdown record protects an existing launch, including on Windows.
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.exit(1, f"Port {args.port} is occupied. Use the running host or choose --port.\n")
        listener.listen(128)
        listener.setblocking(False)
        host = StudioHost(corpus, Path(workspace), base, tunnel=args.tunnel)
        app = create_app(host)
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="warning"))
        def stop():
            server.should_exit = True
        host.shutdown = stop
        print(f"Teams Mode: {local_url}/\nDeveloper Mode: {local_url}/studio.html\nCorpus: {corpus}", flush=True)
        for role, env_name in (("developer", "PPT_STUDIO_ADMIN_PASSWORD"), ("user", "PPT_STUDIO_USER_PASSWORD")):
            if (role == "developer" or not host.local_auto) and not os.getenv(env_name):
                print(f"{role.title()} password for this launch: {host.passwords[role]}", flush=True)
        print("Press Ctrl+C to stop Studio and its tunnel.", flush=True)
        tmp_record = run_file.with_suffix(".tmp")
        tmp_record.unlink(missing_ok=True)
        fd = os.open(tmp_record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"token": host.stop_token}, f)
        os.replace(tmp_record, run_file)
        tunnel = None
        try:
            if args.tunnel:
                tunnel = subprocess.Popen(["cloudflared", "tunnel", "--url", local_url], stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True, errors="replace")
                def watch_tunnel():
                    assigned = None
                    for line in tunnel.stdout:
                        # The success banner contains only the allocated URL. An error may
                        # also print an API URL, which must never become a guest link.
                        match = re.search(r"\|\s*https://([a-z0-9-]+\.trycloudflare\.com)\s*\|", line)
                        if match and match[1] != "api.trycloudflare.com":
                            assigned = match[1]
                        if assigned and not host.remote_host and "Registered tunnel connection" in line:
                            host.remote_host = assigned
                            print(f"Guest Teams link: https://{assigned}/", flush=True)
                        if "failed to request quick Tunnel" in line:
                            print("Cloudflare could not allocate a Quick Tunnel. Check your network and DNS.", flush=True)
                    host.remote_host = None
                    if not server.should_exit:
                        print("The tunnel closed. Studio remains available on localhost.", flush=True)
                threading.Thread(target=watch_tunnel, daemon=True).start()
            server.run(sockets=[listener])
        finally:
            server.should_exit = True
            if tunnel and tunnel.poll() is None:
                tunnel.terminate()
                try:
                    tunnel.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    tunnel.kill()
                    tunnel.wait()
            run_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
