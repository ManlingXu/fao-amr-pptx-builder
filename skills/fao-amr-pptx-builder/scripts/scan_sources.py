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
