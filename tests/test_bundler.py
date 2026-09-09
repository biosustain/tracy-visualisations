"""Tests for tracy_visualisations."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_TRACE = DATA_DIR / "sample_trace.json"
SAMPLE_INDIGO = DATA_DIR / "sample_indigo.json"
SAMPLE_MSA = DATA_DIR / "sample_msa.align.fa"


# ---------------------------------------------------------------------------
# JS transformation helpers
# ---------------------------------------------------------------------------

class TestAdaptTraceviewJs:
    def _adapted(self):
        from tracy_visualisations.bundler import (
            _adapt_traceview_js,
            _read_vendor_file,
            _VENDOR_TRACE_JS,
        )
        return _adapt_traceview_js(_read_vendor_file(_VENDOR_TRACE_JS))

    def test_removes_export_default(self):
        assert "export default" not in self._adapted()

    def test_keeps_class_definition(self):
        assert "class TraceViewElement" in self._adapted()

    def test_adds_custom_elements_define(self):
        # Registration is emitted by the component registry rather than spelled
        # out per tag, so assert the tag is registered, not how it is written.
        assert 'defineElement("teal-trace-view", TraceViewElement)' in self._adapted()

    def test_guards_against_double_registration(self):
        assert "if (!customElements.get(tag))" in self._adapted()


class TestAdaptIndigoJs:
    def _adapted(self):
        from tracy_visualisations.bundler import (
            _adapt_indigo_js,
            _read_vendor_file,
            _VENDOR_INDIGO_JS,
        )
        return _adapt_indigo_js(_read_vendor_file(_VENDOR_INDIGO_JS))

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
        assert "<teal-trace-view" in html

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
        assert "<indigo-alignment-view" in html

    def test_indigo_html_embeds_data(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO)
        assert "allele1fraction" in html

    def test_explicit_type_trace(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_INDIGO, data_type="trace")
        assert "<teal-trace-view" in html
        assert "<indigo-alignment-view" not in html

    def test_explicit_type_indigo(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_TRACE, data_type="indigo")
        assert "<indigo-alignment-view" in html

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
# bundle — indigo variant links
# ---------------------------------------------------------------------------

class TestIndigoVariantLinks:
    """`?<variants-table id>=<n>` opens the viewer on the n-th variant."""

    def _indigo_html(self):
        from tracy_visualisations import bundle

        return bundle(SAMPLE_INDIGO)

    def test_reads_the_variant_index_from_the_query_string(self):
        # Given / When an indigo viewer is bundled
        html = self._indigo_html()

        # Then the page reads the variant to show out of the URL query
        assert "requestedVariantIndex" in html
        assert "new URLSearchParams(window.location.search)" in html

    def test_names_the_parameter_after_the_variants_table(self):
        # Given / When an indigo viewer is bundled
        html = self._indigo_html()

        # Then the parameter is keyed on the table's element id, both when read
        # and when written back
        assert ".get(variantsTable.id)" in html
        assert "params.set(variantsTable.id, index)" in html

    def test_reuses_the_variants_table_show_action(self):
        # Given / When an indigo viewer is bundled
        html = self._indigo_html()

        # Then it goes through the callback the variants table registers, so a
        # link lands on the same view as a hand-clicked row
        assert "trackVariantSelection" in html
        assert "window.__variantViewers" in html

    def test_keeps_a_clicked_row_in_the_url(self):
        # Given / When an indigo viewer is bundled
        html = self._indigo_html()

        # Then clicking a row pushes the URL, so the address bar is always a
        # link to what is on screen and back/forward have somewhere to go
        assert "rememberVariantInUrl" in html
        assert "window.history.pushState" in html

    def test_follows_the_url_changing_under_it(self):
        # Given / When an indigo viewer is bundled
        html = self._indigo_html()

        # Then back and forward, which move between those entries without
        # reloading, bring the view along
        assert "'popstate'" in html
        assert "followUrl" in html

    def test_trace_viewer_has_no_variant_links(self):
        from tracy_visualisations import bundle

        # Given a trace (non-indigo) JSON file
        # When it is bundled
        html = bundle(SAMPLE_TRACE)

        # Then the variants-table specific handling is absent
        assert "trackVariantSelection" not in html


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
        assert "<indigo-alignment-view" in out.read_text()

    def test_missing_input(self):
        result = self._run("/no/such/file.json")
        assert result.returncode != 0

    def test_prints_output_path(self, tmp_path):
        out = tmp_path / "result.html"
        result = self._run(str(SAMPLE_TRACE), str(out))
        assert str(out) in result.stdout



# ---------------------------------------------------------------------------
# Sabre / multiple sequence alignment
# ---------------------------------------------------------------------------

class TestIsFasta:
    def test_recognises_a_fasta_header(self):
        from tracy_visualisations.bundler import _is_fasta

        assert _is_fasta(">read_1\nACGT\n")

    def test_tolerates_leading_whitespace(self):
        from tracy_visualisations.bundler import _is_fasta

        assert _is_fasta("\n  >read_1\nACGT\n")

    def test_rejects_json(self):
        from tracy_visualisations.bundler import _is_fasta

        assert not _is_fasta('{"gappedTrace": {}}')


class TestBundleMsa:
    def test_renders_a_fasta_without_an_explicit_type(self):
        from tracy_visualisations import bundle

        assert "Alignment Browser" in bundle(SAMPLE_MSA)

    def test_inlines_the_sabre_stylesheet(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_MSA)
        assert ".alignment-block" in html
        assert ".tie-match" in html

    def test_declares_d_none_locally_so_the_page_works_offline(self):
        from tracy_visualisations import bundle

        assert ".d-none { display: none !important; }" in bundle(SAMPLE_MSA)

    def test_leaves_no_unsubstituted_placeholders(self):
        from tracy_visualisations import bundle

        assert not re.search(r"\{\{\w+\}\}", bundle(SAMPLE_MSA))

    def test_renders_through_the_msa_view_element(self):
        from tracy_visualisations import bundle

        # Given a FASTA alignment
        # When it is bundled
        html = bundle(SAMPLE_MSA)

        # Then the page hands it to the element rather than reproducing
        # sabre's page scaffold of hidden inputs and buttons
        assert "<sabre-msa-view" in html
        assert "MsaViewElement" in html
        assert 'defineElement("sabre-msa-view"' in html

    def test_needs_none_of_sabres_page_scaffold(self):
        from tracy_visualisations import bundle

        # Given the componentised sabre
        html = bundle(SAMPLE_MSA)

        # When the ids sabre.js used to resolve at module scope are looked for
        # Then they are gone, along with the hidden elements that fed them
        for retired in ("btn-submit", "btn-example", "link-results", "input-file"):
            assert f'id="{retired}"' not in html

    def test_passes_the_alignment_as_data_not_markup(self):
        from tracy_visualisations import bundle

        # Given the fixture alignment
        # When it is bundled
        html = bundle(SAMPLE_MSA)

        # Then it travels as a JS string handed to displayData, the way the
        # trace and indigo templates already pass their data
        assert "displayData(fasta)" in html
        assert "read_1 (forward)" in html

    def test_exposes_characters_per_line_as_an_attribute(self):
        from tracy_visualisations import bundle

        html = bundle(SAMPLE_MSA)
        assert 'characters-per-line="80"' in html

    def test_explicit_msa_type(self):
        from tracy_visualisations import bundle

        assert "Alignment Browser" in bundle(SAMPLE_MSA, data_type="msa")

    def test_rejects_a_json_type_for_a_fasta_input(self):
        from tracy_visualisations import bundle

        with pytest.raises(ValueError, match="which is FASTA"):
            bundle(SAMPLE_MSA, data_type="trace")

    def test_rejects_the_msa_type_for_a_json_input(self):
        from tracy_visualisations import bundle

        with pytest.raises(ValueError, match="which is JSON"):
            bundle(SAMPLE_TRACE, data_type="msa")

    def test_writes_the_html_file(self, tmp_path):
        from tracy_visualisations import bundle

        out = tmp_path / "msa.html"
        bundle(SAMPLE_MSA, out)
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    def test_cli_renders_an_alignment(self, tmp_path):
        out = tmp_path / "msa.html"
        result = subprocess.run(
            [sys.executable, "-m", "tracy_visualisations", str(SAMPLE_MSA), str(out)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()


# ---------------------------------------------------------------------------
# CLI — emitting the standalone component bundle
# ---------------------------------------------------------------------------

class TestCLIEmitComponents:
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "tracy_visualisations", *args],
            capture_output=True,
            text=True,
        )

    def test_writes_a_bundle_without_any_input_file(self, tmp_path):
        # Given no input file at all
        out = tmp_path / "gear-components.js"

        # When only the emit flag is given
        result = self._run("--emit-components", str(out))

        # Then a bundle is written, because components do not come from input
        assert result.returncode == 0, result.stderr
        assert out.exists()
        assert "customElements" in out.read_text(encoding="utf-8")

    def test_reports_the_written_path(self, tmp_path):
        out = tmp_path / "bundle.js"
        result = self._run("--emit-components", str(out))
        assert str(out) in result.stdout

    def test_bundles_teal_and_indigo_together(self, tmp_path):
        # Given the two apps that both call their viewer a trace view
        out = tmp_path / "bundle.js"

        # When both are requested
        result = self._run(
            "--emit-components", str(out), "--components", "teal,indigo"
        )

        # Then they ship together: the tags are namespaced by app and each
        # component is emitted in its own scope, so the two identically named
        # TraceViewElement classes no longer collide
        assert result.returncode == 0, result.stderr
        emitted = out.read_text(encoding="utf-8")
        assert 'defineElement("teal-trace-view"' in emitted
        assert 'defineElement("indigo-trace-view"' in emitted

    def test_an_unknown_component_fails_loudly(self, tmp_path):
        # Given a component name that is not registered
        out = tmp_path / "bundle.js"

        # When it is requested
        result = self._run("--emit-components", str(out), "--components", "sage")

        # Then it names what is available rather than writing an empty bundle
        assert result.returncode == 1
        assert "unknown component" in result.stderr
        assert not out.exists()

    def test_never_overwrites_a_file_that_is_not_a_bundle(self, tmp_path):
        # Given tracy results the user names before remembering the flag
        results = tmp_path / "results.json"
        results.write_text('{"basecalls": {}}', encoding="utf-8")

        # When they emit components with that path in the way
        result = self._run(str(results), "--emit-components")

        # Then their data survives and the error says why
        assert result.returncode == 1
        assert results.read_text(encoding="utf-8") == '{"basecalls": {}}'
        assert "would overwrite" in result.stderr

    def test_regenerating_an_existing_bundle_is_allowed(self, tmp_path):
        # Given a bundle emitted earlier
        out = tmp_path / "bundle.js"
        first = self._run("--emit-components", str(out))
        assert first.returncode == 0, first.stderr

        # When it is emitted again over the same path
        second = self._run("--emit-components", str(out), "--components", "teal")

        # Then it is rewritten, because only our own bundles may be replaced
        assert second.returncode == 0, second.stderr
        assert 'defineElement("teal-trace-view"' in out.read_text(encoding="utf-8")

    def test_an_input_and_an_output_together_is_rejected(self, tmp_path):
        # Given both positionals, so which one is the bundle is ambiguous
        results = tmp_path / "results.json"
        results.write_text("{}", encoding="utf-8")
        out = tmp_path / "bundle.js"

        # When both are passed with the emit flag
        result = self._run(str(results), str(out), "--emit-components")

        # Then it refuses rather than guessing
        assert result.returncode != 0
        assert "INPUT is not used" in result.stderr
        assert not out.exists()

    def test_requires_an_input_when_not_emitting(self):
        # Given neither an input file nor the emit flag
        result = self._run()

        # Then argparse explains which one is missing
        assert result.returncode != 0
        assert "INPUT is required" in result.stderr


# ---------------------------------------------------------------------------
# Raw, unaligned traces
# ---------------------------------------------------------------------------

class TestRawTraceDetection:
    """teal's viewer normalises a raw peak trace, so it is worth detecting."""

    def _raw_trace(self):
        return {
            "peakA": [1, 2],
            "peakC": [3, 4],
            "peakG": [5, 6],
            "peakT": [7, 8],
            "basecallPos": [0, 1],
            "basecalls": {"1": "A:1", "2": "C:2"},
        }

    def test_raw_peak_arrays_are_detected_as_a_trace(self):
        from tracy_visualisations import detect_data_type

        # Given a tracy trace that has not been aligned to a reference
        data = self._raw_trace()

        # When its type is detected
        # Then it is a trace, explicitly rather than by falling through
        assert detect_data_type(data) == "trace"

    def test_indigo_output_still_wins_over_raw_peaks(self):
        from tracy_visualisations import detect_data_type

        # Given output carrying both raw peaks and indigo's own fields
        data = dict(self._raw_trace(), variants={"columns": [], "rows": []})

        # When its type is detected
        # Then indigo wins, because its page is the richer of the two
        assert detect_data_type(data) == "indigo"

    def test_a_partial_peak_set_is_not_treated_as_a_raw_trace(self):
        from tracy_visualisations import detect_data_type
        from tracy_visualisations.bundler import _RAW_TRACE_KEYS

        # Given JSON with only some of the peak arrays
        data = {"peakA": [1], "peakC": [2]}

        # When its type is detected
        # Then it reaches the fallback rather than matching the raw shape
        assert not _RAW_TRACE_KEYS <= data.keys()
        assert detect_data_type(data) == "trace"

    def test_a_raw_trace_bundles_into_a_viewer(self, tmp_path):
        import json

        from tracy_visualisations import bundle

        # Given a raw trace written to disk
        source = tmp_path / "raw.json"
        source.write_text(json.dumps(self._raw_trace()), encoding="utf-8")

        # When it is bundled
        html = bundle(source)

        # Then it produces a trace page carrying the data
        assert "<teal-trace-view" in html
        assert "peakA" in html


# ---------------------------------------------------------------------------
# Pearl assemblies
# ---------------------------------------------------------------------------

SAMPLE_ASSEMBLY = DATA_DIR / "sample_assembly.json"


class TestAssemblyDetection:
    def test_gapped_traces_are_detected_as_an_assembly(self):
        from tracy_visualisations import detect_data_type

        # Given pearl output: several traces aligned to a reference
        data = {"gappedTraces": [], "msa": [], "gappedConsensus": ""}

        # When its type is detected
        # Then it is an assembly, not a single trace
        assert detect_data_type(data) == "assembly"

    def test_a_single_gapped_trace_is_still_a_trace(self):
        from tracy_visualisations import detect_data_type

        # `gappedTrace` and `gappedTraces` differ by one character, so the two
        # must not be confused.
        assert detect_data_type({"gappedTrace": {"peakA": []}}) == "trace"

    def test_indigo_output_wins_over_an_assembly(self):
        from tracy_visualisations import detect_data_type

        data = {"gappedTraces": [], "variants": {"columns": [], "rows": []}}
        assert detect_data_type(data) == "indigo"


class TestBundleAssembly:
    def test_renders_an_assembly_without_an_explicit_type(self):
        from tracy_visualisations import bundle

        assert "Assembly Editor" in bundle(SAMPLE_ASSEMBLY)

    def test_uses_the_assembly_view_element(self):
        from tracy_visualisations import bundle

        # Given a pearl assembly
        # When it is bundled
        html = bundle(SAMPLE_ASSEMBLY)

        # Then the editor is the element, which brings its own toolbar rather
        # than the page supplying buttons wired to globals
        assert "<pearl-assembly-view" in html
        assert "AssemblyViewElement" in html
        assert 'defineElement("pearl-assembly-view"' in html

    def test_never_reaches_the_backend_when_rendering(self):
        from tracy_visualisations import bundle

        # Pearl's upload logic shares a file with its element, so the page's
        # code does travel with the component. What must not happen is any of
        # it running: every listener it installs is optional-chained onto an
        # element a host page does not have, and `process.env` - which would
        # throw in a browser - is read inside the upload call, not at load.
        html = bundle(SAMPLE_ASSEMBLY)

        assert "submitButton?.addEventListener" in html
        assert "const API_URL = process.env.API_URL" in html
        assert html.count("process.env") == 1

    def test_reopens_a_saved_session_without_rederiving_it(self):
        from tracy_visualisations import bundle

        # Given a report page
        html = bundle(SAMPLE_ASSEMBLY)

        # Then it decides by whether the data already carries edits, so a saved
        # session keeps them instead of being recomputed from the traces
        assert "controlSequence" in html
        assert "prepared: alreadyEdited" in html

    def test_leaves_no_unsubstituted_placeholders(self):
        from tracy_visualisations import bundle

        assert not re.search(r"\{\{\w+\}\}", bundle(SAMPLE_ASSEMBLY))

    def test_explicit_assembly_type(self):
        from tracy_visualisations import bundle

        assert "Assembly Editor" in bundle(SAMPLE_ASSEMBLY, data_type="assembly")

    def test_rejects_the_assembly_type_for_a_fasta_input(self):
        from tracy_visualisations import bundle

        with pytest.raises(ValueError, match="which is FASTA"):
            bundle(SAMPLE_MSA, data_type="assembly")

    def test_cli_renders_an_assembly(self, tmp_path):
        out = tmp_path / "assembly.html"
        result = subprocess.run(
            [sys.executable, "-m", "tracy_visualisations",
             str(SAMPLE_ASSEMBLY), str(out)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()

    def test_loads_the_icon_font_the_toolbar_uses(self):
        from tracy_visualisations import bundle

        # Given a report page
        html = bundle(SAMPLE_ASSEMBLY)

        # When pearl's toolbar renders its gavel icons
        # Then the font behind them is on the page, as it is for indigo
        assert "fas fa-gavel" in html
        assert "font-awesome" in html
