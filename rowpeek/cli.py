"""Command-line interface — thin by design.

All parsing/printing lives here; everything else is imported. argparse
owns usage errors (exit 2); RowpeekError owns runtime failures, printed
as one line on stderr with exit 2 as well. Exit 0 means a report was
produced; exit 3 means the report couldn't be written.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .errors import OutputError, RowpeekError
from .infer import DEFAULT_NULL_LIKE
from .profile import profile_csv
from .render import render_json, render_text

EXIT_USAGE = 2
EXIT_FAILED = 2
EXIT_OUTPUT = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rowpeek",
        description=(
            "Peek inside any CSV: shape, column types, null %, ranges, "
            "top values. Zero dependencies, instant."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="CSV file to profile (default: read from stdin)",
    )
    parser.add_argument(
        "-n",
        "--rows",
        type=int,
        default=None,
        metavar="N",
        help="profile only the first N data rows (for huge files)",
    )
    parser.add_argument(
        "-t",
        "--top",
        type=int,
        default=5,
        metavar="N",
        help="show top N values per column (default: 5, 0 to hide)",
    )
    parser.add_argument(
        "--nulls",
        default=None,
        metavar="TOKENS",
        help=(
            "comma-separated cell values to treat as missing, "
            f"replacing the default {sorted(DEFAULT_NULL_LIKE)}"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report format (default: text)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="write the report to FILE instead of stdout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow overwriting an existing output file",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _write_output(report: str, output: str, force: bool) -> None:
    """Write via temp file + atomic rename; never clobber without --force."""
    target = Path(output)
    if target.exists() and not force:
        raise OutputError(
            f"{output} already exists — use --force to overwrite it"
        )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(report)
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OutputError:
        raise
    except OSError as exc:
        raise OutputError(f"can't write {output}: {exc.strerror or exc}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.rows is not None and args.rows < 1:
        parser.error("--rows must be at least 1")
    if args.top < 0:
        parser.error("--top can't be negative")

    null_like = DEFAULT_NULL_LIKE
    if args.nulls is not None:
        null_like = frozenset(t.strip().lower() for t in args.nulls.split(","))

    try:
        report = profile_csv(
            None if args.path == "-" else args.path,
            max_rows=args.rows,
            top_n=args.top,
            null_like=null_like,
        )
    except RowpeekError as exc:
        print(f"rowpeek: error: {exc}", file=sys.stderr)
        return EXIT_FAILED

    text = render_json(report) if args.format == "json" else render_text(report)

    if args.output:
        try:
            _write_output(text, args.output, args.force)
        except OutputError as exc:
            print(f"rowpeek: error: {exc}", file=sys.stderr)
            return EXIT_OUTPUT
    else:
        # Broken pipe (e.g. `rowpeek big.csv | head`) shouldn't traceback.
        try:
            sys.stdout.write(text)
        except BrokenPipeError:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
