from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/revise_deck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("revise_deck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_revise_deck_shortens_content_slides():
    plan = {
        "title": "AMR history in FAO",
        "slides": [
            {"slide_number": 1, "layout": "title", "title": "Title", "bullets": [], "source_ids": []},
            {"slide_number": 2, "layout": "content", "title": "A", "bullets": ["one", "two", "three"], "source_ids": []},
            {"slide_number": 3, "layout": "content", "title": "B", "bullets": ["one", "two", "three"], "source_ids": []},
            {"slide_number": 4, "layout": "sources", "title": "Sources", "bullets": ["source"], "source_ids": []},
        ],
    }

    module = load_module()
    revised = module.revise_deck(plan, "make it shorter")

    assert len(revised["slides"]) == 3
    assert revised["revision_note"] == "make it shorter"
    assert [slide["slide_number"] for slide in revised["slides"]] == [1, 2, 3]
