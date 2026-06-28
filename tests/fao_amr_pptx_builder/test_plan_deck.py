from pathlib import Path
import importlib.util


SCRIPT = Path("skills/fao-amr-pptx-builder/scripts/plan_deck.py")
SCAFFOLD_PHRASES = (
    "summarize",
    "reuse strong points",
    "support key claims",
    "invite discussion",
)


def load_module():
    spec = importlib.util.spec_from_file_location("plan_deck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plan_deck_creates_history_outline_with_sources():
    index = [
        {
            "source_id": "src001",
            "text": "FAO AMR timeline One Health Quadripartite country support",
            "relative_path": "history.pptx",
            "location": "slide 1",
        },
        {
            "source_id": "src002",
            "text": "FAO Action Plan on Antimicrobial Resistance surveillance governance",
            "relative_path": "action-plan.pdf",
            "location": "page 2",
        },
    ]

    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", index)

    assert plan["title"] == "AMR history in FAO"
    assert len(plan["slides"]) >= 10
    assert plan["slides"][0]["layout"] == "title"
    assert any("Key milestones" in slide["title"] for slide in plan["slides"])
    content_slides = [slide for slide in plan["slides"] if slide["layout"] != "title"]
    assert any(slide["source_ids"] for slide in content_slides)


def test_plan_deck_uses_source_text_for_bullets_not_scaffold_instructions():
    index = [
        {
            "source_id": "src001",
            "text": (
                "FAO AMR work links food and agriculture to public health through One Health. "
                "The FAO Action Plan on Antimicrobial Resistance supports countries with "
                "surveillance, governance, and responsible antimicrobial use. "
                "Quadripartite collaboration aligns FAO, WHO, WOAH, and UNEP priorities."
            ),
            "relative_path": "history.pptx",
            "location": "slide 1",
            "kind": "presentation",
        },
        {
            "source_id": "src002",
            "text": (
                "AMR surveillance evidence helps countries monitor risks in agrifood systems. "
                "FAO country support includes national action planning and implementation."
            ),
            "relative_path": "surveillance.pdf",
            "location": "page 3",
            "kind": "report",
        },
    ]

    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", index)

    normal_bullets = [
        bullet
        for slide in plan["slides"]
        if slide["layout"] == "content"
        for bullet in slide["bullets"]
    ]

    assert normal_bullets
    assert not any(
        phrase in bullet.lower()
        for bullet in normal_bullets
        for phrase in SCAFFOLD_PHRASES
    )
    assert any("FAO Action Plan" in bullet for bullet in normal_bullets)
    assert any("Quadripartite" in bullet for bullet in normal_bullets)


def test_plan_deck_returns_evidence_gap_plan_for_empty_index():
    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", [])

    assert plan["title"] == "Evidence gap: AMR history in FAO"
    assert len(plan["slides"]) <= 4
    assert any("evidence gap" in slide["title"].lower() for slide in plan["slides"])
    assert all(not slide["source_ids"] for slide in plan["slides"])


def test_plan_deck_returns_evidence_gap_plan_when_index_has_no_relevant_evidence():
    index = [
        {
            "source_id": "src001",
            "text": "Office catering options and meeting room booking reminders.",
            "relative_path": "admin.txt",
            "location": "document",
            "kind": "document",
        }
    ]

    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", index)

    assert plan["title"] == "Evidence gap: AMR history in FAO"
    content_slides = [slide for slide in plan["slides"] if slide["layout"] == "content"]
    assert content_slides
    assert all("src001" not in slide["source_ids"] for slide in content_slides)


def test_plan_deck_excludes_extraction_warning_from_content_slide_sources():
    index = [
        {
            "source_id": "normal-1",
            "text": "FAO AMR history includes regional action plans and governance milestones.",
            "relative_path": "history.pdf",
            "location": "slide 1",
        },
        {
            "source_id": "warning-1",
            "text": "FAO AMR extraction warning with partial text for slide reconstruction.",
            "relative_path": "history.pdf",
            "location": "extraction warning",
        },
    ]

    module = load_module()
    plan = module.plan_deck("give me a PPT of AMR history in FAO", index)

    content_slide_sources = [
        source_id
        for slide in plan["slides"]
        if slide["layout"] == "content"
        for source_id in slide["source_ids"]
    ]

    assert "warning-1" not in content_slide_sources
    assert "normal-1" in content_slide_sources
