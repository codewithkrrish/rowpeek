"""Value-level type inference.

The rule is deliberately simple: a column's type is the narrowest type
that *every* non-null value in it parses as. int < float < bool < str.

So ["1", "2", "3"] is int, ["1", "2.5"] is float, ["yes", "no"] is bool,
and ["1", "two"] is str — mixed columns fall back to str rather than
guessing wrong. That's the honest choice for a tool whose job is to
tell you what you're actually looking at.
"""

from __future__ import annotations

import re

# Truthy / falsy words. Deliberately small: "1"/"0" stay int, "y"/"n"
# are ambiguous so we call them bool and say so in the README.
TRUE_WORDS = frozenset({"true", "t", "yes", "y"})
FALSE_WORDS = frozenset({"false", "f", "no", "n"})

# What counts as "missing" by default. Override with --nulls.
# (Keeping "na" out of the *default* was tempting — Namibia — but for a
# quick-peek tool the common export conventions win; it's one flag away.)
DEFAULT_NULL_LIKE = frozenset({"", "null", "none", "na", "n/a", "-", "?"})

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


def is_null(value: str, null_like: frozenset[str] = DEFAULT_NULL_LIKE) -> bool:
    """True if a raw cell value should be treated as missing."""
    return value.strip().lower() in null_like


def _classify(value: str) -> str:
    """Classify one non-null cell. Never called with nulls."""
    text = value.strip()
    if _INT_RE.match(text):
        return "int"
    if _FLOAT_RE.match(text):
        return "float"
    if text.lower() in TRUE_WORDS or text.lower() in FALSE_WORDS:
        return "bool"
    return "str"


def infer_type(values: list[str]) -> str:
    """Narrowest type shared by all values; "str" if they disagree."""
    kinds = {_classify(v) for v in values}
    if len(kinds) == 1:
        return kinds.pop()
    # int + float columns are just float in disguise
    if kinds == {"int", "float"}:
        return "float"
    return "str"


def coerce(value: str, kind: str) -> int | float | bool | str:
    """Parse a cell into its inferred kind. Assumes the value parses."""
    text = value.strip()
    if kind == "int":
        return int(text)
    if kind == "float":
        return float(text)
    if kind == "bool":
        return text.lower() in TRUE_WORDS
    return text
