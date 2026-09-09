#!/usr/bin/env python3
"""Write the JavaScript the npm package publishes.

The package is the component registry made installable. Each component gets a
file of its own, so a page that only shows traces does not also ship indigo's
Plotly charts and pearl's editing toolbar, and the default selection gets one
combined bundle as the package's root entry:

    dist/gear-components.js   the default bundle - every component but the one
                              another supersedes - reached by importing the
                              package itself
    dist/teal.js              one component, reached by its subpath
    dist/indigo.js
    ...

The registry decides what is written; package.json's ``exports`` has to name
the same set, which ``tests/test_npm_package.py`` checks.

Usage::

    ./scripts/build_npm_package.py            # writes ./dist
    ./scripts/build_npm_package.py --output _dist
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The package is imported rather than shelled out to, so a stale install cannot
# publish JavaScript built from different sources than the checkout has.
sys.path.insert(0, str(REPO_ROOT / "src"))

from tracy_visualisations.components import COMPONENTS, build_bundle  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist"

# The root entry keeps the name the CLI gives it, so the file someone installs
# and the file `tracy-vis --emit-components` writes are recognisably the same
# thing.
BUNDLE_FILENAME = "gear-components.js"


def component_filename(name: str) -> str:
    """Return the file one component is published as."""
    return f"{name}.js"


def publishable_components() -> list[str]:
    """Return the components that can be published as a file of their own.

    A component that only works inside a generated report - one still
    resolving page elements at module scope - cannot be a standalone file, and
    the registry says so rather than this script guessing.
    """
    return [
        name
        for name, component in COMPONENTS.items()
        if component.standalone_blocker is None
    ]


def build_package_files(output_dir: Path) -> list[Path]:
    """Write every published file into *output_dir*, and return their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = []

    # build_bundle() with no selection is the default bundle, the same one the
    # CLI writes when it is not told otherwise.
    bundle_path = output_dir / BUNDLE_FILENAME
    bundle_path.write_text(build_bundle(), encoding="utf-8")
    written.append(bundle_path)

    for name in publishable_components():
        component_path = output_dir / component_filename(name)
        component_path.write_text(build_bundle([name]), encoding="utf-8")
        written.append(component_path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the JavaScript files the npm package publishes."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write the files into (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args(argv)

    for path in build_package_files(args.output):
        print(f"Written: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
