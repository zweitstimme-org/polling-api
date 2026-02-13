"""Respondents transformation utilities."""

import re
from dataclasses import dataclass


@dataclass
class RespondentParseResult:
    """Result of parsing respondents field."""

    count: int | None
    method_hint: str | None
    date_range: str | None


def normalize_respondents(respondents_str: str) -> int | None:
    """Extract numeric respondent count from string.

    Args:
        respondents_str: String containing respondent count

    Returns:
        Numeric count or None
    """
    if not respondents_str:
        return None

    s = str(respondents_str)

    # Extract number (handle German format: 1.234)
    match = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)", s)
    if match:
        count_str = match.group(1).replace(".", "")
        try:
            return int(count_str)
        except ValueError:
            pass

    return None


def parse_respondents(respondents_str: str) -> RespondentParseResult:
    """Parse respondents field for count, method, and dates.

    Args:
        respondents_str: Raw respondents field

    Returns:
        Parsed result with count, method hint, and date range
    """
    if not respondents_str:
        return RespondentParseResult(None, None, None)

    s = str(respondents_str)

    # Extract method from prefix (e.g., "O • 2.004" or "TOM • 1.202")
    method_hint = None
    method_prefix_match = re.match(r"^(O|TOM|TO)\s*•\s*", s)
    if method_prefix_match:
        method_prefix = method_prefix_match.group(1).upper()
        if method_prefix == "O":
            method_hint = "Online"
        elif method_prefix in ("TOM", "TO"):
            method_hint = "Telefon & Online"
        # Remove prefix from string for further processing
        s = s[method_prefix_match.end() :]

    # Extract count
    count = normalize_respondents(s)

    # Detect method from remaining text (if not already detected)
    if not method_hint:
        s_lower = s.lower()
        if "telefon" in s_lower or "cati" in s_lower:
            method_hint = "Telefonisch"
        elif "online" in s_lower or "cawi" in s_lower or "panel" in s_lower:
            method_hint = "Online"
        elif (
            "persönlich" in s_lower
            or "persoenlich" in s_lower
            or "face" in s_lower
            or "f2f" in s_lower
        ):
            method_hint = "Persönlich"
        elif "tom" in s_lower or "mixed" in s_lower or "komb" in s_lower:
            method_hint = "Telefon & Online"

    # Extract embedded date range
    date_range = None
    date_match = re.search(r"(\d{1,2}[\.\s]*[–\-][\s]*\d{1,2}[\.\s]*\d{2}[\.\s]*\d{4})", s)
    if date_match:
        date_range = date_match.group(1)

    return RespondentParseResult(count, method_hint, date_range)
