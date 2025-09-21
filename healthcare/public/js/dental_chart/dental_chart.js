/* dental_chart.js — robust clicks + surface mode + auto dark mode
   - Surface overlays disabled (pointer-events:none) when Surface mode is OFF
   - Hover hint only when Surface mode is ON
   - Body-hit rect handles whole-tooth clicks when Surface mode is OFF
   - Pointer-capture on surfaces for reliability; click fallback included
   - Auto dark mode via prefers-color-scheme
*/

(function () {
    // ---------- Inject CSS ----------
    function injectStylesOnce() {
        if (document.getElementById('dc-styles')) return;
        const css = `
.dc-wrap{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial; user-select:none;color:#111827}
.dc-toolbar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-bottom:.75rem}
.dc-btn{border:1px solid #e5e7eb;padding:.45rem .9rem;border-radius:999px;background:#fff;cursor:pointer;font-size:.85rem;box-shadow:0 1px 0 rgba(0,0,0,.03)}
.dc-btn:hover{background:#f9fafb}
.dc-btn.active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.25);background:#eef2ff;color:#3730a3}
.dc-badge{padding:.25rem .5rem;border-radius:999px;font-size:.75rem;background:#eef2ff;color:#3730a3}

.dc-canvas{width:100%;min-height:760px}
.dc-canvas svg{width:100%;height:100%;display:block;touch-action:none}

.tooth-rect{fill:#fff;stroke:#64748b;stroke-width:1}
.tooth .tooth-rect{filter:drop-shadow(0 .5px .5px rgba(0,0,0,.08))}
.tooth.selected .tooth-rect{stroke:#6366f1;stroke-width:2}

/* Hit zones:
   - When ON: pointer-events enabled; invisible but clickable (opacity .001)
   - When OFF: pointer-events disabled; body-hit receives the click */
.surf{cursor:pointer; fill-opacity:.001;}
.surf.hover{fill:#94a3b8; fill-opacity:.06; stroke:#cbd5e1; stroke-linejoin: round;}

.body-hit{cursor:pointer; fill:#000; fill-opacity:.001; stroke:transparent; pointer-events:all}

/* tooth-level states (body only) */
.state-healthy .tooth-rect{fill:#f8fafc}
.state-caries .tooth-rect{fill:#fee2e2;stroke:#ef4444}
.state-missing .tooth-rect{fill:#f3f4f6;stroke:#9ca3af;stroke-dasharray:3 2}
.state-crown .tooth-rect{fill:#fff7ed;stroke:#f59e0b}
.state-implant .tooth-rect{fill:#eff6ff;stroke:#3b82f6}

/* chip (hidden unless text) */
.chip{pointer-events:none;font-size:10px;fill:#111827;display:none}
.chip-bg{fill:#e5e7eb;rx:3;ry:3}

/* tooltip */
.dc-tip{position:fixed;pointer-events:none;background:#111827;color:#fff;font-size:12px;padding:.2rem .4rem;border-radius:.35rem;transform:translate(-50%,calc(-100% - 8px));display:none;z-index:50}
.dc-tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#111827}

/* Dark theme is now opt-in via data-theme */
.dc-wrap[data-theme="dark"]{color:#e5e7eb}
.dc-wrap[data-theme="dark"] .dc-btn{background:#0b0f19;border-color:#1f2937;color:#e5e7eb}
.dc-wrap[data-theme="dark"] .dc-btn:hover{background:#111827}
.dc-wrap[data-theme="dark"] .dc-btn.active{background:#1e293b;border-color:#475569;box-shadow:0 0 0 2px rgba(99,102,241,.35);color:#c7d2fe}
.dc-wrap[data-theme="dark"] .dc-badge{background:#1e293b;color:#c7d2fe}
.dc-wrap[data-theme="dark"] .tooth-rect{fill:#0b0f19;stroke:#94a3b8}
.dc-wrap[data-theme="dark"] .tooth .tooth-rect{filter:none}
.dc-wrap[data-theme="dark"] .state-healthy .tooth-rect{fill:#0b1220}
.dc-wrap[data-theme="dark"] .state-caries .tooth-rect{fill:#3a1b1b;stroke:#f87171}
.dc-wrap[data-theme="dark"] .state-missing .tooth-rect{fill:#0f172a;stroke:#64748b}
.dc-wrap[data-theme="dark"] .state-crown .tooth-rect{fill:#3b2a17;stroke:#f59e0b}
.dc-wrap[data-theme="dark"] .state-implant .tooth-rect{fill:#0b1b34;stroke:#60a5fa}
.dc-wrap[data-theme="dark"] .chip{fill:#e5e7eb}
.dc-wrap[data-theme="dark"] .chip-bg{fill:#334155}
.dc-wrap[data-theme="dark"] .dc-tip{background:#0b0f19}
.dc-wrap[data-theme="dark"] .dc-tip::after{border-top-color:#0b0f19}
    `;
        const s = document.createElement('style');
        s.id = 'dc-styles'; s.textContent = css; document.head.appendChild(s);
    }

    // ---------- Helpers ----------
    const el = (t, a = {}, ...kids) => { const n = document.createElement(t); for (const k in a) n.setAttribute(k, a[k]); kids.forEach(c => { if (c == null) return; n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); }); return n; }
    const svgEl = (t, a = {}) => { const n = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) n.setAttribute(k, a[k]); return n; }
    const Cap = s => s.charAt(0).toUpperCase() + s.slice(1);
    const short = x => ({ healthy: '', caries: 'Caries', filled: 'Filled', missing: 'Missing', crown: 'Crown', implant: 'Implant' })[x] || x;

    // ---------- Shapes / data ----------
    const SHAPES = {
        incisor: (w, h) => `M ${0.15 * w},0 Q ${0.50 * w},${0.05 * h} ${0.85 * w},0 Q ${0.95 * w},${0.35 * h} ${0.70 * w},${0.85 * h} Q ${0.50 * w},${0.98 * h} ${0.30 * w},${0.85 * h} Q ${0.05 * w},${0.35 * h} ${0.15 * w},0 Z`,
        canine: (w, h) => `M ${0.20 * w},0 Q ${0.50 * w},${0.08 * h} ${0.80 * w},0 Q ${0.95 * w},${0.40 * h} ${0.65 * w},${0.92 * h} Q ${0.50 * w},${1.00 * h} ${0.35 * w},${0.92 * h} Q ${0.05 * w},${0.40 * h} ${0.20 * w},0 Z`,
        premolar: (w, h) => `M ${0.12 * w},${0.05 * h} Q ${0.50 * w},0 ${0.88 * w},${0.05 * h} Q ${0.98 * w},${0.45 * h} ${0.75 * w},${0.90 * h} Q ${0.50 * w},${1.02 * h} ${0.25 * w},${0.90 * h} Q ${0.02 * w},${0.45 * h} ${0.12 * w},${0.05 * h} Z`,
        molar: (w, h) => `M ${0.10 * w},${0.10 * h} Q ${0.50 * w},${-0.02 * h} ${0.90 * w},${0.10 * h} Q ${1.02 * w},${0.52 * h} ${0.80 * w},${0.92 * h} Q ${0.50 * w},${1.08 * h} ${0.20 * w},${0.92 * h} Q ${-0.02 * w},${0.52 * h} ${0.10 * w},${0.10 * h} Z`,
    };
    const typeOf = fdi => { const n = Number(fdi) % 10; return (n === 1 || n === 2) ? 'incisor' : (n === 3) ? 'canine' : (n === 4 || n === 5) ? 'premolar' : 'molar'; };
    const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
    const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

    // ---------- Spline sampling / layout ----------
    function sampleCR(points, res = 300) {
        const pts = points.map(p => ({ x: +p.x, y: +p.y }));
        const P = [pts[0], ...pts, pts[pts.length - 1]], out = [];
        for (let i = 0; i < P.length - 3; i++) {
            const p0 = P[i], p1 = P[i + 1], p2 = P[i + 2], p3 = P[i + 3];
            for (let t = 0; t < res; t++) {
                const u = t / res, u2 = u * u, u3 = u2 * u;
                const b0 = -.5 * u3 + 1 * u2 - .5 * u, b1 = 1.5 * u3 - 2.5 * u2 + 1, b2 = -1.5 * u3 + 2 * u2 + .5 * u, b3 = .5 * u3 - .5 * u2;
                out.push({ x: b0 * p0.x + b1 * p1.x + b2 * p2.x + b3 * p3.x, y: b0 * p0.y + b1 * p1.y + b2 * p2.y + b3 * p3.y });
            }
        }
        out.push(pts[pts.length - 1]); return out;
    }
    function arcTable(poly) {
        const s = [0];
        for (let i = 1; i < poly.length; i++) { const dx = poly[i].x - poly[i - 1].x, dy = poly[i].y - poly[i - 1].y; s.push(s[i - 1] + Math.hypot(dx, dy)); }
        return { poly, s, L: s[s.length - 1] };
    }
    function pointAtArclen(tab, dist) {
        const { poly, s, L } = tab;
        if (dist <= 0) return { ...poly[0], ang: 0 };
        if (dist >= L) { const n = poly.length - 1, dx = poly[n].x - poly[n - 1].x, dy = poly[n].y - poly[n - 1].y; return { ...poly[n], ang: Math.atan2(dy, dx) }; }
        let lo = 0, hi = s.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; (s[m] < dist ? lo = m : hi = m); }
        const t = (dist - s[lo]) / ((s[hi] - s[lo]) || 1);
        const x = poly[lo].x + t * (poly[hi].x - poly[lo].x), y = poly[lo].y + t * (poly[hi].y - poly[lo].y);
        const dx = poly[hi].x - poly[lo].x, dy = poly[hi].y - poly[lo].y; return { x, y, ang: Math.atan2(dy, dx) };
    }
    function widthForFDI(baseW, fdi) {
        const t = typeOf(fdi);
        return t === 'incisor' ? baseW * 0.78 : t === 'canine' ? baseW * 0.90 : t === 'premolar' ? baseW * 0.98 : baseW * 1.05;
    }
    function archPositionsWeighted(fdis, ctrlPts, totalW, gapPx) {
        const table = arcTable(sampleCR(ctrlPts, 120));
        const halfs = fdis.map(f => widthForFDI(totalW / 16, f) / 2);
        const centers = []; let cur = halfs[0]; centers.push(cur);
        for (let i = 1; i < fdis.length; i++) { cur += halfs[i - 1] + (gapPx || 0) + halfs[i]; centers.push(cur); }
        const required = centers[centers.length - 1] || 1, margin = Math.max(halfs[0], halfs[halfs.length - 1]) + 10;
        const usable = Math.max(10, table.L - 2 * margin); const posScale = usable / required; const layoutScale = Math.min(1, posScale);
        const positions = centers.map(c => { const p = pointAtArclen(table, margin + c * posScale); return { x: p.x, y: p.y, rot: (p.ang * 180 / Math.PI) }; });
        return { positions, layoutScale };
    }

    // ---------- Chart ----------
    class DentalChart {
        constructor(target, opts = {}) {
            this.root = (typeof target === 'string') ? document.querySelector(target) : target;
            if (!this.root) throw new Error('DentalChart: target not found');

            this.opts = Object.assign({
                width: 920, height: 760, toothW: 48, toothH: 60,
                archTightness: 0.92, gapPx: 10, autoFit: true, minScale: 0.96,
                showQuadrants: false, // (you can re-add the visual lines/pills if needed)
                useSurfaceToggle: true, startSurfaceMode: false, // start with surfaces ON
                onChange: null, initial: {},
                palette: ['caries', 'filled', 'crown', 'implant', 'missing', 'healthy']
            }, opts);

            const theme = (this.opts.theme === 'auto')
                ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
                : this.opts.theme;
            this.root.setAttribute('data-theme', theme);


            this.state = JSON.parse(JSON.stringify(this.opts.initial || {}));
            this.currentTool = 'healthy';
            this.surfaceMode = !!this.opts.startSurfaceMode;

            this._allSurfaces = []; // references for mode toggling
            this._lastW = 0;
            this._mount();
        }

        getState() { return JSON.parse(JSON.stringify(this.state)); }
        setState(next) { this.state = JSON.parse(JSON.stringify(next || {})); this._redrawStates(); this._emit(); }
        _emit() { if (typeof this.opts.onChange === 'function') this.opts.onChange(this.getState()); }

        _mount() {
            injectStylesOnce();
            this.root.innerHTML = '';
            const bar = this._renderToolbar();
            const canvas = this._renderSVG();
            this.root.appendChild(bar); this.root.appendChild(canvas);
            this._applySurfaceInteractivity();  // ensure correct pointer-events at mount
            this._redrawStates();
            if (!this._ro) { this._ro = new ResizeObserver(() => this._remountIfSizeChanged()); this._ro.observe(this.root); }
        }
        _remountIfSizeChanged() { const w = this.root.clientWidth || 0; if (Math.abs(this._lastW - w) > 24) { this._lastW = w; this._mount(); } }

        _renderToolbar() {
            const bar = el('div', { class: 'dc-toolbar' });
            this.opts.palette.forEach(name => {
                const b = el('button', { class: 'dc-btn', 'data-tool': name }, Cap(name));
                if (name === this.currentTool) b.classList.add('active');
                b.addEventListener('click', () => {
                    this.currentTool = name;
                    bar.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
                    b.classList.add('active');
                });
                bar.appendChild(b);
            });

            if (this.opts.useSurfaceToggle !== false) {
                const surfBtn = el('button', { class: 'dc-btn', style: 'margin-left:.5rem' }, 'Surfaces');
                const sync = () => surfBtn.classList.toggle('active', !!this.surfaceMode);
                surfBtn.addEventListener('click', () => {
                    this.surfaceMode = !this.surfaceMode;
                    sync();
                    this._applySurfaceInteractivity(); // live toggle
                });
                sync(); bar.appendChild(surfBtn);
            }

            bar.appendChild(el('span', { class: 'dc-badge', style: 'margin-left:auto' }, 'Tooth or Surfaces (pill)'));
            return bar;
        }

        _renderSVG() {
            const containerW = this.root.clientWidth || 0;
            const W = Math.max(720, containerW || this.opts.width || 920);
            const H = this.opts.height || 760;
            const k = this.opts.archTightness || 1;

            const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });

            const cx = W / 2;
            // upper & lower control points (mouth-shaped curves facing each other)
            const upperCtrl = [{ x: cx - W * (0.36 * k), y: H * 0.39 }, { x: cx - W * (0.18 * k), y: H * 0.30 }, { x: cx, y: H * 0.27 }, { x: cx + W * (0.18 * k), y: H * 0.30 }, { x: cx + W * (0.36 * k), y: H * 0.39 }];
            const lowerCtrl = [{ x: cx - W * (0.36 * k), y: H * 0.71 }, { x: cx - W * (0.18 * k), y: H * 0.80 }, { x: cx, y: H * 0.83 }, { x: cx + W * (0.18 * k), y: H * 0.80 }, { x: cx + W * (0.36 * k), y: H * 0.71 }];

            const totalWidthPx = this.opts.toothW * 15.2 * k;
            const up = archPositionsWeighted(UPPER, upperCtrl, totalWidthPx, this.opts.gapPx);
            const lo = archPositionsWeighted(LOWER, lowerCtrl, totalWidthPx, this.opts.gapPx);

            const fit = Math.min(up.layoutScale, lo.layoutScale);
            this._drawScale = this.opts.autoFit ? Math.max(this.opts.minScale, fit) : 1;

            this._allSurfaces.length = 0; // reset references

            const gU = svgEl('g'), gL = svgEl('g'); svg.append(gU, gL);
            UPPER.forEach((n, i) => { const p = up.positions[i]; gU.append(this._makeTooth(n, p.x, p.y, p.rot, true)); });
            LOWER.forEach((n, i) => { const p = lo.positions[i]; gL.append(this._makeTooth(n, p.x, p.y, p.rot, false)); });

            this.svg = svg;
            this._onSvgClick = (e) => {
                if (!this.surfaceMode) return;

                const t = e.target;
                if (!(t instanceof SVGElement) || !t.classList.contains('surf')) return;

                const toothG = t.closest('g.tooth');
                if (!toothG) return;

                const fdi = +toothG.getAttribute('data-tooth');
                let surfKey = t.getAttribute('data-surf-key')     // preferred (dataset.surfKey)
                    || t.getAttribute('data-surfkey')     // fallback
                    || (t.dataset && (t.dataset.surfKey || t.dataset.surfkey));
                if (!surfKey) return;
                surfKey = String(surfKey).toUpperCase();          // <<< normalize

                if (this.currentTool === 'healthy') {
                    const k = String(fdi);
                    const T = this.state[k] || { state: 'healthy', surfaces: {} };
                    if (T.surfaces && T.surfaces[surfKey]) delete T.surfaces[surfKey];
                    this.state[k] = T;
                    this._redrawTooth(fdi);
                    this._emit();
                } else {
                    this._applyTool(fdi, surfKey);
                }
                e.stopPropagation();
            };


            this.svg.addEventListener('click', this._onSvgClick, false);

            return el('div', { class: 'dc-canvas', style: `min-height:${this.opts.height || 760}px` }, svg);
        }

        // Surface mode interactivity
        _applySurfaceInteractivity() {
            const on = !!this.surfaceMode;
            this._allSurfaces.forEach(r => {
                r.setAttribute('pointer-events', on ? 'all' : 'none');
                if (!on) r.classList.remove('hover');
            });
        }

        // Make a tooth group
        _makeTooth(fdi, x, y, rotDeg, isUpper) {
            const g = svgEl('g', { class: 'tooth', 'data-tooth': String(fdi) });
            const s = this._drawScale || 1, typ = typeOf(fdi);
            const w = widthForFDI(this.opts.toothW, fdi) * s, h = this.opts.toothH * s;

            const bodyPath = svgEl('path', { d: SHAPES[typ](w, h), class: 'tooth-rect' });
            const bodyHit = svgEl('rect', { class: 'body-hit', x: 0, y: 0, width: w, height: h, rx: 4, ry: 4 });
            const hits = this._makeSurfaceHits(w, h);

            const rotation = isUpper ? rotDeg : rotDeg + 180;
            g.setAttribute('transform', `translate(${x - w / 2},${y - h / 2}) rotate(${rotation},${w / 2},${h / 2})`);

            const ly = isUpper ? (-4) : (h + 12);
            const label = svgEl('text', { x: w / 2, y: ly, 'text-anchor': 'middle', 'font-size': '10px', fill: '#6b7280' }); label.textContent = String(fdi);

            const chipG = svgEl('g', { class: 'chip', transform: `translate(4,12)` });
            const chipBg = svgEl('rect', { class: 'chip-bg', width: 32, height: 12 });
            const chipTx = svgEl('text', { x: 3, y: 9, 'font-size': '9px' }, ''); chipG.append(chipBg, chipTx);

            g.append(bodyPath, bodyHit);
            hits.forEach(p => g.appendChild(p));
            g.append(label, chipG);

            hits.forEach(r => this._allSurfaces.push(r));

            // Hover hint ONLY when Surface mode is ON
            const tip = document.getElementById('dc-tip');
            g.addEventListener('pointerover', (e) => {
                if (!this.surfaceMode) return;
                if (e.target.classList?.contains('surf')) e.target.classList.add('hover');
                const t = this._tooltipFor(e, fdi); if (t && tip) { tip.textContent = t; tip.style.display = 'block'; }
            });
            g.addEventListener('pointermove', (e) => {
                if (!this.surfaceMode) return;
                if (!tip) return; const r = e.target.getBoundingClientRect(); tip.style.left = (r.left + r.width / 2) + 'px'; tip.style.top = (r.top) + 'px';
            });
            g.addEventListener('pointerout', (e) => {
                if (e.target.classList?.contains('surf')) e.target.classList.remove('hover');
                if (tip) tip.style.display = 'none';
            });

            // Bind surfaces
            hits.forEach(p => this._bindSurface(p, fdi));

            // Body click -> whole tooth (only when surface mode is OFF)
            bodyHit.addEventListener('click', () => {
                this._applyTool(fdi, null);   // always allow whole-tooth click
            });
            ;

            // stash
            g._chip = chipG; g._chipText = chipTx; g._chipBg = chipBg; g._rect = bodyPath; g._cells = [...hits];
            return g;
        }

        _makeSurfaceHits(w, h) {
            const pad = Math.max(2, Math.round(Math.min(w, h) * 0.06));
            const r = Math.max(3, Math.round(Math.min(w, h) * 0.10)); // corner radius

            const arr = [];
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: pad, width: w - 2 * pad, height: h * 0.28 }));                  // B
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: h - (h * 0.28) - pad, width: w - 2 * pad, height: h * 0.28 }));  // L
            arr.push(svgEl('rect', { class: 'surf', x: pad, y: (h * 0.28) + pad, width: w * 0.28, height: h * 0.44 }));         // M
            arr.push(svgEl('rect', { class: 'surf', x: w - (w * 0.28) - pad, y: (h * 0.28) + pad, width: w * 0.28, height: h * 0.44 })); // D
            arr.push(svgEl('rect', { class: 'surf center', x: w * 0.30, y: h * 0.30, width: w * 0.40, height: h * 0.40 }));     // O

            const keys = ['B', 'L', 'M', 'D', 'O'];
            arr.forEach((n, i) => {
                const v = keys[i];
                n.dataset.surfKey = v;                 // JS API (maps to data-surf-key)
                n.setAttribute('data-surf-key', v);    // explicit HTML attr
                n.setAttribute('data-surfkey', v);     // alternative spelling seen in some code
            });
            return arr;
        }

        _bindSurface(node, fdi) {
            let down = null;
            node.addEventListener('pointerdown', (e) => {
                if (!this.surfaceMode) return;
                try { node.setPointerCapture(e.pointerId); } catch { }
                down = { x: e.clientX, y: e.clientY, tool: this.currentTool };
            });
            node.addEventListener('pointerup', (e) => {
                if (!this.surfaceMode) return;
                if (!down) return;
                const dx = e.clientX - down.x, dy = e.clientY - down.y;
                try { node.releasePointerCapture(e.pointerId); } catch { }
                const moved = (dx * dx + dy * dy) > 9;
                if (!moved) {
                    const surfKey = this._surfaceFromCell(node);
                    if (surfKey && down.tool !== 'healthy') {
                        this.currentTool = down.tool;
                        this._applyTool(fdi, surfKey);
                    }
                }
                down = null;
            });
            node.addEventListener('click', () => {
                if (!this.surfaceMode) return;
                const surfKey = this._surfaceFromCell(node);
                if (surfKey && this.currentTool !== 'healthy') this._applyTool(fdi, surfKey);
            });
        }

        _tooltipFor(e, fdi) {
            const sk = this._surfaceFromCell(e.target);
            const name = sk ? ({ M: 'Mesial', D: 'Distal', B: 'Buccal/Labial', L: 'Lingual/Palatal', O: 'Occlusal/Incisal' })[sk] : null;
            const t = this.state[String(fdi)], state = t?.state || 'healthy';
            return name ? `${fdi} • ${name} • ${Cap(state)}` : `${fdi} • ${Cap(state)}`;
        }
        _surfaceFromCell(node) { return (node instanceof SVGElement && node.classList.contains('surf')) ? (node.dataset.surfKey || null) : null; }

        _applyTool(fdi, surface) {
            const key = String(fdi);
            const T = this.state[key] || { state: 'healthy', surfaces: {} };
            if (surface) {
                if (T.surfaces[surface] === this.currentTool) delete T.surfaces[surface];
                else T.surfaces[surface] = this.currentTool;
            } else {
                T.state = this.currentTool;
            }
            this.state[key] = T; this._redrawTooth(fdi); this._emit();
        }

        _redrawStates() { this.svg.querySelectorAll('g.tooth').forEach(g => this._redrawTooth(+g.dataset.tooth)); }
        _redrawTooth(fdi) {
            const key = String(fdi), g = this.svg.querySelector(`g.tooth[data-tooth="${key}"]`); if (!g) return;
            const T = this.state[key];
            g.classList.remove('state-healthy', 'state-caries', 'state-filled', 'state-missing', 'state-crown', 'state-implant', 'selected');
            if (T) {
                g.classList.add('selected', `state-${T.state || 'healthy'}`);
                const text = (T.state && T.state !== 'healthy') ? short(T.state) : '';
                g._chipText.textContent = text;
                if (text) { g._chip.style.display = 'block'; g._chipBg.setAttribute('width', String(Math.max(18, 6 + text.length * 5))); }
                else g._chip.style.display = 'none';

                const isMissing = T.state === 'missing', isCrown = T.state === 'crown';
                g._cells.forEach(cell => {
                    const rr = cell.dataset && cell.dataset.rx ? cell.dataset.rx : '4';
                    cell.setAttribute('rx', rr);
                    cell.setAttribute('ry', rr);
                    const sk = this._surfaceFromCell(cell), mark = T.surfaces?.[sk];
                    if (isMissing) {
                        cell.setAttribute('fill', '#000'); cell.setAttribute('fill-opacity', '.001'); cell.setAttribute('stroke', 'transparent');
                        return;
                    }
                    if (mark) {
                        cell.style.fill = this._surfaceTint(mark);
                        cell.style.fillOpacity = '1';
                        cell.style.stroke = this._surfaceStroke(mark);
                        cell.style.strokeWidth = '1.2';
                    } else {
                        cell.style.fill = '';          // fall back to CSS/default
                        cell.style.fillOpacity = '.001';
                        cell.style.stroke = '';
                        cell.style.strokeWidth = '';
                    }

                });
            } else {
                g._chip.style.display = 'none';
                g._cells.forEach(cell => { cell.setAttribute('fill', '#000'); cell.setAttribute('fill-opacity', '.001'); cell.setAttribute('stroke', 'transparent'); });
            }
        }

        _surfaceTint(tool) {
            switch (tool) {
                case 'caries': return '#fee2e2';
                case 'filled': return '#dcfce7';
                case 'missing': return '#e5e7eb';
                case 'crown': return '#ffedd5';
                case 'implant': return '#dbeafe';
                default: return '#000';
            }
        }
        _surfaceStroke(tool) {
            switch (tool) {
                case 'caries': return '#ef4444';
                case 'filled': return '#16a34a';
                case 'missing': return '#9ca3af';
                case 'crown': return '#f59e0b';
                case 'implant': return '#3b82f6';
                default: return 'transparent';
            }
        }
    }

    // expose
    window.DentalChart = DentalChart;
})();
