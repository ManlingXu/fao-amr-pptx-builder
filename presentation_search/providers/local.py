from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .base import MAX_LIBRARY_FILES, KnowledgeProvider, Source


class LocalKnowledgeProvider(KnowledgeProvider):
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def materialize_presentations(self, keys: set[str] | None = None) -> Iterator[Source]:
        self.root.mkdir(parents=True, exist_ok=True)
        count = 0
        for path in self.root.rglob("*"):
            if path.suffix.lower() != ".pptx" or path.name.startswith("~$") or path.is_symlink():
                continue
            if not path.is_file() or not path.resolve().is_relative_to(self.root):
                continue
            count += 1
            if count > MAX_LIBRARY_FILES:
                raise ValueError("Approved library exceeds the pilot file limit")
            key = path.relative_to(self.root).as_posix()
            if keys is None or key in keys:
                yield Source(path, key, path.name, folder=path.parent.relative_to(self.root).as_posix())
