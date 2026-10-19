# rowpeek

Peek inside any CSV in seconds — shape, column types, null %, ranges, top values. Zero dependencies, instant.

```
$ rowpeek users.csv
rowpeek: users.csv
rows: 12,483
columns: 7
delimiter: comma (,)
encoding: utf-8-sig

[age]
  type:     int
  nulls:    312 (2.5%)
  distinct: 84
  min: 13   max: 97   mean: 34.2

[country]
  type:     str
  nulls:    0 (0.0%)
  distinct: 148
  top values:
    US  4,102
    IN  2,877
    GB  1,204
```

## Why I built this

I download a lot of CSVs — scraped datasets, dashboard exports, Kaggle files — and before I trust one I always end up writing the same five-line pandas script: how many rows, what are the columns, what's missing, what do the values look like. pandas takes a few seconds just to import. I wanted something that answers in the time it takes to hit enter.

rowpeek is that. Point it at a file, get the one-page summary you'd have eyeballed anyway.

## Install

```bash
pip install rowpeek
```

Or run it without installing:

```bash
python -m rowpeek data.csv
```

Requires Python 3.9+. No dependencies at all — that's the point.

## Usage

```bash
rowpeek data.csv                  # profile a file
rowpeek data.csv -n 10000         # only peek at the first 10k rows (huge files)
rowpeek data.csv -t 10            # show top 10 values per column
rowpeek data.csv --format json    # machine-readable output for scripts
rowpeek data.csv -o report.txt    # save the report (won't clobber without --force)
cat data.csv | rowpeek            # works on stdin too

rowpeek --help
```

Custom null tokens (replaces the default set of `""`, `null`, `none`, `na`, `n/a`, `-`, `?`):

```bash
rowpeek data.csv --nulls "missing,unknown,-999"
```

What it figures out on its own: the delimiter (comma, semicolon, tab, pipe), the encoding (tries UTF-8, falls back to latin-1), and each column's type (int, float, bool, or str — a column is only `int` if *every* value parses as one).

## What it won't do (honest limitations)

- **Dates are strings.** It won't tell you `2024-01-03` is a date — type detection is int/float/bool/str only. Date parsing has too many formats to guess safely, and I'd rather under-claim.
- **Delimiter sniffing can be fooled.** Weird files with commas inside unquoted fields will confuse it, like they'd confuse anything.
- **Big files: use `-n`.** It streams in one pass so memory stays flat, but profiling 10M rows still takes a while. Sample first.
- **`--nulls` replaces, doesn't extend**, the default null set. And yes, `na` being null-by-default is wrong if your column is countries (Namibia). Override it.

## Project structure

```
rowpeek/
  rowpeek/
    cli.py       # argparse, exit codes, atomic file writes — thin by design
    profile.py   # one-pass CSV profiling, the actual logic
    infer.py     # type guessing: narrowest type every value parses as
    render.py    # text and JSON report formatting
    errors.py    # specific exceptions, human messages, no tracebacks
  tests/         # pytest, 46 tests
```

## License

MIT — see [LICENSE](LICENSE).

Built by [Krrish](https://github.com/codewithkrrish).
