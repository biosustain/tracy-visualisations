# tracy-visualisations

A Python package that bundles [Tracy](https://github.com/gear-genomics/tracy)
JSON output files together with the
[TraceView](https://github.com/gear-genomics/sage) and
[Indigo](https://github.com/gear-genomics/indigo) web components into
**self-contained HTML files** that can be opened in any modern browser with no
server required.

## Installation

```bash
pip install .
```

## Quick start

### As a CLI tool

```bash
# Auto-detect visualisation type from the JSON content
tracy-vis results.json

# Explicit output path
tracy-vis results.json report.html

# Force indigo visualisation type
tracy-vis results.json report.html --type indigo
```

### As a Python module

```python
from tracy_visualisations import bundle

# Write to file and return the HTML string
html = bundle("results.json", "report.html")

# Return HTML string only (no file written)
html = bundle("results.json")

# Force a specific visualisation type
html = bundle("results.json", "report.html", data_type="trace")
```

### As a Docker container

```bash
# Build the image
docker build -t tracy-vis .

# Run it against files in the current directory
docker run --rm -v "$PWD:/work" tracy-vis results.json

# Explicit output path and visualisation type
docker run --rm -v "$PWD:/work" tracy-vis results.json report.html --type indigo

# Run using precompiled image
docker run --rm -v "$PWD:/work" ghcr.io/biosustain/tracy-visualisations results.json 
```


The container starts the `tracy-vis` CLI directly, so any CLI arguments can be passed after the image name.

## Visualisation types

| Type | Detected when | Components used |
|------|--------------|-----------------|
| `trace` | JSON contains a `gappedTrace` key | `<trace-view>` from [traceView.js](https://github.com/gear-genomics/sage/blob/main/client/src/static/js/traceView.js) |
| `indigo` | JSON contains `alt1align`, `decomposition`, or `variants` | `<trace-view>`, `<alignment-view>`, `<decomposition-view>`, `<variants-view>` from [elements.js](https://github.com/gear-genomics/indigo/blob/main/client/src/static/js/elements.js) |

## Linking to a variant

Indigo viewers read the variant to show from a query parameter named after the
variants table, whose value is the 0-based row index of the variant in the
`variants` table of the Tracy JSON:

```
report.html?variants-table=2
```

Opening such a link triggers the variants table's own "show in trace viewer"
action, so the viewer lands on exactly the view a hand-clicked row would, with
no clicking through the table first. Values that are missing, non-numeric or out
of range are ignored, and the viewer still renders in full.

The same parameter is written back into the URL whenever a row's chart icon is
clicked, so the address bar is always a link to what is on screen and can be
copied and shared as one. Each change pushes a history entry (repeated clicks on
one row do not), and the viewer follows the URL changing under it, so back and
forward step through the variants that were looked at.

Because the index is just the row order of the Tracy JSON, tables derived from
the same JSON (for example the mutation CSVs of
[dsp_bulk-sangerseq](https://github.com/biosustain/dsp_bulk-sangerseq)) can link
each of their rows straight to the matching electropherogram position.

## Running tests

```bash
pip install ".[dev]"
pytest
```

## LICENSING
This project depends on GPL-3.0 licensed libraries.
As a result, this project is also distributed under the GPL-3.0 license.
