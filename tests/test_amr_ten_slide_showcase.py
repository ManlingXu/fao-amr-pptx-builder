import csv
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from lxml import etree as ET
from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Inches

from presentation_search.assembly import P


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_amr_ten_slide_showcase.py"
SLIDE_NUMBERS = (1, 2, 3, 5, 8, 10, 11, 15, 17, 19)


def load_showcase_module():
    assert SCRIPT.is_file(), "the 10-slide AMR showcase script has not been implemented"
    spec = importlib.util.spec_from_file_location("run_amr_ten_slide_showcase", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_verified_deck(root: Path, deck_id: str = "zambia-demo") -> Path:
    presentations = root / "presentations"
    presentations.mkdir()
    path = presentations / f"{deck_id}.pptx"
    deck = Presentation()
    deck.slide_width = Inches(13.333333)
    deck.slide_height = Inches(7.5)
    picture = io.BytesIO()
    Image.new("RGB", (80, 45), (40, 90, 120)).save(picture, format="PNG")
    picture_blob = picture.getvalue()
    for number in range(1, 21):
        slide = deck.slides.add_slide(deck.slide_layouts[3 if number == 11 else 1])
        slide.shapes.title.text = f"Source slide {number}"
        slide.placeholders[1].text = f"Evidence page {number}"
        if number == 11:
            slide.shapes.add_picture(io.BytesIO(picture_blob), Inches(6.8), Inches(2), width=Inches(4))
            source_credit = slide.shapes.add_textbox(Inches(0.5), Inches(7), Inches(4), Inches(0.25))
            source_credit.text = "Source credit 11"
            credit_placeholder = ET.Element(P + "ph")
            credit_placeholder.set("type", "ftr")
            credit_placeholder.set("idx", "98")
            source_credit._element.nvSpPr.nvPr.append(credit_placeholder)
            page_number = slide.shapes.add_textbox(Inches(12), Inches(7), Inches(0.5), Inches(0.25))
            page_number.text = "11"
            placeholder = ET.Element(P + "ph")
            placeholder.set("type", "sldNum")
            placeholder.set("idx", "99")
            page_number._element.nvSpPr.nvPr.append(placeholder)
        slide.notes_slide.notes_text_frame.text = f"Speaker note {number}"
    deck.save(path)
    row = {
        "id": deck_id,
        "title": "Antimicrobial stewardship in Zambia",
        "source_page": "https://example.org/zambia",
        "download_url": "https://example.org/zambia.pptx",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "author": "Example Author",
        "publisher": "Example Publisher",
        "license": "CC BY 4.0",
        "issued": "2025-03",
        "sector": "animal",
        "topic": "Veterinary stewardship",
        "language": "en",
        "series": "",
    }
    with (root / "verified.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    return path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def slide_titles(path: Path) -> list[str]:
    return [slide.shapes.title.text for slide in Presentation(path).slides]


def slide_notes(path: Path) -> list[str]:
    return [slide.notes_slide.notes_text_frame.text for slide in Presentation(path).slides]


def slide_text(path: Path) -> list[list[str]]:
    def collect(shapes):
        values = []
        for shape in shapes:
            if (shape.is_placeholder
                    and shape.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER):
                continue
            if shape.has_text_frame:
                if shape.text.strip():
                    values.append(shape.text)
            if shape.has_table:
                values.extend(cell.text for row in shape.table.rows for cell in row.cells)
            if hasattr(shape, "shapes"):
                values.extend(collect(shape.shapes))
        return values

    return [sorted(collect(slide.shapes)) for slide in Presentation(path).slides]


def slide_picture_counts(path: Path) -> list[int]:
    def count(shapes):
        return sum(
            (1 if shape._element.tag == P + "pic" else 0)
            + (count(shape.shapes) if hasattr(shape, "shapes") else 0)
            for shape in shapes
        )

    return [count(slide.shapes) for slide in Presentation(path).slides]


def master_text(path: Path) -> str:
    presentation = Presentation(path)
    return "\n".join(
        shape.text
        for master in presentation.slide_masters
        for shape in master.shapes
        if shape.has_text_frame
    )


def test_showcase_creates_three_traceable_ten_slide_versions(tmp_path):
    module = load_showcase_module()
    write_verified_deck(tmp_path)
    output = tmp_path / "showcase"

    summary = module.run_showcase(
        tmp_path,
        output,
        deck_id="zambia-demo",
        slide_numbers=SLIDE_NUMBERS,
    )

    original = output / "AMR_10_Slide_Original.pptx"
    blue = output / "AMR_10_Slide_Blue.pptx"
    green = output / "AMR_10_Slide_Green.pptx"
    expected_titles = [f"Source slide {number}" for number in SLIDE_NUMBERS]
    expected_notes = [f"Speaker note {number}" for number in SLIDE_NUMBERS]
    expected_text = []
    for number in SLIDE_NUMBERS:
        values = [f"Source slide {number}", f"Evidence page {number}"]
        if number == 11:
            values.append("Source credit 11")
        expected_text.append(sorted(values))
    assert slide_titles(original) == slide_titles(blue) == slide_titles(green) == expected_titles
    assert slide_notes(original) == slide_notes(blue) == slide_notes(green) == expected_notes
    assert slide_text(original) == slide_text(blue) == slide_text(green) == expected_text
    assert slide_picture_counts(original) == slide_picture_counts(blue) == slide_picture_counts(green)
    assert slide_picture_counts(original)[6] == 1
    assert len({original.read_bytes(), blue.read_bytes(), green.read_bytes()}) == 3
    assert "BLUE" in master_text(blue)
    assert "GREEN" in master_text(green)
    demo_template = Presentation(output / "Template_Blue.pptx")
    content_layout = next(layout for layout in demo_template.slide_layouts
                          if layout.name == "Title and Content")
    content_box = next(shape for shape in content_layout.placeholders
                       if shape.placeholder_format.type == PP_PLACEHOLDER.OBJECT)
    title_layout = next(layout for layout in demo_template.slide_layouts
                        if layout.name == "Title Slide")
    title_box = next(shape for shape in title_layout.placeholders
                     if shape.placeholder_format.type == PP_PLACEHOLDER.CENTER_TITLE)
    footer_box = next(shape for shape in demo_template.slide_master.shapes
                      if shape.has_text_frame and "SYNTHETIC TEMPLATE" in shape.text)
    assert content_box.width >= demo_template.slide_width * 0.8
    assert content_box.height >= demo_template.slide_height * 0.73
    assert title_box.height >= demo_template.slide_height * 0.25
    assert footer_box.top >= demo_template.slide_height * 0.96

    sources = read_json(output / "source_map.json")
    assert [(item["outputSlide"], item["deckName"], item["slideNumber"])
            for item in sources] == [
        (position, "zambia-demo.pptx", number)
        for position, number in enumerate(SLIDE_NUMBERS, 1)
    ]
    assert all(item["sourcePage"] == "https://example.org/zambia" for item in sources)
    analysis = read_json(output / "slide_analysis.json")
    assert len(analysis["slides"]) == 10
    assert [item["slideNumber"] for item in analysis["slides"]] == list(SLIDE_NUMBERS)
    decisions = read_json(output / "layout_decisions.json")
    assert len(decisions) == 10
    assert decisions[6]["contentType"] == "image"
    assert decisions[6]["templateA"]["requestedLayout"] == "Two Content"
    assert read_json(output / "layout_report_blue.json")["slideCount"] == 10
    assert read_json(output / "layout_report_green.json")["slideCount"] == 10
    storyline = read_json(output / "storyline.json")
    assert all(item["storyRole"].startswith("Curated source page") for item in storyline)

    assert summary["status"] == "completed"
    assert summary["slides"] == 10
    assert summary["template_switches"] == 2
    assert summary["source_map_preserved"] is True
    assert summary["notes_preserved"] is True
    assert summary["slide_text_preserved"] is True
    assert summary["pictures_preserved"] is True
    assert summary["llm_called"] is False
    assert summary["microsoft_services_called"] is False
    assert read_json(output / "summary.json") == summary


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("1,2,3,4,5,6,7,8,9", "exactly 10"),
        ("1,2,3,4,5,6,7,8,9,10,11", "exactly 10"),
        ("1,2,3,4,5,6,7,8,9,9", "unique"),
        ("0,1,2,3,4,5,6,7,8,9", "1-based"),
        ("1,2,three,4,5,6,7,8,9,10", "Invalid slide number"),
    ],
)
def test_slide_number_parser_rejects_a_non_ten_page_showcase(value, message):
    module = load_showcase_module()

    with pytest.raises(ValueError, match=message):
        module.parse_slide_numbers(value)


def test_out_of_range_selection_fails_before_creating_output(tmp_path):
    module = load_showcase_module()
    write_verified_deck(tmp_path)
    output = tmp_path / "showcase"

    with pytest.raises(ValueError, match="out of range"):
        module.run_showcase(
            tmp_path,
            output,
            deck_id="zambia-demo",
            slide_numbers=(1, 2, 3, 4, 5, 6, 7, 8, 9, 21),
        )

    assert not output.exists()


def test_showcase_script_runs_directly_from_the_repository_root():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=SCRIPT.parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--template-a" in result.stdout and "--template-b" in result.stdout


def test_failed_generation_does_not_mix_new_files_with_an_existing_showcase(tmp_path, monkeypatch):
    module = load_showcase_module()
    write_verified_deck(tmp_path)
    output = tmp_path / "showcase"
    output.mkdir()
    existing = {
        "AMR_10_Slide_Original.pptx": b"old original",
        "AMR_10_Slide_Blue.pptx": b"old blue",
        "AMR_10_Slide_Green.pptx": b"old green",
        "summary.json": b"old summary",
    }
    for name, content in existing.items():
        (output / name).write_bytes(content)
    real_upload = module._upload_template
    calls = 0

    def fail_second_upload(client, path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("second template failed")
        return real_upload(client, path)

    monkeypatch.setattr(module, "_upload_template", fail_second_upload)

    with pytest.raises(ValueError, match="second template failed"):
        module.run_showcase(
            tmp_path,
            output,
            deck_id="zambia-demo",
            slide_numbers=SLIDE_NUMBERS,
        )

    assert {name: (output / name).read_bytes() for name in existing} == existing


def test_custom_templates_can_replace_both_generated_demo_templates(tmp_path):
    module = load_showcase_module()
    write_verified_deck(tmp_path)
    first = tmp_path / "first-template.pptx"
    second = tmp_path / "second-template.pptx"
    module.synthetic_template(first, "D9EAF7", "CUSTOM FIRST")
    module.synthetic_template(second, "E5F2D8", "CUSTOM SECOND")

    summary = module.run_showcase(
        tmp_path,
        tmp_path / "custom-showcase",
        deck_id="zambia-demo",
        slide_numbers=SLIDE_NUMBERS,
        template_a=first,
        template_b=second,
    )

    assert summary["generated_demo_templates"] == {"template_a": False, "template_b": False}
    assert summary["template_a"] == first.name
    assert summary["template_b"] == second.name


def test_directory_publish_restores_previous_showcase_when_swap_fails(tmp_path, monkeypatch):
    module = load_showcase_module()
    stage = tmp_path / "stage"
    output = tmp_path / "showcase"
    stage.mkdir()
    output.mkdir()
    (stage / "summary.json").write_text("new", encoding="utf-8")
    (output / "summary.json").write_text("old", encoding="utf-8")
    real_replace = module.os.replace

    def fail_new_directory_swap(source, target):
        if Path(source) == stage and Path(target) == output:
            raise PermissionError("PowerPoint has a file open")
        return real_replace(source, target)

    monkeypatch.setattr(module.os, "replace", fail_new_directory_swap)

    with pytest.raises(PermissionError, match="PowerPoint has a file open"):
        module._publish_showcase(stage, output)

    assert (output / "summary.json").read_text(encoding="utf-8") == "old"
    assert (stage / "summary.json").read_text(encoding="utf-8") == "new"

