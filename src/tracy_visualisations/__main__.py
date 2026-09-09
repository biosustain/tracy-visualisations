"""Command-line interface for tracy_visualisations.

Usage
-----
    tracy-vis INPUT [OUTPUT] [--type trace|indigo|msa]

INPUT is either a Tracy JSON file (``tracy align`` / ``tracy decompose``)
or a gapped multi-FASTA alignment such as the ``.align.fa`` written by
``tracy assemble``.

Examples
--------
    # Write output.html beside the input file
    tracy-vis results.json

    # Specify an explicit output path
    tracy-vis results.json /tmp/report.html

    # Force the indigo visualisation type
    tracy-vis results.json report.html --type indigo

    # Render an assembly alignment.  Note the default output path keeps
    # every suffix but the last, i.e. group.align.fa -> group.align.html
    tracy-vis group.align.fa group.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bundler import DATA_TYPES, bundle
from .components import (
    BUNDLE_MARKER,
    COMPONENTS,
    build_bundle,
    default_bundle_components,
)


DEFAULT_COMPONENT_BUNDLE = "gear-components.js"


def _is_generated_bundle(path: Path) -> bool:
    """Return whether *path* holds a bundle this tool wrote earlier."""
    # The marker sits in the banner comment that opens the bundle, so a short
    # prefix of the file is enough to recognise it.
    try:
        with path.open("r", encoding="utf-8") as handle:
            head = handle.read(len(BUNDLE_MARKER) + 200)
    except (OSError, UnicodeDecodeError):
        return False
    return BUNDLE_MARKER in head


def _emit_components(args, parser) -> int:
    """Write the standalone component bundle described by *args*."""
    names = None
    if args.components is not None:
        names = [name.strip() for name in args.components.split(",") if name.strip()]

    # The bundle is built from the vendored sources, so there is no input file
    # to read.  The single positional therefore names the bundle to write, and
    # a second one is a mistake rather than something to guess about.
    if args.output is not None:
        parser.error("INPUT is not used with --emit-components; pass OUTPUT only")

    output_path = Path(args.input or DEFAULT_COMPONENT_BUNDLE)

    # An existing file here is usually the input the user typed out of habit,
    # and the bundle would destroy it.  Replace only our own earlier output.
    if output_path.exists() and not _is_generated_bundle(output_path):
        print(
            f"Error: would overwrite {output_path}, which is not a bundle "
            f"written by tracy-vis.  Remove it or choose another output path.",
            file=sys.stderr,
        )
        return 1

    try:
        script = build_bundle(names)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(script, encoding="utf-8")
    print(f"Written: {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tracy-vis",
        description=(
            "Bundle a Tracy output file (JSON, or a multi-FASTA "
            "alignment) with web visualisation components into a "
            "self-contained HTML file."
        ),
    )
    parser.add_argument(
        "input",
        metavar="INPUT",
        nargs="?",
        default=None,
        help="Path to the Tracy JSON or multi-FASTA input file.",
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
        choices=list(DATA_TYPES),
        default=None,
        help=(
            "Visualisation type to use.  "
            "Auto-detected from the file content when not specified."
        ),
    )

    parser.add_argument(
        "--emit-components",
        action="store_true",
        help=(
            "Write a standalone JavaScript bundle of the web components "
            "instead of a report.  Load it with a plain <script src> and use "
            "the custom elements directly.  The single path argument names "
            "the bundle to write and defaults to 'gear-components.js'; INPUT "
            "is not used."
        ),
    )
    parser.add_argument(
        "--components",
        default=None,
        help=(
            "Comma-separated components for --emit-components.  "
            f"Available: {', '.join(COMPONENTS)}.  "
            f"Defaults to {','.join(default_bundle_components())}."
        ),
    )

    args = parser.parse_args(argv)

    if args.emit_components:
        return _emit_components(args, parser)

    if args.input is None:
        parser.error("INPUT is required unless --emit-components is given")

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
