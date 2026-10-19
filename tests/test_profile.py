"""Tests for rowpeek.profile — reading CSVs and building reports."""

import pytest

from rowpeek.errors import CsvParseError, FileReadError
from rowpeek.profile import profile_csv

SAMPLE = """name,age,city,score,active
amy,30,Delhi,9.5,yes
bob,,Mumbai,8.0,no
cara,25,Delhi,,yes
dev,41,,7.25,yes
"""


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_happy_path(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", SAMPLE))
    assert report.rows == 4
    assert report.column_count == 5
    assert report.delimiter == ","
    assert not report.sampled

    by_name = {c.name: c for c in report.columns}
    assert by_name["age"].kind == "int"
    assert by_name["age"].null_count == 1
    assert by_name["age"].minimum == 25
    assert by_name["age"].maximum == 41
    assert by_name["score"].kind == "float"
    assert by_name["active"].kind == "bool"
    assert by_name["name"].kind == "str"

    city = by_name["city"]
    assert city.null_count == 1
    assert city.distinct == 2
    assert city.top_values[0] == ("Delhi", 2)


def test_null_percentage(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", SAMPLE))
    age = next(c for c in report.columns if c.name == "age")
    assert age.null_pct == pytest.approx(25.0)


def test_semicolon_delimiter_sniffed(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", "a;b\n1;2\n3;4\n"))
    assert report.delimiter == ";"
    assert report.rows == 2


def test_tab_delimiter_sniffed(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", "a\tb\n1\t2\n"))
    assert report.delimiter == "\t"


def test_sampling_reports_honestly(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", SAMPLE), max_rows=2)
    assert report.rows == 2
    assert report.sampled is True


def test_no_sampling_flag_when_file_fits(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", SAMPLE), max_rows=10)
    assert report.sampled is False


def test_ragged_rows_padded_not_crashed(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", "a,b,c\n1,2\n3,4,5,6\n"))
    assert report.rows == 2
    by_name = {c.name: c for c in report.columns}
    assert by_name["c"].null_count == 1  # short row padded


def test_custom_null_tokens(tmp_path):
    report = profile_csv(
        _write(tmp_path, "s.csv", "a\n1\nMISSING\n3\n"),
        null_like=frozenset({"missing"}),
    )
    col = report.columns[0]
    assert col.null_count == 1
    assert col.kind == "int"


def test_missing_file():
    with pytest.raises(FileReadError):
        profile_csv("/does/not/exist.csv")


def test_empty_file(tmp_path):
    with pytest.raises(CsvParseError):
        profile_csv(_write(tmp_path, "e.csv", "   \n"))


def test_header_only(tmp_path):
    with pytest.raises(CsvParseError):
        profile_csv(_write(tmp_path, "h.csv", "a,b,c\n"))


def test_directory_rejected(tmp_path):
    with pytest.raises(FileReadError):
        profile_csv(tmp_path)


def test_latin1_fallback(tmp_path):
    path = tmp_path / "l.csv"
    path.write_bytes("name\ncaf\xe9\n".encode("latin-1"))
    report = profile_csv(path)
    assert report.rows == 1
    assert report.encoding == "latin-1"


def test_json_dict_shape(tmp_path):
    report = profile_csv(_write(tmp_path, "s.csv", SAMPLE))
    data = report.to_dict()
    assert data["rows"] == 4
    assert data["fields"][0]["name"] == "name"
    assert "null_pct" in data["fields"][0]
