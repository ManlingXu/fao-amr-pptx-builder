from __future__ import annotations

import argparse
import json
from pathlib import Path


def _clean(text: str) -> str:
    return " ".join(text.split())


def _extract_pptx(path: Path, base: dict) -> list[dict]:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError("Install python-pptx to extract PowerPoint files.") from exc

    prs = Presentation(str(path))
    items: list[dict] = []
    for index, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text)
        text = _clean("\n".join(parts))
        if text:
            item = dict(base)
            item["location"] = f"slide {index}"
            item["text"] = text
            items.append(item)
    return items


def _extract_text(path: Path, base: dict) -> list[dict]:
    item = dict(base)
    item["location"] = "document"
    item["text"] = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    return [item] if item["text"] else []


def _extract_pdf(path: Path, base: dict) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    reader = PdfReader(str(path))
    items: list[dict] = []
    for index, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if text:
            item = dict(base)
            item["location"] = f"page {index}"
            item["text"] = text
            items.append(item)
    return items


def _extract_docx(path: Path, base: dict) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        return []
    document = Document(str(path))
    text = _clean("\n".join(paragraph.text for paragraph in document.paragraphs))
    if not text:
        return []
    item = dict(base)
    item["location"] = "document"
    item["text"] = text
    return [item]


def build_source_index(sources: list[dict]) -> list[dict]:
    items: list[dict] = []
    for source in sources:
        path = Path(source["path"])
        base = {
            "source_id": "",
            "path": str(path),
            "relative_path": source["relative_path"],
            "kind": source["kind"],
            "title": path.stem.replace("_", " ").replace("-", " "),
        }
        extension = source["extension"]
        if extension == ".pptx":
            extracted = _extract_pptx(path, base)
        elif extension == ".pdf":
            extracted = _extract_pdf(path, base)
        elif extension == ".docx":
            extracted = _extract_docx(path, base)
        else:
            extracted = _extract_text(path, base)
        items.extend(extracted)

    for index, item in enumerate(items, start=1):
        item["source_id"] = f"src{index:03d}"
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAO AMR source index.")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    items = build_source_index(sources)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(items)} indexed items to {output}")


if __name__ == "__main__":
    main()
