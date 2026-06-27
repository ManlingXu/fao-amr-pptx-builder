### Task 2: Source Scanning

**Files:**
- Create: `skills/fao-amr-pptx-builder/scripts/scan_sources.py`
- Create: `tests/fao_amr_pptx_builder/test_scan_sources.py`

**Interfaces:**
- Produces: `scan_sources(root: Path) -> list[dict]`
- Produces CLI: `python scan_sources.py --source-folder <path> --output <sources.json>`

- [ ] **Step 1: Write the failing test**

Create `tests/fao_amr_pptx_builder/test_scan_sources.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_scan_sources.py -v
```

Expected: FAIL because `scan_sources.py` does not exist.

- [ ] **Step 3: Implement scanner**

Create `skills/fao-amr-pptx-builder/scripts/scan_sources.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


SUPPORTED = {
    ".pptx": "presentation",
    ".pdf": "report",
    ".docx": "report",
    ".txt": "text",
    ".md": "text",
    ".html": "text",
    ".htm": "text",
}


def scan_sources(root: Path) -> list[dict]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Source folder does not exist or is not a folder: {root}")

    sources: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        extension = path.suffix.lower()
        kind = SUPPORTED.get(extension)
        if not kind:
            continue
        sources.append(
            {
                "path": str(path.resolve()),
                "relative_path": str(path.relative_to(root)),
                "extension": extension,
                "kind": kind,
                "size_bytes": path.stat().st_size,
            }
        )
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan FAO AMR source materials.")
    parser.add_argument("--source-folder", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = scan_sources(Path(args.source_folder))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(sources)} sources to {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests\fao_amr_pptx_builder\test_scan_sources.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/fao-amr-pptx-builder/scripts/scan_sources.py tests/fao_amr_pptx_builder/test_scan_sources.py
git commit -m "Add FAO AMR source scanner"
```

---

