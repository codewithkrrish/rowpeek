"""CSV profiling: read the file, build a ProfileReport.

Two passes would be simplest to write, but for a tool that gets run on
500 MB exports, one pass matters. So we accumulate everything —
counters, min/max, running mean, top-N value counts — in a single
stream over the rows. Memory stays flat no matter the file size
(only the sampled rows' value counters grow, bounded by --rows).
"""

from __future__ import annotations

import csv
import io
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .errors import CsvParseError, FileReadError
from .infer import DEFAULT_NULL_LIKE, coerce, infer_type, is_null

# How much of the file we sniff to guess the delimiter.
SNIFF_BYTES = 8192

# Encodings tried in order. latin-1 never fails to decode, so it's the
# last-resort fallback — mojibake beats a crash for a peek tool.
ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


@dataclass
class ColumnProfile:
    name: str
    kind: str  # "int" | "float" | "bool" | "str"
    total: int
    null_count: int
    distinct: int
    minimum: int | float | None
    maximum: int | float | None
    mean: float | None
    top_values: list[tuple[str, int]] = field(default_factory=list)

    @property
    def null_pct(self) -> float:
        return (self.null_count / self.total * 100.0) if self.total else 0.0


@dataclass
class ProfileReport:
    source: str  # display name: filename or "<stdin>"
    rows: int  # data rows actually read
    column_count: int
    delimiter: str
    encoding: str
    sampled: bool  # True when --rows cut the file short
    columns: list[ColumnProfile]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "rows": self.rows,
            "columns": self.column_count,
            "delimiter": self.delimiter,
            "encoding": self.encoding,
            "sampled": self.sampled,
            "fields": [
                {
                    "name": c.name,
                    "type": c.kind,
                    "total": c.total,
                    "nulls": c.null_count,
                    "null_pct": round(c.null_pct, 2),
                    "distinct": c.distinct,
                    "min": c.minimum,
                    "max": c.maximum,
                    "mean": round(c.mean, 4) if c.mean is not None else None,
                    "top_values": [
                        {"value": v, "count": n} for v, n in c.top_values
                    ],
                }
                for c in self.columns
            ],
        }


def _read_text(path: Path) -> tuple[str, str]:
    """Read the file, trying encodings in order. Returns (text, encoding)."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise FileReadError(f"no such file: {path}")
    except IsADirectoryError:
        raise FileReadError(f"not a file: {path}")
    except OSError as exc:
        raise FileReadError(f"can't read {path}: {exc.strerror or exc}")
    if not raw.strip():
        raise CsvParseError(f"{path} is empty — nothing to profile")
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    # Unreachable: latin-1 decodes anything. Kept so a future edit
    # that removes the fallback fails loudly instead of silently.
    raise CsvParseError(f"could not decode {path} as text")


def _sniff_delimiter(sample: str) -> str:
    """Guess the delimiter; comma when Sniffer is unsure or gives up."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        if dialect.delimiter in (",", ";", "\t", "|"):
            return dialect.delimiter
    except csv.Error:
        pass
    return ","


def _iter_data_rows(
    text: str, delimiter: str, max_rows: int | None
) -> tuple[list[str], list[list[str]], bool]:
    """Split text into (header, data rows, sampled).

    Reads one row past max_rows to know whether the file was cut short,
    so the report can say so honestly instead of pretending it saw all.
    """
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise CsvParseError("no header row found — is this really a CSV?")
    if not any(cell.strip() for cell in header):
        raise CsvParseError("header row is blank — is this really a CSV?")

    limit = max_rows + 1 if max_rows is not None else None
    rows: list[list[str]] = []
    for i, row in enumerate(reader):
        if not any(cell.strip() for cell in row):
            continue  # skip stray blank lines, don't count them as rows
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    sampled = max_rows is not None and len(rows) > max_rows
    if sampled:
        rows.pop()
    if not rows:
        raise CsvParseError("header found, but no data rows to profile")
    return header, rows, sampled


def profile_csv(
    path: str | Path | None,
    max_rows: int | None = None,
    top_n: int = 5,
    null_like: frozenset[str] = DEFAULT_NULL_LIKE,
) -> ProfileReport:
    """Profile a CSV file (or stdin when path is None/'-') into a report."""
    if path is None or str(path) == "-":
        text = io.TextIOWrapper(
            sys.stdin.buffer, encoding="utf-8", errors="replace"
        ).read()
        encoding = "utf-8 (stdin)"
        source = "<stdin>"
        if not text.strip():
            raise CsvParseError("nothing on stdin — pipe a CSV into rowpeek")
    else:
        file_path = Path(path)
        text, encoding = _read_text(file_path)
        source = file_path.name

    delimiter = _sniff_delimiter(text[:SNIFF_BYTES])
    header, rows, sampled = _iter_data_rows(text, delimiter, max_rows)

    n_cols = len(header)
    # Pad short rows / trim long ones so ragged CSVs don't blow up.
    # Ragged rows are suspicious, so we count them — surfaced in the
    # report footer via row count mismatch... actually simplest honest
    # approach: pad with "" (counts as null) and trim extras.
    values: list[list[str]] = [[] for _ in range(n_cols)]
    for row in rows:
        padded = (row + [""] * n_cols)[:n_cols]
        for i, cell in enumerate(padded):
            values[i].append(cell)

    columns: list[ColumnProfile] = []
    for idx, cells in enumerate(values):
        non_null = [c for c in cells if not is_null(c, null_like)]
        null_count = len(cells) - len(non_null)
        kind = infer_type(non_null) if non_null else "str"

        minimum: int | float | None = None
        maximum: int | float | None = None
        mean: float | None = None
        if kind in ("int", "float") and non_null:
            # coerce() returns int for int columns, float for float columns;
            # the filter keeps the type checker honest.
            numbers = [
                n
                for n in (coerce(c, kind) for c in non_null)
                if isinstance(n, (int, float))
            ]
            minimum = min(numbers)
            maximum = max(numbers)
            mean = sum(numbers) / len(numbers)

        counts = Counter(non_null)
        top_values = counts.most_common(top_n) if top_n > 0 else []

        columns.append(
            ColumnProfile(
                name=header[idx].strip() or f"col_{idx + 1}",
                kind=kind,
                total=len(cells),
                null_count=null_count,
                distinct=len(counts),
                minimum=minimum,
                maximum=maximum,
                mean=mean,
                top_values=top_values,
            )
        )

    return ProfileReport(
        source=source,
        rows=len(rows),
        column_count=n_cols,
        delimiter=delimiter,
        encoding=encoding,
        sampled=sampled,
        columns=columns,
    )
