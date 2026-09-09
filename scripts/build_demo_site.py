#!/usr/bin/env python3
"""Assemble the GitHub Pages demo site into a directory.

The site is the README's "using the components directly" section made
clickable: one page that loads the very bundle ``tracy-vis --emit-components``
writes, hands each custom element a sample file, and links the self-contained
report the CLI builds from that same sample.

Nothing here is a copy of the front-end code or of the samples. The bundle is
built by :func:`tracy_visualisations.components.build_bundle`, the traces come
out of the vendored apps' own demo data, and the rest are this suite's
fixtures, so a page section can only go blank if a source moves - which
``tests/test_demo_site.py`` fails on.

Usage::

    ./scripts/build_demo_site.py            # writes ./site
    ./scripts/build_demo_site.py --output _site
    python3 -m http.server --directory site # then open localhost:8000
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent

# The package is imported rather than shelled out to, so a stale install cannot
# hand the page a bundle built from different sources than the checkout has.
sys.path.insert(0, str(REPO_ROOT / "src"))

from tracy_visualisations import bundle  # noqa: E402
from tracy_visualisations.components import COMPONENTS, build_bundle  # noqa: E402

PAGE_SOURCE = REPO_ROOT / "demo" / "index.html"

DEFAULT_OUTPUT_DIR = REPO_ROOT / "site"
BUNDLE_FILENAME = "gear-components.js"
DATA_DIRNAME = "data"
REPORTS_DIRNAME = "reports"

_VENDOR = Path("src/tracy_visualisations/vendor")
_FIXTURES = Path("tests/data")


# ---------------------------------------------------------------------------
# Reading a sample out of the repository
# ---------------------------------------------------------------------------

def read_text_file(path: Path) -> str:
    """Return a sample that is already in the shape the elements take."""
    return path.read_text(encoding="utf-8")


def read_gear_sample(path: Path) -> str:
    """Return the trace inside one of the gear apps' gzipped demo files.

    Each app ships the response its own server would have returned, so the
    trace sits under a ``data`` key that only that app's page unwraps. The
    elements take the trace itself.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        response = json.load(handle)
    return json.dumps(response["data"], separators=(",", ":"))


# ---------------------------------------------------------------------------
# The samples the page renders
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DemoDataset:
    """One sample file the demo page fetches, and the report built from it.

    ``filename`` is what the page asks for under ``data/``, so it is also the
    name the page has to spell; ``report`` is the name under ``reports/`` that
    the page links to. Keeping the three together is what lets the tests check
    that the page and the build agree on every path.
    """

    filename: str
    source: Path
    read: Callable[[Path], str]
    report: str


# Real traces where the upstream apps ship one, fixtures for the shapes they
# do not: indigo publishes no sample of its decomposition output, and pearl
# ships raw .abi files rather than an assembled session.
DATASETS = (
    DemoDataset(
        filename="raw-trace.json",
        source=_VENDOR / "teal/client/src/static/bin/sample.json.gz",
        read=read_gear_sample,
        report="raw-trace.html",
    ),
    DemoDataset(
        filename="indigo.json",
        source=_FIXTURES / "sample_indigo.json",
        read=read_text_file,
        report="indigo.html",
    ),
    DemoDataset(
        filename="alignment.align.fa",
        source=_FIXTURES / "sample_msa.align.fa",
        read=read_text_file,
        report="alignment.html",
    ),
    DemoDataset(
        filename="assembly.json",
        source=_FIXTURES / "sample_assembly.json",
        read=read_text_file,
        report="assembly.html",
    ),
    DemoDataset(
        filename="aligned-trace.json",
        source=_VENDOR / "sage/client/src/static/bin/sample.json.gz",
        read=read_gear_sample,
        report="aligned-trace.html",
    ),
)


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def build_site(output_dir: Path) -> None:
    """Write the demo site into *output_dir*, replacing what is there."""
    output_dir = Path(output_dir)
    data_dir = output_dir / DATA_DIRNAME
    reports_dir = output_dir / REPORTS_DIRNAME

    for directory in (data_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(PAGE_SOURCE, output_dir / "index.html")

    # Every component, sage included. The default bundle leaves sage out
    # because teal's viewer supersedes it, but this page is where the two can
    # be seen side by side.
    script = build_bundle(list(COMPONENTS))
    (output_dir / BUNDLE_FILENAME).write_text(script, encoding="utf-8")

    for dataset in DATASETS:
        sample_path = data_dir / dataset.filename
        sample_path.write_text(
            dataset.read(REPO_ROOT / dataset.source), encoding="utf-8"
        )
        # Built from the copy the page fetches, so the report and the live
        # elements above it are demonstrably rendering the same bytes.
        bundle(sample_path, reports_dir / dataset.report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the GitHub Pages demo site for the web components."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write the site into (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args(argv)

    build_site(args.output)

    print(f"Built demo site: {args.output}")
    print(f"Preview it with: python3 -m http.server --directory {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
