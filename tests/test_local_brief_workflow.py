import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from pptx import Presentation


ROOT = Path(__file__).resolve().parents[1]


def corpus_fixture(tmp_path):
    corpus = tmp_path / "corpus"
    presentations = corpus / "presentations"
    presentations.mkdir(parents=True)
    rows = []
    for country, contents in [
        ("Zambia", [
            ("Antibiotic stewardship training for farmers", "Zambia trained livestock farmers in prudent antibiotic use through workshops."),
            ("Radio outreach on antibiotic stewardship", "Zambian veterinary teams used radio broadcasts to promote responsible use of antibiotics."),
        ]),
        ("Vietnam", [
            ("Veterinary stewardship in Vietnam", "Vietnam surveyed veterinarians on access to antibiotics."),
        ]),
    ]:
        p = Presentation()
        for title, body in contents:
            s = p.slides.add_slide(p.slide_layouts[1])
            s.shapes.title.text = title
            s.placeholders[1].text = body
        path = presentations / f"{country.lower()}.pptx"
        p.save(path)
        rows.append(dict(id=country.lower(), title=f"AMR and veterinary stewardship in {country}",
                         publisher="Teaching service", author="Training team", sector="animal",
                         topic="Antimicrobial stewardship", language="en", issued="2024", series="",
                         training_country=country, source_page="https://example.org/" + country,
                         download_url="https://example.org/" + path.name, zip_member="", license="",
                         evidence_slide="1", slide_count=len(contents),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with (corpus / "verified.csv").open("w", encoding="utf-8", newline="") as stream:
        csvout = csv.DictWriter(stream, fieldnames=rows[0])
        csvout.writeheader()
        csvout.writerows(rows)
    return corpus


def test_cli_exports_only_supported_pages_and_keeps_previous_runs(tmp_path):
    corpus = corpus_fixture(tmp_path)
    root = tmp_path / "briefs"
    cmd = [sys.executable, str(ROOT / "scripts" / "run_local_brief.py"), "--corpus-dir", str(corpus),
           "--output-dir", str(root), "--topic", "Zambia veterinary antibiotic stewardship",
           "--pages", "10"]
    first = subprocess.run(cmd, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    summary = json.loads(first.stdout)
    run = Path(summary["output_directory"])
    assert summary["status"] == "partial" and 0 < summary["selected_pages"] <= 2
    assert summary["requested_pages"] == 10 and not summary["llm_called"]
    assert all(s["source_url"] == "https://example.org/Zambia" for s in summary["selected"])
    assert len(Presentation(run / "styled.pptx").slides) == len(summary["selected"])
    assert json.loads((run / "summary.json").read_text(encoding="utf-8")) == summary
    rerun = subprocess.run(cmd, capture_output=True, text=True)
    assert rerun.returncode == 0, rerun.stderr
    assert Path(json.loads(rerun.stdout)["output_directory"]) != run and (run / "draft.pptx").exists()


def test_no_evidence_produces_a_gap_report_without_a_deck(tmp_path):
    from presentation_search.local_brief import build_brief

    summary = build_brief(corpus_fixture(tmp_path), tmp_path / "runs", topic="medieval harpsichord tuning", pages=5)
    run = Path(summary["output_directory"])
    assert (summary["status"], summary["selected_pages"], summary["llm_called"]) == ("no_evidence", 0, False)
    assert (run / "summary.json").is_file()
    assert not list(run.glob("*.pptx"))


def test_model_evidence_matches_the_published_source_map(tmp_path, monkeypatch):
    from presentation_search import local_brief

    def choose(topic, cards, *, model, limit):
        card = cards[0]
        return [{"slide_id": card["slide_id"], "evidence": "antibiotic" if "antibiotic" in card["snippet"] else card["title"]}]

    monkeypatch.setattr(local_brief, "rerank_candidates", choose)
    report = local_brief.build_brief(corpus_fixture(tmp_path), tmp_path / "runs",
                                     topic="Zambia veterinary antibiotic stewardship", pages=1, model="demo")
    selected = report["selected"][0]
    assert report["llm_called"] and selected["model_evidence"] == selected["evidence"]
    source_map = json.loads((Path(report["output_directory"]) / "source_map.json").read_text())
    assert source_map[0]["evidence"] == selected["model_evidence"]
