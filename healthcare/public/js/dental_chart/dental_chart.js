/* Dental Chart (Frappe-ready)
   - Whole-tooth states + per-surface markers (rounded)
   - Hover preview only on UNmarked surfaces
   - Buttons (black text); Healthy/Missing auto-disabled in Surface mode
   - Right-aligned Surfaces toggle (switch)
   - Quadrant pills (UR/UL/LL/LR)
   - Theme: 'light' | 'dark' | 'auto' (Desk + OS + DOM observers)
*/
(function () {
	// ---------- CSS ----------
	function injectStylesOnce() {
		if (document.getElementById('dc-styles')) return;
		const css = `
.dc-wrap{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial;user-select:none;color:#111827}
.dc-toolbar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-bottom:.75rem}
.dc-btn{border:1px solid #e5e7eb;padding:.45rem .9rem;border-radius:999px;background:#fff;cursor:pointer;font-size:.85rem;box-shadow:0 1px 0 rgba(0,0,0,.03);color:#111827}
.dc-btn:hover{background:#f9fafb}
.dc-btn.active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.25)}
.dc-btn:disabled,.dc-btn.disabled{opacity:.55;box-shadow:none;cursor:not-allowed}

.dc-canvas{width:100%;min-height:740px}
.dc-canvas svg{width:100%;height:100%;display:block;touch-action:none}

.tooth-rect{fill:#fff;stroke:#64748b;stroke-width:1}
.tooth .tooth-rect{filter:drop-shadow(0 .5px .5px rgba(0,0,0,.08))}
.tooth.selected .tooth-rect{stroke:#6366f1;stroke-width:2}

/* SURFACES — hover only if not marked */
.surf{cursor:pointer;fill-opacity:.001;stroke-linejoin:round}
.surf.hover:not([data-marked="1"]){
  fill:#94a3b8;fill-opacity:.18;stroke:#6366f1;stroke-width:1.4;stroke-opacity:.9;
}
.dc-wrap[data-theme="dark"] .surf.hover:not([data-marked="1"]){
  fill:#94a3b8;fill-opacity:.22;stroke:#a5b4fc;stroke-width:1.4;stroke-opacity:.95;
}
.body-hit{cursor:pointer;fill:#000;fill-opacity:.001;stroke:transparent;pointer-events:all}

/* quadrant axes */
.quad-axis { stroke:#9ca3af; stroke-width:1; stroke-dasharray:4 3; opacity:.9 }
.dc-wrap[data-theme="dark"] .quad-axis { stroke:#64748b; opacity:.85 }

/* tooth-level states */
.state-healthy .tooth-rect{fill:#f8fafc}
.state-caries .tooth-rect{fill:#fee2e2;stroke:#ef4444}
.state-missing .tooth-rect{fill:#f3f4f6;stroke:#9ca3af;stroke-dasharray:3 2}
.state-crown .tooth-rect{fill:#fff7ed;stroke:#f59e0b}
.state-implant .tooth-rect{fill:#eff6ff;stroke:#3b82f6}

/* chip (hidden unless text) */
.chip{pointer-events:none;font-size:10px;fill:#111827;display:none}
.chip-bg{fill:#e5e7eb;rx:3;ry:3}

/* tooltip */
.dc-tip{position:fixed;pointer-events:none;background:#111827;color:#fff;font-size:12px;padding:.2rem .4rem;border-radius:.35rem;transform:translate(-50%,calc(-100% - 8px));display:none;z-index:9999}
.dc-tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#111827}

/* tool button fills (text stays black) */
.dc-btn.tool-healthy{background:#f8fafc;border-color:#e5e7eb}
.dc-btn.tool-caries{background:#fff5f5;border-color:#ffe4e6}
.dc-btn.tool-filled{background:#f0fdf4;border-color:#dcfce7}
.dc-btn.tool-missing{background:#f3f4f6;border-color:#e5e7eb}
.dc-btn.tool-crown{background:#fff7ed;border-color:#ffedd5}
.dc-btn.tool-implant{background:#eff6ff;border-color:#dbeafe}

/* dark theme */
.dc-wrap[data-theme="dark"]{color:#e5e7eb}
.dc-wrap[data-theme="dark"] .dc-btn{background:#0b0f19;border-color:#1f2937;color:#e5e7eb}
.dc-wrap[data-theme="dark"] .dc-btn:hover{background:#111827}
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

/* right-aligned Surfaces toggle */
.dc-toolbar .dc-spacer{margin-left:auto}
.dc-switch{display:inline-flex;align-items:center;gap:.5rem;cursor:pointer;font-size:.85rem;user-select:none}
.dc-switch input{display:none}
.dc-switch-ui{position:relative;width:42px;height:24px;border-radius:999px;background:#e5e7eb;border:1px solid #d1d5db;transition:all .18s ease}
.dc-switch-ui::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:999px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.12);transition:transform .18s ease}
.dc-switch input:checked + .dc-switch-ui{background:#6366f1;border-color:#6366f1}
.dc-switch input:checked + .dc-switch-ui::after{transform:translateX(18px)}
.dc-wrap[data-theme="dark"] .dc-switch-ui{background:#1f2937;border-color:#374151}
.dc-wrap[data-theme="dark"] .dc-switch input:checked + .dc-switch-ui{background:#4f46e5;border-color:#4f46e5}

/* Quadrant pills */
.quad-pill{font-size:.78rem;fill:#374151}
.quad-bg{fill:#e5e7eb;rx:10;ry:10}
.dc-wrap[data-theme="dark"] .quad-bg{fill:#1f2937}
.dc-wrap[data-theme="dark"] .quad-pill{fill:#d1d5db}
    `;
		const s = document.createElement('style'); s.id = 'dc-styles'; s.textContent = css; document.head.appendChild(s);
	}

	// ---------- helpers ----------
	const el = (t, a = {}, ...kids) => { const n = document.createElement(t); for (const k in a) n.setAttribute(k, a[k]); kids.forEach(c => n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)); return n; };
	const svgEl = (t, a = {}) => { const n = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) n.setAttribute(k, a[k]); return n; };
	const Cap = s => s.charAt(0).toUpperCase() + s.slice(1);
	const shortLabel = x => ({ healthy: '', caries: 'Caries', filled: 'Filled', missing: 'Missing', crown: 'Crown', implant: 'Implant' })[x] || x;

	// ---------- shapes / data ----------
	const SHAPES = {
		incisor: (w, h) => `M ${.15 * w},0 Q ${.50 * w},${.05 * h} ${.85 * w},0 Q ${.95 * w},${.35 * h} ${.70 * w},${.85 * h} Q ${.50 * w},${.98 * h} ${.30 * w},${.85 * h} Q ${.05 * w},${.35 * h} ${.15 * w},0 Z`,
		canine: (w, h) => `M ${.20 * w},0 Q ${.50 * w},${.08 * h} ${.80 * w},0 Q ${.95 * w},${.40 * h} ${.65 * w},${.92 * h} Q ${.50 * w},${1.00 * h} ${.35 * w},${.92 * h} Q ${.05 * w},${.40 * h} ${.20 * w},0 Z`,
		premolar: (w, h) => `M ${.12 * w},${.05 * h} Q ${.50 * w},0 ${.88 * w},${.05 * h} Q ${.98 * w},${.45 * h} ${.75 * w},${.90 * h} Q ${.50 * w},${1.02 * h} ${.25 * w},${.90 * h} Q ${.02 * w},${.45 * h} ${.12 * w},${.05 * h} Z`,
		molar: (w, h) => `M ${.10 * w},${.10 * h} Q ${.50 * w},${-.02 * h} ${.90 * w},${.10 * h} Q ${1.02 * w},${.52 * h} ${.80 * w},${.92 * h} Q ${.50 * w},${1.08 * h} ${.20 * w},${.92 * h} Q ${-.02 * w},${.52 * h} ${.10 * w},${.10 * h} Z`
	};
	const typeOf = fdi => { const n = Number(fdi) % 10; return (n === 1 || n === 2) ? 'incisor' : (n === 3) ? 'canine' : (n === 4 || n === 5) ? 'premolar' : 'molar'; };
	const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
	const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

	// ---------- layout (Catmull–Rom + arclength) ----------
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
	function arcTable(poly) { const s = [0]; for (let i = 1; i < poly.length; i++) { const dx = poly[i].x - poly[i - 1].x, dy = poly[i].y - poly[i - 1].y; s.push(s[i - 1] + Math.hypot(dx, dy)); } return { poly, s, L: s[s.length - 1] }; }
	function pointAtArclen(tab, dist) {
		const { poly, s, L } = tab; if (dist <= 0) return { ...poly[0], ang: 0 };
		if (dist >= L) { const n = poly.length - 1, dx = poly[n].x - poly[n - 1].x, dy = poly[n].y - poly[n - 1].y; return { ...poly[n], ang: Math.atan2(dy, dx) } }
		let lo = 0, hi = s.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; (s[m] < dist ? lo = m : hi = m) }
		const t = (dist - s[lo]) / ((s[hi] - s[lo]) || 1), x = poly[lo].x + t * (poly[hi].x - poly[lo].x), y = poly[lo].y + t * (poly[hi].y - poly[lo].y);
		const dx = poly[hi].x - poly[lo].x, dy = poly[hi].y - poly[lo].y; return { x, y, ang: Math.atan2(dy, dx) };
	}
	function widthForFDI(baseW, fdi) { const t = typeOf(fdi); return t === 'incisor' ? baseW * 0.78 : t === 'canine' ? baseW * 0.90 : t === 'premolar' ? baseW * 0.98 : baseW * 1.05; }
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

	// ---------- theme helpers ----------
	function autoTheme() {
		const boot = (window.frappe && window.frappe.boot && window.frappe.boot.desk_theme) || null;
		if (boot) return /dark/i.test(String(boot)) ? 'dark' : 'light';
		const doc = document.documentElement, body = document.body;
		const attr = (doc.getAttribute('data-theme') || body?.getAttribute?.('data-theme') || '').toLowerCase();
		if (attr === 'dark' || attr === 'light') return attr;
		const cls = (doc.className + ' ' + (body?.className || '')).toLowerCase();
		if (/\bdark\b/.test(cls)) return 'dark';
		if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
		return 'light';
	}

	class DentalChart {
		constructor(target, opts = {}) {
			this.root = (typeof target === 'string') ? document.querySelector(target) : target;
			if (!this.root) throw new Error('DentalChart: target not found');

			this.opts = Object.assign({
				width: 920, height: 740,
				toothW: 48, toothH: 60,
				archTightness: 0.92, gapPx: 10,
				autoFit: true, minScale: 0.96,
				useSurfaceToggle: true, startSurfaceMode: false,
				theme: 'auto',
				onChange: null, initial: {},
				showQuadrants: true,
				quadrantSpread: 60,
				quadPill: { padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 },
				quadrantLabels: ['Upper Right', 'Upper Left', 'Lower Left', 'Lower Right'],
				quadrantAxisStyle: { stroke: '#9ca3af', width: 1, dash: '4 3', opacity: 0.9 },
				palette: ['caries', 'filled', 'crown', 'implant', 'missing', 'healthy']
			}, opts);

			injectStylesOnce();
			this._ensureTip();

			this._allSurfaces = [];
			this._themeTimer = null;
			this.state = JSON.parse(JSON.stringify(this.opts.initial || {}));
			this.currentTool = 'healthy';
			this.surfaceMode = !!this.opts.startSurfaceMode;

			this.setTheme(this.opts.theme);
			this._mount();
		}

		// -------------- public --------------
		getState() { return JSON.parse(JSON.stringify(this.state)); }
		setState(next) { this.state = JSON.parse(JSON.stringify(next || {})); this._redrawStates(); this._emit(); }
		setTheme(mode) {
			this._themeModeExplicit = mode || 'light';
			if (this._themeModeExplicit === 'auto') this._startThemeAutoSync();
			else { this._stopThemeAutoSync(); this.root.setAttribute('data-theme', this._themeModeExplicit === 'dark' ? 'dark' : 'light'); }
		}

		// -------------- theme auto --------------
		_applyThemeFromSignals() {
			if (this._themeModeExplicit !== 'auto') return;
			const next = autoTheme();
			const cur = this.root.getAttribute('data-theme') || '';
			if (next !== cur) this.root.setAttribute('data-theme', next);
		}
		_startThemeAutoSync() {
			// initial
			this.root.setAttribute('data-theme', autoTheme());

			// DOM mutations
			const mo = new MutationObserver(() => this._applyThemeFromSignals());
			mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
			if (document.body) mo.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
			this._themeMO = mo;

			// storage
			this._onStorage = () => this._applyThemeFromSignals();
			window.addEventListener('storage', this._onStorage, false);

			// OS
			if (window.matchMedia) {
				const mq = window.matchMedia('(prefers-color-scheme: dark)');
				const cb = () => this._applyThemeFromSignals();
				mq.addEventListener ? mq.addEventListener('change', cb) : mq.addListener(cb);
				this._themeMQ = { mq, cb };
			}

			// gentle periodic check
			this._themeTimer = window.setInterval(() => this._applyThemeFromSignals(), 2000);
		}
		_stopThemeAutoSync() {
			if (this._themeMO) { this._themeMO.disconnect(); this._themeMO = null; }
			if (this._onStorage) { window.removeEventListener('storage', this._onStorage, false); this._onStorage = null; }
			if (this._themeMQ) {
				const { mq, cb } = this._themeMQ;
				mq.removeEventListener ? mq.removeEventListener('change', cb) : mq.removeListener(cb);
				this._themeMQ = null;
			}
			if (this._themeTimer) { clearInterval(this._themeTimer); this._themeTimer = null; }
		}

		// -------------- lifecycle --------------
		_emit() { if (typeof this.opts.onChange === 'function') this.opts.onChange(this.getState()); }
		_ensureTip() {
			if (!document.getElementById('dc-tip')) {
				const tip = el('div', { id: 'dc-tip', class: 'dc-tip' });
				document.body.appendChild(tip);
			}
		}

		_mount() {
			this.root.innerHTML = '';
			const bar = this._renderToolbar();
			const canvas = this._renderSVG();
			this.root.append(bar, canvas);
			this._applySurfaceInteractivity();
			this._redrawStates();

			if (!this._ro) { this._ro = new ResizeObserver(() => this._remountIfSizeChanged()); this._ro.observe(this.root); }
		}
		_remountIfSizeChanged() { const w = this.root.clientWidth || 0; if (Math.abs((this._lastW || 0) - w) > 24) { this._lastW = w; this._mount(); } }

		// -------------- toolbar --------------
		_renderToolbar() {
			const bar = el('div', { class: 'dc-toolbar' });
			this._toolButtons = {};
			// tools (left)
			this.opts.palette.forEach(name => {
				const b = el('button', { class: 'dc-btn tool-' + name, 'data-tool': name, type: 'button' }, Cap(name));
				this._toolButtons[name] = b;
				if (name === this.currentTool) b.classList.add('active');
				b.addEventListener('click', () => {
					if (b.disabled) return;
					this.currentTool = name;
					bar.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
					b.classList.add('active');
				});
				bar.appendChild(b);
			});
			// surfaces toggle (right)
			const right = el('div', { class: 'dc-spacer' });
			const switchId = 'dc-surfaces-' + Math.random().toString(36).slice(2, 8);
			const label = el('label', { class: 'dc-switch', for: switchId });
			const input = el('input', { type: 'checkbox', id: switchId, role: 'switch', 'aria-checked': this.surfaceMode ? 'true' : 'false' });
			input.checked = !!this.surfaceMode;
			const ui = el('span', { class: 'dc-switch-ui' });
			const txt = document.createTextNode('Surfaces');
			label.append(input, ui, txt);
			right.appendChild(label);
			bar.appendChild(right);

			const sync = () => {
				input.checked = !!this.surfaceMode;
				input.setAttribute('aria-checked', this.surfaceMode ? 'true' : 'false');
				this._syncSurfaceToolDisables();
			};
			input.addEventListener('change', () => {
				this.surfaceMode = !!input.checked;
				this._applySurfaceInteractivity();
				sync();
			});
			sync();

			return bar;
		}
		_syncSurfaceToolDisables() {
			const dis = !!this.surfaceMode;
			['healthy', 'missing'].forEach(name => {
				const btn = this._toolButtons[name]; if (!btn) return;
				btn.disabled = dis;
				btn.setAttribute('aria-disabled', dis ? 'true' : 'false');
				btn.classList.toggle('disabled', dis);
				if (dis && this.currentTool === name) {
					const fallback = this._toolButtons['caries'] ? 'caries'
						: Object.keys(this._toolButtons).find(n => !['healthy', 'missing'].includes(n));
					if (fallback) {
						this.currentTool = fallback;
						Object.entries(this._toolButtons).forEach(([k, b]) => b.classList.toggle('active', k === fallback));
					}
				}
			});
		}

		// -------------- SVG + layout --------------
		_renderSVG() {
			const containerW = this.root.clientWidth || 0;
			const W = Math.max(720, containerW || this.opts.width || 920);
			const H = this.opts.height || 740;
			const k = this.opts.archTightness || 1;

			const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });

			const cx = W / 2;
			const upperCtrl = [{ x: cx - W * (.36 * k), y: H * .39 }, { x: cx - W * (.18 * k), y: H * .30 }, { x: cx, y: H * .27 }, { x: cx + W * (.18 * k), y: H * .30 }, { x: cx + W * (.36 * k), y: H * .39 }];
			const lowerCtrl = [{ x: cx - W * (.36 * k), y: H * .71 }, { x: cx - W * (.18 * k), y: H * .80 }, { x: cx, y: H * .83 }, { x: cx + W * (.18 * k), y: H * .80 }, { x: cx + W * (.36 * k), y: H * .71 }];

			const totalWidthPx = this.opts.toothW * 15.2 * k;
			const up = archPositionsWeighted(UPPER, upperCtrl, totalWidthPx, this.opts.gapPx);
			const lo = archPositionsWeighted(LOWER, lowerCtrl, totalWidthPx, this.opts.gapPx);
			const fit = Math.min(up.layoutScale, lo.layoutScale);
			this._drawScale = this.opts.autoFit ? Math.max(this.opts.minScale, fit) : 1;

			this._allSurfaces.length = 0;

			const gU = svgEl('g'), gL = svgEl('g'); svg.append(gU, gL);
			UPPER.forEach((n, i) => { const p = up.positions[i]; gU.append(this._makeTooth(n, p.x, p.y, p.rot, true)); });
			LOWER.forEach((n, i) => { const p = lo.positions[i]; gL.append(this._makeTooth(n, p.x, p.y, p.rot, false)); });

			if (this.opts.showQuadrantAxes) this._renderQuadrantAxes(svg, W, H, upperCtrl, lowerCtrl);
			if (this.opts.showQuadrants) this._renderQuadrants(svg, upperCtrl, lowerCtrl);

			this.svg = svg;

			// delegated surface click (ensures clicks always register)
			this._onSvgClick && this.svg.removeEventListener('click', this._onSvgClick, false);
			this._onSvgClick = (e) => {
				if (!this.surfaceMode) return;
				const t = e.target;
				if (!(t instanceof SVGElement) || !t.classList.contains('surf')) return;
				const toothG = t.closest('g.tooth'); if (!toothG) return;
				const fdi = +toothG.getAttribute('data-tooth');
				const surfKey = (t.dataset && (t.dataset.surfKey || t.dataset.surfkey)) || t.getAttribute('data-surf-key') || t.getAttribute('data-surfkey');
				if (!surfKey) return;
				if (this.currentTool === 'healthy' || this.currentTool === 'missing') return; // disabled in surface mode
				this._applyTool(fdi, String(surfKey).toUpperCase());
				e.stopPropagation();
			};
			this.svg.addEventListener('click', this._onSvgClick, false);

			return el('div', { class: 'dc-canvas', style: `min-height:${H}px` }, svg);
		}

		_renderQuadrants(svg, upperCtrl, lowerCtrl) {
			const labels = this.opts.quadrantLabels || ['UR', 'UL', 'LL', 'LR'];
			const spread = Number(this.opts.quadrantSpread || 0);

			const pillCfg = Object.assign(
				{ padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 },
				this.opts.quadPill || {}
			);

			// end points of the two arches
			const u0 = upperCtrl[0], u1 = upperCtrl[upperCtrl.length - 1];
			const l0 = lowerCtrl[0], l1 = lowerCtrl[lowerCtrl.length - 1];

			// helper to make a pill at (x,y) with centered text
			const makePill = (x, y, text, anchor = 'middle') => {
				const w = Math.max(pillCfg.minW, pillCfg.padX * 2 + text.length * 7.2);
				const h = Math.max(pillCfg.minH, pillCfg.padY * 2 + 12);
				const g = svgEl('g', { transform: `translate(${x},${y})` });
				const bg = svgEl('rect', {
					class: 'quad-bg',
					x: -w / 2, y: -h / 2, width: w, height: h,
					rx: pillCfg.radius, ry: pillCfg.radius
				});
				const tx = svgEl('text', {
					class: 'quad-pill',
					'text-anchor': anchor,
					x: 0, y: 4
				});
				tx.textContent = text;
				g.append(bg, tx);
				svg.appendChild(g);
			};

			// Compute outward directions (roughly away from center line)
			const cx = (u0.x + u1.x + l0.x + l1.x) / 4;

			// Upper Right (viewer’s right): u0
			const urX = u0.x - spread; const urY = u0.y - spread;
			// Upper Left: u1
			const ulX = u1.x + spread; const ulY = u1.y - spread;
			// Lower Left: l0
			const llX = l0.x - spread; const llY = l0.y + spread;
			// Lower Right: l1
			const lrX = l1.x + spread; const lrY = l1.y + spread;

			makePill(urX, urY, labels[0]); // UR
			makePill(ulX, ulY, labels[1]); // UL
			makePill(llX, llY, labels[2]); // LL
			makePill(lrX, lrY, labels[3]); // LR
		}

		_renderQuadrantAxes(svg, W, H, upperCtrl, lowerCtrl) {
			const st = Object.assign({ stroke: '#9ca3af', width: 1, dash: '4 3', opacity: 0.9 },
				this.opts.quadrantAxisStyle || {});
			const cx = W / 2;

			// Midline (vertical through center)
			const v = svgEl('line', {
				x1: cx, x2: cx,
				y1: H * 0.18, y2: H * 0.92,
				class: 'quad-axis'
			});

			// Horizontal divider between arches (approx)
			const hy = (upperCtrl[0].y + lowerCtrl[0].y) / 2; // between the two control rows
			const h = svgEl('line', {
				x1: W * 0.06, x2: W * 0.94,
				y1: hy, y2: hy,
				class: 'quad-axis'
			});

			// style overrides (so you can customize)
			[v, h].forEach(line => {
				if (st.stroke) line.setAttribute('stroke', st.stroke);
				if (st.width != null) line.setAttribute('stroke-width', String(st.width));
				if (st.dash) line.setAttribute('stroke-dasharray', st.dash);
				if (st.opacity != null) line.setAttribute('opacity', String(st.opacity));
			});

			// draw behind teeth & pills: insert at svg start
			svg.insertBefore(v, svg.firstChild);
			svg.insertBefore(h, svg.firstChild);
		}


		_applySurfaceInteractivity() {
			const on = !!this.surfaceMode;
			this._allSurfaces.forEach(r => {
				r.setAttribute('pointer-events', on ? 'all' : 'none');
				if (!on) r.classList.remove('hover');
			});
		}

		_makeTooth(fdi, x, y, rotDeg, isUpper) {
			const g = svgEl('g', { class: 'tooth', 'data-tooth': String(fdi) });
			const s = this._drawScale || 1, typ = typeOf(fdi);
			const w = widthForFDI(this.opts.toothW, fdi) * s, h = this.opts.toothH * s;

			const body = svgEl('path', { d: SHAPES[typ](w, h), class: 'tooth-rect' });
			const bodyHit = svgEl('rect', { class: 'body-hit', x: 0, y: 0, width: w, height: h, rx: 4, ry: 4 });
			const hits = this._makeSurfaceHits(w, h);

			const rotation = isUpper ? rotDeg : rotDeg + 180;
			g.setAttribute('transform', `translate(${x - w / 2},${y - h / 2}) rotate(${rotation},${w / 2},${h / 2})`);

			const ly = isUpper ? (-4) : (h + 12);
			const label = svgEl('text', { x: w / 2, y: ly, 'text-anchor': 'middle', 'font-size': '10px', fill: '#6b7280' }); label.textContent = String(fdi);

			const chipG = svgEl('g', { class: 'chip', transform: `translate(4,12)` });
			const chipBg = svgEl('rect', { class: 'chip-bg', width: 32, height: 12 });
			const chipTx = svgEl('text', { x: 3, y: 9, 'font-size': '9px' }, ''); chipG.append(chipBg, chipTx);

			g.append(body, bodyHit);
			hits.forEach(p => g.appendChild(p));
			g.append(label, chipG);

			hits.forEach(r => this._allSurfaces.push(r));

			const tip = document.getElementById('dc-tip');

			// Hover hint ONLY for unmarked surfaces
			g.addEventListener('pointerover', (e) => {
				if (!this.surfaceMode) return;
				const n = e.target;
				if (n.classList?.contains('surf') && n.getAttribute('data-marked') !== '1') {
					n.classList.add('hover');
					n.style.removeProperty('fill-opacity'); // let CSS handle hover opacity
				}
				if (tip) { const t = this._tooltipFor(e, fdi); if (t) { tip.textContent = t; tip.style.display = 'block'; } }
			});
			g.addEventListener('pointermove', (e) => {
				if (!this.surfaceMode || !tip) return;
				const r = e.target.getBoundingClientRect(); tip.style.left = (r.left + r.width / 2) + 'px'; tip.style.top = (r.top) + 'px';
			});
			g.addEventListener('pointerout', (e) => {
				const n = e.target;
				if (n.classList?.contains('surf')) {
					n.classList.remove('hover');
					if (n.getAttribute('data-marked') !== '1') n.style.removeProperty('fill-opacity');
				}
				if (tip) tip.style.display = 'none';
			});

			// Whole-tooth click
			bodyHit.addEventListener('click', () => { this._applyTool(fdi, null); });

			// cache
			g._chip = chipG; g._chipText = chipTx; g._chipBg = chipBg; g._rect = body; g._cells = [...hits];
			return g;
		}

		_makeSurfaceHits(w, h) {
			const pad = Math.max(2, Math.round(Math.min(w, h) * 0.06));
			const r = Math.max(3, Math.round(Math.min(w, h) * 0.10)); // rounded
			const arr = [];
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));                   // B
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: h - (h * .28) - pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));         // L
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r }));             // M
			arr.push(svgEl('rect', { class: 'surf', x: w - (w * .28) - pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r }));   // D
			arr.push(svgEl('rect', { class: 'surf center', x: w * .30, y: h * .30, width: w * .40, height: h * .40, rx: r, ry: r }));          // O
			const keys = ['B', 'L', 'M', 'D', 'O'];
			arr.forEach((n, i) => { const v = keys[i]; n.dataset.surfKey = v; n.setAttribute('data-surf-key', v); n.setAttribute('data-surfkey', v); n.dataset.rx = String(r); });
			return arr;
		}

		_tooltipFor(e, fdi) {
			const sk = (e.target && e.target.classList?.contains('surf')) ? (e.target.dataset.surfKey || '') : '';
			const name = sk ? ({ M: 'Mesial', D: 'Distal', B: 'Buccal/Labial', L: 'Lingual/Palatal', O: 'Occlusal/Incisal' })[sk] : null;
			const t = this.state[String(fdi)], st = t?.state || 'healthy';
			return name ? `${fdi} • ${name} • ${Cap(st)}` : `${fdi} • ${Cap(st)}`;
		}

		// -------------- state --------------
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
				const text = (T.state && T.state !== 'healthy') ? shortLabel(T.state) : '';
				g._chipText.textContent = text;
				if (text) { g._chip.style.display = 'block'; g._chipBg.setAttribute('width', String(Math.max(18, 6 + text.length * 5))); }
				else g._chip.style.display = 'none';

				const isMissing = T.state === 'missing';
				g._cells.forEach(cell => {
					const rr = (cell.dataset && cell.dataset.rx) ? cell.dataset.rx : '4';
					cell.setAttribute('rx', rr); cell.setAttribute('ry', rr);

					const k = (cell.dataset && cell.dataset.surfKey) ? cell.dataset.surfKey.toUpperCase() : null;
					const mark = k ? T.surfaces?.[k] : null;

					if (isMissing) {
						cell.removeAttribute('data-marked');
						cell.style.cssText = '';
						return;
					}

					if (mark) {
						cell.setAttribute('data-marked', '1');
						cell.style.fill = this._surfaceTint(mark);
						cell.style.fillOpacity = '0.85';
						cell.style.stroke = this._surfaceStroke(mark);
						cell.style.strokeWidth = '1.6';
						cell.style.strokeOpacity = '0.9';
					} else {
						cell.removeAttribute('data-marked');
						cell.style.cssText = '';
					}
				});
			} else {
				g._chip.style.display = 'none';
				g._cells.forEach(cell => { const rr = cell.dataset?.rx || '4'; cell.setAttribute('rx', rr); cell.setAttribute('ry', rr); cell.removeAttribute('data-marked'); cell.style.cssText = ''; });
			}
		}

		// subtle pastels
		_surfaceTint(tool) {
			switch (tool) {
				case 'caries': return '#ffe4e6'; // rose-100
				case 'filled': return '#dcfce7'; // green-100
				case 'crown': return '#ffedd5'; // orange-100
				case 'implant': return '#dbeafe'; // blue-100
				case 'missing': return '#e5e7eb';
				default: return '#e5e7eb';
			}
		}
		_surfaceStroke(tool) {
			switch (tool) {
				case 'caries': return '#fb7185'; // rose-400
				case 'filled': return '#34d399'; // green-400
				case 'crown': return '#f59e0b'; // amber-500
				case 'implant': return '#60a5fa'; // blue-400
				case 'missing': return '#9ca3af';
				default: return '#9ca3af';
			}
		}
	}

	window.DentalChart = DentalChart;
})();
