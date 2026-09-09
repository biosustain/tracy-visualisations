"""Checks on the vendored gear-genomics submodules.

The bundler reads its JavaScript straight out of the `vendor/` submodules, so a
checkout that is missing or has drifted produces either a `FileNotFoundError`
from deep inside `bundle()` or, worse, an HTML page that renders nothing. These
tests turn both into an obvious failure naming the file and the fix.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "src" / "tracy_visualisations"
PYPROJECT = REPO_ROOT / "pyproject.toml"

BOOTSTRAP_HINT = "run ./scripts/bootstrap-submodules.sh"


def _packaged_vendor_files() -> list[str]:
    """Return the vendor paths listed in pyproject's package-data block."""
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(
        r'"tracy_visualisations"\s*=\s*\[(.*?)\]', text, flags=re.DOTALL
    )
    assert block, "package-data block not found in pyproject.toml"

    entries = re.findall(r'"([^"]+)"', block.group(1))
    return [entry for entry in entries if entry.startswith("vendor/")]


# The vendored sources the package promises to ship.

class TestPackagedVendorFiles:
    def test_pyproject_lists_vendor_files(self):
        # Given the package-data block
        # When the vendor entries are read
        entries = _packaged_vendor_files()

        # Then it names at least one vendored source, or this whole module is
        # silently testing nothing
        assert entries

    @pytest.mark.parametrize("relative", _packaged_vendor_files())
    def test_every_packaged_vendor_file_exists(self, relative):
        # Given a vendor path promised by package-data
        full = PACKAGE_ROOT / relative

        # When the checkout is inspected
        # Then the file is present and non-empty
        assert full.exists(), f"missing vendored file {relative}; {BOOTSTRAP_HINT}"
        assert full.stat().st_size > 0, f"empty vendored file {relative}"


# Submodule pins have to be reachable, not merely recorded.

class TestSubmodulePins:
    def _submodule_status(self):
        result = subprocess.run(
            ["git", "submodule", "status"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("not a git checkout")
        return result.stdout.splitlines()

    def test_no_submodule_is_uninitialised(self):
        # Given the recorded submodules
        lines = self._submodule_status()

        # When their status prefixes are read ('-' means never checked out)
        uninitialised = [line.strip() for line in lines if line.startswith("-")]

        # Then none of them is missing from the working tree
        assert not uninitialised, (
            f"uninitialised submodules: {uninitialised}; {BOOTSTRAP_HINT}"
        )

    def test_every_pin_is_reachable_in_its_checkout(self):
        # Given each submodule's pinned commit
        unreachable = []
        for line in self._submodule_status():
            fields = line.strip().lstrip("-+U").split()
            if len(fields) < 2:
                continue
            pinned, path = fields[0], fields[1]

            # When the commit is looked up inside that submodule
            found = subprocess.run(
                ["git", "-C", path, "cat-file", "-e", f"{pinned}^{{commit}}"],
                cwd=REPO_ROOT,
                capture_output=True,
            )
            if found.returncode != 0:
                unreachable.append(f"{path}@{pinned}")

        # Then every pin resolves, so a fresh clone can reproduce this tree
        assert not unreachable, (
            f"submodule pins not reachable: {unreachable}; {BOOTSTRAP_HINT}"
        )


# The registry and the packaging list have to agree.

class TestRegistryIsPackaged:
    def test_every_registered_source_is_shipped(self):
        from tracy_visualisations.components import COMPONENTS

        # Given the files the registry reads at bundle time
        packaged = set(_packaged_vendor_files())
        referenced = {
            path.as_posix()
            for component in COMPONENTS.values()
            for path in component.sources + component.stylesheets
        }

        # When they are compared with what the wheel ships
        missing = referenced - packaged

        # Then nothing the registry needs is left out of the distribution,
        # which would only show up as a broken install
        assert not missing, f"registry reads files that package-data omits: {missing}"

    def test_every_registered_source_exists_on_disk(self):
        from tracy_visualisations.components import COMPONENTS

        for component in COMPONENTS.values():
            for relative in component.sources + component.stylesheets:
                full = PACKAGE_ROOT / relative
                assert full.exists(), (
                    f"component {component.name!r} reads {relative}, which is "
                    f"missing; {BOOTSTRAP_HINT}"
                )
