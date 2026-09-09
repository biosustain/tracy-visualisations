"""
Core bundling logic for tracy_visualisations.

Reading and adapting the vendored front-end sources lives in
:mod:`tracy_visualisations.components`; this module is about turning an input
file into a rendered report.
"""

from __future__ import annotations

import importlib.resources
import json
import os
from pathlib import Path
from typing import Optional, Union

from .components import (
    COMPONENTS,
    ComponentConflict,
    component_css,
    component_js,
    read_vendor_file,
    strip_module_syntax,
)

# ---------------------------------------------------------------------------
# Vendor JS paths (inside the git submodules)
# ---------------------------------------------------------------------------

_VENDOR_TRACE_JS = COMPONENTS["teal"].sources[0]
_VENDOR_INDIGO_JS = COMPONENTS["indigo"].sources[0]
_VENDOR_MSA_JS = COMPONENTS["sabre"].sources[0]
_VENDOR_MSA_CSS = COMPONENTS["sabre"].stylesheets[0]

_read_vendor_file = read_vendor_file
_skip_exports = strip_module_syntax


def _adapt_traceview_js(source: str) -> str:
    """Prepare teal's traceView.js for inline use in a plain HTML page."""
    return component_js(["teal"])


def _adapt_indigo_js(source: str) -> str:
    """Prepare indigo's elements.js for inline use in a plain HTML page."""
    return component_js(["indigo"])


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

# Every visualisation type ``bundle`` accepts, grouped by the input format it
# is rendered from.
JSON_DATA_TYPES = ("trace", "indigo", "assembly")
FASTA_DATA_TYPES = ("msa",)
DATA_TYPES = JSON_DATA_TYPES + FASTA_DATA_TYPES


# The peak arrays a raw tracy trace carries before alignment.
_RAW_TRACE_KEYS = frozenset({"peakA", "peakC", "peakG", "peakT", "basecalls"})


def detect_data_type(data: dict) -> str:
    """Return ``'trace'`` or ``'indigo'`` depending on the JSON structure.

    Parameters
    ----------
    data:
        Parsed Tracy JSON object.

    Returns
    -------
    ``'trace'``
        The data comes from a teal/tracify run and contains a ``gappedTrace``
        structure expected by the *TraceView* web component.
    ``'indigo'``
        The data comes from an indigo run and contains alignment + variant
        fields expected by the *Indigo* web components.
    """
    if "gappedTrace" in data:
        return "trace"
    # Indigo output contains at least one of these keys. Checked before the raw
    # peaks below, because indigo output can carry both and its page is the
    # richer of the two.
    indigo_keys = {"alt1align", "alt2align", "decomposition", "variants"}
    if indigo_keys & data.keys():
        return "indigo"
    # Pearl's assembly: several traces aligned to a reference or consensus,
    # which the assembly editor can reopen and keep editing.
    if "gappedTraces" in data:
        return "assembly"
    # A raw, unaligned trace: teal's TraceViewElement normalises this shape
    # itself, so it renders rather than producing an empty viewer.
    if _RAW_TRACE_KEYS <= data.keys():
        return "trace"
    # Fall back to trace view so the file is always rendered. This is now the
    # only path that can still produce an empty viewer.
    return "trace"


def _is_fasta(text: str) -> bool:
    """Return whether *text* opens with a FASTA record header."""
    return text.lstrip().startswith(">")


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

# Which vendored apps each visualisation type is built from. A type is named
# after the data it renders; the apps are named after where their components
# were taken from, which is also the prefix on the custom element tags they
# register. The first app names the template, so a template sits next to the
# vendored source it embeds.
_TYPE_APPS: dict[str, tuple[str, ...]] = {
    "trace": ("teal",),
    "indigo": ("indigo",),
    "assembly": ("pearl",),
    "msa": ("sabre",),
}


def _render(data_type: str, filename: str, **substitutions: str) -> str:
    """Render *data_type*'s template with its components inlined.

    The data substitution goes in last: it is the one value that comes from
    user input, so nothing it happens to contain can be read as another
    placeholder.
    """
    apps = _TYPE_APPS[data_type]
    template_app = apps[0]
    template = _load_template(f"{template_app}.html")

    replacements = {
        "components_css": component_css(apps),
        "components_js": component_js(apps),
        "filename": _escape_html(filename),
        **substitutions,
    }
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    return template


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
    """Bundle a Tracy output file with visualisation components into HTML.

    Parameters
    ----------
    input_path:
        Path to a Tracy output file: either a JSON file (``tracy align`` /
        ``tracy decompose``) or a gapped multi-FASTA alignment such as the
        ``.align.fa`` written by ``tracy assemble``.
    output_path:
        Optional path where the generated HTML will be written.  If *None*
        the HTML string is returned but no file is written.
    data_type:
        Force the visualisation type: ``'trace'``, ``'indigo'`` or ``'msa'``.
        When *None* (default) the type is inferred from the file contents.

    Returns
    -------
    str
        The generated HTML string (regardless of whether *output_path* was
        given).

    Raises
    ------
    ValueError
        If *data_type* is not a known visualisation type, or if it disagrees
        with the input file's format (``'msa'`` renders FASTA; ``'trace'`` and
        ``'indigo'`` render JSON).
    FileNotFoundError
        If *input_path* does not exist.
    """
    input_path = Path(input_path)

    if data_type is not None and data_type not in DATA_TYPES:
        expected = ", ".join(repr(name) for name in DATA_TYPES)
        raise ValueError(f"data_type must be one of {expected}, got {data_type!r}")

    # utf-8-sig so a byte-order mark cannot hide a FASTA header's leading '>'
    # from the format sniff.
    text = input_path.read_text(encoding="utf-8-sig")

    if _is_fasta(text):
        data = None
        detected_type = "msa"
    else:
        data = json.loads(text)
        detected_type = detect_data_type(data)

    if data_type is None:
        data_type = detected_type
    elif (data_type in FASTA_DATA_TYPES) != (detected_type in FASTA_DATA_TYPES):
        actual_format = "FASTA" if detected_type in FASTA_DATA_TYPES else "JSON"
        raise ValueError(
            f"data_type {data_type!r} cannot render {input_path.name}, "
            f"which is {actual_format}"
        )

    filename = input_path.name

    if data_type == "msa":
        fasta_json = json.dumps(text, ensure_ascii=False)
        html = _render("msa", filename, fasta_json=fasta_json)
    else:
        data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        html = _render(data_type, filename, data_json=data_json)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.write_text(html, encoding="utf-8")

    return html
