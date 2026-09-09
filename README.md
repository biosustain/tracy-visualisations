# tracy-visualisations

Packages the [GEAR Genomics](https://github.com/gear-genomics) web front-ends as
**custom elements**, so they can be embedded in any page without bringing along
each app's Flask backend or Parcel build.

Two things are built from that component layer:

* **Self-contained HTML reports** — [Tracy](https://github.com/gear-genomics/tracy)
  output bundled with the components it needs into a single file that opens in
  any modern browser with no server.
* **A standalone JavaScript bundle** — one `<script src>` that registers the
  elements on someone else's page (see [Using the components
  directly](#using-the-components-directly)).

Both are on show, rendering real sample files, on the **[demo
page](https://biosustain.github.io/tracy-visualisations/)**.

The components come from [Teal](https://github.com/gear-genomics/teal),
[Indigo](https://github.com/gear-genomics/indigo),
[Sabre](https://github.com/gear-genomics/sabre) and
[Pearl](https://github.com/gear-genomics/pearl), vendored as git submodules.
[Sage](https://github.com/gear-genomics/sage) is vendored too: teal's trace
viewer replaced it, but it stays available under `--components sage`.

Two input formats are accepted: Tracy's JSON output (`tracy align` /
`tracy decompose`), and a gapped multi-FASTA alignment such as the `.align.fa`
written by `tracy assemble`.

## Installation

```bash
git clone --recursive https://github.com/biosustain/tracy-visualisations
cd tracy-visualisations
./scripts/bootstrap-submodules.sh   # checks out the submodules, checks the pins
pip install .
```

The front-ends are git submodules, and some carry local changes that are not
yet upstream: those pins live on forks that `.gitmodules` points at directly.
`bootstrap-submodules.sh` verifies every pin is reachable and names the
submodule, commit and remote when one is not; it is safe to re-run.

## Quick start

### As a CLI tool

```bash
# Auto-detect visualisation type from the JSON content
tracy-vis results.json

# Explicit output path
tracy-vis results.json report.html

# Force indigo visualisation type
tracy-vis results.json report.html --type indigo

# Emit the web components as a standalone script instead of a report
tracy-vis --emit-components gear-components.js
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

| Type | Detected when | Elements used |
|------|--------------|-----------------|
| `trace` | JSON contains `gappedTrace`, or the raw `peakA`/`peakC`/`peakG`/`peakT` arrays | `<teal-trace-view>` from [teal](https://github.com/gear-genomics/teal/blob/main/client/src/static/js/traceView.js) |
| `indigo` | JSON contains `alt1align`, `decomposition`, or `variants` | `<indigo-trace-view>`, `<indigo-alignment-view>`, `<indigo-decomposition-view>`, `<indigo-variants-view>` from [indigo](https://github.com/gear-genomics/indigo/blob/main/client/src/static/js/elements.js) |
| `assembly` | JSON contains `gappedTraces` | `<pearl-assembly-view>` from [pearl](https://github.com/gear-genomics/pearl) |
| `msa` | the file opens with a FASTA header (`>`) | `<sabre-msa-view>` from [sabre](https://github.com/gear-genomics/sabre) |

`trace` uses teal's viewer rather than sage's: it is the same element with the
same `displayData` entry point, but it also normalises a raw, unaligned trace
and scales its SVG to the page instead of a fixed 1200px.

The format decides how the file is parsed, so `--type` can only pick between
types that match it: `msa` renders FASTA, `trace` and `indigo` render JSON, and
a mismatch raises an error instead of producing an empty viewer.

## Using the components directly

The components are published to GitHub Packages as
`@biosustain/tracy-visualisations`. Point the scope at GitHub's registry, then
install:

```ini
# .npmrc
@biosustain:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

```bash
npm install @biosustain/tracy-visualisations
```

The token is not optional: GitHub Packages serves npm only to authenticated
requests, public repository or not. Any token with `read:packages` will do.

Importing the package registers every element; there is nothing to call.

```js
import '@biosustain/tracy-visualisations'
```

Each component is also importable on its own, so a page takes only the viewers
it shows:

```js
import '@biosustain/tracy-visualisations/teal'    // <teal-trace-view>
import '@biosustain/tracy-visualisations/indigo'  // the four <indigo-*> elements
import '@biosustain/tracy-visualisations/sabre'   // <sabre-msa-view>
import '@biosustain/tracy-visualisations/pearl'   // <pearl-assembly-view>
import '@biosustain/tracy-visualisations/sage'    // the viewer teal's supersedes
```

That is worth doing: unminified, the four `<indigo-*>` elements are 9 kB of the
default bundle's 108, and a page taking only indigo neither ships pearl's
editing toolbar nor teal's SVG viewer. Each file declares its own required
globals on `window.TracyVis.requires`, so a page importing everything but
indigo does not need Plotly at all.

Every file is a classic script, so a page with no bundler can load one straight
out of `node_modules` instead:

```html
<script src="node_modules/@biosustain/tracy-visualisations/dist/teal.js"></script>
```

The CLI writes the same files, and takes any selection at all — one bundle
carrying several components, which is what the package's root entry is:

```bash
tracy-vis --emit-components gear-components.js
tracy-vis --emit-components viewer.js --components teal,sabre
```

Either way, the elements are then used the same:

```html
<script src="gear-components.js"></script>

<teal-trace-view id="trace"></teal-trace-view>
<sabre-msa-view id="alignment" characters-per-line="80"></sabre-msa-view>
<pearl-assembly-view id="assembly"></pearl-assembly-view>

<script>
  document.getElementById('trace').displayData(tracyJson);
  document.getElementById('alignment').displayData(fastaText);
  document.getElementById('assembly').displayData(pearlJson);
</script>
```

Every tag is namespaced with the app it came from — `teal-`, `indigo-`,
`sabre-`, `pearl-`, `sage-`. Several of these apps ship a viewer they all call
a *trace view*: teal draws one in SVG, indigo draws one with Plotly, and sage
draws the SVG teal's supersedes. The prefix keeps them tellable apart, and lets
one page use them all.

The bundle is plain classic JavaScript — no module loader, no build step. It
carries its own CSS, injects it once on load, and registers each element only
if the tag is still free, so loading it twice is harmless.

Every element follows the same contract as the upstream apps: `displayData()`
takes the data and renders.

* `<sabre-msa-view>` reflects a `characters-per-line` attribute and reports what the
  cursor is over as an `msa-hover` event, leaving the host page to decide where
  that goes.
* `<pearl-assembly-view>` brings its own editing toolbar, exposes `assembly`,
  `userEditedSequence` and `editPosition`, and raises `assembly-change` and
  `position-change` as the user works. Pass `{ prepared: true }` to reopen an
  already-edited session without deriving it again.

Pick components with `--components`:

```bash
tracy-vis --emit-components viewer.js --components teal,sabre
```

Components are selected by the app they come from: `teal`, `indigo`, `sabre`,
`pearl`, `sage`. The default is all but `sage`, which teal's viewer superseded
and which therefore only ships when asked for by name. Each component is
emitted in its own scope, so apps that happen to declare an identically named
class (teal, indigo and sage all have a `TraceViewElement`) no longer clash.

One caveat: **some elements need a global.** Indigo's charts require Plotly
(≥ 1.39) to be on the page already; the bundle lists what it expects in its
header banner and on `window.TracyVis.requires`.

## Multiple sequence alignments

An `msa` page renders reads and reference as wrapped alignment blocks, colouring
mismatches, ambiguous consensus calls and leading/trailing gaps, with a hover
panel giving alignment position, sequence position and record metadata. The
characters-per-line selector redraws the alignment in place.

Note that the colouring is by **column consensus**, not against the reference:
the reference is simply another row in the count. So where several reads agree
against the reference it is the *reference* base that is marked as the mismatch,
and where a single read disagrees with the reference the 1-1 tie renders as an
ambiguous consensus rather than a mismatch.

Sabre cannot show electropherograms; use a `trace` or `indigo` page for those.

## Assembly editing

An `assembly` page reopens a pearl assembly — several Sanger traces aligned to a
reference or consensus — as an editable viewer. The consensus overview is colour
coded by agreement (grey no information, green consensus, orange conflict, red
mismatch against the reference, bright green edited), "Jump to next conflict"
walks the positions that need a decision, and the electropherograms below show
every trace covering the current position.

Edits are made in the browser and the page has no server to save back to, so the
corrected sequence leaves through the download button. Feeding a saved pearl
session (`multipleAlignment.json`) back in reopens it with its edits intact
rather than recomputing them from the traces.

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

## Releasing the npm package

`.github/workflows/publish-npm.yml` publishes `@biosustain/tracy-visualisations`
to GitHub Packages when a release is published, and on demand from the Actions
tab. It emits the files from the checkout during the run, so nothing built is
ever committed, and it refuses a release whose tag does not match the version in
`package.json` — which `tests/test_npm_package.py` keeps in step with
`pyproject.toml`, so one commit is one release whether it is installed with pip
or with npm.

## Demo site

[biosustain.github.io/tracy-visualisations](https://biosustain.github.io/tracy-visualisations/)
is one page that loads the emitted bundle exactly as another site would, hands
each element a sample file, and links the self-contained report the CLI builds
from that same sample. It is built and published from `main` by
`.github/workflows/pages.yml`, which needs the repository's Pages source set to
*GitHub Actions*.

Nothing in it is a copy: the bundle comes from `build_bundle()`, the traces are
the vendored apps' own demo files, and the remaining samples are this suite's
fixtures. `tests/test_demo_site.py` fails if a sample moves or the page asks for
a file the build does not produce, because either would show up in a browser
only as a section that renders nothing.

Build and preview it locally:

```bash
./scripts/build_demo_site.py            # writes ./site
python3 -m http.server --directory site # then open localhost:8000
```

The page has to be served rather than opened from disk: it fetches its samples,
which `file://` refuses. The reports under `site/reports/` do open from disk,
being the point of them.

## Running tests

```bash
pip install ".[dev]"
pytest
```

## LICENSING
This project depends on GPL-3.0 licensed libraries.
As a result, this project is also distributed under the GPL-3.0 license.
