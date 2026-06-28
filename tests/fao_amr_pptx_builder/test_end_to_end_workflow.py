import json
import subprocess
import sys
from pathlib import Path

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx import Presentation


ROOT = Path.cwd()
SCAN = ROOT / "skills/fao-amr-pptx-builder/scripts/scan_sources.py"
INDEX = ROOT / "skills/fao-amr-pptx-builder/scripts/build_source_index.py"
PLAN = ROOT / "skills/fao-amr-pptx-builder/scripts/plan_deck.py"
CREATE = ROOT / "skills/fao-amr-pptx-builder/scripts/create_pptx.py"
SCAFFOLD_PHRASES = (
    "summarize",
    "reuse strong points",
    "support key claims",
    "invite discussion",
)


def _slide_texts(slide) -> list[str]:
    texts: list[str] = []
    for shape in slide.shapes:
        if hasattr(shape, "text") and shape.text.strip():
            texts.append(shape.text.strip())
    return texts


def test_end_to_end_workflow_creates_editable_pptx(tmp_path):
    materials = tmp_path / "OneDrive AMR Materials"
    materials.mkdir()
    source_deck = materials / "history.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "FAO AMR timeline"
    slide.placeholders[1].text = "One Health and Action Plan milestones"
    prs.save(source_deck)

    sources = tmp_path / "sources.json"
    index = tmp_path / "source_index.json"
    plan = tmp_path / "deck_plan.json"
    output = tmp_path / "draft.pptx"
    source_map = tmp_path / "source_map.json"
    template = tmp_path / "template.pptx"

    template_prs = Presentation()
    sample_slide = template_prs.slides.add_slide(template_prs.slide_layouts[1])
    sample_slide.shapes.title.text = "Template sample slide"
    sample_slide.placeholders[1].text = "REMOVE ME FROM GENERATED DECK"
    template_prs.save(template)

    subprocess.run([sys.executable, str(SCAN), "--source-folder", str(materials), "--output", str(sources)], check=True)
    subprocess.run([sys.executable, str(INDEX), "--sources", str(sources), "--output", str(index)], check=True)
    subprocess.run([sys.executable, str(PLAN), "--prompt", "give me a PPT of AMR history in FAO", "--index", str(index), "--output", str(plan)], check=True)
    subprocess.run(
        [
            sys.executable,
            str(CREATE),
            "--plan",
            str(plan),
            "--index",
            str(index),
            "--output",
            str(output),
            "--template",
            str(template),
            "--source-map",
            str(source_map),
        ],
        check=True,
    )

    assert output.exists()
    assert source_map.exists()
    plan_payload = json.loads(plan.read_text(encoding="utf-8"))
    index_payload = json.loads(index.read_text(encoding="utf-8"))
    assert plan_payload["title"] == "AMR history in FAO"
    assert index_payload
    assert not plan_payload["title"].lower().startswith("evidence gap")
    normal_bullets = [
        bullet
        for slide_plan in plan_payload["slides"]
        if slide_plan["layout"] == "content"
        for bullet in slide_plan["bullets"]
    ]
    assert normal_bullets
    assert not any(
        phrase in bullet.lower()
        for bullet in normal_bullets
        for phrase in SCAFFOLD_PHRASES
    )
    substantive_slides = [
        slide_plan
        for slide_plan in plan_payload["slides"]
        if slide_plan["layout"] == "content"
    ]
    sourced_substantive_slides = [
        slide_plan for slide_plan in substantive_slides if slide_plan["source_ids"]
    ]
    assert len(sourced_substantive_slides) >= max(1, int(len(substantive_slides) * 0.75))
    generated = Presentation(str(output))
    assert len(generated.slides) == len(plan_payload["slides"])

    all_text = "\n".join(text for slide in generated.slides for text in _slide_texts(slide))
    assert "REMOVE ME FROM GENERATED DECK" not in all_text
    assert "Template sample slide" not in all_text

    for slide, slide_plan in zip(generated.slides, plan_payload["slides"]):
        slide_texts = _slide_texts(slide)
        assert slide_plan["title"] in slide_texts
        if slide_plan["bullets"]:
            for bullet in slide_plan["bullets"]:
                assert any(bullet in text for text in slide_texts)

        has_native_text = bool(slide_texts)
        has_picture = any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes)
        assert has_native_text
        assert not (has_picture and not has_native_text)

    source_map_payload = json.loads(source_map.read_text(encoding="utf-8"))
    assert source_map_payload["title"] == plan_payload["title"]
    assert len(source_map_payload["slides"]) == len(plan_payload["slides"])
    assert all(
        set(slide_entry) >= {"slide_number", "title", "sources"}
        for slide_entry in source_map_payload["slides"]
    )
    source_map_slides = source_map_payload["slides"]
    for slide_plan, slide_entry in zip(plan_payload["slides"], source_map_slides):
        assert slide_entry["slide_number"] == slide_plan["slide_number"]
        assert slide_entry["title"] == slide_plan["title"]
        assert [source["source_id"] for source in slide_entry["sources"]] == slide_plan["source_ids"]
        assert all(source.get("resolved") is True for source in slide_entry["sources"])

    resolved_sources = [
        source
        for slide_entry in source_map_payload["slides"]
        for source in slide_entry["sources"]
        if source.get("resolved")
    ]
    assert resolved_sources
    assert any(source["relative_path"] == "history.pptx" for source in resolved_sources)
    assert any(str(source.get("location", "")).startswith("slide ") for source in resolved_sources)
