from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.group import GroupShape


_WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def _shape_text(shape) -> list[str]:
    values: list[str] = []
    if getattr(shape, "has_text_frame", False):
        value = shape.text_frame.text.strip()
        if value:
            values.append(value)
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                value = cell.text.strip()
                if value:
                    values.append(value)
    if isinstance(shape, GroupShape):
        for child in shape.shapes:
            values.extend(_shape_text(child))
    return values


def _walk_shapes(shapes: Iterable) -> Iterable:
    for shape in shapes:
        yield shape
        if isinstance(shape, GroupShape):
            yield from _walk_shapes(shape.shapes)


def _has_content(shape) -> bool:
    if _shape_text(shape):
        return True
    if getattr(shape, "has_table", False) or getattr(shape, "has_chart", False):
        return True
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return True
    return isinstance(shape, GroupShape) and any(_has_content(child) for child in shape.shapes)


def _count_words(values: Iterable[str]) -> int:
    return sum(len(_WORD.findall(value)) for value in values)


def _analyze_slide(slide, slide_number: int, slide_width: int, slide_height: int) -> dict:
    all_shapes = list(_walk_shapes(slide.shapes))
    shape_counts = {
        "text_boxes": sum(
            1
            for shape in all_shapes
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip()
        ),
        "pictures": sum(1 for shape in all_shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE),
        "tables": sum(1 for shape in all_shapes if getattr(shape, "has_table", False)),
        "charts": sum(1 for shape in all_shapes if getattr(shape, "has_chart", False)),
        "groups": sum(1 for shape in all_shapes if isinstance(shape, GroupShape)),
    }

    text_values: list[str] = []
    for shape in slide.shapes:
        text_values.extend(_shape_text(shape))
    word_count = _count_words(text_values)

    canvas_area = slide_width * slide_height
    occupied_area = sum(
        max(0, int(shape.width)) * max(0, int(shape.height))
        for shape in slide.shapes
        if _has_content(shape)
    )
    occupancy_ratio = round(min(1.0, occupied_area / canvas_area), 4) if canvas_area else 0.0

    title_shape = slide.shapes.title
    title_words = _count_words([title_shape.text]) if title_shape is not None else 0
    body_words = max(0, word_count - title_words)
    structured_types = [
        name
        for name, count_key in (("image", "pictures"), ("table", "tables"), ("chart", "charts"))
        if shape_counts[count_key]
    ]
    if len(structured_types) > 1 or (structured_types and body_words >= 25):
        content_type = "mixed"
    elif structured_types:
        content_type = structured_types[0]
    elif body_words:
        content_type = "text"
    else:
        content_type = "title"

    content_shape_count = sum(shape_counts.values()) - shape_counts["groups"]
    if word_count >= 80 or occupancy_ratio >= 0.75 or content_shape_count >= 8:
        density = "high"
    elif word_count >= 25 or occupancy_ratio >= 0.4 or content_shape_count >= 4:
        density = "medium"
    else:
        density = "low"

    if density == "high":
        recommended_layout_action = "review"
    elif density == "medium" or content_type in {"image", "table", "chart", "mixed"}:
        recommended_layout_action = "reflow"
    else:
        recommended_layout_action = "reuse"

    return {
        "slide_number": slide_number,
        "shape_counts": shape_counts,
        "word_count": word_count,
        "occupancy_ratio": occupancy_ratio,
        "content_type": content_type,
        "density": density,
        "recommended_layout_action": recommended_layout_action,
    }


def analyze_slides(path: Path, slide_numbers: Sequence[int]) -> list[dict]:
    """Return deterministic structural hints for selected 1-based slides.

    The result intentionally describes observable PowerPoint structure. It does
    not claim to understand the meaning or quality of pictures.
    """

    presentation = Presentation(Path(path))
    slide_count = len(presentation.slides)
    for slide_number in slide_numbers:
        if slide_number < 1:
            raise ValueError(f"Slide number {slide_number} must be 1-based")
        if slide_number > slide_count:
            raise ValueError(
                f"Slide number {slide_number} is out of range for a {slide_count}-slide presentation"
            )

    return [
        _analyze_slide(
            presentation.slides[slide_number - 1],
            slide_number,
            presentation.slide_width,
            presentation.slide_height,
        )
        for slide_number in slide_numbers
    ]
