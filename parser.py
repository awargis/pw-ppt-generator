"""Tolerant answer-key parser for pasted/plain-text keys.

The answer box is intentionally format-flexible.  A key may use option letters
(A-D), option numbers ((1)-(4) or 1-4), or numeric/numerical values such as
246, 100, 1.00, -2.5, etc.  Entries may appear in any order and may be
separated by newlines, commas, semicolons, pipes, or spaces.
"""

import re

# A value may be an option label, an integer/decimal numerical answer, or a
# simple fraction.  Parentheses around the value are ignored during cleanup.
_VALUE = r"(?:[A-Da-d]|[-+]?\d+(?:\.\d+)?(?:\s*/\s*[-+]?\d+(?:\.\d+)?)?)"

# The important design choice is to find *key entries*, not to assume that
# question numbers are in ascending order.  ``1: (4), 23: 246, 7: B`` all
# parse independently and therefore order does not matter.
_ENTRY = re.compile(
    rf"(?<!\d)(?:Q(?:uestion)?\.?\s*)?(\d{{1,3}})"
    rf"\s*(?::|=|->|[-–—]|[.)])\s*"
    rf"\(?\s*({_VALUE}(?:\s*[,/&|]\s*{_VALUE})*)\s*\)?",
    re.IGNORECASE,
)

# Also support the compact but common ``1 A`` / ``23 246`` form.  This is
# intentionally used only when the answer value is unambiguous and followed
# by a likely next key or end-of-text, reducing accidental matches.
_SPACE_ENTRY = re.compile(
    rf"(?<!\d)(?:Q(?:uestion)?\.?\s*)?(\d{{1,3}})\s+"
    rf"\(?\s*({_VALUE}(?:\s*[,/&|]\s*{_VALUE})*)\s*\)?"
    rf"(?=\s*(?:[,;|]\s*|(?:Q(?:uestion)?\.?\s*)?\d{{1,3}}\s*(?:[:=->.)]|\s)|$))",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", "", value)
    value = value.strip("()")
    value = value.upper().replace("|", "/")
    return value


def parse(text: str) -> dict[int, str]:
    """Parse an answer key into ``{question_number: answer}``.

    Later occurrences of the same question number intentionally replace an
    earlier one, which makes pasted corrections easy to apply.  The resulting
    dictionary is independent of the order in which entries were supplied.
    """
    source = text or ""
    result: dict[int, str] = {}
    spans: list[tuple[int, int]] = []

    for match in _ENTRY.finditer(source):
        number = int(match.group(1))
        result[number] = _normalize(match.group(2))
        spans.append(match.span())

    # Fill gaps with compact ``question answer`` entries, but never overwrite
    # an explicit colon/equal/dash entry.
    for match in _SPACE_ENTRY.finditer(source):
        if any(match.start() < end and match.end() > start for start, end in spans):
            continue
        number = int(match.group(1))
        result.setdefault(number, _normalize(match.group(2)))

    return result
