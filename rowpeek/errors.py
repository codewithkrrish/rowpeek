"""User-facing errors for rowpeek.

Every failure a user can hit gets its own type so the CLI can print a
one-line, human message on stderr with the right exit code — never a
raw traceback for something as mundane as a missing file.
"""


class RowpeekError(Exception):
    """Base class. The CLI catches this, prints str(err), exits 2."""


class FileReadError(RowpeekError):
    """The input file can't be found or read."""


class CsvParseError(RowpeekError):
    """The file exists but isn't something we can profile as CSV."""


class OutputError(RowpeekError):
    """The report couldn't be written (path exists, unwritable, ...)."""
