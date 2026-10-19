"""Report rendering: human text output and machine JSON."""

from __future__ import annotations

import json

from .profile import ColumnProfile, ProfileReport

# Printable names for delimiters Sniffer can return.
DELIMITER_NAMES = {",": "comma (,)", ";": "semicolon (;)", "\t": "tab", "|": "pipe (|)"}


def _fmt_number(value: int | float | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, float):
        return f"{value:,.4g}"
    return f"{value:,}"


def render_text(report: ProfileReport) -> str:
    """A scannable one-page-ish text report."""
    lines = [
        f"rowpeek: {report.source}",
        f"rows: {report.rows:,}"
        + (" (sampled — file has more)" if report.sampled else ""),
        f"columns: {report.column_count}",
        f"delimiter: {DELIMITER_NAMES.get(report.delimiter, repr(report.delimiter))}",
        f"encoding: {report.encoding}",
        "",
    ]
    for col in report.columns:
        lines.append(_render_column(col))
    return "\n".join(lines).rstrip() + "\n"


def _render_column(col: ColumnProfile) -> str:
    lines = [
        f"[{col.name}]",
        f"  type:     {col.kind}",
        f"  nulls:    {col.null_count:,} ({col.null_pct:.1f}%)",
        f"  distinct: {col.distinct:,}",
    ]
    if col.kind in ("int", "float"):
        lines.append(
            f"  min: {_fmt_number(col.minimum)}   "
            f"max: {_fmt_number(col.maximum)}   "
            f"mean: {_fmt_number(col.mean)}"
        )
    if col.top_values:
        lines.append("  top values:")
        width = max(len(str(v)) for v, _ in col.top_values)
        for value, count in col.top_values:
            lines.append(f"    {str(value):<{width}}  {count:,}")
    return "\n".join(lines) + "\n"


def render_json(report: ProfileReport) -> str:
    """The same report as JSON, for scripts and notebooks."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
