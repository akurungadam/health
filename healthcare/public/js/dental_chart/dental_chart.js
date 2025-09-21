/* dental_chart.js — Mouth-shaped dental chart with auto-fit spacing, quadrant pills, and tooth/surface marking */
(function () {
    // ---------------------------
    // Style injector
    // ---------------------------
    function injectStylesOnce() {
        if (document.getElementById('dc-styles')) return;
        const css = `
            .dc-wrap{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial}
            .dc-toolbar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-bottom:.75rem}
            .dc-btn{border:1px solid #e5e7eb;padding:.45rem .9rem;border-radius:999px;background:#fff;cursor:pointer;font-size:.85rem;box-shadow:0 1px 0 rgba(0,0,0,.03)}
            .dc-btn:hover{background:#f9fafb}
            .dc-btn.active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.25);background:#eef2ff;color:#3730a3}

            .dc-canvas{width:100%;min-height:760px}
            .dc-canvas svg{width:100%;height:100%;display:block}

            .tooth-rect{fill:#fff;stroke:#9ca3af;stroke-width:1}
            .tooth .tooth-rect{filter:drop-shadow(0 .5px .5px rgba(0,0,0,.08))}
            .tooth.selected .tooth-rect{stroke:#6366f1;stroke-width:2}
            .tooth-rect { pointer-events: none; }


            .surf{fill:#f9fafb;stroke:#d1d5db;stroke-width:.8}
            .surf.hover{fill:#e5e7eb}
            /* idle surface hit-zones: invisible but clickable */
            .surf { fill: transparent; stroke: transparent; stroke-width:.8; }
            .surf.hover { stroke:#cbd5e1; fill: rgba(148,163,184,.06); } /* light hint on hover */


            /* state tints (tooth-level) */
            .state-healthy .tooth-rect{fill:#f8fafc}
            .state-caries .surf,.state-caries .tooth-rect{fill:#fee2e2;stroke:#ef4444}
            .state-filled .surf.center{fill:#dcfce7;stroke:#16a34a}
            .state-missing .tooth-rect{fill:#f3f4f6;stroke:#9ca3af;stroke-dasharray:3 2}
            .state-crown .tooth-rect{fill:#fff7ed;stroke:#f59e0b}
            .state-implant .tooth-rect{fill:#eff6ff;stroke:#3b82f6}

            /* status chip */
            .chip{pointer-events:none;font-size:10px;fill:#111827;display:none} /* hidden by default; shown only if text */
            .chip-bg{fill:#e5e7eb;rx:3;ry:3}

            /* tooltip */
            .dc-tip{position:fixed;pointer-events:none;background:#111827;color:#fff;font-size:12px;padding:.2rem .4rem;border-radius:.35rem;transform:translate(-50%,calc(-100% - 8px));display:none;z-index:50}
            .dc-tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#111827}

            /* Quadrants */
            .dc-canvas .quad-line{stroke:#e5e7eb;stroke-width:1;stroke-dasharray:4 4}
            .dc-canvas .quad-badge{cursor:pointer}
            .dc-canvas .quad-pill{fill:#f3f4f6;stroke:#e5e7eb}
            .dc-canvas .quad-badge:hover .quad-pill{fill:#eef2ff;stroke:#c7d2fe}
            .dc-canvas .quad-badge.active .quad-pill{fill:#eef2ff;stroke:#6366f1}
            .dc-canvas .quad-text{fill:#374151;font-weight:600}

            /* Dimming non-focused quadrants */
            .dc-wrap[data-quad-focus] g.tooth{opacity:.28;transition:opacity .15s ease}
            .dc-wrap[data-quad-focus="1"] g.tooth[data-quad="1"],
            .dc-wrap[data-quad-focus="2"] g.tooth[data-quad="2"],
            .dc-wrap[data-quad-focus="3"] g.tooth[data-quad="3"],
            .dc-wrap[data-quad-focus="4"] g.tooth[data-quad="4"]{opacity:1}
        `;
        const style = document.createElement('style');
        style.id = 'dc-styles';
        style.textContent = css;
        document.head.appendChild(style);
    }

    // ---------------------------
    // DOM helpers
    // ---------------------------
    function el(tag, attrs = {}, ...children) {
        const n = document.createElement(tag);
        for (const k in attrs) if (attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
        children.forEach((c) => {
            if (c == null) return;
            if (typeof c === 'string') n.appendChild(document.createTextNode(c));
            else n.appendChild(c);
        });
        return n;
    }
    function svgEl(tag, attrs = {}) { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in attrs) n.setAttribute(k, attrs[k]); return n; }
    function prettyLabel(x) { return x.charAt(0).toUpperCase() + x.slice(1); }
    function shortLabel(x) { return ({ healthy: '', caries: 'Caries', filled: 'Filled', missing: 'Missing', crown: 'Crown', implant: 'Implant' })[x] || x; }

    // ---------------------------
    // Tooth shapes
    // ---------------------------
    const TOOTH_TEMPLATES = {
        incisor: (w, h) => `M ${0.15 * w},0 Q ${0.50 * w},${0.05 * h} ${0.85 * w},0 Q ${0.95 * w},${0.35 * h} ${0.70 * w},${0.85 * h} Q ${0.50 * w},${0.98 * h} ${0.30 * w},${0.85 * h} Q ${0.05 * w},${0.35 * h} ${0.15 * w},0 Z`,
        canine: (w, h) => `M ${0.20 * w},0 Q ${0.50 * w},${0.08 * h} ${0.80 * w},0 Q ${0.95 * w},${0.40 * h} ${0.65 * w},${0.92 * h} Q ${0.50 * w},${1.00 * h} ${0.35 * w},${0.92 * h} Q ${0.05 * w},${0.40 * h} ${0.20 * w},0 Z`,
        premolar: (w, h) => `M ${0.12 * w},${0.05 * h} Q ${0.50 * w},0 ${0.88 * w},${0.05 * h} Q ${0.98 * w},${0.45 * h} ${0.75 * w},${0.90 * h} Q ${0.50 * w},${1.02 * h} ${0.25 * w},${0.90 * h} Q ${0.02 * w},${0.45 * h} ${0.12 * w},${0.05 * h} Z`,
        molar: (w, h) => `M ${0.10 * w},${0.10 * h} Q ${0.50 * w},${-0.02 * h} ${0.90 * w},${0.10 * h} Q ${1.02 * w},${0.52 * h} ${0.80 * w},${0.92 * h} Q ${0.50 * w},${1.08 * h} ${0.20 * w},${0.92 * h} Q ${-0.02 * w},${0.52 * h} ${0.10 * w},${0.10 * h} Z`,
    };
    function toothTypeFromFDI(fdi) { const n = Number(fdi) % 10; if (n === 1 || n === 2) return 'incisor'; if (n === 3) return 'canine'; if (n === 4 || n === 5) return 'premolar'; return 'molar'; }
    const UPPER_FDI = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
    const LOWER_FDI = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

    // ---------------------------
    // Spline + spacing + auto-fit
    // ---------------------------
    function sampleCR(points, resolution = 300) {
        const pts = points.map(p => ({ x: +p.x, y: +p.y }));
        const P = [pts[0], ...pts, pts[pts.length - 1]];
        const out = [];
        for (let i = 0; i < P.length - 3; i++) {
            const p0 = P[i], p1 = P[i + 1], p2 = P[i + 2], p3 = P[i + 3];
            for (let t = 0; t < resolution; t++) {
                const u = t / resolution, u2 = u * u, u3 = u2 * u;
                const b0 = -0.5 * u3 + 1.0 * u2 - 0.5 * u;
                const b1 = 1.5 * u3 - 2.5 * u2 + 1.0;
                const b2 = -1.5 * u3 + 2.0 * u2 + 0.5 * u;
                const b3 = 0.5 * u3 - 0.5 * u2;
                out.push({ x: b0 * p0.x + b1 * p1.x + b2 * p2.x + b3 * p3.x, y: b0 * p0.y + b1 * p1.y + b2 * p2.y + b3 * p3.y });
            }
        }
        out.push(pts[pts.length - 1]);
        return out;
    }
    function arcTable(poly) { const s = [0]; for (let i = 1; i < poly.length; i++) { const dx = poly[i].x - poly[i - 1].x, dy = poly[i].y - poly[i - 1].y; s.push(s[i - 1] + Math.hypot(dx, dy)); } return { poly, s, L: s[s.length - 1] }; }
    function pointAtArclen(tab, dist) {
        const { poly, s, L } = tab;
        if (dist <= 0) return { ...poly[0], ang: 0 };
        if (dist >= L) { const n = poly.length - 1; const dx = poly[n].x - poly[n - 1].x, dy = poly[n].y - poly[n - 1].y; return { ...poly[n], ang: Math.atan2(dy, dx) }; }
        let lo = 0, hi = s.length - 1; while (hi - lo > 1) { const mid = (lo + hi) >> 1; (s[mid] < dist ? lo = mid : hi = mid); }
        const t = (dist - s[lo]) / ((s[hi] - s[lo]) || 1);
        const x = poly[lo].x + t * (poly[hi].x - poly[lo].x), y = poly[lo].y + t * (poly[hi].y - poly[lo].y);
        const dx = poly[hi].x - poly[lo].x, dy = poly[hi].y - poly[lo].y;
        return { x, y, ang: Math.atan2(dy, dx) };
    }
    function widthForFDI(baseW, fdi) {
        const typ = toothTypeFromFDI(fdi);
        return typ === 'incisor' ? baseW * 0.78 : typ === 'canine' ? baseW * 0.90 : typ === 'premolar' ? baseW * 0.98 : baseW * 1.05;
    }

    // returns { positions: [...], layoutScale: number }
    function archPositionsSplineWeighted(fdiList, ctrlPts, totalWidthPx, gapPx) {
        const poly = sampleCR(ctrlPts, 120);
        const table = arcTable(poly);

        const halfs = fdiList.map(f => widthForFDI(totalWidthPx / 16, f) / 2);
        const centers = [];
        let cur = halfs[0];
        centers.push(cur);
        for (let i = 1; i < fdiList.length; i++) {
            cur += halfs[i - 1] + (gapPx || 0) + halfs[i];
            centers.push(cur);
        }

        const requiredLen = centers[centers.length - 1] || 1;
        const margin = Math.max(halfs[0], halfs[halfs.length - 1]) + 10;
        const usable = Math.max(10, table.L - 2 * margin);

        const posScale = usable / requiredLen;
        const layoutScale = Math.min(1, posScale); // shrink if needed; never enlarge beyond 1

        const positions = centers.map(c => {
            const p = pointAtArclen(table, margin + c * posScale);
            return { x: p.x, y: p.y, rot: (p.ang * 180 / Math.PI) };
        });

        return { positions, layoutScale };
    }

    class DentalChart {
        constructor(target, opts = {}) {
            this.root = (typeof target === 'string') ? document.querySelector(target) : target;
            if (!this.root) throw new Error('DentalChart: target not found');

            this.opts = Object.assign({
                width: 920,
                height: 760,
                toothW: 48,
                toothH: 60,
                archTightness: 0.9,    // 1.0 wide … 0.9 = 10% tighter
                gapPx: 10,              // inter-tooth gap along the curve
                showQuadrants: true,
                quadrantLabels: { 1: 'UR', 2: 'UL', 3: 'LL', 4: 'LR' },
                quadOffset: 56,         // distance from arch (px)
                quadSpreadX: 0.84,      // outward spread (0..1 of half width)
                quadPill: { padX: 10, padY: 5, radius: 10, minW: 30, minH: 20 },
                useSurfaceToggle: true, // show a "Surfaces" toggle instead of Shift
                onChange: null,
                initial: {},
                palette: ['healthy', 'caries', 'filled', 'missing', 'crown', 'implant']
            }, opts);

            this.state = JSON.parse(JSON.stringify(this.opts.initial || {}));
            this.currentTool = 'healthy';
            this.surfaceMode = !!this.opts.startSurfaceMode;
            this._lastW = 0;
            this._mount();
        }

        getState() { return JSON.parse(JSON.stringify(this.state)); }
        setState(next) { this.state = JSON.parse(JSON.stringify(next || {})); this._redrawStates(); this._emit(); }
        _emit() { if (typeof this.opts.onChange === 'function') this.opts.onChange(this.getState()); }

        _mount() {
            injectStylesOnce();
            this.root.innerHTML = '';
            const toolbar = this._renderToolbar();
            const canvas = this._renderSVG();
            this.root.appendChild(toolbar);
            this.root.appendChild(canvas);
            this._redrawStates();

            if (!this._ro) {
                this._ro = new ResizeObserver(() => this._remountIfSizeChanged());
                this._ro.observe(this.root);
            }
        }
        _remountIfSizeChanged() {
            const w = this.root.clientWidth || 0;
            if (Math.abs(this._lastW - w) > 24) {
                this._lastW = w;
                this._mount();
            }
        }

        _renderToolbar() {
            const bar = el('div', { class: 'dc-toolbar' });

            // tool buttons
            this.opts.palette.forEach(name => {
                const b = el('button', { class: 'dc-btn', 'data-tool': name }, prettyLabel(name));
                if (name === this.currentTool) b.classList.add('active');
                b.addEventListener('click', () => {
                    this.currentTool = name;
                    bar.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
                    b.classList.add('active');
                });
                bar.appendChild(b);
            });

            // surface toggle (preferred over Shift)
            if (this.opts.useSurfaceToggle) {
                const surfBtn = el('button', { class: 'dc-btn', style: 'margin-left:.5rem' }, 'Surfaces');
                const sync = () => surfBtn.classList.toggle('active', this.surfaceMode);
                surfBtn.addEventListener('click', () => { this.surfaceMode = !this.surfaceMode; sync(); });
                sync();
                bar.appendChild(surfBtn);
            }

            // optional tip (remove if you don’t want any)
            const tip = el('span', { class: 'dc-badge', style: 'margin-left:auto' },
                this.opts.useSurfaceToggle ? 'Surface Mode toggles by pill' : 'Tip: Shift+Click to mark a surface'
            );
            bar.appendChild(tip);

            return bar;
        }

        _renderSVG() {
            const containerW = this.root.clientWidth || 0;
            const W = Math.max(720, containerW || this.opts.width || 920);
            const H = this.opts.height || 760;
            const k = this.opts.archTightness || 1.0;

            const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });

            // Control points (mouth-like), tightened by k
            const cx = W / 2;
            const upperCtrl = [
                { x: cx - W * (0.36 * k), y: H * 0.39 },
                { x: cx - W * (0.18 * k), y: H * 0.30 },
                { x: cx, y: H * 0.27 },
                { x: cx + W * (0.18 * k), y: H * 0.30 },
                { x: cx + W * (0.36 * k), y: H * 0.39 },
            ];
            const lowerCtrl = [
                { x: cx - W * (0.36 * k), y: H * 0.71 },
                { x: cx - W * (0.18 * k), y: H * 0.80 },
                { x: cx, y: H * 0.83 },
                { x: cx + W * (0.18 * k), y: H * 0.80 },
                { x: cx + W * (0.36 * k), y: H * 0.71 },
            ];

            // width along curve (also tightened by k)
            const totalWidthPx = this.opts.toothW * 15.2 * k;

            // positions + auto-fit scaling
            const up = archPositionsSplineWeighted(UPPER_FDI, upperCtrl, totalWidthPx, this.opts.gapPx);
            const lo = archPositionsSplineWeighted(LOWER_FDI, lowerCtrl, totalWidthPx, this.opts.gapPx);

            const fit = Math.min(up.layoutScale, lo.layoutScale);
            this._drawScale = this.opts.autoFit ? Math.max(this.opts.minScale, fit) : 1;


            const gU = svgEl('g'), gL = svgEl('g'); svg.append(gU, gL);
            UPPER_FDI.forEach((num, i) => { const p = up.positions[i]; gU.append(this._makeTooth(num, p.x, p.y, p.rot, true)); });
            LOWER_FDI.forEach((num, i) => { const p = lo.positions[i]; gL.append(this._makeTooth(num, p.x, p.y, p.rot, false)); });

            if (this.opts.showQuadrants) this._renderQuadrants(svg, W, H);

            this.svg = svg;
            const container = el('div', { class: 'dc-canvas' });
            container.style.minHeight = (this.opts.height || 760) + 'px'; // respects your height option
            container.appendChild(svg);
            return container;
        }

        _renderQuadrants(svg, W, H) {
            const g = svgEl('g', { class: 'dc-quads' });

            // crosshair (subtle)
            const midY = H * 0.55;
            g.append(
                svgEl('line', { x1: W / 2, y1: H * 0.18, x2: W / 2, y2: H * 0.92, class: 'quad-line' }),
                svgEl('line', { x1: W * 0.08, y1: midY, x2: W * 0.92, y2: midY, class: 'quad-line' })
            );

            const labs = this.opts.quadrantLabels || { 1: 'UR', 2: 'UL', 3: 'LL', 4: 'LR' };

            const upperArcY = H * 0.34, lowerArcY = H * 0.76;
            const v = (this.opts.quadOffset ?? 56);
            const s = (this.opts.quadSpreadX ?? 0.84);
            const cx = W / 2, xLeft = cx - (W * 0.5 * s), xRight = cx + (W * 0.5 * s);

            const pillCfg = Object.assign({ padX: 10, padY: 5, radius: 10, minW: 30, minH: 20 }, this.opts.quadPill || {});
            const makePill = (x, y, text, q) => {
                const grp = svgEl('g', { class: 'quad-badge', 'data-q': String(q), transform: `translate(${x},${y})` });
                const t = svgEl('text', { x: 0, y: 4, 'text-anchor': 'middle', 'font-size': '11px', class: 'quad-text' });
                t.textContent = text;

                grp.appendChild(t);
                svg.appendChild(grp);                // append first to measure
                const b = t.getBBox();

                const w = Math.max(pillCfg.minW, b.width + pillCfg.padX * 2);
                const h = Math.max(pillCfg.minH, b.height + pillCfg.padY * 2);
                const r = pillCfg.radius;

                const rect = svgEl('rect', { x: -w / 2, y: -h / 2, width: w, height: h, rx: r, ry: r, class: 'quad-pill' });
                grp.insertBefore(rect, t);

                grp.addEventListener('click', () => this._toggleQuadrant(q));
                return grp;
            };

            const b1 = makePill(xRight, upperArcY - v, labs[1], 1); // UR
            const b2 = makePill(xLeft, upperArcY - v, labs[2], 2); // UL
            const b3 = makePill(xLeft, lowerArcY + v, labs[3], 3); // LL
            const b4 = makePill(xRight, lowerArcY + v, labs[4], 4); // LR

            g.append(b1, b2, b3, b4);
            svg.appendChild(g);
        }
        _toggleQuadrant(q) {
            const wrap = this.root;
            const cur = wrap.getAttribute('data-quad-focus');
            if (cur === String(q)) {
                wrap.removeAttribute('data-quad-focus');
                wrap.querySelectorAll('.quad-badge').forEach(b => b.classList.remove('active'));
                return;
            }
            wrap.setAttribute('data-quad-focus', String(q));
            wrap.querySelectorAll('.quad-badge').forEach(b => {
                b.classList.toggle('active', b.getAttribute('data-q') === String(q));
            });
        }

        _makeTooth(fdi, x, y, rotDeg, isUpper) {
            const g = svgEl('g', { class: 'tooth', 'data-tooth': String(fdi) });

            // quadrant tag (FDI: 1=UR, 2=UL, 3=LL, 4=LR)
            const q = (fdi >= 11 && fdi <= 18) ? 1 :
                (fdi >= 21 && fdi <= 28) ? 2 :
                    (fdi >= 31 && fdi <= 38) ? 3 : 4;
            g.dataset.quad = String(q);

            const s = this._drawScale || 1;   // auto-fit scale
            const typ = toothTypeFromFDI(fdi);
            const baseW = this.opts.toothW, baseH = this.opts.toothH;
            const w = widthForFDI(baseW, fdi) * s;
            const h = baseH * s;

            const d = TOOTH_TEMPLATES[typ](w, h);
            const body = svgEl('path', { d, class: 'tooth-rect', fill: '#fff', stroke: '#9ca3af', 'stroke-width': 1 });

            // orientation: artwork points DOWN at 0°, so use tangent for upper; tangent-180 for lower
            const alpha = rotDeg;
            const rotation = isUpper ? alpha : (alpha - 180);
            g.setAttribute('transform', `translate(${x - w / 2}, ${y - h / 2}) rotate(${rotation}, ${w / 2}, ${h / 2})`);

            // surfaces (B, L, M, D, O)
            const hits = this._makeSurfaceHits(w, h); hits.forEach(p => g.appendChild(p));

            // FDI label (upper above, lower below)
            const labelY = isUpper ? (-4) : (h + 12);
            const label = svgEl('text', { x: w / 2, y: labelY, 'text-anchor': 'middle', 'font-size': '10px', fill: '#6b7280' }); label.textContent = String(fdi);

            // status chip (hidden unless text is non-empty)
            const chipG = svgEl('g', { class: 'chip', transform: `translate(4,12)` });
            const chipBg = svgEl('rect', { class: 'chip-bg', width: 32, height: 12 });
            const chipTx = svgEl('text', { x: 3, y: 9, 'font-size': '9px' }, '');
            chipG.append(chipBg, chipTx);

            g.append(body, label, chipG);

            // tooltip + clicks
            const tip = document.getElementById('dc-tip');
            g.addEventListener('pointerover', (e) => { const name = this._tooltipFor(e, fdi); if (name) { tip.textContent = name; tip.style.display = 'block'; } });
            g.addEventListener('pointermove', (e) => { const r = e.target.getBoundingClientRect(); tip.style.left = (r.left + r.width / 2) + 'px'; tip.style.top = (r.top) + 'px'; });
            g.addEventListener('pointerout', () => { tip.style.display = 'none'; });

            g.addEventListener('click', (e) => {
                const surf = this.opts.useSurfaceToggle
                    ? (this.surfaceMode ? this._surfaceFromCell(e.target) : null)
                    : (e.shiftKey ? this._surfaceFromCell(e.target) : null);
                this._applyTool(fdi, surf);
            });

            // stash
            g._chip = chipG; g._chipText = chipTx; g._chipBg = chipBg; g._rect = body; g._cells = Array.from(g.querySelectorAll('.surf'));
            return g;
        }

        _makeSurfaceHits(w, h) {
            const pad = Math.max(2, Math.round(Math.min(w, h) * 0.06)); // scaled padding
            const arr = [];
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: pad, width: w - 2 * pad, height: h * 0.28 }));                       // B
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: h - (h * 0.28) - pad, width: w - 2 * pad, height: h * 0.28 }));           // L
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: (h * 0.28) + pad, width: w * 0.28, height: h * 0.44 }));              // M
            arr.push(svgEl('rect', { class: 'surf', x: w - (w * 0.28) - pad, y: (h * 0.28) + pad, width: w * 0.28, height: h * 0.44 }));   // D
            arr.push(svgEl('rect', { class: 'surf center', x: w * 0.30, y: h * 0.30, width: w * 0.40, height: h * 0.40 }));          // O
            const keys = ['B', 'L', 'M', 'D', 'O']; arr.forEach((n, i) => { n.dataset.surfKey = keys[i]; });
            return arr;
        }

        _tooltipFor(e, fdi) {
            const surfKey = this._surfaceFromCell(e.target);
            const surfName = surfKey ? ({ M: 'Mesial', D: 'Distal', B: 'Buccal/Labial', L: 'Lingual/Palatal', O: 'Occlusal/Incisal' })[surfKey] : null;
            const t = this.state[String(fdi)]; const state = t?.state || 'healthy';
            return surfName ? `${fdi} • ${surfName} • ${prettyLabel(state)}` : `${fdi} • ${prettyLabel(state)}`;
        }
        _surfaceFromCell(node) { if (!(node instanceof SVGElement) || !node.classList.contains('surf')) return null; return node.dataset.surfKey || null; }

        _applyTool(fdi, surface) {
            const key = String(fdi);
            const T = this.state[key] || { state: 'healthy', surfaces: {} };

            // Surface mode: toggle the selected tool on that surface (one tool per surface)
            if (surface) {
                if (T.surfaces[surface] === this.currentTool) delete T.surfaces[surface];
                else T.surfaces[surface] = this.currentTool;
            } else {
                // Tooth mode: set tooth-level state (e.g., Crown). This can co-exist with surface marks.
                T.state = this.currentTool;
            }
            this.state[key] = T; this._redrawTooth(fdi); this._emit();
        }

        _redrawStates() { this.svg.querySelectorAll('g.tooth').forEach(g => this._redrawTooth(+g.dataset.tooth)); }

        _redrawTooth(fdi) {
            const key = String(fdi);
            const g = this.svg.querySelector(`g.tooth[data-tooth="${key}"]`);
            if (!g) return;
            const T = this.state[key];
            g.classList.remove('state-healthy', 'state-caries', 'state-filled', 'state-missing', 'state-crown', 'state-implant', 'selected');

            if (T) {
                g.classList.add('selected', `state-${T.state || 'healthy'}`);
                const isMissing = T.state === 'missing';
                const isCrown = T.state === 'crown';

                // status chip text (hide chip entirely if empty)
                const text = (T.state && T.state !== 'healthy') ? shortLabel(T.state) : '';
                g._chipText.textContent = text;
                if (text) {
                    g._chip.style.display = 'block';
                    g._chipBg.setAttribute('width', String(Math.max(18, 6 + text.length * 5)));
                } else {
                    g._chip.style.display = 'none';
                }

                // surfaces
                g._cells.forEach(cell => {
                    const surfKey = this._surfaceFromCell(cell);
                    const mark = T.surfaces?.[surfKey];

                    if (isMissing) {
                        cell.setAttribute('fill', '#f3f4f6'); cell.setAttribute('stroke', '#9ca3af'); return;
                    }
                    if (mark) {
                        cell.setAttribute('fill', this._surfaceTint(mark));
                        cell.setAttribute('stroke', this._surfaceStroke(mark));
                    } else {
                        if (isCrown) { cell.setAttribute('fill', '#fff3e6'); cell.setAttribute('stroke', '#f59e0b'); }
                        else { cell.setAttribute('fill', '#f9fafb'); cell.setAttribute('stroke', '#d1d5db'); }
                    }
                });
            } else {
                g._chip.style.display = 'none';
                g._cells.forEach(cell => { cell.setAttribute('fill', '#f9fafb'); cell.setAttribute('stroke', '#d1d5db'); });
            }
        }

        _surfaceTint(tool) {
            switch (tool) {
                case 'caries': return '#fee2e2';
                case 'filled': return '#dcfce7';
                case 'missing': return '#e5e7eb';
                case 'crown': return '#ffedd5';
                case 'implant': return '#dbeafe';
                default: return '#f3f4f6';
            }
        }
        _surfaceStroke(tool) {
            switch (tool) {
                case 'caries': return '#ef4444';
                case 'filled': return '#16a34a';
                case 'missing': return '#9ca3af';
                case 'crown': return '#f59e0b';
                case 'implant': return '#3b82f6';
                default: return '#d1d5db';
            }
        }
    }

    // Export
    window.DentalChart = DentalChart;
})();
