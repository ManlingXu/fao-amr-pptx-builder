"""Small real decks exercise index, retrieval and traceability together."""
import csv
import hashlib

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches


def _corpus(root):
    files = root / "presentations"
    files.mkdir()
    cases = {
        "zambia": ("Zambia veterinary stewardship", "animal", [
            ("National policy", "The action plan sets a national framework for antibiotic stewardship."),
            ("Outreach", "Radio programmes and meetings reached farmers and traditional leaders."),
            ("Monitoring", "The surveillance network reports antibiotic use in poultry."),
            ("Travel", "Hotel check-in is available from noon."),
            ("AMR stewardship", "The following selected PowerPoint slides provide the core for a presentation on veterinary stewardship, poultry surveillance and farmers."),
        ]),
        "indian": ("Indian stewardship", "animal", [
            ("Farmer outreach", "Local farmers in India met traditional leaders at community meetings."),
        ]),
        "human": ("Zambia clinical stewardship", "human", [
            ("Hospital monitoring", "Hospital antibiotic surveillance covers patient wards."),
        ]),
        "repeat": ("Zambia public stewardship", "one-health", [
            ("Outreach", "Radio programmes and meetings reached farmers and traditional leaders."),
        ]),
    }
    rows = []
    for deck_id, (title, sector, entries) in cases.items():
        prs = Presentation()
        for heading, body in entries:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = heading
            slide.placeholders[1].text = body
        path = files / f"{deck_id}.pptx"
        prs.save(path)
        rows.append(dict(id=deck_id, title=title, sector=sector,
                         publisher="Example publisher", source_page=f"https://example.org/{deck_id}",
                         download_url=f"https://example.org/{deck_id}.pptx",
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with (root / "verified.csv").open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_geography_species_local_evidence_and_duplicates(tmp_path):
    from presentation_search.brief_index import build_brief_index

    _corpus(tmp_path)
    index = build_brief_index(tmp_path)
    hits = index.search("赞比亚如何向农户和传统领袖宣传合理用药", limit=10)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["deck_id"] in {"zambia", "repeat"}
    assert hit["evidence"] in hit[hit["evidence_field"]]
    assert "farmers" in hit["evidence"]
    assert hit["source_url"] == f"https://example.org/{hit['deck_id']}"
    assert hit["source_hash"] == hashlib.sha256(
        (tmp_path / "presentations" / hit["deck_name"]).read_bytes()
    ).hexdigest()
    assert [(h["deck_id"], h["slide_number"])
            for h in index.search("Zambia poultry surveillance", limit=10)] == [("zambia", 3)]
    assert index.search("How did Zambia reach farmers and traditional leaders?", 4)[0]["evidence"] == hit["evidence"]
    assert not index.search("Zambia poultry surveillance", limit=5, sectors=["human"])
    assert not index.search("Nebula photometry", limit=9)


def test_incremental_cache_excludes_changed_and_removed_files(tmp_path):
    from presentation_search.brief_index import build_brief_index

    _corpus(tmp_path)
    db = tmp_path / "saved.sqlite3"
    assert build_brief_index(tmp_path, db).stats["parsed_decks"] == 4
    warm = build_brief_index(tmp_path, db)
    assert db.is_file()
    assert warm.stats["reused_decks"] == 4
    deck = tmp_path / "presentations" / "zambia.pptx"
    with deck.open("ab") as stream:
        stream.write(b"new version")
    (tmp_path / "presentations" / "repeat.pptx").unlink()
    after = build_brief_index(tmp_path, db)
    assert after.stats["decks"] == 2
    assert after.stats["reused_decks"] == 2
    assert {x["deck_id"] for x in after.stats["failures"]} == {"zambia", "repeat"}
    assert not after.search("Zambia poultry surveillance", 10)


def test_returns_supported_order_and_page_level_reasons(tmp_path):
    from presentation_search.brief_index import build_brief_index, order_story

    _corpus(tmp_path)
    index = build_brief_index(tmp_path)
    hits = index.search("Zambia veterinary stewardship", limit=8, sectors=["animal"])
    assert {h["slide_number"] for h in hits} == {1, 2, 3}
    assert all(h["deck_id"] == "zambia" and h["score"] > 0 and h["reason"] for h in hits)
    assert [h["slide_number"] for h in order_story(list(reversed(hits)))] == [1, 2, 3]


def test_multisection_topic_can_cover_a_policy_audience_and_species(tmp_path):
    from presentation_search.brief_index import build_brief_index

    _corpus(tmp_path)
    topic = "Veterinary stewardship in Zambia: national action plan, farmer outreach, training and surveillance in poultry and pigs"
    hits = build_brief_index(tmp_path).search(topic, 10, sectors=["animal"])
    assert {r["slide_number"] for r in hits} == {1, 2, 3}


def test_annual_series_orders_measures_then_reporting_year_and_source_page():
    from presentation_search.brief_index import order_story

    def candidate(year, number, title, body, score):
        return dict(deck_id=str(year), deck_title=f"UK-VARSS {year}", series="UK VARSS",
                    issued="2024" if year == 2019 else "2023", slide_number=number,
                    title=title, body=body, stage="Monitoring", score=score)

    rows = [
        candidate(2021, 17, "Slide 17", "Clinical surveillance of diagnostic samples", 10),
        candidate(2021, 4, "Antibiotic Sales", "Annual sales in mg/kg", 9),
        candidate(2019, 8, "Antibiotic Sales", "The total amount sold was 190 tonnes", 8),
        candidate(2019, 13, "Clinical Surveillance", "Cattle samples", 7),
        candidate(2019, 6, "Sales of Antibiotics", "Primary measure in mg/kg", 6),
        candidate(2019, 12, "Clinical Surveillance", "Sheep samples", 5),
        candidate(2021, 3, "Antibiotic Sales", "The total amount sold was 170 tonnes", 4),
    ]
    assert [(row["deck_id"], row["slide_number"]) for row in order_story(rows)] == [
        ("2019", 6), ("2021", 4), ("2019", 8), ("2021", 3),
        ("2019", 12), ("2019", 13), ("2021", 17),
    ]
    for row in rows:
        if row["deck_id"] == "2021":
            row["deck_title"] = "UK-VARSS comparative report 2020–2021"
    assert order_story(rows)[0] is rows[0]  # No assumed reporting year when ambiguous.


def test_selects_readable_content_instead_of_repeating_a_generic_title(tmp_path):
    from presentation_search.brief_index import _evidence, Features

    title = "Zambia: awareness and outreach"
    page = dict(title=title, body=title + "\nRadio programs\nMeetings\n\nFarmers\nTraditional leaders", notes="")
    evidence, field = _evidence(page, Features.of("Zambia awareness and outreach"))
    assert field == "body" and "Radio" in evidence and "Farmers" in evidence
    assert evidence in page["body"]


def test_parsed_chart_title_axis_and_labels_are_searchable_as_actual_text(tmp_path):
    from presentation_search.pptx_parser import parse_presentation

    chart_data = CategoryChartData()
    chart_data.categories = ["District clinics", "Regional hospitals"]
    chart_data.add_series("Prescribing audits", (4, 9))
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1),
                                   Inches(6), Inches(3), chart_data).chart
    chart.has_title = True
    chart.chart_title.text_frame.text = "Antibiotic stewardship coverage"
    chart.value_axis.has_title = True
    chart.value_axis.axis_title.text_frame.text = "Number of reviews"
    f = tmp_path / "chart.pptx"
    deck.save(f)
    body = parse_presentation(f).slides[0].text
    assert all(s in body for s in ("Antibiotic stewardship coverage", "Number of reviews",
                                   "Prescribing audits", "District clinics", "Regional hospitals"))
