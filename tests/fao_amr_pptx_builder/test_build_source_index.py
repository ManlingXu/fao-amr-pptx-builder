from pathlib import Path
import importlib.util

from pptx import Presentation


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/build_source_index.py")


def load_module():
    spec = importlib.util.spec_from_file_location("build_source_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_source_index_extracts_pptx_and_text(tmp_path):
    pptx_path = tmp_path / "history.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "FAO AMR timeline"
    slide.placeholders[1].text = "One Health collaboration and country support"
    prs.save(pptx_path)

    text_path = tmp_path / "brief.txt"
    text_path.write_text("FAO Action Plan on AMR evidence.", encoding="utf-8")

    sources = [
        {"path": str(pptx_path), "relative_path": "history.pptx", "kind": "presentation", "extension": ".pptx"},
        {"path": str(text_path), "relative_path": "brief.txt", "kind": "text", "extension": ".txt"},
    ]

    module = load_module()
    items = module.build_source_index(sources)

    assert len(items) == 2
    assert items[0]["source_id"] == "src001"
    assert items[0]["location"] == "slide 1"
    assert "FAO AMR timeline" in items[0]["text"]
    assert items[1]["location"] == "document"
    assert "Action Plan" in items[1]["text"]
