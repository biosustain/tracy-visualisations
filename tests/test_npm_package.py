"""Tests for the npm package: its manifest, and the files it publishes.

The package is the component registry made installable - one file per
component, plus the default bundle as the root entry - so the manifest has to
agree with three things it cannot import: the version in pyproject.toml, the
paths the build script writes, and which components the registry actually
ships. JSON takes no comments either, so what the manifest cannot explain about
itself is asserted here instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_npm_package  # noqa: E402

MANIFEST = REPO_ROOT / "package.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"

GITHUB_REGISTRY = "https://npm.pkg.github.com"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    """Return a directory the package's JavaScript has been built into."""
    output_dir = tmp_path_factory.mktemp("dist")
    build_npm_package.build_package_files(output_dir)
    return output_dir


def _python_version() -> str:
    """Return the version pyproject declares for the Python package."""
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert match, "no version found in pyproject.toml"
    return match.group(1)


def _repository_owner(manifest: dict) -> str:
    """Return the GitHub owner the manifest's repository URL points at."""
    url = manifest["repository"]["url"]
    match = re.search(r"github\.com/([^/]+)/", url)
    assert match, f"cannot read an owner out of {url!r}"
    return match.group(1)


def _standalone_components() -> list[str]:
    """Return the components that can be published as a file of their own."""
    from tracy_visualisations.components import COMPONENTS

    return [
        name
        for name, component in COMPONENTS.items()
        if component.standalone_blocker is None
    ]


def _registered_tags(script: str) -> set[str]:
    """Return the custom element tags *script* registers."""
    return set(re.findall(r'defineElement\("([^"]+)"', script))


# Publishing to GitHub Packages puts requirements on the manifest itself.

class TestGitHubPackages:
    def test_the_scope_is_the_repository_owner(self, manifest):
        # Given the package name and the repository it is published from
        scope = manifest["name"].split("/")[0].lstrip("@")

        # When the two are compared
        # Then they match: GitHub Packages refuses a package whose scope is not
        # the owning account, and the error it gives says only "not found"
        assert scope == _repository_owner(manifest)

    def test_the_name_is_scoped(self, manifest):
        # Then the name carries a scope at all, which an unscoped package
        # cannot on this registry
        assert manifest["name"].startswith("@")
        assert "/" in manifest["name"]

    def test_it_publishes_to_the_github_registry(self, manifest):
        # Then a plain `npm publish` goes to GitHub rather than npmjs.com,
        # without the publisher having to remember --registry
        assert manifest["publishConfig"]["registry"] == GITHUB_REGISTRY


# The two version numbers for one release.

class TestVersion:
    def test_it_matches_the_python_package(self, manifest):
        # Given the version each half of the release declares
        # When they are compared
        # Then they are the same version: one commit is one release, whether it
        # is installed with pip or with npm
        assert manifest["version"] == _python_version()


# Every component has to be installable on its own.

class TestComponentSubpaths:
    """The registry decides what is importable; the manifest has to follow."""

    @pytest.mark.parametrize("name", _standalone_components())
    def test_every_component_has_a_subpath_of_its_own(self, name, manifest):
        # Given a component the registry can emit as a standalone bundle
        # When the manifest's exports are read
        # Then it is importable by name, so a page can take one viewer without
        # shipping the other apps' JavaScript
        assert f"./{name}" in manifest["exports"], (
            f"component {name!r} is not importable as "
            f"{manifest['name']}/{name}"
        )

    def test_no_subpath_names_a_component_that_is_not_registered(self, manifest):
        # Given every subpath but the root entry
        subpaths = [key for key in manifest["exports"] if key != "."]

        # When each is matched against the registry
        unknown = [
            key for key in subpaths if key.lstrip("./") not in _standalone_components()
        ]

        # Then none of them promises a component that no longer exists, which
        # would install and then register nothing
        assert not unknown, f"exports name components the registry does not ship: {unknown}"

    def test_every_export_target_is_written_by_the_build(self, manifest, built):
        # Given the files the build script produces
        # When each export target is resolved against them
        missing = [
            target
            for target in manifest["exports"].values()
            if not (built / Path(target).name).exists()
        ]

        # Then every one of them is there; an export pointing at a file the
        # build does not write installs as a broken import
        assert not missing, f"exports point at files the build does not write: {missing}"

    def test_every_export_target_is_packed(self, manifest):
        # Given what `files` promises to publish
        packed = [entry.rstrip("/") for entry in manifest["files"]]

        # When each export target is checked against it
        unpacked = [
            target
            for target in manifest["exports"].values()
            if not any(
                target.lstrip("./") == entry or target.lstrip("./").startswith(entry + "/")
                for entry in packed
            )
        ]

        # Then all of them ship: a target left out of `files` is an import that
        # only breaks once the package is installed from the registry
        assert not unpacked, f"exports point outside `files`: {unpacked}"


# What each published file actually contains.

class TestPublishedFiles:
    def test_the_root_entry_is_the_default_bundle(self, manifest, built):
        from tracy_visualisations.components import COMPONENTS, default_bundle_components

        # Given the root entry
        root = (built / Path(manifest["exports"]["."]).name).read_text(encoding="utf-8")
        registered = _registered_tags(root)

        # When the registry's default selection is compared with it
        expected = {
            tag
            for name in default_bundle_components()
            for tag in COMPONENTS[name].tags
        }

        # Then a bare `import` of the package gets exactly the default bundle -
        # every component but the one another supersedes
        assert registered == expected

    @pytest.mark.parametrize("name", _standalone_components())
    def test_a_component_file_registers_only_its_own_elements(self, name, built):
        from tracy_visualisations.components import COMPONENTS

        # Given one component's file
        script = (built / build_npm_package.component_filename(name)).read_text(
            encoding="utf-8"
        )

        # When the tags it registers are read
        registered = _registered_tags(script)

        # Then they are that component's and no one else's, which is the whole
        # point of the split: importing teal must not pull in indigo's charts
        assert registered == set(COMPONENTS[name].tags)

    def test_the_built_files_are_ignored_by_git(self, manifest):
        # Given the entry file the build writes.  Asking about the directory
        # instead would only answer while it happens to exist on disk: the
        # pattern is `dist/`, and git cannot match a directory-only pattern
        # against a name it has nothing to resolve
        built_entry = manifest["main"]

        # When git is asked whether it is ignored
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", built_entry],
            cwd=REPO_ROOT,
            capture_output=True,
        )

        # Then it is: the files are emitted from the vendored sources on every
        # publish, and a stale copy committed by hand would quietly become what
        # npm ships
        assert ignored.returncode == 0, f"{built_entry} is not gitignored"

    def test_side_effects_are_declared(self, manifest):
        # Then a bundler is told to keep the import: the package's whole job is
        # the side effect of registering the elements, and tree-shaking it away
        # leaves a page of unknown tags that render nothing
        assert manifest["sideEffects"] is True
