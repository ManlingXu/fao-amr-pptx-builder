from __future__ import annotations

import calendar
import re
from datetime import date, datetime

from .models import DateSignal

YEAR = r"(?:19\d{2}|20\d{2}|2100)"
YEAR_RE = re.compile(rf"(?<!\d)({YEAR})(?!\d)")
RANGE_RE = re.compile(rf"(?<!\d)({YEAR})\s*[-–—/]\s*({YEAR})(?!\d)")
MONTH = "|".join(calendar.month_name[1:]) + "|" + "|".join(calendar.month_abbr[1:])
MONTH_NUMBERS = {
    name.lower(): number
    for number in range(1, 13)
    for name in (calendar.month_name[number], calendar.month_abbr[number])
}
WRITTEN_DATE = (
    rf"(?:\d{{1,2}}\s+(?:{MONTH})\s+{YEAR}|(?:{MONTH})\s+\d{{1,2}},?\s+{YEAR})"
)
PERIOD = (
    rf"(?:{WRITTEN_DATE}|{YEAR}(?:-\d{{2}}(?:-\d{{2}})?)?|"
    rf"(?:{MONTH})\s+{YEAR}|Q[1-4]\s+{YEAR})"
)
DATA_THROUGH_RE = re.compile(
    rf"(?:data\s*(?:through|to|until|up\s*to|:)|as\s+of|report(?:ing)?\s+(?:date|period)\s*:?|"
    rf"截至|报告日期\s*[:：]?)\s*({PERIOD})(?!\d)(?:\s*[-–—/]\s*({PERIOD})(?!\d))?",
    re.I,
)
VERSION_WORDS_RE = re.compile(
    r"\b(?:final\d*|new|latest|updated?|revised|revision|draft|copy|v\s*\d+|version\s*\d+)\b", re.I
)


def _parse_period(raw: str) -> str | None:
    parts = raw.replace(",", "").split()
    if len(parts) == 3:
        first, second, year = parts
        day, month = (first, second) if first.isdigit() else (second, first)
        month_number = MONTH_NUMBERS.get(month.lower())
        if month_number is None:
            return None
        try:
            return date(int(year), month_number, int(day)).isoformat()
        except ValueError:
            return None
    if raw[:1].isdigit():
        try:
            if len(raw) == 10:
                date.fromisoformat(raw)
            elif len(raw) == 7:
                date.fromisoformat(raw + "-01")
            return raw
        except ValueError:
            return None
    token, year = parts
    if re.fullmatch("Q[1-4]", token, re.I):
        return f"{year}-{int(token[1]) * 3:02d}"
    month_number = MONTH_NUMBERS.get(token.lower())
    if month_number is not None:
        return f"{year}-{month_number:02d}"
    return None


def extract_date_signals(*, text: str, filename: str, modified_at: datetime | None) -> DateSignal:
    """Return the most explicit content period. File timestamps are audit metadata."""
    explicit = []
    for match in DATA_THROUGH_RE.finditer(text or ""):
        period = _parse_period(match.group(2) or match.group(1))
        if period:
            explicit.append((period, match.group(0)))
    if explicit:
        period, evidence = max(explicit)
        return DateSignal(int(period[:4]), 1.0, f"explicit data period ({evidence})", report_date=period)

    ranges = [end for start, end in RANGE_RE.findall(text or "") if start <= end]
    for values, confidence, reason in (
        (ranges, 0.98, "explicit year range"),
        (YEAR_RE.findall(text or ""), 0.60, "slide year"),
        (YEAR_RE.findall(filename), 0.50, "filename year"),
    ):
        if values:
            year = max(values)
            return DateSignal(int(year), confidence, reason, report_date=year)
    return DateSignal(None, 0.0, "date unknown")


def normalize_family_key(value: str) -> str:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    normalized = VERSION_WORDS_RE.sub(" ", YEAR_RE.sub(" ", normalized))
    normalized = re.sub(r"\bupdate\b", " ", normalized)
    return " ".join(re.findall(r"[^\W_]+", normalized, re.UNICODE))


def freshness_score(year: int | None, confidence: float, reference_year: int) -> float:
    if year is None:
        return 0.0
    age = max(0, reference_year - year)
    return round(max(0.0, 1.0 - age / 10.0) * confidence, 6)
