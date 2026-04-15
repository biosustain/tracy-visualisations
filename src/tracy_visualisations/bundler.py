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
_VENDOR_INDIGO_JS = Path("vendor/indigo/client/src/static/js/elements.js")


def _pkg_root() -> Path:
    """Return the directory that contains this file (the package root)."""
    return Path(__file__).parent


def _read_vendor_js(relative: Path) -> str:
    """Read a bundled JS file, falling back to built-in copies when needed."""
    full = _pkg_root() / relative
    if full.exists():
        return full.read_text(encoding="utf-8")
    raise FileNotFoundError(full)


# ---------------------------------------------------------------------------
# JS transformation helpers
# ---------------------------------------------------------------------------
def _skip_exports(source: str) -> str:
    """Remove ES module export statements from the source."""
    return re.sub(
        r"^export\s+(default\s+)?",
        "",
        source,
        flags=re.MULTILINE,
    )


def _adapt_traceview_js(source: str) -> str:
    """Prepare traceView.js for inline use in a plain HTML page.

    Changes applied to the upstream source:
    * Strip the ``export default`` modifier from the class declaration so the
      class is available as a plain global.
    * Append a ``customElements.define`` call (guarded against double
      registration) so the ``<trace-view>`` element is registered
      automatically when the script is inlined.
    """
    return f"""
        {_skip_exports(source)}
        customElements.define("trace-view", TraceViewElement);
    """


def _adapt_indigo_js(source: str) -> str:
    """Prepare indigo's elements.js for inline use in a plain HTML page.

    Changes applied to the upstream source:
    * Remove the ES module import statement since the dependencies are bundled
      together.
    * Append a block that registers all the custom elements
    """
    return f"""
        {_skip_exports(source)}
        customElements.define('trace-view', TraceViewElement)
        customElements.define('alignment-view', AlignmentViewElement)
        customElements.define('decomposition-view', DecompositionViewElement)
        customElements.define('variants-view', VariantsTableElement)
    """


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
        template.replace("{{traceview_js}}", traceview_js)
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
        template.replace("{{indigo_js}}", indigo_js)
        .replace("{{data_json}}", data_json)
        .replace("{{filename}}", _escape_html(filename))
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
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
