"""Tests for tracy_visualisations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_TRACE = DATA_DIR / "sample_trace.json"
SAMPLE_INDIGO = DATA_DIR / "sample_indigo.json"


# ---------------------------------------------------------------------------
# JS transformation helpers
# ---------------------------------------------------------------------------

class TestAdaptTraceviewJs:
    def _adapted(self):
        from tracy_visualisations.bundler import (
            _adapt_traceview_js,
            _read_vendor_js,
            _VENDOR_SAGE_JS,
        )
        return _adapt_traceview_js(_read_vendor_js(_VENDOR_SAGE_JS))

    def test_removes_export_default(self):
        assert "export default" not in self._adapted()

    def test_keeps_class_definition(self):
        assert "class TraceViewElement" in self._adapted()

    def test_adds_custom_elements_define(self):
        assert 'customElements.define("trace-view"' in self._adapted()

    def test_guards_against_double_registration(self):
        assert 'customElements.get("trace-view")' in self._adapted()


class TestAdaptIndigoJs:
    def _adapted(self):
        from tracy_visualisations.bundler import (
            _adapt_indigo_js,
            _read_vendor_js,
            _VENDOR_INDIGO_JS,
        )
        return _adapt_indigo_js(_read_vendor_js(_VENDOR_INDIGO_JS))

    def test_removes_import_statement(self):
        assert "import {" not in self._adapted()

    def test_removes_process_env(self):
        assert "process.env" not in self._adapted()

    def test_removes_api_calls(self):
        assert "API_URL}/upload" not in self._adapted()

    def test_keeps_alignment_view_element(self):
        assert "AlignmentViewElement" in self._adapted()

    def test_keeps_decomposition_view_element(self):
        assert "DecompositionViewElement" in self._adapted()

    def test_keeps_variants_table_element(self):
        assert "VariantsTableElement" in self._adapted()

    def test_keeps_trace_view_element(self):
        assert "TraceViewElement" in self._adapted()

    def test_keeps_custom_elements_define(self):
        assert "customElements.define" in self._adapted()

    def test_keeps_zip_helper(self):
        assert "function zip()" in self._adapted()

    def test_keeps_ungapped_helper(self):
        assert "function ungapped(" in self._adapted()


# ---------------------------------------------------------------------------
# detect_data_type
# ---------------------------------------------------------------------------

class TestDetectDataType:
    def test_trace_detected_by_gapped_trace_key(self):
        from tracy_visualisations import detect_data_type

        data = {"gappedTrace": {"peakA": []}}
        assert detect_data_type(data) == "trace"

    def test_indigo_detected_by_alt1align(self):
        from tracy_visualisations import detect_data_type

        data = {"alt1align": "ACGT", "alt2align": "ACGT"}
        assert detect_data_type(data) == "indigo"

    def test_indigo_detected_by_decomposition(self):
        from tracy_visualisations import detect_data_type

        data = {"decomposition": {"x": [], "y": []}}
        assert detect_data_type(data) == "indigo"

    def test_indigo_detected_by_variants(self):
        from tracy_visualisations import detect_data_type

        data = {"variants": {"columns": [], "rows": []}}
        assert detect_data_type(data) == "indigo"

    def test_unknown_falls_back_to_trace(self):
        from tracy_visualisations import detect_data_type

        assert detect_data_type({"someKey": 1}) == "trace"


# ---------------------------------------------------------------------------
# bundle — return value
# ---------------------------------------------------------------------------

class TestBundleReturnValue:
    def test_returns_string(self):
        from tracy_visualisations import bundle

        result = bundle(SAMPLE_TRACE)
        assert isinstance(result, str)

    def test_trace_html_contains_doctype(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE)
        assert html.startswith("<!DOCTYPE html>")

    def test_trace_html_contains_trace_view_element(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE)
        assert "<trace-view" in html

    def test_trace_html_contains_traceview_js(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE)
        assert "TraceViewElement" in html
        assert "customElements.define" in html

    def test_trace_html_embeds_data(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE)
        data = json.loads(SAMPLE_TRACE.read_text())
        assert str(data["refchr"]) in html

    def test_indigo_html_contains_indigo_components(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO)
        assert "AlignmentViewElement" in html
        assert "DecompositionViewElement" in html
        assert "VariantsTableElement" in html

    def test_indigo_html_contains_alignment_view_element(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO)
        assert "<alignment-view" in html

    def test_indigo_html_embeds_data(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO)
        assert "allele1fraction" in html

    def test_explicit_type_trace(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO, data_type="trace")
        assert "<trace-view" in html
        assert "<alignment-view" not in html

    def test_explicit_type_indigo(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE, data_type="indigo")
        assert "<alignment-view" in html

    def test_invalid_type_raises(self):
        from tracy_visualisations import bundle

        with pytest.raises(ValueError, match="data_type must be"):
            bundle(SAMPLE_TRACE, data_type="unknown")

    def test_missing_file_raises(self):
        from tracy_visualisations import bundle

        with pytest.raises(FileNotFoundError):
            bundle("/nonexistent/path.json")

    def test_filename_appears_in_output(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE)
        assert SAMPLE_TRACE.name in html


# ---------------------------------------------------------------------------
# bundle — file output
# ---------------------------------------------------------------------------

class TestBundleFileOutput:
    def test_writes_html_file(self, tmp_path):
        from tracy_visualisations import bundle

        output = tmp_path / "out.html"
        bundle(SAMPLE_TRACE, output)
        assert output.exists()
        assert output.read_text().startswith("<!DOCTYPE html>")

    def test_returns_html_even_when_writing_file(self, tmp_path):
        from tracy_visualisations import bundle

        output = tmp_path / "out.html"
        result = bundle(SAMPLE_TRACE, output)
        assert isinstance(result, str)
        assert result == output.read_text()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "tracy_visualisations", *args],
            capture_output=True,
            text=True,
        )

    def test_help(self):
        result = self._run("--help")
        assert result.returncode == 0
        assert "INPUT" in result.stdout

    def test_creates_html_file(self, tmp_path):
        import shutil

        src = tmp_path / "sample.json"
        shutil.copy(SAMPLE_TRACE, src)
        result = self._run(str(src))
        assert result.returncode == 0, result.stderr
        out = tmp_path / "sample.html"
        assert out.exists()

    def test_explicit_output_path(self, tmp_path):
        out = tmp_path / "report.html"
        result = self._run(str(SAMPLE_TRACE), str(out))
        assert result.returncode == 0, result.stderr
        assert out.exists()

    def test_type_flag(self, tmp_path):
        out = tmp_path / "out.html"
        result = self._run(str(SAMPLE_TRACE), str(out), "--type", "indigo")
        assert result.returncode == 0, result.stderr
        assert "<alignment-view" in out.read_text()

    def test_missing_input(self):
        result = self._run("/no/such/file.json")
        assert result.returncode != 0

    def test_prints_output_path(self, tmp_path):
        out = tmp_path / "result.html"
        result = self._run(str(SAMPLE_TRACE), str(out))
        assert str(out) in result.stdout

