"""
Core bundling logic for tracy_visualisations.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import re
from pathlib import Path
from typing import Optional, Union

# ---------------------------------------------------------------------------
# Vendor JS paths (inside the git submodules)
# ---------------------------------------------------------------------------

_VENDOR_SAGE_JS = Path("vendor/sage/client/src/static/js/traceView.js")
_VENDOR_INDIGO_JS = Path("vendor/indigo/client/src/static/js/indigo.js")


def _pkg_root() -> Path:
    """Return the directory that contains this file (the package root)."""
    return Path(__file__).parent


def _read_vendor_js(relative: Path) -> str:
    """Read a JS file from a git submodule bundled with the package."""
    full = _pkg_root() / relative
    return full.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# JS transformation helpers
# ---------------------------------------------------------------------------

def _adapt_traceview_js(source: str) -> str:
    """Prepare traceView.js for inline use in a plain HTML page.

    Changes applied to the upstream source:
    * Strip the ``export default`` modifier from the class declaration so the
      class is available as a plain global.
    * Append a ``customElements.define`` call (guarded against double
      registration) so the ``<trace-view>`` element is registered
      automatically when the script is inlined.
    """
    adapted = re.sub(
        r"^export\s+default\s+class\s+TraceViewElement",
        "class TraceViewElement",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    adapted = adapted.rstrip()
    adapted += (
        '\nif (!customElements.get("trace-view")) {'
        ' customElements.define("trace-view", TraceViewElement); }\n'
    )
    return adapted


def _adapt_indigo_js(source: str) -> str:
    """Extract the visualisation components from indigo.js for standalone use.

    The upstream indigo.js file is a full application that:
    * Uses an ES module import (``file-saver``).
    * References a build-time ``process.env.API_URL`` value.
    * Makes HTTP requests to a server API.

    Only the custom-element class definitions and the helper functions they
    depend on are needed for rendering pre-computed data.  Everything related
    to file upload, server communication, and the UI form is removed.
    """
    lines = source.splitlines(keepends=True)

    # Collect ranges to DROP (1-indexed line numbers, inclusive)
    drop_ranges: list[tuple[int, int]] = []

    # 1. Remove the import line
    import_pat = re.compile(r"^\s*import\s+")
    # 2. Remove process.env.API_URL assignment
    api_url_pat = re.compile(r"^\s*const\s+API_URL\s*=")
    # 3. Top-level const/let variable names that reference DOM elements to remove
    #    (all are app-wiring code; visualisation classes don't depend on them)
    _dom_var_prefixes = (
        "resultLink", "submitButton", "exampleButton", "inputFile",
        "leftTrim", "rightTrim", "peakRatio", "targetFastaFile",
        "targetChromatogramFile", "targetGenomes", "targetTabs",
        "linkPdf", "decompositionChart", "alignmentChart", "traceChart",
        "variantsTable", "resultContainer", "resultInfo", "resultError",
        "downloadUrl",
    )
    top_level_dom_pat = re.compile(
        r"^\s*(?:const|let|var)\s+("
        + "|".join(re.escape(v) for v in _dom_var_prefixes)
        + r")\b"
    )
    # Functions to drop entirely
    drop_fns = {
        "run",
        "showExample",
        "downloadBcf",
        "showElement",
        "hideElement",
        "handleSuccess",
        "updatePeakRatioValue",
    }
    fn_def_pat = re.compile(r"^(?:async\s+)?function\s+(\w+)\s*\(")
    window_assign_pat = re.compile(r"^window\.(\w+)\s*=")

    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1  # 1-indexed

        # Drop import statements
        if import_pat.match(line):
            drop_ranges.append((lineno, lineno))
            i += 1
            continue

        # Drop process.env.API_URL
        if api_url_pat.match(line):
            drop_ranges.append((lineno, lineno))
            i += 1
            continue

        # Drop top-level DOM variable declarations that wire up the app UI
        if re.match(r"^\s*\$\(", line) or top_level_dom_pat.match(line):
            drop_ranges.append((lineno, lineno))
            i += 1
            continue

        # Drop top-level calls like updatePeakRatioValue()
        if re.match(r"^updatePeakRatioValue\(\)", line):
            drop_ranges.append((lineno, lineno))
            i += 1
            continue

        # Drop window.foo = foo assignments for unwanted functions
        wm = window_assign_pat.match(line)
        if wm and wm.group(1) in drop_fns:
            drop_ranges.append((lineno, lineno))
            i += 1
            continue

        # Drop entire function bodies for unwanted functions
        fm = fn_def_pat.match(line)
        if fm and fm.group(1) in drop_fns:
            # Find the matching closing brace
            start = lineno
            depth = 0
            j = i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and j > i:
                    break
                j += 1
            drop_ranges.append((start, j + 1))
            i = j + 1
            continue

        i += 1

    # Build a set of 1-indexed line numbers to drop
    drop_set: set[int] = set()
    for start, end in drop_ranges:
        drop_set.update(range(start, end + 1))

    kept = [line for idx, line in enumerate(lines, start=1) if idx not in drop_set]
    return "".join(kept)


def _load_template(name: str) -> str:
    """Read an HTML template that ships with the package."""
    try:
        # Python 3.9+
        ref = importlib.resources.files("tracy_visualisations.templates").joinpath(name)
        return ref.read_text(encoding="utf-8")
    except AttributeError:
        # Python 3.8 fallback
        with importlib.resources.open_text(  # type: ignore[attr-defined]
            "tracy_visualisations.templates", name
        ) as fh:
            return fh.read()


# ---------------------------------------------------------------------------
# Data-type detection
# ---------------------------------------------------------------------------

def detect_data_type(data: dict) -> str:
    """Return ``'trace'`` or ``'indigo'`` depending on the JSON structure.

    Parameters
    ----------
    data:
        Parsed Tracy JSON object.

    Returns
    -------
    ``'trace'``
        The data comes from a sage/tracify run and contains a ``gappedTrace``
        structure expected by the *TraceView* web component.
    ``'indigo'``
        The data comes from an indigo run and contains alignment + variant
        fields expected by the *Indigo* web components.
    """
    if "gappedTrace" in data:
        return "trace"
    # Indigo output contains at least one of these keys
    indigo_keys = {"alt1align", "alt2align", "decomposition", "variants"}
    if indigo_keys & data.keys():
        return "indigo"
    # Fall back to trace view so the file is always rendered
    return "trace"


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _render_trace_html(data: dict, filename: str) -> str:
    """Render a standalone HTML page using the TraceView component."""
    template = _load_template("trace.html")
    raw_js = _read_vendor_js(_VENDOR_SAGE_JS)
    traceview_js = _adapt_traceview_js(raw_js)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        template
        .replace("{{traceview_js}}", traceview_js)
        .replace("{{data_json}}", data_json)
        .replace("{{filename}}", _escape_html(filename))
    )


def _render_indigo_html(data: dict, filename: str) -> str:
    """Render a standalone HTML page using the Indigo web components."""
    template = _load_template("indigo.html")
    raw_js = _read_vendor_js(_VENDOR_INDIGO_JS)
    indigo_js = _adapt_indigo_js(raw_js)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        template
        .replace("{{indigo_js}}", indigo_js)
        .replace("{{data_json}}", data_json)
        .replace("{{filename}}", _escape_html(filename))
    )


def _escape_html(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def bundle(
    input_path: Union[str, os.PathLike],
    output_path: Optional[Union[str, os.PathLike]] = None,
    *,
    data_type: Optional[str] = None,
) -> str:
    """Bundle a Tracy JSON file with visualisation components into HTML.

    Parameters
    ----------
    input_path:
        Path to a Tracy JSON output file.
    output_path:
        Optional path where the generated HTML will be written.  If *None*
        the HTML string is returned but no file is written.
    data_type:
        Force the visualisation type: ``'trace'`` or ``'indigo'``.  When
        *None* (default) the type is inferred automatically from the JSON
        contents.

    Returns
    -------
    str
        The generated HTML string (regardless of whether *output_path* was
        given).

    Raises
    ------
    ValueError
        If *data_type* is provided but is not ``'trace'`` or ``'indigo'``.
    FileNotFoundError
        If *input_path* does not exist.
    """
    input_path = Path(input_path)

    with open(input_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if data_type is None:
        data_type = detect_data_type(data)
    elif data_type not in ("trace", "indigo"):
        raise ValueError(f"data_type must be 'trace' or 'indigo', got {data_type!r}")

    filename = input_path.name

    if data_type == "indigo":
        html = _render_indigo_html(data, filename)
    else:
        html = _render_trace_html(data, filename)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")

    return html
