"""
tracy_visualisations
====================
Bundle Tracy JSON output files together with the Indigo / TraceView web
components into self-contained HTML files.

Basic usage::

    from tracy_visualisations import bundle

    # Write to a file
    bundle("results.json", "results.html")

    # Get HTML as a string
    html = bundle("results.json")
"""

from .bundler import bundle, detect_data_type

__all__ = ["bundle", "detect_data_type"]
