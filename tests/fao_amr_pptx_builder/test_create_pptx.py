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


def _slide_text(slide):
    return "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text"))


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
    slide_text = _slide_text(prs.slides[1])
    assert "Food and agriculture relevance" in slide_text
    source_map_data = json.loads(source_map.read_text(encoding="utf-8"))
    assert source_map_data["slides"][1]["sources"][0]["relative_path"] == "history.pptx"
    assert source_map_data["slides"][1]["sources"][0]["resolved"] is True


def test_create_pptx_uses_template_without_carrying_existing_slides(tmp_path):
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "Generated title", "bullets": [], "source_ids": []},
            {
                "slide_number": 2,
                "layout": "content",
                "title": "Generated content",
                "bullets": ["Deck content"],
                "source_ids": [],
            },
        ],
    }
    template = tmp_path / "template.pptx"
    output = tmp_path / "draft.pptx"

    template_prs = Presentation()
    template_slide = template_prs.slides.add_slide(template_prs.slide_layouts[0])
    template_slide.shapes.title.text = "Template sample slide"
    template_prs.save(template)

    module = load_module()
    module.create_pptx(plan, [], output, template=template)

    prs = Presentation(str(output))
    all_text = "\n".join(_slide_text(slide) for slide in prs.slides)
    assert len(prs.slides) == len(plan["slides"])
    assert "Template sample slide" not in all_text
    assert "Generated title" in all_text
    assert "Generated content" in all_text


def test_create_pptx_keeps_unresolved_sources_in_notes_and_source_map(tmp_path):
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {
                "slide_number": 1,
                "layout": "content",
                "title": "Traceability",
                "bullets": ["Known and missing sources"],
                "source_ids": ["src001", "missing"],
            }
        ],
    }
    index = [
        {
            "source_id": "src001",
            "relative_path": "history.pptx",
            "location": "slide 3",
            "text": "Known source",
        }
    ]
    output = tmp_path / "draft.pptx"
    source_map = tmp_path / "source_map.json"

    module = load_module()
    module.create_pptx(plan, index, output, source_map=source_map)

    prs = Presentation(str(output))
    notes_text = prs.slides[0].notes_slide.notes_text_frame.text
    assert "src001: history.pptx (slide 3)" in notes_text
    assert "missing: UNRESOLVED (missing from source_index)" in notes_text

    source_map_data = json.loads(source_map.read_text(encoding="utf-8"))
    assert source_map_data["slides"][0]["sources"] == [
        {
            "source_id": "src001",
            "relative_path": "history.pptx",
            "location": "slide 3",
            "resolved": True,
        },
        {
            "source_id": "missing",
            "relative_path": "UNRESOLVED",
            "location": "missing from source_index",
            "resolved": False,
        },
    ]
