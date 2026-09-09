        function getSpanIndex(node){
            while (node && node !== view){
                if (node.dataset && node.dataset.idx) return parseInt(node.dataset.idx, 10);
                node = node.parentNode;
            }
            return null;
        }

        this._seqSelectionHandler = () => {
            var sel = window.getSelection();
            if (!sel || sel.rangeCount === 0) return;
            var range = sel.getRangeAt(0);
            var startIdx = getSpanIndex(range.startContainer);
            var endIdx = getSpanIndex(range.endContainer);
            if (startIdx === null || endIdx === null) return;
            if (range.endOffset === 0) endIdx = endIdx - 1;
            if (startIdx > endIdx) { var t=startIdx; startIdx=endIdx; endIdx=t; }
            startIdx = Math.max(0,startIdx);
            endIdx = Math.min(tr.gappedTrace.basecallPos.length-1, endIdx);
            if (endIdx < startIdx) return;

            var startBase = parseFloat(tr.gappedTrace.basecallPos[startIdx]);
            var endBase   = parseFloat(tr.gappedTrace.basecallPos[endIdx]);
            if (!isFinite(startBase) || !isFinite(endBase)) return;

            var selSpan = Math.max(1, endBase - startBase + 1);
            var spanWithMargin = Math.max(10, selSpan * 1.2);
            var centerBase = (startBase + endBase) / 2;

            self.winXst = centerBase - spanWithMargin / 2;
            self.winXend = centerBase + spanWithMargin / 2;

            self.#checkWindow(tr.gappedTrace.peakA.length - 1);
            self.#SVGRepaint();
        };
