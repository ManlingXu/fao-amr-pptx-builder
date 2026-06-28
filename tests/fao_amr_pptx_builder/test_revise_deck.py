import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/revise_deck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("revise_deck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_plan():
    return {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "Title", "bullets": [], "source_ids": []},
            {"slide_number": 2, "layout": "content", "title": "A", "bullets": ["one", "two", "three"], "source_ids": ["src-1"]},
            {"slide_number": 3, "layout": "content", "title": "B", "bullets": ["one", "two", "three"], "source_ids": ["src-2"]},
            {"slide_number": 4, "layout": "sources", "title": "Sources", "bullets": ["source"], "source_ids": []},
        ],
    }


def test_revise_deck_shortens_content_slides_and_preserves_retained_source_ids():
    plan = make_plan()
    module = load_module()
    revised = module.revise_deck(plan, "make it shorter")

    assert len(revised["slides"]) == 3
    assert revised["revision_note"] == "make it shorter"
    assert [slide["slide_number"] for slide in revised["slides"]] == [1, 2, 3]
    assert revised["slides"][1]["source_ids"] == ["src-1"]
    assert "revision_context" not in revised


def test_revise_deck_more_technical_does_not_mutate_input_and_adds_context():
    plan = make_plan()
    original = deepcopy(plan)
    module = load_module()

    revised = module.revise_deck(
        plan,
        "make it more technical",
        source_index=[{"source_id": "src-1"}, {"source_id": "src-2"}],
        source_map={
            "slides": {
                "2": ["src-1", "src-missing"],
                "3": ["src-2"],
            }
        },
    )

    assert plan == original
    assert revised["slides"][1]["bullets"][-1] == "Add technical detail from source evidence during manual review"
    assert revised["revision_context"] == {
        "source_index_count": 2,
        "source_map_slide_count": 2,
        "unresolved_source_ids": ["src-missing"],
    }


def test_cli_accepts_optional_source_context_and_writes_revision_context(tmp_path):
    plan_path = tmp_path / "plan.json"
    index_path = tmp_path / "source_index.json"
    source_map_path = tmp_path / "source_map.json"
    output_path = tmp_path / "revised.json"

    plan_path.write_text(json.dumps(make_plan()), encoding="utf-8")
    index_path.write_text(json.dumps([{"source_id": "src-1"}]), encoding="utf-8")
    source_map_path.write_text(
        json.dumps({"slides": {"2": ["src-1", "src-unresolved"]}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--plan",
            str(plan_path),
            "--review",
            "make it shorter",
            "--index",
            str(index_path),
            "--source-map",
            str(source_map_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    revised = json.loads(output_path.read_text(encoding="utf-8"))
    assert revised["revision_context"] == {
        "source_index_count": 1,
        "source_map_slide_count": 1,
        "unresolved_source_ids": ["src-unresolved"],
    }
