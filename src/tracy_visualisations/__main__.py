"""Command-line interface for tracy_visualisations.

Usage
-----
    tracy-vis INPUT [OUTPUT] [--type trace|indigo]

Examples
--------
    # Write output.html beside the input file
    tracy-vis results.json

    # Specify an explicit output path
    tracy-vis results.json /tmp/report.html

    # Force the indigo visualisation type
    tracy-vis results.json report.html --type indigo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bundler import bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tracy-vis",
        description=(
            "Bundle a Tracy JSON output file with web visualisation "
            "components into a self-contained HTML file."
        ),
    )
    parser.add_argument(
        "input",
        metavar="INPUT",
        help="Path to the Tracy JSON input file.",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        nargs="?",
        default=None,
        help=(
            "Path for the generated HTML file.  "
            "Defaults to INPUT with the extension replaced by '.html'."
        ),
    )
    parser.add_argument(
        "--type",
        dest="data_type",
        choices=["trace", "indigo"],
        default=None,
        help=(
            "Visualisation type to use.  "
            "Auto-detected from the JSON content when not specified."
        ),
    )

    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    if args.output is None:
        output_path = input_path.with_suffix(".html")
    else:
        output_path = Path(args.output)

    try:
        bundle(input_path, output_path, data_type=args.data_type)
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
