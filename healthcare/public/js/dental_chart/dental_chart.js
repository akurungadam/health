(function () {
	function injectStylesOnce() {
		if (document.getElementById('dc-styles')) return;
		const css = `
			/* ===== Base wrapper & toolbar ===== */
			.dc-wrap{font-family:ui-sans-serif,system-ui,Roboto,Arial;user-select:none;color:#111827}
			.dc-toolbar{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
			.dc-toolbar .dc-spacer{margin-left:auto}
			.dc-right{display:flex;align-items:center;gap:.4rem}

			/* Buttons (palette + selects styled like pills) */
			.dc-btn{border:1px solid #e5e7eb;padding:.28rem .55rem;border-radius:999px;background:#fff;cursor:pointer;
			font-size:.78rem;line-height:1.2;box-shadow:0 1px 0 rgba(0,0,0,.03);color:#111827}
			.dc-btn:hover{background:#f9fafb}
			.dc-btn.active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.25)}
			.dc-btn:disabled,.dc-btn.disabled{opacity:.55;box-shadow:none;cursor:not-allowed}
			.dc-toolbar select.dc-btn{min-width:auto;max-width:120px;padding-right:1rem;appearance:none;background-position:right .45rem center;background-repeat:no-repeat}

			/* Edit mode: stronger base buttons — but skip tool buttons */
			.dc-wrap.dc-edit .dc-btn:not([data-tool]){background:#f3f4f6;border-color:#cbd5e1;box-shadow:0 1px 0 rgba(0,0,0,.04)}
			.dc-wrap.dc-edit .dc-btn:not([data-tool]):hover{background:#e5e7eb}
			.dc-wrap.dc-edit .dc-btn:not([data-tool]).active{border-color:#4f46e5;box-shadow:0 0 0 2px rgba(79,70,229,.25)}

			/* Switches (Surface Marks & Perio share this) */
			.dc-switch{display:inline-flex;align-items:center;gap:.3rem;cursor:pointer;font-size:.78rem;white-space:nowrap}
			.dc-switch input{display:none}
			.dc-switch-ui{position:relative;width:34px;height:18px;border-radius:999px;background:#e5e7eb;border:1px solid #d1d5db;transition:all .18s ease}
			.dc-switch-ui::after{content:"";position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:999px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.12);transition:transform .18s ease}
			.dc-switch input:checked + .dc-switch-ui{background:#6366f1;border-color:#6366f1}
			.dc-switch input:checked + .dc-switch-ui::after{transform:translateX(16px)}

			/* Canvas */
			.dc-canvas{width:100%;min-height:740px}
			.dc-canvas svg{width:100%;height:100%;display:block;touch-action:none}

			/* Read-only */
			.dc-canvas.dc-readonly{pointer-events:none;cursor:default}
			.dc-btn.legend-disabled{opacity:.6;pointer-events:none;filter:grayscale(12%)}

			/* Tooth base */
			.tooth-rect{fill:#fff;stroke:#64748b;stroke-width:1}
			.tooth .tooth-rect{filter:drop-shadow(0 .5px .5px rgba(0,0,0,.08))}
			.tooth.selected .tooth-rect{stroke:#6366f1;stroke-width:2}

			/* Surfaces (hover only if not marked) */
			.surf{cursor:pointer;fill-opacity:.001;stroke-linejoin:round}
			.surf.hover:not([data-marked="1"]){fill:#94a3b8;fill-opacity:.18;stroke:#6366f1;stroke-width:1.4;stroke-opacity:.9}
			.dc-wrap[data-theme="dark"] .surf.hover:not([data-marked="1"]){fill:#94a3b8;fill-opacity:.22;stroke:#a5b4fc;stroke-width:1.4;stroke-opacity:.95}
			.body-hit{cursor:pointer;fill:#000;fill-opacity:.001;stroke:transparent;pointer-events:all}

			/* Quadrant axes & pills */
			.quad-axis{stroke:#9ca3af;stroke-width:1;stroke-dasharray:4 3;opacity:.9}
			.dc-wrap[data-theme="dark"] .quad-axis{stroke:#64748b;opacity:.85}
			.quad-pill{font-size:.78rem;fill:#374151}
			.quad-bg{fill:#e5e7eb;rx:10;ry:10}
			.dc-wrap[data-theme="dark"] .quad-bg{fill:#1f2937}
			.dc-wrap[data-theme="dark"] .quad-pill{fill:#d1d5db}

			/* Tooth-level states */
			.state-healthy .tooth-rect{fill:#f8fafc}
			.state-caries .tooth-rect{fill:#fee2e2;stroke:#ef4444}
			.state-missing .tooth-rect{fill:#f3f4f6;stroke:#9ca3af;stroke-dasharray:3 2}
			.state-crown .tooth-rect{fill:#fff7ed;stroke:#f59e0b}
			.state-implant .tooth-rect{fill:#eff6ff;stroke:#3b82f6}

			/* Chip (hidden unless text) */
			.chip{pointer-events:none;font-size:10px;fill:#111827;display:none}
			.chip-bg{fill:#e5e7eb;rx:3;ry:3}

			/* Tooltip */
			.dc-tip{position:fixed;pointer-events:none;background:#111827;color:#fff;font-size:12px;padding:.2rem .4rem;border-radius:.35rem;transform:translate(-50%,calc(-100% - 8px));display:none;z-index:9999}
			.dc-tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#111827}

			/* Dark theme */
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

			/* Palette color pills keep vivid */
			.dc-wrap .dc-btn[data-tool].tool-healthy{ background:#f8fafc; border-color:#e5e7eb }
			.dc-wrap .dc-btn[data-tool].tool-caries{  background:#fff5f5; border-color:#ffe4e6 }
			.dc-wrap .dc-btn[data-tool].tool-filled{  background:#f0fdf4; border-color:#dcfce7 }
			.dc-wrap .dc-btn[data-tool].tool-missing{ background:#f3f4f6; border-color:#e5e7eb }
			.dc-wrap .dc-btn[data-tool].tool-crown{   background:#fff7ed; border-color:#ffedd5 }
			.dc-wrap .dc-btn[data-tool].tool-implant{ background:#eff6ff; border-color:#dbeafe }

			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-healthy{ background:#0f172a; border-color:#1f2937 }
			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-caries{  background:#2a1216; border-color:#3a1b1f }
			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-filled{  background:#102316; border-color:#12301b }
			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-missing{ background:#111827; border-color:#2a3342 }
			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-crown{   background:#2a1d0f; border-color:#3a2917 }
			.dc-wrap[data-theme="dark"] .dc-btn[data-tool].tool-implant{ background:#0b1b34; border-color:#1f3a65 }

			.dc-wrap .dc-btn[data-tool].active{
			border-color:#4f46e5;
			box-shadow:0 0 0 2px rgba(79,70,229,.25);
			}
			/* Print */
			@media print {
			.dc-toolbar, .dc-tip { display: none !important; }
			.dc-wrap { color: #000 !important; }
			.dc-canvas { min-height: 0 !important; }
			.dc-canvas svg { width: 100% !important; height: auto !important; }
			.dc-wrap, .dc-canvas, body { background: #fff !important; }
			}
			/* === Toolbar vertical alignment fix (uniform control height) === */
			.dc-toolbar { --ctl-h: 28px; }
			.dc-btn,
			.dc-toolbar select.dc-btn {display: inline-flex; align-items: center; min-height: var(--ctl-h); line-height: 1; vertical-align: middle; padding-top: .28rem; padding-bottom: .28rem;}

			/* Switches use the same height and are truly centered */
			.dc-switch {display: inline-flex; align-items: center; gap: .35rem; height: var(--ctl-h); line-height: 1; margin: 0; vertical-align: middle;}

			.dc-switch-ui {position: relative; width: 34px; height: 18px; border-radius: 999px; background: #e5e7eb; border: 1px solid #d1d5db;}

			/* Center the knob by anchoring to 50% vertically */
			.dc-switch-ui::after {content: ""; position: absolute; left: 2px; top: 50%; width: 14px; height: 14px; border-radius: 999px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.12); transform: translateY(-50%);}

			/* Checked state keeps the same vertical center */
			.dc-switch input:checked + .dc-switch-ui::after {transform: translate(16px, -50%);}

			/* Ensure the right-side row keeps everything aligned */
			.dc-right > * { margin: 0; vertical-align: middle; }

    	`;
		const s = document.createElement('style'); s.id = 'dc-styles'; s.textContent = css; document.head.appendChild(s);
	}

	// utils
	const el = (t, a = {}, ...kids) => { const n = document.createElement(t); for (const k in a) n.setAttribute(k, a[k]); kids.forEach(c => n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)); return n; };
	const svgEl = (t, a = {}) => { const n = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) n.setAttribute(k, a[k]); return n; };
	const toTitleCase = s => window.frappe?.utils?.to_title_case ? window.frappe.utils.to_title_case(s) : String(s || '').replace(/\b\w/g, m => m.toUpperCase());
	const shortLabel = x => ({ healthy: '', caries: 'Caries', filled: 'Filled', missing: 'Missing', crown: 'Crown', implant: 'Implant' })[x] || x;
	const isEmptyObj = (o) => !o || (typeof o === 'object' && !Array.isArray(o) && Object.keys(o).length === 0);

	// shapes (anatomic default)
	const SHAPES = {
		incisor: (w, h) => `M ${.15 * w},0 Q ${.50 * w},${.05 * h} ${.85 * w},0 Q ${.95 * w},${.35 * h} ${.70 * w},${.85 * h} Q ${.50 * w},${.98 * h} ${.30 * w},${.85 * h} Q ${.05 * w},${.35 * h} ${.15 * w},0 Z`,
		canine: (w, h) => `M ${.20 * w},0 Q ${.50 * w},${.08 * h} ${.80 * w},0 Q ${.95 * w},${.40 * h} ${.65 * w},${.92 * h} Q ${.50 * w},${1.00 * h} ${.35 * w},${.92 * h} Q ${.05 * w},${.40 * h} ${.20 * w},0 Z`,
		premolar: (w, h) => `M ${.12 * w},${.05 * h} Q ${.50 * w},0 ${.88 * w},${.05 * h} Q ${.98 * w},${.45 * h} ${.75 * w},${.90 * h} Q ${.50 * w},${1.02 * h} ${.25 * w},${.90 * h} Q ${.02 * w},${.45 * h} ${.12 * w},${.05 * h} Z`,
		molar: (w, h) => `M ${.10 * w},${.10 * h} Q ${.50 * w},${-.02 * h} ${.90 * w},${.10 * h} Q ${1.02 * w},${.52 * h} ${.80 * w},${.92 * h} Q ${.50 * w},${1.08 * h} ${.20 * w},${.92 * h} Q ${-.02 * w},${.52 * h} ${.10 * w},${.10 * h} Z`
	};
	const typeOf = fdi => { const n = Number(fdi) % 10; return (n === 1 || n === 2) ? 'incisor' : (n === 3) ? 'canine' : (n === 4 || n === 5) ? 'premolar' : 'molar'; };

	// FDI permanent dentition
	const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
	const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

	// === PRESET SUPPORT: Tooth sets & numbering labels ===
	const UPPER_PEDO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
	const LOWER_PEDO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];

	const FDI_TO_UNIV = {
		18: 1, 17: 2, 16: 3, 15: 4, 14: 5, 13: 6, 12: 7, 11: 8,
		21: 9, 22: 10, 23: 11, 24: 12, 25: 13, 26: 14, 27: 15, 28: 16,
		38: 17, 37: 18, 36: 19, 35: 20, 34: 21, 33: 22, 32: 23, 31: 24,
		41: 25, 42: 26, 43: 27, 44: 28, 45: 29, 46: 30, 47: 31, 48: 32
	};

	const FDI_TO_UNIV_PEDO = {
		55: 'A', 54: 'B', 53: 'C', 52: 'D', 51: 'E', 61: 'F', 62: 'G', 63: 'H', 64: 'I', 65: 'J',
		75: 'K', 74: 'L', 73: 'M', 72: 'N', 71: 'O', 81: 'P', 82: 'Q', 83: 'R', 84: 'S', 85: 'T'
	};

	function labelForToothFDI(fdi, numbering, isPedo) {
		const sys = String(numbering || 'FDI').toUpperCase();
		if (sys === 'UNIVERSAL') {
			if (isPedo) return FDI_TO_UNIV_PEDO[fdi] || String(fdi);
			return String(FDI_TO_UNIV[fdi] || fdi);
		}
		return String(fdi);
	}

	// catmull–rom + arclength
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
		const t = (dist - s[lo]) / ((s[hi] - s[lo]) || 1);
		const x = poly[lo].x + t * (poly[hi].x - poly[lo].x);
		const y = poly[lo].y + t * (poly[hi].y - poly[lo].y);
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
	// theme utils
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

	const _fallbackDebounce = (fn, ms) => {
		let t = null;
		return function (...args) {
			clearTimeout(t);
			t = setTimeout(() => fn.apply(this, args), ms);
		};
	};
	const debounce = (fn, ms) =>
		(window.frappe?.utils?.debounce ? window.frappe.utils.debounce(fn, ms) : _fallbackDebounce(fn, ms));

	class DentalChart {
		constructor(target, opts = {}) {
			this.root = (typeof target === 'string') ? document.querySelector(target) : target;
			if (!this.root) throw new Error('DentalChart: target not found');
			this.root.classList.add('dc-wrap');

			this.opts = Object.assign({
				width: 920, height: 740,
				toothW: 48, toothH: 60,
				archTightness: 0.92, gapPx: 10,
				autoFit: true, minScale: 0.96,
				useSurfaceToggle: true,
				startSurfaceMode: false,
				theme: 'auto',
				initial: {},
				showQuadrantAxes: true,
				quadrantSpread: 60,
				quadPill: { padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 },
				quadrantLabels: ['Upper Right', 'Upper Left', 'Lower Right', 'Lower Left'],
				quadrantAxisStyle: { stroke: '#9ca3af', width: 1, dash: '4 3', opacity: 0.9 },
				palette: ['caries', 'filled', 'crown', 'implant', 'missing', 'healthy'],

				readOnly: 'auto',
				bindToFrappe: true,
				storeField: 'observation_store',
				autoSave: false,
				saveDebounceMs: 600,

				// NEW: preset & numbering & renderer
				preset: 'anatomic',           // 'anatomic' | 'pedo' | 'restorative' | 'ortho'
				numbering: 'FDI',             // 'FDI' | 'Universal'
				renderer: 'dental',           // 'dental' | 'mask'
				maskId: null,
				maskShapes: null,
				regionLabels: null,

				onChange: null,
			}, opts);

			injectStylesOnce();
			this._ensureTip();

			this._allSurfaces = [];
			this._themeTimer = null;
			this._stateHash = null;
			this._lastPulledJson = null;
			this.state = JSON.parse(JSON.stringify(this.opts.initial || {}));
			this.currentTool = 'healthy';
			this.surfaceMode = !!this.opts.startSurfaceMode;

			// doc/form tracking
			this._docKey = null;
			this._lastPushedJson = null;

			this.setTheme(this.opts.theme);

			// bind helpers
			this._debouncedAutoSave = debounce(() => this.save(), this.opts.saveDebounceMs);

			// readonly init
			this._readOnly = this._initReadonly();
			this._mount();
			// form binding init
			if (this.opts.bindToFrappe) {
				this._loadFromForm();       // prime from current form
				this._startFormAutoSync();  // keep in sync
			}
		}

		// --- PRESET RESOLVER ---
		_presetConfig() {
			const p = String(this.opts.preset || 'anatomic').toLowerCase();

			if (p === 'pedo') {
				return {
					upper: UPPER_PEDO,
					lower: LOWER_PEDO,
					isPedo: true,
					straight: false,
					showSurfaces: true,
				};
			}
			if (p === 'restorative') {
				return {
					upper: UPPER,
					lower: LOWER,
					isPedo: false,
					straight: true,      // straight rows for quick surface entry
					showSurfaces: true,
				};
			}
			if (p === 'ortho') {
				return {
					upper: UPPER,
					lower: LOWER,
					isPedo: false,
					straight: true,      // straight rows
					showSurfaces: false, // simpler UI by default
				};
			}
			// default anatomic
			return {
				upper: UPPER,
				lower: LOWER,
				isPedo: false,
				straight: false,
				showSurfaces: true,
			};
		}

		// public
		getValue() { return this.getState(); }
		getState() { return JSON.parse(JSON.stringify(this.state)); }

		setValue(next) { this.setState(next); }
		setState(next) {
			const clean = (next && typeof next === 'string') ? this._safeParse(next) : next;
			const data = (clean && typeof clean === 'object' && !Array.isArray(clean)) ? clean : {};
			const sig = this._stateSig(data);
			if (sig === this._stateHash) return;  // nothing changed
			this._stateHash = sig;

			this.state = JSON.parse(JSON.stringify(data || {}));
			if (this.svg) { this._redrawStates(); }
			this._emit();
		}

		save() {
			if (!this.opts.bindToFrappe || !window.cur_frm) return;
			try {
				const frm = window.cur_frm;
				const field = this.opts.storeField;
				const valObj = this.getState();
				const ft = this._fieldTypeOf(frm, field);
				const isJSON = String(ft || '').toUpperCase() === 'JSON';
				const toWrite = isJSON ? valObj : JSON.stringify(valObj || {});
				if (this._readOnly) return;

				const curRaw = frm.doc ? frm.doc[field] : undefined;

				let isSame = false;
				if (isJSON) {
					const nextStr = JSON.stringify(valObj || {});
					const curStr = JSON.stringify((typeof curRaw === 'object' ? curRaw : this._safeParse(curRaw)) || {});
					isSame = (nextStr === curStr);
				} else {
					isSame = String(toWrite ?? '') === String(curRaw ?? '');
				}
				if (isSame) return;

				if (typeof frm.set_value === 'function') {
					frm.set_value(field, toWrite);
				} else {
					frm.doc[field] = toWrite;
					if (typeof frm.dirty === 'function') frm.dirty();
				}
				this._lastPushedJson = JSON.stringify(valObj || {});
			} catch (e) { /* no-op */ }
		}

		setTheme(mode) {
			this._themeModeExplicit = mode || 'light';
			if (this._themeModeExplicit === 'auto') this._startThemeAutoSync();
			else { this._stopThemeAutoSync(); this.root.setAttribute('data-theme', this._themeModeExplicit === 'dark' ? 'dark' : 'light'); }
		}
		_getMaskState(maskId) {
			this.state._anatomy = this.state._anatomy || {};
			this.state._anatomy[maskId] = this.state._anatomy[maskId] || {};
			return this.state._anatomy[maskId];
		}
		_setMaskMark(maskId, regionId, toolOrNull) {
			const m = this._getMaskState(maskId);
			if (!toolOrNull) delete m[regionId];
			else m[regionId] = toolOrNull;
		}

		_applyThemeFromSignals() {
			if (this._themeModeExplicit !== 'auto') return;
			const next = autoTheme();
			const cur = this.root.getAttribute('data-theme') || '';
			if (next !== cur) this.root.setAttribute('data-theme', next);
		}
		_startThemeAutoSync() {
			this.root.setAttribute('data-theme', autoTheme());
			const mo = new MutationObserver(() => this._applyThemeFromSignals());
			mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
			if (document.body) mo.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
			this._themeMO = mo;
			this._onStorage = () => this._applyThemeFromSignals();
			window.addEventListener('storage', this._onStorage, false);
			if (window.matchMedia) {
				const mq = window.matchMedia('(prefers-color-scheme: dark)');
				const cb = () => this._applyThemeFromSignals();
				mq.addEventListener ? mq.addEventListener('change', cb) : mq.addListener(cb);
				this._themeMQ = { mq, cb };
			}
		}
		_stopThemeAutoSync() {
			if (this._themeMO) { this._themeMO.disconnect(); this._themeMO = null; }
			if (this._onStorage) { window.removeEventListener('storage', this._onStorage, false); this._onStorage = null; }
			if (this._themeMQ) { const { mq, cb } = this._themeMQ; mq.removeEventListener ? mq.removeEventListener('change', cb) : mq.removeListener(cb); this._themeMQ = null; }
		}

		_emit() {
			if (typeof this.opts.onChange === 'function') {
				try { this.opts.onChange(this.getState()); } catch (e) { /* no-op */ }
			}
			if (this.opts.autoSave && !this._readOnly) {
				this._debouncedAutoSave();
			}
		}
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

			this.setReadOnly(this._readOnly);
			if (this.opts.readOnly === 'auto') this._startReadonlyAutoSync();

			if (!this._ro) { this._ro = new ResizeObserver(() => this._remountIfSizeChanged()); this._ro.observe(this.root); }
		}
		_remountIfSizeChanged() { const w = this.root.clientWidth || 0; if (Math.abs((this._lastW || 0) - w) > 24) { this._lastW = w; this._mount(); } }

		// toolbar
		// toolbar
		_renderToolbar() {
			const bar = el('div', { class: 'dc-toolbar' });
			this._toolButtons = {};

			// --- LEFT: tool palette ----------------------------------------------------
			(this.opts.palette || []).forEach(name => {
				const b = el(
					'button',
					{ class: 'dc-btn tool-' + name, 'data-tool': name, type: 'button' },
					toTitleCase(name)
				);
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

			// --- RIGHT: controls container (one spacer, one row) -----------------------
			const spacer = el('div', { class: 'dc-spacer' });
			bar.appendChild(spacer);

			const right = el('div', { class: 'dc-right' }); // flex row container
			bar.appendChild(right);

			// (1) Surface Marks switch
			const surfId = 'dc-surfaces-' + Math.random().toString(36).slice(2, 8);
			const surfLabel = el('label', { class: 'dc-switch', 'data-role': 'surfaces-toggle', for: surfId });
			const surfInput = el('input', { type: 'checkbox', id: surfId, role: 'switch' });
			const surfUI = el('span', { class: 'dc-switch-ui' });
			surfInput.checked = !!this.surfaceMode;
			surfInput.setAttribute('aria-checked', this.surfaceMode ? 'true' : 'false');
			surfLabel.append(surfInput, surfUI, document.createTextNode('Surface Marks'));
			right.appendChild(surfLabel);

			const syncSurface = () => {
				surfInput.checked = !!this.surfaceMode;
				surfInput.setAttribute('aria-checked', this.surfaceMode ? 'true' : 'false');
				this._syncSurfaceToolDisables();
			};
			surfInput.addEventListener('change', () => {
				this.surfaceMode = !!surfInput.checked;

				if (this.surfaceMode) {
					if (this.currentTool === 'healthy' || this.currentTool === 'missing') {
						this.currentTool = null;
						bar.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
					}
				} else {
					if (!this.currentTool) {
						this.currentTool = 'healthy';
						const hb = this._toolButtons?.healthy;
						if (hb) hb.classList.add('active');
					}
				}

				this._applySurfaceInteractivity();
				syncSurface();
			});

			// (2) Preset select
			const presetSel = el('select', { class: 'dc-btn', 'data-role': 'preset', title: 'Chart Preset' });
			['anatomic', 'pedo', 'restorative', 'ortho'].forEach(p => {
				const opt = el('option', { value: p }, p[0].toUpperCase() + p.slice(1));
				if (String(this.opts.preset || 'anatomic').toLowerCase() === p) opt.selected = true;
				presetSel.appendChild(opt);
			});
			presetSel.addEventListener('change', () => this.setPreset(presetSel.value));
			right.appendChild(presetSel);

			// (3) Numbering select
			const numberingSel = el('select', { class: 'dc-btn', 'data-role': 'numbering', title: 'Numbering System' });
			['FDI', 'Universal'].forEach(n => {
				const opt = el('option', { value: n }, n);
				if (String(this.opts.numbering || 'FDI').toUpperCase() === n.toUpperCase()) opt.selected = true;
				numberingSel.appendChild(opt);
			});
			numberingSel.addEventListener('change', () => this.setNumbering(numberingSel.value));
			right.appendChild(numberingSel);

			// (4) Perio switch (true toggle, same UI as Surface Marks)
			const perioId = 'dc-perio-' + Math.random().toString(36).slice(2, 8);
			const perioLabel = el('label', { class: 'dc-switch', 'data-role': 'perio-toggle', for: perioId });
			const perioInput = el('input', { type: 'checkbox', id: perioId, role: 'switch' });
			const perioUI = el('span', { class: 'dc-switch-ui' });
			perioLabel.append(perioInput, perioUI, document.createTextNode('Perio'));

			const hasMask = Array.isArray(this.opts.maskShapes) && this.opts.maskShapes.length > 0;
			const isMask = String(this.opts.renderer || 'dental').toLowerCase() === 'mask';

			perioInput.checked = !!isMask;
			perioInput.setAttribute('aria-checked', isMask ? 'true' : 'false');
			perioInput.disabled = !hasMask;
			if (!hasMask) { perioLabel.style.opacity = '.6'; perioLabel.style.pointerEvents = 'none'; }

			perioInput.addEventListener('change', () => {
				if (!hasMask) {
					if (window.frappe?.msgprint) window.frappe.msgprint(__('Perio view isn’t configured yet.'));
					perioInput.checked = false;
					perioInput.setAttribute('aria-checked', 'false');
					return;
				}
				const wantMask = !!perioInput.checked;
				if (wantMask) this.setRenderer('mask', { maskId: this.opts.maskId || 'perio' });
				else this.setRenderer('dental');
				perioInput.setAttribute('aria-checked', wantMask ? 'true' : 'false');
			});
			right.appendChild(perioLabel);

			// Read-only mode handling
			if (this._readOnly) {
				// Hide both switches entirely (consistent with your previous RO behavior)
				surfLabel.style.display = 'none';
				perioLabel.style.display = 'none';
				// Keep selects visible but disabled (optional)
				presetSel.disabled = true;
				numberingSel.disabled = true;
			}

			// initial sync
			this._syncSurfaceToolDisables();
			return bar;
		}

		_syncSurfaceToolDisables() {
			if (!this._toolButtons || typeof this._toolButtons !== 'object') return;
			if (this._readOnly) {
				Object.values(this._toolButtons || {}).forEach(b => {
					if (!b) return;
					b.disabled = true;
					b.setAttribute('aria-disabled', 'true');
					b.classList.add('legend-disabled');
					b.classList.remove('disabled');
				});
				return;
			}
			Object.values(this._toolButtons || {}).forEach(b => {
				if (!b) return;
				b.classList.remove('legend-disabled');
				b.removeAttribute('aria-disabled');
				if (!['healthy', 'missing'].includes(b.getAttribute('data-tool'))) {
					b.disabled = false;
					b.classList.remove('disabled');
				}
			});
			const dis = !!this.surfaceMode;
			['healthy', 'missing'].forEach(name => {
				const btn = this._toolButtons[name]; if (!btn) return;
				btn.disabled = dis;
				btn.setAttribute('aria-disabled', dis ? 'true' : 'false');
				btn.classList.toggle('disabled', dis);
			});
			Object.entries(this._toolButtons || {}).forEach(([name, btn]) => {
				btn.classList.toggle('active', !!this.currentTool && this.currentTool === name);
			});
		}

		_renderSVG() {
			const containerW = this.root.clientWidth || 0;
			const W = Math.max(720, containerW || this.opts.width || 920);
			const H = this.opts.height || 740;

			// Mask renderer path (basic)
			if (String(this.opts.renderer).toLowerCase() === 'mask') {
				return this._renderMaskSVG(W, H);
			}

			const cfg = this._presetConfig();
			const UPPER_SET = cfg.upper;
			const LOWER_SET = cfg.lower;
			const straight = !!cfg.straight;

			const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });
			const cx = W / 2;

			let upperCtrl, lowerCtrl;
			if (!straight) {
				const k = this.opts.archTightness || 1;
				upperCtrl = [
					{ x: cx - W * (.36 * k), y: H * .39 },
					{ x: cx - W * (.18 * k), y: H * .30 },
					{ x: cx, y: H * .27 },
					{ x: cx + W * (.18 * k), y: H * .30 },
					{ x: cx + W * (.36 * k), y: H * .39 }
				];
				lowerCtrl = [
					{ x: cx - W * (.36 * k), y: H * .71 },
					{ x: cx - W * (.18 * k), y: H * .80 },
					{ x: cx, y: H * .83 },
					{ x: cx + W * (.18 * k), y: H * .80 },
					{ x: cx + W * (.36 * k), y: H * .71 }
				];
			} else {
				const yU = H * 0.35, yL = H * 0.75, span = W * 0.76;
				upperCtrl = [{ x: cx - span / 2, y: yU }, { x: cx - span / 4, y: yU }, { x: cx, y: yU }, { x: cx + span / 4, y: yU }, { x: cx + span / 2, y: yU }];
				lowerCtrl = [{ x: cx - span / 2, y: yL }, { x: cx - span / 4, y: yL }, { x: cx, y: yL }, { x: cx + span / 4, y: yL }, { x: cx + span / 2, y: yL }];
			}

			const totalWidthPx = this.opts.toothW * 15.2;
			const up = archPositionsWeighted(UPPER_SET, upperCtrl, totalWidthPx, this.opts.gapPx);
			const lo = archPositionsWeighted(LOWER_SET, lowerCtrl, totalWidthPx, this.opts.gapPx);
			const fit = Math.min(up.layoutScale, lo.layoutScale);
			this._drawScale = this.opts.autoFit ? Math.max(this.opts.minScale, fit) : 1;

			this._allSurfaces.length = 0;

			const gU = svgEl('g'), gL = svgEl('g'); svg.append(gU, gL);
			UPPER_SET.forEach((n, i) => { const p = up.positions[i]; gU.append(this._makeTooth(n, p.x, p.y, p.rot, true)); });
			LOWER_SET.forEach((n, i) => { const p = lo.positions[i]; gL.append(this._makeTooth(n, p.x, p.y, p.rot, false)); });

			if (this.opts.showQuadrantAxes) this._renderQuadrantAxes(svg, W, H, upperCtrl, lowerCtrl);
			if (this._showQuadrantPills()) this._renderQuadrants(svg, upperCtrl, lowerCtrl);

			this.svg = svg;

			// delegated surface click
			this._onSvgClick && this.svg.removeEventListener('click', this._onSvgClick, false);
			this._onSvgClick = (e) => {
				if (!this.surfaceMode || this._readOnly) return;
				const t = e.target;
				if (!(t instanceof SVGElement) || !t.classList.contains('surf')) return;

				if (!this.currentTool || this.currentTool === 'healthy' || this.currentTool === 'missing') return;

				const toothG = t.closest('g.tooth'); if (!toothG) return;
				const fdi = +toothG.getAttribute('data-tooth');
				const surfKey = t.dataset?.surfKey || t.dataset?.surfkey || t.getAttribute('data-surf-key') || t.getAttribute('data-surfkey');
				if (!surfKey) return;

				this._applyTool(fdi, String(surfKey).toUpperCase());
				e.stopPropagation();
			};
			this.svg.addEventListener('click', this._onSvgClick, false);

			return el('div', { class: 'dc-canvas', style: `min-height:${H}px` }, svg);
		}

		_renderMaskSVG(W, H) {
			const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });
			this._allSurfaces.length = 0;

			const shapes = Array.isArray(this.opts.maskShapes) ? this.opts.maskShapes : [];
			const maskId = this.opts.maskId || 'perio';
			const labels = this.opts.regionLabels || {};

			const g = svgEl('g'); svg.appendChild(g);

			shapes.forEach(r => {
				let elr = null;
				if (r.d) {
					elr = svgEl('path', { class: 'surf', d: r.d });
				} else if (r.points) {
					elr = svgEl('polygon', { class: 'surf', points: r.points });
				} else if (r.rect) {
					const { x, y, width, height, rx = 4, ry = 4 } = r.rect;
					elr = svgEl('rect', { class: 'surf', x, y, width, height, rx, ry });
				}
				if (!elr) return;

				elr.dataset.surfKey = String(r.id);
				elr.setAttribute('data-surf-key', String(r.id));
				elr.setAttribute('data-surfkey', String(r.id));
				elr.dataset.rx = '4';
				g.appendChild(elr);
				this._allSurfaces.push(elr);

				// optional region label
				if (labels[r.id]) {
					const bb = { x: 0, y: 0, w: 0, h: 0 };
					try {
						const b = elr.getBBox();
						bb.x = b.x + b.width / 2;
						bb.y = b.y + b.height / 2;
					} catch { }
					const tx = svgEl('text', { x: bb.x, y: bb.y, 'text-anchor': 'middle', 'font-size': '10px', fill: '#6b7280' });
					tx.textContent = labels[r.id];
					g.appendChild(tx);
				}
			});

			// click handler for mask mode
			this._onSvgClick && this.svg?.removeEventListener('click', this._onSvgClick, false);
			this._onSvgClick = (e) => {
				if (this._readOnly) return;
				const t = e.target;
				if (!(t instanceof SVGElement) || !t.classList.contains('surf')) return;

				// In mask mode, use non-healthy/missing tools as region marks; if no tool, toggle off
				const tool = this.currentTool && !['healthy', 'missing'].includes(this.currentTool) ? this.currentTool : null;
				const regionId = t.dataset?.surfKey || t.getAttribute('data-surf-key');
				const id = String(regionId || '');

				if (!id) return;

				// toggle: if already marked with same tool, clear; else set
				const m = this._getMaskState(maskId);
				const cur = m[id] || null;
				const next = (cur === tool) ? null : tool;

				this._setMaskMark(maskId, id, next);

				// visual
				if (next) {
					t.setAttribute('data-marked', '1');
					t.style.fill = this._surfaceTint(next);
					t.style.fillOpacity = '0.85';
					t.style.stroke = this._surfaceStroke(next);
					t.style.strokeWidth = '1.6';
					t.style.strokeOpacity = '0.9';
				} else {
					t.removeAttribute('data-marked');
					t.style.cssText = '';
				}

				this._emit();
				e.stopPropagation();
			};
			svg.addEventListener('click', this._onSvgClick, false);

			this.svg = svg;
			return el('div', { class: 'dc-canvas', style: `min-height:${H}px` }, svg);
		}

		_renderQuadrants(svg, upperCtrl, lowerCtrl) {
			const labels = this.opts.quadrantLabels || ['UR', 'UL', 'LL', 'LR'];
			const spread = Number(this.opts.quadrantSpread || 0);
			const pillCfg = Object.assign({ padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 }, this.opts.quadPill || {});

			const u0 = upperCtrl[0], u1 = upperCtrl[upperCtrl.length - 1];
			const l0 = lowerCtrl[0], l1 = lowerCtrl[lowerCtrl.length - 1];

			const makePill = (x, y, text, anchor = 'middle') => {
				const w = Math.max(pillCfg.minW, pillCfg.padX * 2 + text.length * 7.2);
				const h = Math.max(pillCfg.minH, pillCfg.padY * 2 + 12);
				const g = svgEl('g', { transform: `translate(${x},${y})` });
				const bg = svgEl('rect', { class: 'quad-bg', x: -w / 2, y: -h / 2, width: w, height: h, rx: pillCfg.radius, ry: pillCfg.radius });
				const tx = svgEl('text', { class: 'quad-pill', 'text-anchor': anchor, x: 0, y: 4 });
				tx.textContent = text;
				g.append(bg, tx);
				svg.appendChild(g);
			};

			const urX = u0.x - spread; const urY = u0.y - spread;
			const ulX = u1.x + spread; const ulY = u1.y - spread;
			const llX = l0.x - spread; const llY = l0.y + spread;
			const lrX = l1.x + spread; const lrY = l1.y + spread;

			makePill(urX, urY, labels[0]);
			makePill(ulX, ulY, labels[1]);
			makePill(llX, llY, labels[2]);
			makePill(lrX, lrY, labels[3]);
		}

		_showQuadrantPills() {
			if (this.opts.showQuadrants === false) return false;
			if (this.opts.showQuadrantLabels === false) return false;
			return true;
		}

		_renderQuadrantAxes(svg, W, H, upperCtrl, lowerCtrl) {
			const st = Object.assign({ stroke: '#9ca3af', width: 1, dash: '4 3', opacity: 0.9 }, this.opts.quadrantAxisStyle || {});
			const cx = W / 2;

			const v = svgEl('line', { x1: cx, x2: cx, y1: H * 0.18, y2: H * 0.92, class: 'quad-axis' });
			const hy = (upperCtrl[0].y + lowerCtrl[0].y) / 2;
			const h = svgEl('line', { x1: W * 0.06, x2: W * 0.94, y1: hy, y2: hy, class: 'quad-axis' });

			[v, h].forEach(line => {
				if (st.stroke) line.setAttribute('stroke', st.stroke);
				if (st.width != null) line.setAttribute('stroke-width', String(st.width));
				if (st.dash) line.setAttribute('stroke-dasharray', st.dash);
				if (st.opacity != null) line.setAttribute('opacity', String(st.opacity));
			});

			svg.insertBefore(v, svg.firstChild);
			svg.insertBefore(h, svg.firstChild);
		}

		_applySurfaceInteractivity() {
			const on = !!this.surfaceMode && !this._readOnly && String(this.opts.renderer).toLowerCase() !== 'mask';
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

			const cfg = this._presetConfig();
			const rotation = isUpper ? rotDeg : rotDeg + 180;
			g.setAttribute('transform', `translate(${x - w / 2},${y - h / 2}) rotate(${rotation},${w / 2},${h / 2})`);

			const ly = isUpper ? (-4) : (h + 12);
			const label = svgEl('text', { x: w / 2, y: ly, 'text-anchor': 'middle', 'font-size': '10px', fill: '#6b7280' });
			label.textContent = labelForToothFDI(+fdi, this.opts.numbering, cfg.isPedo);

			const chipG = svgEl('g', { class: 'chip', transform: `translate(4,12)` });
			const chipBg = svgEl('rect', { class: 'chip-bg', width: 32, height: 12 });
			const chipTx = svgEl('text', { x: 3, y: 9, 'font-size': '9px' }, ''); chipG.append(chipBg, chipTx);

			g.append(body, bodyHit);
			hits.forEach(p => g.appendChild(p));
			g.append(label, chipG);

			hits.forEach(r => this._allSurfaces.push(r));

			const tip = document.getElementById('dc-tip');

			g.addEventListener('pointerover', (e) => {
				if (!this.surfaceMode) return;
				const n = e.target;
				if (n.classList?.contains('surf') && n.getAttribute('data-marked') !== '1') {
					n.classList.add('hover');
					n.style.removeProperty('fill-opacity');
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

			bodyHit.addEventListener('click', () => {
				if (this._readOnly) return;
				this._applyTool(fdi, null);
			});

			g._chip = chipG; g._chipText = chipTx; g._chipBg = chipBg; g._rect = body; g._cells = [...hits];
			return g;
		}

		_makeSurfaceHits(w, h) {
			const pad = Math.max(2, Math.round(Math.min(w, h) * 0.06));
			const r = Math.max(3, Math.round(Math.min(w, h) * 0.10));
			const arr = [];
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));                   // B
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: h - (h * .28) - pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));   // L
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r }));           // M
			arr.push(svgEl('rect', { class: 'surf', x: w - (w * .28) - pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r })); // D
			arr.push(svgEl('rect', { class: 'surf center', x: w * .30, y: h * .30, width: w * .40, height: h * .40, rx: r, ry: r }));        // O
			const keys = ['B', 'L', 'M', 'D', 'O'];
			arr.forEach((n, i) => { const v = keys[i]; n.dataset.surfKey = v; n.setAttribute('data-surf-key', v); n.setAttribute('data-surfkey', v); n.dataset.rx = String(r); });
			return arr;
		}

		_tooltipFor(e, fdi) {
			const sk = (e.target && e.target.classList?.contains('surf')) ? (e.target.dataset.surfKey || '') : '';
			const name = sk ? ({ M: 'Mesial', D: 'Distal', B: 'Buccal/Labial', L: 'Lingual/Palatal', O: 'Occlusal/Incisal' })[sk] : null;
			const t = this.state[String(fdi)], st = t?.state || 'healthy';
			return name ? `${fdi} • ${name} • ${toTitleCase(st)}` : `${fdi} • ${toTitleCase(st)}`;
		}

		_applyTool(fdi, surface) {
			const key = String(fdi);
			const T = this.state[key] || { state: 'healthy', surfaces: {} };
			if (surface) {
				if (T.surfaces[surface] === this.currentTool) delete T.surfaces[surface];
				else T.surfaces[surface] = this.currentTool;
			} else {
				T.state = this.currentTool;
			}
			this.state[key] = T;
			this._redrawTooth(fdi);
			this._stateHash = this._stateSig(this.state);
			this._emit();
		}

		_stateSig(obj) {
			try { return JSON.stringify(obj || {}); } catch { return ''; }
		}

		_redrawStates() {
			if (!this.svg) return;
			if (String(this.opts.renderer).toLowerCase() === 'mask') return; // mask regions updated on click
			this.svg.querySelectorAll('g.tooth').forEach(g => this._redrawTooth(+g.dataset.tooth));
		}
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

		_surfaceTint(tool) {
			switch (tool) {
				case 'caries': return '#ffe4e6';
				case 'filled': return '#dcfce7';
				case 'crown': return '#ffedd5';
				case 'implant': return '#dbeafe';
				case 'missing': return '#e5e7eb';
				default: return '#e5e7eb';
			}
		}
		_surfaceStroke(tool) {
			switch (tool) {
				case 'caries': return '#fb7185';
				case 'filled': return '#34d399';
				case 'crown': return '#f59e0b';
				case 'implant': return '#60a5fa';
				case 'missing': return '#9ca3af';
				default: return '#9ca3af';
			}
		}

		// ===== Read-only handling for submitted docs =====
		_initReadonly() {
			if (this.opts.readOnly === 'auto') {
				return this._computeReadonlyFromEnv();
			}
			return !!this.opts.readOnly;
		}

		_computeReadonlyFromEnv() {
			// Prefer cur_frm.doc.docstatus if available
			const ds = window.cur_frm?.doc?.docstatus;
			if (typeof ds === 'number') return ds === 1;

			// Fallback: walk up DOM looking for data-docstatus="1"
			let p = this.root;
			while (p) {
				const v = p.getAttribute?.('data-docstatus');
				if (v != null && v !== '') return Number(v) === 1;
				p = p.parentElement;
			}
			return false;
		}

		_startReadonlyAutoSync() {
			if (this._roTimer) clearInterval(this._roTimer);
			this._roTimer = setInterval(() => {
				const next = this._computeReadonlyFromEnv();
				if (next !== this._readOnly) this.setReadOnly(next);
			}, 900);
		}

		setReadOnly(flag) {
			const next = !!flag;
			this._readOnly = next;

			this.root.classList.toggle('dc-edit', !next);

			// Hide surfaces toggle in RO
			const surfToggle = this.root.querySelector('[data-role="surfaces-toggle"]');
			if (surfToggle) surfToggle.style.display = next ? 'none' : '';

			// Disable tool buttons
			if (this._toolButtons) {
				Object.values(this._toolButtons).forEach(btn => {
					if (!btn) return;
					btn.disabled = next;
					btn.setAttribute('aria-disabled', next ? 'true' : 'false');
					btn.classList.toggle('legend-disabled', next);
					if (!next) btn.classList.remove('legend-disabled');
				});
			}

			// Disable canvas hit testing
			const cnv = this.root.querySelector('.dc-canvas');
			if (cnv) cnv.classList.toggle('dc-readonly', next);

			this._applySurfaceInteractivity();
			this._syncSurfaceToolDisables();
		}

		// ===== Binding to Frappe form (load/save/sync) =====
		_safeParse(x) {
			if (!x) return {};
			if (typeof x === 'object') return x;
			try {
				const v = JSON.parse(x);
				return (v && typeof v === 'object') ? v : {};
			} catch { return {}; }
		}

		_fieldTypeOf(frm, fieldname) {
			try {
				const df = frm.get_docfield ? frm.get_docfield(fieldname, frm.doc.name) : null;
				return df ? df.fieldtype : null;
			} catch { return null; }
		}

		_curDocKey() {
			const f = window.cur_frm;
			if (!f || !f.doctype || !f.doc?.name) return null;
			return `${f.doctype}:${f.doc.name}`;
		}

		_readStoreFromForm() {
			const f = window.cur_frm, field = this.opts.storeField;
			if (!f) return {};
			const raw = f.doc ? f.doc[field] : {};
			return this._safeParse(raw);
		}

		_loadFromForm() {
			if (!this.opts.bindToFrappe || !window.cur_frm) return;

			const key = this._curDocKey();
			if (!key) return;

			const store = this._readStoreFromForm();
			const storeJson = JSON.stringify(store || {});

			// Document switch
			if (key !== this._docKey) {
				this._docKey = key;
				if (isEmptyObj(store)) this.setState({});
				else this.setState(store);
				this._lastPulledJson = storeJson; // track adopted snapshot
				if (this.opts.readOnly === 'auto') this.setReadOnly(this._computeReadonlyFromEnv());
				return;
			}

			// Same doc: adopt external changes unless it's our own last push
			if (!isEmptyObj(store)) {
				if (storeJson !== this._lastPulledJson && storeJson !== this._lastPushedJson) {
					this.setState(store);
					this._lastPulledJson = storeJson;
				}
			}
		}

		_startFormAutoSync() {
			if (this._formTimer) clearInterval(this._formTimer);
			this._formTimer = setInterval(() => this._loadFromForm(), 800);
		}

		// ===== Public methods for UI switches (preset/numbering/renderer) =====
		setPreset(preset) {
			const p = String(preset || 'anatomic').toLowerCase();
			if (!['anatomic', 'pedo', 'restorative', 'ortho'].includes(p)) return;
			this.opts.preset = p;
			this._mount(); // re-render with new tooth set/layout
			this._redrawStates();
		}

		setNumbering(system) {
			const s = String(system || 'FDI').toUpperCase();
			this.opts.numbering = (s === 'UNIVERSAL') ? 'Universal' : 'FDI';
			this._mount();       // remount to refresh labels
			this._redrawStates();
		}

		setRenderer(mode, { maskId, maskShapes, regionLabels } = {}) {
			const m = String(mode || 'dental').toLowerCase();
			if (!['dental', 'mask'].includes(m)) return;

			if (m === 'mask') {
				const shapes = maskShapes ?? this.opts.maskShapes;
				if (!shapes || !Array.isArray(shapes) || shapes.length === 0) {
					if (window.frappe?.msgprint) window.frappe.msgprint(__('Perio view isn’t configured yet (no regions).'));
					return;
				}
			}

			this.opts.renderer = m;
			if (maskId !== undefined) this.opts.maskId = maskId;
			if (maskShapes !== undefined) this.opts.maskShapes = maskShapes;
			if (regionLabels !== undefined) this.opts.regionLabels = regionLabels;

			this._mount();
			this._redrawStates();
		}
	}

	// --- Export global ---
	window.DentalChart = DentalChart;
})();
