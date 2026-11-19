from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from ..models import SlideDocument

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
MAX_LIBRARY_FILES = 2000
STALE = (
    "The selected source changed or left the approved folder. Refresh the index, search and confirm again."
)


class SourceTooLargeError(ValueError):
    """A single source exceeds the supported size, independently of Graph availability."""


@dataclass(frozen=True)
class Source:
    path: Path
    key: str
    name: str
    url: str = ""
    folder: str = ""


@dataclass(frozen=True)
class SourceFailure:
    """An unsupported source reported during an otherwise successful full scan."""

    name: str
    error: str


class KnowledgeProvider(ABC):
    @abstractmethod
    def materialize_presentations(self, keys: set[str] | None = None) -> Iterator[Source | SourceFailure]:
        """Expose approved files or per-source failures; scan-wide failures must raise."""

    def snapshot(self, slides: list[SlideDocument], directory: Path) -> dict[str, Path]:
        wanted = {slide.source_key: slide for slide in slides}
        directory.mkdir(parents=True, exist_ok=True)
        paths = {}
        total = 0
        for source in self.materialize_presentations(set(wanted)):
            if isinstance(source, SourceFailure):
                raise ValueError(source.error)
            content = read_bounded(source.path)
            digest = sha256(content).hexdigest()
            expected = wanted[source.key]
            if (
                digest != expected.source_hash
                or source.name != expected.deck_name
                or (source.url and source.url != expected.source_url)
            ):
                raise ValueError(STALE)
            total += len(content)
            if total > MAX_SNAPSHOT_BYTES:
                raise ValueError("The selected source decks exceed the 256 MiB limit.")
            path = directory / f"{sha256(source.key.encode()).hexdigest()}.pptx"
            path.write_bytes(content)
            paths[source.key] = path
        if paths.keys() != wanted.keys():
            raise ValueError(STALE)
        return paths

    def publish(self, path: Path, filename: str) -> str | None:
        return None


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise SourceTooLargeError("A source deck exceeds the 64 MiB limit.")
    return data


def write_bounded(path: Path, chunks: Iterable[bytes]):
    count = 0
    with path.open("wb") as output:
        for chunk in chunks:
            count += len(chunk)
            if count > MAX_FILE_BYTES:
                raise SourceTooLargeError("A source deck exceeds the 64 MiB limit.")
            output.write(chunk)
