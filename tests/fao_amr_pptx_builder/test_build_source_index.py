import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/build_source_index.py")


def load_module():
    spec = importlib.util.spec_from_file_location("build_source_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_source_index_extracts_pptx_tables_and_grouped_shapes(tmp_path):
    pptx_path = tmp_path / "history.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(4), Inches(0.5)).text = "FAO AMR timeline"

    table = slide.shapes.add_table(2, 2, Inches(0.5), Inches(1.5), Inches(5), Inches(1.5)).table
    table.cell(0, 0).text = "Year"
    table.cell(0, 1).text = "Milestone"
    table.cell(1, 0).text = "2024"
    table.cell(1, 1).text = "Country support"

    group = slide.shapes.add_group_shape()
    group_text = group.shapes.add_textbox(Inches(0), Inches(0), Inches(3), Inches(0.5))
    group_text.text = "One Health collaboration"
    prs.save(pptx_path)

    sources = [
        {"path": str(pptx_path), "relative_path": "history.pptx", "kind": "presentation", "extension": ".pptx"},
    ]

    module = load_module()
    items = module.build_source_index(sources)

    assert len(items) == 1
    assert items[0]["source_id"] == "src001"
    assert items[0]["location"] == "slide 1"
    assert "FAO AMR timeline" in items[0]["text"]
    assert "Year" in items[0]["text"]
    assert "Country support" in items[0]["text"]
    assert "One Health collaboration" in items[0]["text"]


def test_build_source_index_reports_missing_pdf_dependency_as_warning(tmp_path, monkeypatch):
    pdf_path = tmp_path / "evidence.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    module = load_module()
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pypdf":
            raise ImportError("No module named 'pypdf'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    items = module.build_source_index(
        [{"path": str(pdf_path), "relative_path": "evidence.pdf", "kind": "report", "extension": ".pdf"}]
    )

    assert items == [
        {
            "source_id": "src001",
            "path": str(pdf_path),
            "relative_path": "evidence.pdf",
            "kind": "report",
            "title": "evidence",
            "location": "extraction warning",
            "text": "Unable to extract evidence.pdf: missing optional dependency pypdf.",
        }
    ]


def test_build_source_index_cli_writes_json_output(tmp_path):
    text_path = tmp_path / "brief.txt"
    text_path.write_text("FAO Action Plan on AMR evidence.", encoding="utf-8")
    sources_path = tmp_path / "sources.json"
    output_path = tmp_path / "source_index.json"
    sources_path.write_text(
        json.dumps(
            [{"path": str(text_path), "relative_path": "brief.txt", "kind": "text", "extension": ".txt"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sources", str(sources_path), "--output", str(output_path)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "Wrote 1 indexed items" in result.stdout
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {
            "source_id": "src001",
            "path": str(text_path),
            "relative_path": "brief.txt",
            "kind": "text",
            "title": "brief",
            "location": "document",
            "text": "FAO Action Plan on AMR evidence.",
        }
    ]
