"""Lets you run the tool as `python -m rowpeek` too."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
