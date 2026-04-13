"""
Core bundling logic for tracy_visualisations.
"""

from __future__ import annotations

import importlib.resources
import json
import os
from pathlib import Path
from typing import Optional, Union

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_package_text(subpackage: str, filename: str) -> str:
    """Read a text file that ships with the package."""
    pkg = f"tracy_visualisations.{subpackage}" if subpackage else "tracy_visualisations"
    try:
        # Python 3.9+
        ref = importlib.resources.files(pkg).joinpath(filename)
        return ref.read_text(encoding="utf-8")
    except AttributeError:
        # Python 3.8 fallback
        with importlib.resources.open_text(pkg, filename) as fh:  # type: ignore[attr-defined]
            return fh.read()


def _load_js(name: str) -> str:
    return _read_package_text("js", name)


def _load_template(name: str) -> str:
    return _read_package_text("templates", name)


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
    traceview_js = _load_js("traceView.js")
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
    indigo_js = _load_js("indigoComponents.js")
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
