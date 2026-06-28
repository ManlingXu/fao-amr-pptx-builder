import json
import subprocess
import sys
from pathlib import Path

from pptx import Presentation


ROOT = Path.cwd()
SCAN = ROOT / "skills/fao-amr-pptx-builder/scripts/scan_sources.py"
INDEX = ROOT / "skills/fao-amr-pptx-builder/scripts/build_source_index.py"
PLAN = ROOT / "skills/fao-amr-pptx-builder/scripts/plan_deck.py"
CREATE = ROOT / "skills/fao-amr-pptx-builder/scripts/create_pptx.py"


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

    subprocess.run([sys.executable, str(SCAN), "--source-folder", str(materials), "--output", str(sources)], check=True)
    subprocess.run([sys.executable, str(INDEX), "--sources", str(sources), "--output", str(index)], check=True)
    subprocess.run([sys.executable, str(PLAN), "--prompt", "give me a PPT of AMR history in FAO", "--index", str(index), "--output", str(plan)], check=True)
    subprocess.run([sys.executable, str(CREATE), "--plan", str(plan), "--index", str(index), "--output", str(output), "--source-map", str(source_map)], check=True)

    assert output.exists()
    assert source_map.exists()
    assert json.loads(plan.read_text(encoding="utf-8"))["title"] == "AMR history in FAO"
    generated = Presentation(str(output))
    assert len(generated.slides) >= 10
