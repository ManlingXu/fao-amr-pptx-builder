"""Exercise the real HTTP tool workflow locally with synthetic data."""
from __future__ import annotations
import argparse
import json
import secrets
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from presentation_search.api import create_app
from presentation_search.config import Settings

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "output")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppt-assistant-demo-") as temporary:
        key = secrets.token_urlsafe(32)
        settings = Settings(auth_mode="api_key", copilot_api_key=key,
                            knowledge_provider="local",
                            local_presentation_path=ROOT / "data" / "presentations",
                            drafts_path=Path(temporary) / "drafts",
                            admin_api_key="")
        with TestClient(create_app(settings=settings)) as client:
            headers = {"X-API-Key": key}
            found = client.post("/api/search", headers=headers, json={
                "query": "AMR livestock One Health", "limit": 5, "latest_only": True
            })
            found.raise_for_status()
            search = found.json()
            selected = [item["slideId"] for item in search["results"][:3]]
            if not selected:
                raise RuntimeError("The synthetic library returned no slide candidates.")
            response = client.post("/api/drafts", headers=headers, json={
                "title": "Synthetic AMR presentation demonstration",
                "confirmed": True, "slide_ids": selected
            })
            response.raise_for_status()
            job = response.json()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                response = client.get(job["statusUrl"], headers=headers)
                response.raise_for_status()
                status = response.json()
                if status["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError("Demonstration exceeded the local job timeout.")
            if status["status"] != "completed":
                raise RuntimeError("Assembly failed: " + str(status.get("error")))
            output = client.get(status["downloadUrl"], headers=headers)
            output.raise_for_status()
            (out / "Demo_Draft.pptx").write_bytes(output.content)
            (out / "Demo_Source_Map.json").write_text(
                json.dumps(status["sourceMap"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (out / "Demo_Search_Results.json").write_text(
                json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary = {"synthetic": True, "selected_slides": len(selected),
                       "status": status["status"], "warnings": status.get("warnings", []),
                       "file": "Demo_Draft.pptx", "provenance": "Demo_Source_Map.json",
                       "llm_called": False, "microsoft_services_called": False}
            (out / "Demo_Result.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"output_directory": str(out), **summary}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
