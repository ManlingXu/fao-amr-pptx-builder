from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/scan_sources.py")


def load_module():
    spec = importlib.util.spec_from_file_location("scan_sources", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_scan_sources_recognizes_supported_files(tmp_path):
    (tmp_path / "history.pptx").write_bytes(b"pptx")
    (tmp_path / "report.pdf").write_bytes(b"pdf")
    (tmp_path / "notes.txt").write_text("AMR notes", encoding="utf-8")
    (tmp_path / "~$temporary.pptx").write_bytes(b"ignore")
    (tmp_path / "image.png").write_bytes(b"ignore")

    module = load_module()
    sources = module.scan_sources(tmp_path)

    names = {item["relative_path"] for item in sources}
    assert names == {"history.pptx", "report.pdf", "notes.txt"}
    assert {item["kind"] for item in sources} == {"presentation", "report", "text"}
