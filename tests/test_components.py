"""Tests for the component registry."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


# Selecting components out of the registry.

class TestResolve:
    def test_returns_the_named_component(self):
        from tracy_visualisations.components import resolve

        # Given the registry
        # When one component is selected
        selected = resolve(["sabre"])

        # Then just that component comes back
        assert [component.name for component in selected] == ["sabre"]

    def test_ignores_a_repeated_name(self):
        from tracy_visualisations.components import resolve

        assert [c.name for c in resolve(["sabre", "sabre"])] == ["sabre"]

    def test_orders_by_the_registry_not_the_request(self):
        from tracy_visualisations.components import resolve

        # Given a request in a different order than the registry
        # When it is resolved
        selected = resolve(["sabre", "teal"])

        # Then registry order wins, so concatenation is deterministic
        assert [component.name for component in selected] == ["teal", "sabre"]

    def test_rejects_an_unknown_name(self):
        from tracy_visualisations.components import resolve

        with pytest.raises(ValueError, match="unknown component"):
            resolve(["nope"])


class TestConflicts:
    """Namespacing removed the collision that used to make this a hazard."""

    def test_teal_and_indigo_can_now_ship_together(self):
        from tracy_visualisations.components import resolve

        # Given the two apps that both call their viewer a trace view - teal
        # draws SVG, indigo draws a Plotly chart
        # When both are selected
        selected = resolve(["teal", "indigo"])

        # Then they resolve: their tags are namespaced by app, and each is
        # emitted in its own scope, so neither the tags nor the two identically
        # named classes collide
        assert [component.name for component in selected] == ["teal", "indigo"]

    def test_their_tags_are_distinct(self):
        from tracy_visualisations.components import COMPONENTS

        assert COMPONENTS["teal"].tags == ("teal-trace-view",)
        assert "indigo-trace-view" in COMPONENTS["indigo"].tags

    def test_rejects_two_components_claiming_one_tag(self, monkeypatch):
        from tracy_visualisations import components as module

        # Given a second component that registers a tag another already owns
        impostor = module.Component(
            name="sabre",
            sources=(module.Path("other.js"),),
            elements=(("msa-view", "OtherElement"),),
        )
        monkeypatch.setitem(module.COMPONENTS, "impostor", impostor)

        # When both are selected
        # Then it is refused: one registration would silently lose to the other
        with pytest.raises(module.ComponentConflict, match="sabre-msa-view"):
            module.resolve(["sabre", "impostor"])

    def test_the_conflict_names_both_components(self, monkeypatch):
        from tracy_visualisations import components as module

        impostor = module.Component(
            name="sabre",
            sources=(module.Path("other.js"),),
            elements=(("msa-view", "OtherElement"),),
        )
        monkeypatch.setitem(module.COMPONENTS, "impostor", impostor)

        with pytest.raises(module.ComponentConflict) as excinfo:
            module.resolve(["sabre", "impostor"])

        assert "'sabre'" in str(excinfo.value)

    def test_each_component_alone_is_fine(self):
        from tracy_visualisations.components import resolve

        for name in ("teal", "indigo", "pearl", "sabre"):
            assert resolve([name])



# What the registry emits.

class TestComponentJs:
    @pytest.mark.parametrize("name", ["teal", "indigo", "pearl", "sabre"])
    def test_leaves_no_module_syntax(self, name):
        from tracy_visualisations.components import component_js

        # Given a component
        # When its JavaScript is emitted
        emitted = component_js([name])

        # Then nothing is left that a classic <script> would choke on
        assert not re.search(r"^\s*(import|export)\s", emitted, re.MULTILINE)

    @pytest.mark.parametrize("name", ["teal", "indigo", "pearl", "sabre"])
    def test_declares_every_class_it_registers(self, name):
        from tracy_visualisations.components import COMPONENTS, component_js

        emitted = component_js([name])
        for class_name in COMPONENTS[name].classes:
            assert re.search(rf"\bclass\s+{class_name}\b", emitted)

    @pytest.mark.parametrize("name", ["teal", "indigo", "pearl", "sabre"])
    def test_guards_every_registration(self, name):
        from tracy_visualisations.components import COMPONENTS, component_js

        # Given a component with elements to register
        emitted = component_js([name])

        # When each tag is looked for
        # Then it is registered through the guard, so loading a component
        # twice is a no-op instead of a NotSupportedError
        for tag in COMPONENTS[name].tags:
            assert f'defineElement("{tag}"' in emitted
        if COMPONENTS[name].tags:
            assert "if (!customElements.get(tag))" in emitted

    @pytest.mark.parametrize("name", ["teal", "indigo", "pearl", "sabre"])
    def test_emitted_javascript_parses(self, name, tmp_path):
        from tracy_visualisations.components import component_js

        node = pytest.importorskip("shutil").which("node")
        if node is None:
            pytest.skip("node is not installed")

        # Given the emitted component
        script = tmp_path / f"{name}.js"
        script.write_text(component_js([name]), encoding="utf-8")

        # When node parses it
        result = subprocess.run(
            [node, "--check", str(script)], capture_output=True, text=True
        )

        # Then it is syntactically valid, so the page will not die on load
        assert result.returncode == 0, result.stderr


class TestComponentCss:
    def test_always_carries_the_d_none_fallback(self):
        from tracy_visualisations.components import component_css

        # Given any component - the vendored scripts all toggle Bootstrap's
        # `d-none`, which none of their own stylesheets define
        # When the CSS is emitted
        # Then the fallback is present, so a page works without the CDN
        for name in ("teal", "indigo", "pearl", "sabre"):
            assert ".d-none { display: none !important; }" in component_css([name])

    def test_includes_the_component_stylesheet(self):
        from tracy_visualisations.components import component_css

        emitted = component_css(["sabre"])
        assert ".alignment-block" in emitted


class TestDriftGuards:
    """The registry has to notice when a vendored source moves under it."""

    def _component(self):
        from tracy_visualisations.components import Component

        return Component(
            name="demo",
            sources=(Path("demo.js"),),
            elements=(("demo-view", "DemoElement"),),
        )

    def test_rejects_surviving_module_syntax(self):
        from tracy_visualisations.components import _assert_adaptable

        # Given adapted output that still has an import in it
        adapted = "import x from 'y'\nclass DemoElement {}"

        # When it is checked
        # Then it is refused rather than emitted as a page that cannot run
        with pytest.raises(RuntimeError, match="module syntax"):
            _assert_adaptable(self._component(), Path("demo.js"), adapted)

    def test_rejects_a_class_that_has_been_renamed_upstream(self):
        from tracy_visualisations.components import _assert_adaptable

        with pytest.raises(RuntimeError, match="not declared"):
            _assert_adaptable(
                self._component(), Path("demo.js"), "class RenamedElement {}"
            )

    def test_accepts_a_source_that_still_matches(self):
        from tracy_visualisations.components import _assert_adaptable

        _assert_adaptable(self._component(), Path("demo.js"), "class DemoElement {}")


# The standalone `<script src>` bundle.

class TestBuildBundle:
    def test_defaults_to_the_bundle_safe_components(self):
        from tracy_visualisations.components import default_bundle_components

        # Given the registry
        # When the default set is computed
        names = default_bundle_components()

        # Then it holds every component teal did not supersede: namespaced
        # tags and per-component scoping mean nothing collides any more,
        # indigo included, but sage is left for whoever asks for it by name
        assert names == ["teal", "indigo", "pearl", "sabre"]

    def test_leaves_a_superseded_component_out_of_the_default_set(self):
        from tracy_visualisations.components import (
            COMPONENTS,
            default_bundle_components,
        )

        # Given sage, which teal replaced as the trace viewer
        assert "sage" in COMPONENTS

        # When the default set is computed
        names = default_bundle_components()

        # Then it is absent, so the default bundle does not carry two
        # near-identical trace viewers
        assert "sage" not in names

    def test_a_superseded_component_still_bundles_when_asked_for(self):
        from tracy_visualisations.components import build_bundle

        # Given sage requested by name
        # When it is bundled
        bundle = build_bundle(["sage"])

        # Then it is emitted under its own namespaced tag
        assert 'defineElement("sage-trace-view", TraceViewElement)' in bundle

    def test_sage_and_teal_ship_together(self):
        from tracy_visualisations.components import build_bundle

        # Given the old trace viewer and the one that replaced it
        # When both are bundled
        bundle = build_bundle(["sage", "teal"])

        # Then both register, because the tags are namespaced by app and each
        # TraceViewElement is emitted in its own scope
        assert 'defineElement("sage-trace-view"' in bundle
        assert 'defineElement("teal-trace-view"' in bundle

    def test_every_registered_component_is_now_bundle_safe(self):
        from tracy_visualisations.components import COMPONENTS

        # Sabre was the last page script in the registry; nothing left resolves
        # host-page elements at module scope.
        blocked = {
            name: component.standalone_blocker
            for name, component in COMPONENTS.items()
            if component.standalone_blocker is not None
        }
        assert blocked == {}

    def test_refuses_a_component_that_is_still_a_page_script(self, monkeypatch):
        from tracy_visualisations import components as module

        # Given a component that resolves page elements at module scope
        page_script = module.Component(
            name="legacy",
            sources=(module.Path("legacy.js"),),
            standalone_blocker="resolves #btn-submit at module scope",
        )
        monkeypatch.setitem(module.COMPONENTS, "legacy", page_script)

        # When a standalone bundle is asked for
        # Then it is refused, with the reason, rather than emitting a script
        # that throws on any page lacking those elements
        with pytest.raises(module.ComponentConflict, match="module scope"):
            module.build_bundle(["legacy"])

    def test_carries_its_own_css(self):
        from tracy_visualisations.components import build_bundle

        bundle = build_bundle(["teal"])
        assert "data-tracy-vis" in bundle
        assert "document.createElement(\"style\")" in bundle

    def test_injects_its_css_only_once(self):
        from tracy_visualisations.components import build_bundle

        # Given the bundle loaded twice on one page
        # When the injector runs the second time
        # Then it finds its own marker and does nothing
        assert 'style[data-tracy-vis=' in build_bundle(["teal"])

    def test_records_what_it_registered_without_duplicating(self):
        from tracy_visualisations.components import build_bundle

        bundle = build_bundle(["teal"])
        assert "global.TracyVis" in bundle
        assert "function recordOnce" in bundle

    def test_is_wrapped_so_vendor_helpers_stay_off_the_host_page(self):
        from tracy_visualisations.components import build_bundle

        bundle = build_bundle(["teal"])
        assert bundle.count("(function (global) {") == 1
        assert '"use strict";' in bundle

    def test_banner_names_the_globals_the_page_must_supply(self):
        from tracy_visualisations.components import build_bundle, COMPONENTS

        # Given indigo, which draws with Plotly
        # When it is bundled on its own
        bundle = build_bundle(["indigo"])

        # Then the dependency is stated rather than left to fail at runtime
        assert "Plotly" in bundle.split("*/")[0]
        assert COMPONENTS["indigo"].requires == ("Plotly",)

    def test_bundle_parses(self, tmp_path):
        import shutil

        from tracy_visualisations.components import build_bundle

        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not installed")

        script = tmp_path / "bundle.js"
        script.write_text(build_bundle(["teal"]), encoding="utf-8")

        result = subprocess.run(
            [node, "--check", str(script)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr


class TestAssemblyComponent:
    """Pearl's editor, extracted from a page script into an element."""

    def test_registers_the_assembly_view_element(self):
        from tracy_visualisations.components import component_js

        emitted = component_js(["pearl"])
        assert "class AssemblyViewElement" in emitted
        assert 'defineElement("pearl-assembly-view"' in emitted

    def test_pearls_page_logic_is_present_but_dormant(self):
        from tracy_visualisations.components import component_js

        # Given that the element and the pearl website share one file
        emitted = component_js(["pearl"])

        # When the component is emitted
        # Then the site's wiring comes along, but every listener is attached
        # optionally, to elements only the pearl page has, so none of it runs
        assert "submitButton?.addEventListener" in emitted
        assert "loadJFile?.addEventListener" in emitted
        assert "if (typeof $ !== 'undefined')" in emitted

    def test_nothing_that_would_throw_runs_at_module_scope(self):
        from tracy_visualisations.components import component_js

        # `process` does not exist in a browser, so evaluating
        # `process.env.API_URL` on load would kill the whole bundle.
        emitted = component_js(["pearl"])
        for line in emitted.splitlines():
            if "process.env" in line:
                assert line.startswith("  "), (
                    f"process.env read at module scope: {line!r}"
                )

    def test_the_apps_own_registration_is_dropped(self):
        from tracy_visualisations.components import component_js

        # Upstream registers the element under its bare name from the same
        # file; the registry registers it under a namespaced one, and an
        # unguarded define would throw on a second load.
        emitted = component_js(["pearl"])
        assert "customElements.define('assembly-view'" not in emitted
        assert 'defineElement("pearl-assembly-view"' in emitted

    def test_keeps_no_state_on_the_window_object(self):
        from tracy_visualisations.components import component_js

        # Pearl kept the whole editing buffer in `window.data`, which is what
        # made it impossible to have two of them on a page.
        assert "window.data" not in component_js(["pearl"])

    def test_can_be_bundled_alongside_the_other_components(self):
        from tracy_visualisations.components import build_bundle

        # Given every bundle-safe component
        bundle = build_bundle(["teal", "indigo", "pearl", "sabre"])

        # When they are concatenated
        # Then all three register, with no name collision between them
        for tag in ("teal-trace-view", "indigo-trace-view",
                    "pearl-assembly-view", "sabre-msa-view"):
            assert f'defineElement("{tag}"' in bundle

    def test_resets_the_svg_height_between_repaints(self):
        from tracy_visualisations.components import component_js

        # Upstream set svgHeight once and added a panel height per trace on
        # every repaint, so the viewBox grew without bound as the user
        # navigated. The reset is what keeps it stable.
        emitted = component_js(["pearl"])
        assert "data.tp.svgHeight = 30;" in emitted

    def test_escapes_percent_before_building_the_data_uri(self):
        from tracy_visualisations.components import component_js

        # The SVG is sized in percent, and a literal '%' left in the markup
        # makes the data: URI malformed, which throws before anything renders.
        emitted = component_js(["pearl"])
        assert 'retVal.replace(regEx0, "%25")' in emitted

    def test_paints_into_markup_it_creates_on_demand(self):
        from tracy_visualisations.components import component_js

        # The markup is built in connectedCallback, but displayData paints
        # straight into it, so a host filling in an element it has not yet
        # appended would hit an empty element.
        emitted = component_js(["pearl"])
        body = emitted.split("displayData(assembly, options = {}) {", 1)[1]
        assert body.lstrip().startswith("this.#ensureInitialized()")

    def test_the_edit_position_setter_tolerates_an_empty_buffer(self):
        from tracy_visualisations.components import component_js

        # The buffer starts as "" and a class body is strict mode, so assigning
        # through the setter before any displayData threw rather than no-opping.
        emitted = component_js(["pearl"])
        setter = emitted.split("set editPosition(position) {", 1)[1]
        assert setter.split("}", 1)[0].strip().startswith("if (!this.#data)")

    def test_gives_each_instance_its_own_position_field_id(self):
        from tracy_visualisations.components import component_js

        # Two editors on one page must not emit the same id, or the second
        # label points at the first input.
        emitted = component_js(["pearl"])
        assert 'id="assembly-view-position"' not in emitted
        assert "${this.#positionFieldId}" in emitted
        assert "++AssemblyViewElement.#instanceCount" in emitted

    def test_keeps_the_icons_the_sites_own_buttons_carried(self):
        from tracy_visualisations.components import component_js

        # The buttons are regenerated from #markup now, so anything the
        # hand-written page markup carried has to be reproduced there.
        emitted = component_js(["pearl"])
        assert "fas fa-gavel" in emitted

    def test_reports_whether_a_loaded_file_can_be_displayed(self):
        from tracy_visualisations.components import component_js

        # Upstream revealed the page's result panel from inside repaintData.
        # The element no longer touches page chrome, so it has to say whether
        # the load worked and let the page reveal its own panel.
        emitted = component_js(["pearl"])
        assert "return Promise.reject(new Error(\"no file selected\"))" in emitted
        assert "showElement(resultData)" in emitted.split(
            "loadJFile?.addEventListener", 1
        )[1]
