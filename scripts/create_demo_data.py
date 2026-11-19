from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "presentations"


def add_deck(filename: str, slides: list[tuple[str, str, str]]) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)
    for title, body, notes in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = title
        slide.shapes.title.left = Inches(0.8)
        slide.shapes.title.top = Inches(0.65)
        slide.shapes.title.width = Inches(11.7)
        slide.shapes.title.height = Inches(1.0)
        for paragraph in slide.shapes.title.text_frame.paragraphs:
            paragraph.font.size = Pt(30)
        box = slide.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(11.5), Inches(3.5))
        box.text_frame.word_wrap = True
        box.text_frame.text = body
        for paragraph in box.text_frame.paragraphs:
            paragraph.font.size = Pt(24)
        label = slide.shapes.add_textbox(Inches(0.8), Inches(6.65), Inches(11.5), Inches(0.4))
        label.text_frame.text = "SYNTHETIC DEMONSTRATION | NOT OFFICIAL DATA"
        for paragraph in label.text_frame.paragraphs:
            paragraph.font.size = Pt(12)
        slide.notes_slide.notes_text_frame.text = notes
    prs.save(OUTPUT / filename)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for existing in OUTPUT.glob("*.pptx"):
        existing.unlink()

    add_deck(
        "AMR_Global_Update_2022_final.pptx",
        [
            (
                "AMR surveillance in Africa",
                "Antimicrobial resistance surveillance in livestock. Data: 2019–2021. Reported value: 61 units.",
                "Older version retained for comparison.",
            ),
            (
                "Key AMR drivers",
                "Drivers include inappropriate antimicrobial use, weak surveillance and limited biosecurity. Data through 2021.",
                "Global scope.",
            ),
        ],
    )
    add_deck(
        "AMR_Global_Update_2026.pptx",
        [
            (
                "AMR surveillance in Africa",
                "Antimicrobial resistance surveillance in livestock. Data through 2025. Reported value: 72 units.",
                "Current demonstration source.",
            ),
            (
                "Key AMR drivers",
                "Recent evidence highlights antimicrobial stewardship, surveillance and biosecurity. Data through 2025.",
                "Global scope with Africa examples.",
            ),
        ],
    )
    add_deck(
        "RENOFARM_Regional_2026.pptx",
        [
            (
                "RENOFARM activities in Africa",
                "Project update as of September 2026: regional engagement, country support and responsible antimicrobial use activities.",
                "Synthetic demonstration content only.",
            )
        ],
    )
    add_deck(
        "One_Health_Methodology.pptx",
        [
            (
                "One Health analytical framework",
                "Methodology for organizing human, animal and environmental evidence. This is evergreen conceptual material.",
                "Date intentionally unknown.",
            )
        ],
    )
    print(f"Created demo presentations in {OUTPUT}")


if __name__ == "__main__":
    main()
