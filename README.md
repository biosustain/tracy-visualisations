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

## Visualisation types

| Type | Detected when | Components used |
|------|--------------|-----------------|
| `trace` | JSON contains a `gappedTrace` key | `<trace-view>` from [traceView.js](https://github.com/gear-genomics/sage/blob/main/client/src/static/js/traceView.js) |
| `indigo` | JSON contains `alt1align`, `decomposition`, or `variants` | `<trace-view>`, `<alignment-view>`, `<decomposition-view>`, `<variants-view>` from [indigo.js](https://github.com/gear-genomics/indigo/blob/main/client/src/static/js/indigo.js) |

## Running tests

```bash
pip install ".[dev]"
pytest
```
