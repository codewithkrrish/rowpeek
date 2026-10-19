"""Tests for rowpeek.infer — type guessing and null detection."""

import pytest

from rowpeek.infer import coerce, infer_type, is_null


@pytest.mark.parametrize(
    "values,expected",
    [
        (["1", "2", "3"], "int"),
        (["-4", "+5", "0"], "int"),
        (["1.5", "2", "3"], "float"),
        ([".5", "1e3", "-2.0"], "float"),
        (["true", "false", "TRUE"], "bool"),
        (["yes", "no", "y", "n"], "bool"),
        (["hello", "world"], "str"),
        (["1", "two"], "str"),  # mixed falls back to str, never guesses wrong
        (["2024-01-01", "hello"], "str"),
        (["  42  "], "int"),  # surrounding whitespace is fine
    ],
)
def test_infer_type(values, expected):
    assert infer_type(values) == expected


def test_empty_values_fall_back_to_str():
    # an all-null column: nothing to infer from, call it str
    assert infer_type([]) == "str"


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("", True),
        ("   ", True),
        ("NULL", True),
        ("n/a", True),
        ("-", True),
        ("?", True),
        ("0", False),
        ("none of your business", False),
    ],
)
def test_is_null(cell, expected):
    assert is_null(cell) is expected


def test_custom_null_tokens():
    assert is_null("missing", frozenset({"missing"})) is True
    assert is_null("", frozenset({"missing"})) is False


def test_coerce():
    assert coerce("42", "int") == 42
    assert coerce("2.5", "float") == 2.5
    assert coerce("yes", "bool") is True
    assert coerce("no", "bool") is False
    assert coerce(" hi ", "str") == "hi"
