from datetime import datetime, timezone

import pytest

from presentation_search.freshness import extract_date_signals, normalize_family_key


def test_explicit_data_period_outranks_recent_modified_timestamp():
    old_modified_recently = extract_date_signals(
        text="Global AMR overview. Data: 2019–2021",
        filename="AMR_Global_2022_final.pptx",
        modified_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
    )
    newer_content = extract_date_signals(
        text="Global AMR overview. Data through 2025",
        filename="AMR_Global_Update_2026.pptx",
        modified_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )

    assert old_modified_recently.effective_year == 2021
    assert newer_content.effective_year == 2025
    assert newer_content.confidence > old_modified_recently.modified_time_confidence


def test_filename_year_is_used_when_slide_has_no_date():
    signal = extract_date_signals(
        text="AMR surveillance overview",
        filename="Regional_AMR_Africa_2026_v3.pptx",
        modified_at=None,
    )
    assert signal.effective_year == 2026
    assert signal.reason == "filename year"


def test_family_key_removes_years_and_version_markers():
    assert normalize_family_key("AMR Global Update 2026 FINAL v3") == "amr global"
    assert normalize_family_key("AMR_Global_2025_revised") == "amr global"


@pytest.mark.parametrize(
    ("text", "evidence", "expected"),
    [
        ("Data as of 30 September 2026. Target 2030.", "30 September 2026", "2026-09-30"),
        ("Data through September 30, 2026. Target 2030.", "September 30, 2026", "2026-09-30"),
        ("As of 29 Feb 2024. Target 2030.", "29 Feb 2024", "2024-02-29"),
        ("Reporting date: FEB 29 2024. Target 2030.", "FEB 29 2024", "2024-02-29"),
        (
            "Reporting period: 1 January 2025–30 September 2026. Target 2030.",
            "1 January 2025–30 September 2026",
            "2026-09-30",
        ),
    ],
)
def test_written_reporting_date_outranks_target_year(text, evidence, expected):
    signal = extract_date_signals(text=text, filename="Updated_2031.pptx", modified_at=None)

    assert signal.report_date == expected
    assert signal.effective_year == int(expected[:4])
    assert signal.confidence == 1.0
    assert evidence in signal.reason


@pytest.mark.parametrize(
    "text",
    [
        "Data as of 31 September 2026. Target 2030.",
        "Data through February 29, 2025. Target 2030.",
        "Data as of 0 October 2026. Target 2030.",
        "Data through 2026-02-30. Target 2030.",
    ],
)
def test_invalid_calendar_date_is_not_promoted_to_precise_reporting_evidence(text):
    signal = extract_date_signals(text=text, filename="Report.pptx", modified_at=None)

    assert signal.report_date == "2030"
    assert signal.confidence == 0.60
    assert signal.reason == "slide year"


@pytest.mark.parametrize(
    ("text", "expected", "confidence"),
    [
        ("Data through 2026-09-30. Target 2030.", "2026-09-30", 1.0),
        ("Data through 2026-09. Target 2030.", "2026-09", 1.0),
        ("Data through September 2026. Target 2030.", "2026-09", 1.0),
        ("Data through Q3 2026. Target 2030.", "2026-09", 1.0),
        ("Data: 2019–2021. Target 2030.", "2021", 1.0),
        ("Data through 2026. Target 2030.", "2026", 1.0),
        ("Report for 2026.", "2026", 0.60),
    ],
)
def test_existing_iso_month_quarter_and_year_evidence_remains_supported(text, expected, confidence):
    signal = extract_date_signals(text=text, filename="Report.pptx", modified_at=None)

    assert signal.report_date == expected
    assert signal.confidence == confidence
