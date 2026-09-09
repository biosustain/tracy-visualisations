        // Which bases the selection covers, decided by the range's own point
        // comparisons. Each span holds exactly one character, spanning the two
        // points (text, 0) and (text, 1), so the base is selected when neither
        // of those points falls outside the range - which is precisely what
        // `comparePoint` reports, offsets included.
        //
        // Two other readings do not work here. Deriving the bases from the
        // range's containers misses a boundary that addresses this div by
        // child index, one sitting on a `<br>` between two wrapped lines, and
        // one outside the view entirely because the drag began on the label
        // above it. `Selection.containsNode` misses the two boundary bases,
        // because a range that starts inside a span's text node does not
        // wholly contain that span.
        function selectedBaseRange(range) {
            var spans = view.querySelectorAll('span[data-idx]');
            var first = null;
            var last = null;

            for (var i = 0; i < spans.length; i++) {
                var text = spans[i].firstChild;
                if (!text) continue;
                if (range.comparePoint(text, 0) === -1) continue;  // not there yet
                if (range.comparePoint(text, 1) === 1) break;      // past the end
                var idx = parseInt(spans[i].dataset.idx, 10);
                if (first === null) first = idx;
                last = idx;
            }

            return first === null ? null : { first: first, last: last };
        }

        // Half the distance from the basecall at `from` to the one at `to`, or
        // half a sample where `to` is off either end of the trace.
        function halfGapTo(positions, from, to) {
            if (to < 0 || to >= positions.length) return 0.5;
            var gap = parseFloat(positions[to]) - parseFloat(positions[from]);
            return Math.abs(gap) / 2;
        }

        this._seqSelectionHandler = () => {
            var sel = window.getSelection();
            if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;

            var selected = selectedBaseRange(sel.getRangeAt(0));
            if (!selected) return;

            var positions = tr.gappedTrace.basecallPos;
            var firstBase = parseFloat(positions[selected.first]);
            var lastBase = parseFloat(positions[selected.last]);
            if (!isFinite(firstBase) || !isFinite(lastBase)) return;

            // The window is the selected bases and nothing besides. Each end
            // reaches half way to the basecall outside the selection, so the
            // edge peaks are still drawn whole while that neighbouring base
            // stays short of the window. #renderSeqView highlights whatever
            // the window covers, so a wider window lights up bases that were
            // never selected.
            var maxX = tr.gappedTrace.peakA.length - 1;
            var padBefore = halfGapTo(positions, selected.first, selected.first - 1);
            var padAfter = halfGapTo(positions, selected.last, selected.last + 1);

            self.winXst = Math.max(0, firstBase - padBefore);
            self.winXend = Math.min(maxX, lastBase + padAfter);

            self.#checkWindow(maxX);
            self.#SVGRepaint();
        };
