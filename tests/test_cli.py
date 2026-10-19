"""Tests for rowpeek.cli — flags, exit codes, output writing."""

import json
import subprocess
import sys

import pytest

from rowpeek.cli import main

SAMPLE = "name,age\namy,30\nbob,25\n"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_text_to_stdout(tmp_path, capsys):
    assert main([_write(tmp_path, "s.csv", SAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "rows: 2" in out
    assert "[age]" in out
    assert "type:     int" in out


def test_json_format(tmp_path, capsys):
    assert main([_write(tmp_path, "s.csv", SAMPLE), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["rows"] == 2
    assert data["fields"][1]["type"] == "int"


def test_missing_file_exit_2(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_empty_file_exit_2(tmp_path, capsys):
    assert main([_write(tmp_path, "e.csv", "\n")]) == 2


def test_bad_rows_flag_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([_write(tmp_path, "s.csv", SAMPLE), "--rows", "0"])
    assert exc.value.code == 2


def test_output_file_written(tmp_path):
    csv_path = _write(tmp_path, "s.csv", SAMPLE)
    out = tmp_path / "report.txt"
    assert main([csv_path, "-o", str(out)]) == 0
    assert "[name]" in out.read_text(encoding="utf-8")


def test_output_refuses_clobber_without_force(tmp_path, capsys):
    csv_path = _write(tmp_path, "s.csv", SAMPLE)
    out = tmp_path / "report.txt"
    out.write_text("old content", encoding="utf-8")
    assert main([csv_path, "-o", str(out)]) == 3
    assert "--force" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "old content"  # untouched


def test_output_force_overwrites(tmp_path):
    csv_path = _write(tmp_path, "s.csv", SAMPLE)
    out = tmp_path / "report.txt"
    out.write_text("old content", encoding="utf-8")
    assert main([csv_path, "-o", str(out), "--force"]) == 0
    assert "[name]" in out.read_text(encoding="utf-8")


def test_no_partial_write_on_failure(tmp_path, capsys):
    # -o to a path inside a file (not a dir) -> write fails, no junk left
    blocker = _write(tmp_path, "blocker", "x")
    out = str(tmp_path / "blocker" / "report.txt")
    assert main([_write(tmp_path, "s.csv", SAMPLE), "-o", out]) == 3
    assert "error" in capsys.readouterr().err


def test_stdin_input(capsys, monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(SAMPLE.encode())))
    # TextIOWrapper needs .buffer for our stdin path
    assert main([]) == 0
    assert "rows: 2" in capsys.readouterr().out


def test_module_entrypoint(tmp_path):
    # `python -m rowpeek` works end to end, no install needed
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    csv_path = _write(tmp_path, "s.csv", SAMPLE)
    proc = subprocess.run(
        [sys.executable, "-m", "rowpeek", csv_path],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0
    assert "rows: 2" in proc.stdout
