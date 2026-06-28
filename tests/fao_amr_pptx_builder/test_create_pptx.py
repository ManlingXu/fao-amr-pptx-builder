from pathlib import Path
import importlib.util
import json

from pptx import Presentation


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/create_pptx.py")


def load_module():
    spec = importlib.util.spec_from_file_location("create_pptx", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_create_pptx_writes_editable_deck_and_source_map(tmp_path):
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "AMR history in FAO", "bullets": [], "source_ids": []},
            {
                "slide_number": 2,
                "layout": "content",
                "title": "Why AMR matters to FAO",
                "bullets": ["Food and agriculture relevance"],
                "source_ids": ["src001"],
            },
        ],
    }
    index = [
        {
            "source_id": "src001",
            "relative_path": "history.pptx",
            "location": "slide 3",
            "text": "Food and agriculture relevance",
        }
    ]
    output = tmp_path / "draft.pptx"
    source_map = tmp_path / "source_map.json"

    module = load_module()
    module.create_pptx(plan, index, output, source_map=source_map)

    assert output.exists()
    assert source_map.exists()
    prs = Presentation(str(output))
    assert len(prs.slides) == 2
    slide_text = "\n".join(shape.text for shape in prs.slides[1].shapes if hasattr(shape, "text"))
    assert "Food and agriculture relevance" in slide_text
    source_map_data = json.loads(source_map.read_text(encoding="utf-8"))
    assert source_map_data["slides"][1]["sources"][0]["relative_path"] == "history.pptx"
