"""Tests for the GitHub Pages demo site build.

The site is assembled out of files that live elsewhere in the repository - the
component bundle the package emits, the upstream apps' own sample traces, and
this suite's fixtures - so the two ways it can break are a source moving and
the page asking for a file the build does not produce. Both are checked here,
because neither shows up as anything but a blank section in a browser.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_demo_site  # noqa: E402


# The sample files the demo page renders.

class TestDemoDatasets:
    def test_the_manifest_is_not_empty(self):
        # Given the dataset manifest
        # When it is read
        datasets = build_demo_site.DATASETS

        # Then it names at least one sample, or this module tests nothing
        assert datasets

    @pytest.mark.parametrize(
        "dataset", build_demo_site.DATASETS, ids=lambda d: d.filename
    )
    def test_every_source_is_present_in_the_checkout(self, dataset):
        # Given a sample the demo page promises to render
        source = REPO_ROOT / dataset.source

        # When the checkout is inspected
        # Then the file it is taken from is there and non-empty
        assert source.exists(), (
            f"missing demo sample source {dataset.source}; "
            "run ./scripts/bootstrap-submodules.sh"
        )
        assert source.stat().st_size > 0, f"empty demo sample {dataset.source}"

    @pytest.mark.parametrize(
        "dataset", build_demo_site.DATASETS, ids=lambda d: d.filename
    )
    def test_every_source_reads_as_the_format_it_claims(self, dataset):
        # Given a sample and the reader the manifest pairs it with
        source = REPO_ROOT / dataset.source

        # When it is read
        text = dataset.read(source)

        # Then it is the format the page expects: JSON, or FASTA for the
        # alignment that is deliberately not JSON
        if dataset.filename.endswith(".json"):
            assert isinstance(json.loads(text), dict)
        else:
            assert text.lstrip().startswith(">")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Return a directory the whole site has been built into."""
    # Given an empty output directory
    output_dir = tmp_path_factory.mktemp("site")

    # When the site is built
    build_demo_site.build_site(output_dir)

    return output_dir


# Building the whole site into a directory.

class TestBuildSite:
    def test_writes_the_page(self, site):
        # Then the page is there
        assert (site / "index.html").exists()

    def test_writes_the_component_bundle_the_page_loads(self, site):
        from tracy_visualisations.components import BUNDLE_MARKER

        # Then the bundle is the package's own emitted output, not a copy that
        # could drift from it
        bundle = (site / build_demo_site.BUNDLE_FILENAME).read_text(encoding="utf-8")
        assert BUNDLE_MARKER in bundle

    def test_the_bundle_registers_every_registered_component(self, site):
        from tracy_visualisations.components import COMPONENTS

        # Then every component is demonstrated, sage included: the point of
        # the page is to show what the registry ships
        bundle = (site / build_demo_site.BUNDLE_FILENAME).read_text(encoding="utf-8")
        for component in COMPONENTS.values():
            for tag in component.tags:
                assert f'defineElement("{tag}"' in bundle, f"<{tag}> not registered"

    @pytest.mark.parametrize(
        "dataset", build_demo_site.DATASETS, ids=lambda d: d.filename
    )
    def test_copies_every_dataset_the_page_fetches(self, dataset, site):
        # Then the sample sits where the page fetches it from
        copied = site / build_demo_site.DATA_DIRNAME / dataset.filename
        assert copied.exists()
        assert copied.stat().st_size > 0

    @pytest.mark.parametrize(
        "dataset", build_demo_site.DATASETS, ids=lambda d: d.filename
    )
    def test_renders_a_self_contained_report_for_every_dataset(self, dataset, site):
        # Then each sample also ships as the report the CLI would write for it,
        # so the page can link the components to the product they build
        report = site / build_demo_site.REPORTS_DIRNAME / dataset.report
        html = report.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>")


# The page and the build have to agree on every path.

class TestPageReferences:
    """A renamed sample must fail here, not silently blank a section."""

    def _referenced_paths(self, page: str) -> set[str]:
        """Return the site-relative paths the page loads."""
        # Both the fetch() calls and the report links are plain relative paths
        # in quotes; nothing on the page builds one by concatenation. A link
        # may carry a query - a report linked to one variant - which is the
        # report's own business, not part of the path on disk.
        pattern = (
            rf"['\"]((?:{build_demo_site.DATA_DIRNAME}"
            rf"|{build_demo_site.REPORTS_DIRNAME})/[^'\"]+)['\"]"
        )
        found = re.findall(pattern, page)
        return {re.split(r"[?#]", path)[0] for path in found}

    def test_the_page_references_something(self):
        page = build_demo_site.PAGE_SOURCE.read_text(encoding="utf-8")

        assert self._referenced_paths(page)

    def test_every_path_the_page_loads_is_built(self, site):
        # Given the built site
        page = (site / "index.html").read_text(encoding="utf-8")

        # When every path the page names is resolved against it
        missing = [
            path
            for path in self._referenced_paths(page)
            if not (site / path).exists()
        ]

        # Then none of them is missing
        assert not missing, f"page loads paths the build does not produce: {missing}"

    def test_every_dataset_built_is_used_by_the_page(self):
        # Given the page and the manifest
        page = build_demo_site.PAGE_SOURCE.read_text(encoding="utf-8")
        referenced = self._referenced_paths(page)

        # When each built dataset is looked for
        unused = [
            dataset.filename
            for dataset in build_demo_site.DATASETS
            if f"{build_demo_site.DATA_DIRNAME}/{dataset.filename}" not in referenced
        ]

        # Then the build ships nothing the page never shows
        assert not unused, f"datasets built but not demonstrated: {unused}"
