"""The gear-genomics web components this package can ship.

Each gear-genomics app declares its rendering as custom element classes, with
the site's own logic - uploads, downloads, banners - kept behind a guard that
only that site satisfies. Indigo keeps the two in separate files
(``elements.js`` beside ``indigo.js``); the others keep both in the one file
they already had, which makes for a far smaller diff against upstream. Either
way this module is the registry: which vendored sources make up a component,
which tags it registers, and which globals the host page has to provide.

Tags are namespaced with the app they came from, because two of these apps ship
an element they both call a trace view.

Two consumers share it, so they cannot drift: :mod:`tracy_visualisations.bundler`
inlines a single component into a self-contained HTML report, and
:func:`build_bundle` emits a standalone script other pages load with a plain
``<script src>``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

_VENDOR = Path("vendor")


def _pkg_root() -> Path:
    """Return the directory that contains this file (the package root)."""
    return Path(__file__).parent


# ---------------------------------------------------------------------------
# Source adaptation
# ---------------------------------------------------------------------------

def strip_module_syntax(source: str) -> str:
    """Turn an ES module into something a classic ``<script>`` can run.

    Upstream ships these files as ES modules because their own build step is a
    bundler. Here they are concatenated into one scope instead, so the module
    syntax has to go: ``export`` modifiers are dropped, leaving plain
    declarations, and top-level ``import`` statements are dropped because every
    dependency is either concatenated alongside or is a global the host page
    provides (see ``Component.requires``).
    """
    without_imports = re.sub(r"^import\s+[^\n]*\n", "", source, flags=re.MULTILINE)
    without_exports = re.sub(
        r"^export\s+(default\s+)?", "", without_imports, flags=re.MULTILINE
    )
    # Drop the app's own registration. Upstream registers the element under its
    # bare name from the page script; here the registry decides the tag, and an
    # unguarded define would also throw if the bundle were loaded twice.
    return re.sub(
        r"^\s*(window\.)?customElements\.define\([^\n]*\n",
        "",
        without_exports,
        flags=re.MULTILINE,
    )


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

Adapter = Callable[[str], str]


@dataclass(frozen=True)
class Component:
    """One gear-genomics app's rendering layer.

    ``elements`` pairs each custom element tag with the JavaScript class that
    implements it. Keeping them together rather than in two parallel tuples is
    what lets the registration code and the conflict check below both fall out
    of a single iteration, with no way for the two lists to fall out of step.
    """

    name: str
    sources: Tuple[Path, ...]
    stylesheets: Tuple[Path, ...] = ()
    elements: Tuple[Tuple[str, str], ...] = ()
    requires: Tuple[str, ...] = ()
    adapt: Adapter = strip_module_syntax
    # Why this component cannot go in a `<script src>` bundle, or None when it
    # can. An app that still resolves page elements at module scope only works
    # inside a template that provides them.
    standalone_blocker: Optional[str] = None
    # False for a component another one supersedes: still selectable by name,
    # but kept out of the default bundle so it does not ship a second,
    # near-identical viewer to every page that takes the defaults.
    in_default_bundle: bool = True

    @property
    def tags(self) -> Tuple[str, ...]:
        """The custom element tags this component registers.

        Each is namespaced with the app it came from, so two apps that both
        call their viewer a ``trace-view`` - teal draws one in SVG, indigo
        draws one with Plotly - stay tellable apart on a page carrying both.
        """
        return tuple(f"{self.name}-{tag}" for tag, _ in self.elements)

    @property
    def local_tags(self) -> Tuple[str, ...]:
        """The tags as the upstream app names them, without the prefix."""
        return tuple(tag for tag, _ in self.elements)

    @property
    def classes(self) -> Tuple[str, ...]:
        return tuple(class_name for _, class_name in self.elements)


COMPONENTS: dict[str, Component] = {
    # teal's traceView.js rather than sage's: same class, same entry point,
    # plus a #normalizeData that also accepts a raw peak trace, a responsive
    # SVG instead of a fixed 1200px one, and handler cleanup. It is
    # self-contained - no imports, no external globals.
    "teal": Component(
        name="teal",
        sources=(_VENDOR / "teal/client/src/static/js/traceView.js",),
        elements=(("trace-view", "TraceViewElement"),),
    ),
    # The viewer teal's supersedes, kept registered so a report can still be
    # rendered with the element the earlier ones used. Same class and entry
    # point as teal's, so it is namespaced apart rather than merged.
    "sage": Component(
        name="sage",
        sources=(_VENDOR / "sage/client/src/static/js/traceView.js",),
        elements=(("trace-view", "TraceViewElement"),),
        in_default_bundle=False,
    ),
    "indigo": Component(
        name="indigo",
        sources=(_VENDOR / "indigo/client/src/static/js/elements.js",),
        elements=(
            ("trace-view", "TraceViewElement"),
            ("alignment-view", "AlignmentViewElement"),
            ("decomposition-view", "DecompositionViewElement"),
            ("variants-view", "VariantsTableElement"),
        ),
        requires=("Plotly",),
    ),
    "pearl": Component(
        name="pearl",
        sources=(_VENDOR / "pearl/client/src/static/js/pearl.js",),
        elements=(("assembly-view", "AssemblyViewElement"),),
    ),
    "sabre": Component(
        name="sabre",
        sources=(_VENDOR / "sabre/client/src/static/js/sabre.js",),
        stylesheets=(_VENDOR / "sabre/client/src/static/css/sabre.css",),
        elements=(("msa-view", "MsaViewElement"),),
    ),
}


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

class ComponentConflict(ValueError):
    """Two selected components cannot be shipped together."""


def resolve(names: Optional[Iterable[str]] = None) -> list[Component]:
    """Return the named components, de-duplicated, in registry order.

    ``None`` selects everything registered. Raises :class:`ValueError` for an
    unknown name and :class:`ComponentConflict` when two of the selected
    components would register the same tag.
    """
    if names is None:
        selected = list(COMPONENTS)
    else:
        selected = []
        for name in names:
            if name not in COMPONENTS:
                known = ", ".join(repr(key) for key in COMPONENTS)
                raise ValueError(f"unknown component {name!r}; known: {known}")
            if name not in selected:
                selected.append(name)

    components = [COMPONENTS[name] for name in COMPONENTS if name in selected]
    _reject_conflicts(components)
    return components


def _reject_conflicts(components: list[Component]) -> None:
    """Refuse a selection that would register one tag twice.

    Class names no longer collide across apps - each component is emitted in
    its own scope - and tags are namespaced by the app they came from, so this
    can only fire if two components claim the same prefixed tag. That would
    mean one of them silently losing to the other's registration, so it is
    refused rather than resolved by load order.
    """
    seen_tag: dict[str, Component] = {}

    for component in components:
        for tag in component.tags:
            clash = seen_tag.get(tag)
            if clash is not None:
                raise ComponentConflict(
                    f"components {clash.name!r} and {component.name!r} both "
                    f"register <{tag}>; only one of them could win, so they "
                    "cannot be bundled together."
                )
            seen_tag[tag] = component


# ---------------------------------------------------------------------------
# Reading vendored sources
# ---------------------------------------------------------------------------

def read_vendor_file(relative: Path) -> str:
    """Read a file vendored from one of the git submodules."""
    full = _pkg_root() / relative
    if full.exists():
        return full.read_text(encoding="utf-8")
    raise FileNotFoundError(full)


# ---------------------------------------------------------------------------
# Emitting
# ---------------------------------------------------------------------------

# sage/teal's TraceViewElement puts `d-none` on nine of its internal elements
# and toggles it to show and hide them, and sabre's script does the same with
# its banners - but `d-none` is a Bootstrap utility class that none of the
# vendored stylesheets define. A page that cannot reach the Bootstrap CDN would
# otherwise show every hidden element at once, so the fallback ships with the
# components rather than with any one template.
BASE_CSS = """.d-none { display: none !important; }"""


def _define_helper_js() -> str:
    """Return the guarded ``customElements.define`` helper.

    Registration lives here rather than in the vendored sources because
    upstream registers its tags from the page script, keeping the element files
    import-only. The guard makes loading a component twice - two bundles on one
    page, or a bundle beside a hand-written script - a no-op instead of a
    ``NotSupportedError``.
    """
    return "\n".join(
        [
            "function defineElement(tag, ctor) {",
            "  if (!customElements.get(tag)) { customElements.define(tag, ctor); }",
            "}",
        ]
    )


def _scoped_component_js(component: Component) -> str:
    """Return one component's source and registrations, in their own scope.

    The scope is what lets unrelated apps be concatenated. teal and indigo both
    declare ``class TraceViewElement`` - one draws SVG, the other draws a
    Plotly chart - and two such declarations in a single scope are a
    ``SyntaxError`` that kills the page before anything runs. Giving each
    component its own function scope keeps the collision from ever arising, and
    keeps each app's helpers off the host page besides.
    """
    parts = [f"/* --- {component.name} --- */", "(function () {"]

    for path in component.sources:
        adapted = component.adapt(read_vendor_file(path))
        _assert_adaptable(component, path, adapted)
        parts.append(f"/* {path.as_posix()} */")
        parts.append(adapted)

    for tag, class_name in zip(component.tags, component.classes):
        parts.append(f'defineElement("{tag}", {class_name});')

    parts.append("})();")
    return "\n".join(parts)


def _strip_font_faces(css: str) -> str:
    """Remove ``@font-face`` rules from a vendored stylesheet.

    The gear apps pin Source Code Pro from gear-genomics.com. A component
    embedded in someone else's page must not pull fonts off a third-party host,
    and the declarations that use the family all name a generic fallback, so
    dropping the rules degrades to the local monospace face.
    """
    return re.sub(r"@font-face\s*\{[^}]*\}\s*", "", css)


def component_css(names: Optional[Iterable[str]] = None) -> str:
    """Return the stylesheets the named components need, base rules first."""
    components = resolve(names)
    sheets = [BASE_CSS]
    for component in components:
        sheets += [
            _strip_font_faces(read_vendor_file(path))
            for path in component.stylesheets
        ]
    return "\n".join(sheets)


def component_js(names: Optional[Iterable[str]] = None) -> str:
    """Return the adapted JavaScript for the named components.

    The result is a classic script body: no module syntax, every element
    registered, each component in its own scope. Callers that need a
    standalone file should use :func:`build_bundle` instead.
    """
    components = resolve(names)

    parts = [_define_helper_js()]
    parts += [_scoped_component_js(component) for component in components]
    return "\n".join(parts)


def _assert_adaptable(component: Component, path: Path, adapted: str) -> None:
    """Fail loudly when a vendored source has drifted out from under us.

    The vendored apps are live upstream repositories; a rename or a new
    dependency there would otherwise surface as a silently blank report. These
    checks are cheap and they run on every bundle.
    """
    leftover = re.search(r"^\s*(import|export)\s", adapted, flags=re.MULTILINE)
    if leftover:
        raise RuntimeError(
            f"{path.as_posix()} still contains module syntax after adaptation "
            f"({leftover.group(1)!r}); the adapter is out of date with the "
            "vendored source"
        )

    for class_name in component.classes:
        if not re.search(rf"\bclass\s+{re.escape(class_name)}\b", adapted):
            raise RuntimeError(
                f"component {component.name!r} registers class {class_name}, "
                f"but it is not declared in {path.as_posix()}; the registry is "
                "out of date with the vendored source"
            )


# ---------------------------------------------------------------------------
# The standalone bundle
# ---------------------------------------------------------------------------

# The components that can be shipped to an arbitrary page today. Everything
# registered that is bundle-safe and does not conflict with an earlier pick -
# see `standalone_blocker` and `_reject_conflicts` for why the rest are out.
def default_bundle_components() -> list[str]:
    """Return the largest conflict-free set of bundle-safe component names."""
    chosen: list[Component] = []
    for component in COMPONENTS.values():
        if component.standalone_blocker is not None:
            continue
        if not component.in_default_bundle:
            continue
        try:
            _reject_conflicts(chosen + [component])
        except ComponentConflict:
            continue
        chosen.append(component)
    return [component.name for component in chosen]


# First line of every emitted bundle's banner.  The CLI looks for it before
# replacing an existing file, so it can tell its own output from a file the
# user meant to keep.
BUNDLE_MARKER = "gear-genomics web components, bundled by tracy-visualisations."


def build_bundle(names: Optional[Iterable[str]] = None) -> str:
    """Return a self-contained classic script registering the named components.

    Write the result to a ``.js`` file and load it with a plain
    ``<script src>``; it carries its own CSS and registers each element only if
    the tag is still free. Globals it expects the host page to have already
    loaded are listed in the banner and on ``window.TracyVis.requires`` - most
    notably Plotly for indigo's charts.
    """
    if names is None:
        names = default_bundle_components()
    components = resolve(names)

    blocked = [c for c in components if c.standalone_blocker is not None]
    if blocked:
        details = "; ".join(f"{c.name}: {c.standalone_blocker}" for c in blocked)
        raise ComponentConflict(
            f"cannot build a standalone bundle from {details}"
        )

    selected = [component.name for component in components]
    tags = [tag for component in components for tag in component.tags]
    requires = sorted({name for component in components for name in component.requires})

    banner = "\n".join(
        [
            "/*",
            f" * {BUNDLE_MARKER}",
            f" * components : {', '.join(selected)}",
            f" * elements   : {', '.join(f'<{tag}>' for tag in tags) or 'none'}",
            f" * requires   : {', '.join(requires) or 'nothing'}",
            " *",
            " * Load with a plain <script src>, then call displayData(...) on the",
            " * element. Any global listed above must already be on the page.",
            " */",
        ]
    )

    css = component_css(selected)
    # The IIFE keeps each vendor's helpers (`zip`, `ungapped`, `chunked`) out of
    # the host page's global scope; the contract with the page is the element
    # tags, not the class bindings.
    return "\n".join(
        [
            banner,
            "(function (global) {",
            '"use strict";',
            _style_injector_js(css),
            component_js(selected),
            _namespace_js(selected, tags, requires),
            "})(typeof window !== \"undefined\" ? window : this);",
            "",
        ]
    )


def _style_injector_js(css: str) -> str:
    """Return JS that adds *css* to the document once."""
    return "\n".join(
        [
            "var styleKey = \"tracy-vis-components\";",
            'if (typeof document !== "undefined" &&',
            '    !document.querySelector("style[data-tracy-vis=\\"" + styleKey + "\\"]")) {',
            '  var styleEl = document.createElement("style");',
            '  styleEl.setAttribute("data-tracy-vis", styleKey);',
            f"  styleEl.textContent = {json.dumps(css)};",
            "  document.head.appendChild(styleEl);",
            "}",
        ]
    )


def _namespace_js(
    selected: list[str], tags: list[str], requires: list[str]
) -> str:
    """Return JS publishing what this bundle registered, for feature detection."""
    # Loading the same bundle twice must leave the namespace as it was, the
    # way the style injection and the element registration already do.
    return "\n".join(
        [
            "var registry = global.TracyVis || (global.TracyVis = "
            "{ components: [], elements: [], requires: [] });",
            "function recordOnce(list, values) {",
            "  for (var i = 0; i < values.length; i++) {",
            "    if (list.indexOf(values[i]) === -1) { list.push(values[i]); }",
            "  }",
            "}",
            f"recordOnce(registry.components, {json.dumps(selected)});",
            f"recordOnce(registry.elements, {json.dumps(tags)});",
            f"recordOnce(registry.requires, {json.dumps(requires)});",
        ]
    )
