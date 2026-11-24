"""Conservative, rendering-independent checks for generated PowerPoint layouts.

The checks in this module intentionally report geometry and density heuristics.
They do not attempt to reproduce PowerPoint's font metrics or rendering engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation


_OVERLAP_THRESHOLD = 0.20
_CONTAINMENT_THRESHOLD = 0.95
_BACKGROUND_AREA_THRESHOLD = 0.90
_DENSE_TEXT_WORDS = 180


@dataclass(frozen=True)
class _ShapeGeometry:
    index: int
    name: str
    left: int
    top: int
    width: int
    height: int
    word_count: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def bounds(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


def _words(shape) -> int:
    if not getattr(shape, "has_text_frame", False):
        return 0
    return len(shape.text.split())


def _geometry(shape, index: int) -> _ShapeGeometry:
    return _ShapeGeometry(
        index=index,
        name=str(shape.name),
        left=int(shape.left),
        top=int(shape.top),
        width=int(shape.width),
        height=int(shape.height),
        word_count=_words(shape),
    )


def _is_background(shape: _ShapeGeometry, slide_width: int, slide_height: int) -> bool:
    slide_area = slide_width * slide_height
    if not slide_area or shape.area / slide_area < _BACKGROUND_AREA_THRESHOLD:
        return False
    margin_x = slide_width * 0.02
    margin_y = slide_height * 0.02
    return (
        shape.left <= margin_x
        and shape.top <= margin_y
        and shape.right >= slide_width - margin_x
        and shape.bottom >= slide_height - margin_y
    )


def _overlap_ratio(first: _ShapeGeometry, second: _ShapeGeometry) -> float:
    width = max(0, min(first.right, second.right) - max(first.left, second.left))
    height = max(0, min(first.bottom, second.bottom) - max(first.top, second.top))
    smaller = min(first.area, second.area)
    return 0.0 if not smaller else (width * height) / smaller


def _outside_canvas(shape: _ShapeGeometry, slide_width: int, slide_height: int) -> bool:
    return (
        shape.left < 0
        or shape.top < 0
        or shape.right > slide_width
        or shape.bottom > slide_height
    )


def _validate_slide(slide, slide_number: int, slide_width: int, slide_height: int) -> dict:
    shapes = [_geometry(shape, index) for index, shape in enumerate(slide.shapes, 1)]
    issues: list[dict] = []

    for shape in shapes:
        if _outside_canvas(shape, slide_width, slide_height):
            issues.append(
                {
                    "code": "shape_outside_canvas",
                    "severity": "error",
                    "shapeIndex": shape.index,
                    "shapeName": shape.name,
                    "bounds": shape.bounds(),
                    "reason": "The shape extends beyond the slide canvas and may be clipped.",
                }
            )
        if shape.word_count >= _DENSE_TEXT_WORDS:
            issues.append(
                {
                    "code": "dense_text",
                    "severity": "warning",
                    "shapeIndex": shape.index,
                    "shapeName": shape.name,
                    "wordCount": shape.word_count,
                    "reason": (
                        f"Heuristic review: one text shape contains {shape.word_count} words; "
                        "confirm its legibility in PowerPoint."
                    ),
                }
            )

    ordinary = [
        shape
        for shape in shapes
        if shape.area > 0 and not _is_background(shape, slide_width, slide_height)
    ]
    for position, first in enumerate(ordinary):
        for second in ordinary[position + 1 :]:
            ratio = _overlap_ratio(first, second)
            if ratio < _OVERLAP_THRESHOLD or ratio >= _CONTAINMENT_THRESHOLD:
                continue
            issues.append(
                {
                    "code": "shape_overlap",
                    "severity": "warning",
                    "shapeIndexes": [first.index, second.index],
                    "shapeNames": [first.name, second.name],
                    "overlapRatio": round(ratio, 3),
                    "reason": (
                        "The shapes have a substantive geometric overlap; review whether "
                        "the overlap is intentional."
                    ),
                }
            )

    return {"slideNumber": slide_number, "issues": issues}


def validate_layout(path: Path) -> dict:
    """Return a JSON-serializable heuristic layout report for *path*."""
    presentation = Presentation(path)
    slide_width = int(presentation.slide_width)
    slide_height = int(presentation.slide_height)
    slides = [
        _validate_slide(slide, number, slide_width, slide_height)
        for number, slide in enumerate(presentation.slides, 1)
    ]
    issues = [issue for slide in slides for issue in slide["issues"]]
    return {
        "slideWidth": slide_width,
        "slideHeight": slide_height,
        "slides": slides,
        "summary": {
            "slides": len(slides),
            "issues": len(issues),
            "errors": sum(issue["severity"] == "error" for issue in issues),
            "warnings": sum(issue["severity"] == "warning" for issue in issues),
            "slidesNeedingReview": sum(bool(slide["issues"]) for slide in slides),
        },
        "limitations": [
            "Text density and shape overlap are heuristic checks; PowerPoint rendering is not measured."
        ],
    }
