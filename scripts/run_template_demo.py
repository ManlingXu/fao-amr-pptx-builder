"""Exercise template upload, new-draft styling and a subsequent template change over HTTP."""
from __future__ import annotations

import argparse
import base64
import json
import secrets
import tempfile
import time
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from presentation_search.api import create_app
from presentation_search.assembly import P
from presentation_search.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def synthetic_template(path: Path, color: str, label: str) -> None:
    ppt = Presentation()
    ppt.slide_width, ppt.slide_height = Inches(13.333333), Inches(7.5)
    ppt.slide_master.background.fill.solid()
    ppt.slide_master.background.fill.fore_color.rgb = RGBColor.from_string(color)
    sample = ppt.slides.add_slide(ppt.slide_layouts[6])
    footer = sample.shapes.add_textbox(Inches(0.8), Inches(7.0), Inches(11.5), Inches(0.3))
    footer.text = label + " — SYNTHETIC TEMPLATE"
    footer.text_frame.paragraphs[0].font.size = Pt(12)
    brand = deepcopy(footer._element)
    ids = [int(n.get("id")) for n in ppt.slide_master._element.iter(P + "cNvPr")]
    brand.find(".//" + P + "cNvPr").set("id", str(max(ids) + 1))
    ppt.slide_master.shapes._spTree.append(brand)
    sample.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = "Template example, excluded from output"
    ppt.save(path)


def wait_job(client, response, headers):
    response.raise_for_status()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        status = client.get(response.json()["statusUrl"], headers=headers)
        status.raise_for_status()
        record = status.json()
        if record["status"] == "completed":
            return record
        if record["status"] == "failed":
            raise RuntimeError(record["error"])
        time.sleep(0.05)
    raise RuntimeError("Template demonstration timed out")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "template-demo")
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        key = secrets.token_urlsafe(32)
        settings = Settings(_env_file=None, auth_mode="api_key", copilot_api_key=key,
                            local_presentation_path=ROOT / "data" / "presentations",
                            drafts_path=temporary / "drafts")
        with TestClient(create_app(settings=settings)) as client:
            headers = {"X-API-Key": key}
            results = client.post("/api/search", headers=headers, json={"query": "AMR livestock"})
            results.raise_for_status()
            selected = [s["slideId"] for s in results.json()["results"][:3]]
            templates = []
            for filename, color, label in [("Template_Blue.pptx", "EAF2F8", "BLUE"),
                                            ("Template_Green.pptx", "EFF6EA", "GREEN")]:
                path = out / filename
                synthetic_template(path, color, label)
                upload = client.post("/api/templates", headers=headers, json={
                    "file_name": filename,
                    "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                })
                upload.raise_for_status()
                templates.append(upload.json())
            original = wait_job(client, client.post("/api/drafts", headers=headers, json={
                "title": "Synthetic template demonstration", "slide_ids": selected,
                "confirmed": True, "template_id": templates[0]["templateId"],
            }), headers)
            original_bytes = client.get(original["downloadUrl"], headers=headers).content
            (out / "Draft_Blue.pptx").write_bytes(original_bytes)
            changed = wait_job(client, client.post(
                f"/api/drafts/{original['jobId']}/template", headers=headers, json={
                    "template_id": templates[1]["templateId"], "confirmed": True,
                }), headers)
            download = client.get(changed["downloadUrl"], headers=headers)
            download.raise_for_status()
            (out / "Draft_Green.pptx").write_bytes(download.content)
            assert client.get(original["downloadUrl"], headers=headers).content == original_bytes
            assert changed["sourceMap"] == original["sourceMap"]
            first, second = Presentation(BytesIO(original_bytes)), Presentation(BytesIO(download.content))
            assert len(first.slides) == len(second.slides) == len(selected)
            for before, after in zip(first.slides, second.slides):
                assert before.notes_slide.notes_text_frame.text == after.notes_slide.notes_text_frame.text
            summary = {"synthetic": True, "slides": len(selected), "template_uploads": 2,
                       "original_preserved": True, "source_map_preserved": True,
                       "notes_preserved": True, "warnings": changed["warnings"],
                       "microsoft_services_called": False, "llm_called": False}
            (out / "Template_Demo_Result.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
