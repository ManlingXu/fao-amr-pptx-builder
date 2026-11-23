"""End-to-end synthetic V2 storylining demo: plan → revise → confirm → editable PPT."""
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
    parser.add_argument("--output", type=Path,
                        default=ROOT / "examples" / "output" / "v2")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppt-v2-demo-") as tmp:
        token = secrets.token_urlsafe(32)
        s = Settings(_env_file=None, auth_mode="api_key", copilot_api_key=token,
                     knowledge_provider="local",
                     local_presentation_path=ROOT / "data" / "presentations",
                     drafts_path=Path(tmp) / "drafts")
        headers = {"X-API-Key": token}
        with TestClient(create_app(settings=s)) as client:
            plan_res = client.post("/api/plans", headers=headers, json={
                "title": "Synthetic Africa AMR briefing",
                "audience": "Veterinary authorities",
                "purpose": "Illustrate V2 planning and section rearrangement",
                "sections": [
                    {"title": "AMR surveillance", "query": "AMR surveillance Africa", "slide_count": 1},
                    {"title": "One Health perspective",
                     "query": "One Health analytical framework", "slide_count": 1},
                ],
            })
            plan_res.raise_for_status()
            first = plan_res.json()
            assert first["isReadyForDraft"], first
            assert all(s["slideIds"] for s in first["sections"])
            # A user asks to start with the conceptual One Health framework.
            sections = list(reversed(first["sections"]))
            for section in sections:
                section["slide_ids"] = section.pop("slideIds")
            revised = client.put(f"/api/plans/{first['planId']}", headers=headers, json={
                "expected_revision": 1,
                "sections": [{"title": sec["title"], "query": sec["query"],
                              "slide_ids": sec["slide_ids"], "notes": sec.get("notes", "")}
                             for sec in sections],
            })
            revised.raise_for_status()
            latest = revised.json()
            assert latest["revision"] == 2
            job_res = client.post(f"/api/plans/{first['planId']}/draft", headers=headers,
                                  json={"expected_revision": latest["revision"], "confirmed": True})
            job_res.raise_for_status()
            job = job_res.json()
            for _ in range(400):
                status = client.get(job["statusUrl"], headers=headers).json()
                if status["status"] in {"completed", "failed"}:
                    break
                time.sleep(.04)
            else:
                raise RuntimeError("V2 draft operation timed out")
            if status["status"] != "completed":
                raise RuntimeError("V2 draft failed: " + str(status.get("error")))
            result = client.get(status["downloadUrl"], headers=headers)
            result.raise_for_status()
            (out / "V2_Editable_Draft.pptx").write_bytes(result.content)
            (out / "V2_Storyline.json").write_text(
                json.dumps(latest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (out / "V2_Source_Map.json").write_text(
                json.dumps(status["sourceMap"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            summary = {"synthetic": True, "llm_called": False,
                       "microsoft_services_called": False,
                       "plan_id": latest["planId"], "revisions": latest["revision"],
                       "selected_slides": len(status["sourceMap"]), "status": status["status"]}
            print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
