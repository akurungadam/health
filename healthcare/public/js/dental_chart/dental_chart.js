(function () {
	function injectStylesOnce() {
		if (document.getElementById('dc-styles')) return;
		const css = `
			.dc-wrap{font-family:ui-sans-serif,system-ui,Roboto,Arial;user-select:none;color:#111827;display:flex;flex-direction:column}
			.dc-toolbar{display:flex;flex-direction:column;gap:.4rem;align-items:center}
			.dc-row{display:flex;gap:.4rem;align-items:center;justify-content:center;flex-wrap:wrap}
			.dc-row.dc-palette{margin-top:.15rem}

			/* normalize heights for the controls row */
			.dc-row.dc-controls{ align-items:center; min-height:28px; }
			.dc-row.dc-controls > *{
				display:inline-flex; align-items:center;
				height:28px; line-height:28px;
			}

			/* buttons & selects */
			.dc-btn{border:1px solid #e5e7eb;padding:.28rem .55rem;border-radius:999px;background:#fff;cursor:pointer;font-size:.78rem;line-height:1.2;box-shadow:0 1px 0 rgba(0,0,0,.03);color:#111827;vertical-align:middle}
			.dc-btn:hover{background:#f9fafb}
			.dc-btn.active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.25)}
			.dc-btn:disabled,.dc-btn.disabled{opacity:.55;box-shadow:none;cursor:not-allowed}
			.dc-toolbar select.dc-btn{min-width:auto;max-width:140px;padding-right:1rem;appearance:none}
			.dc-row.dc-controls .dc-btn,
			.dc-row.dc-controls select.dc-btn{
				height:28px; line-height:28px; padding-top:0; padding-bottom:0; display:inline-flex; align-items:center;
			}

			/* edit mode stronger base buttons (skip palette) */
			.dc-wrap.dc-edit .dc-row.dc-controls .dc-btn{background:#f3f4f6;border-color:#cbd5e1;box-shadow:0 1px 0 rgba(0,0,0,.04)}
			.dc-wrap.dc-edit .dc-row.dc-controls .dc-btn:hover{background:#e5e7eb}
			.dc-wrap.dc-edit .dc-row.dc-controls .dc-btn.active{border-color:#4f46e5;box-shadow:0 0 0 2px rgba(79,70,229,.25)}

			/* switches (label + pill + text) */
			.dc-switch{
				display:inline-flex; align-items:center; gap:.45rem; cursor:pointer;
				font-size:.78rem; white-space:nowrap; height:28px; line-height:28px;
				vertical-align:middle;
			}
			.dc-switch input{display:none}
			.dc-switch-ui{
				position:relative; width:34px; height:18px;
				border-radius:999px; background:#e5e7eb; border:1px solid #d1d5db; transition:all .18s ease;
				align-self:center; margin:0;
			}
			.dc-switch-ui::after{
				content:""; position:absolute; left:2px; top:50%;
				width:14px; height:14px; border-radius:999px; background:#fff;
				box-shadow:0 1px 2px rgba(0,0,0,.12);
				transform:translateY(-50%); transition:transform .18s ease;
			}
			.dc-switch input:checked + .dc-switch-ui{background:#6366f1;border-color:#6366f1}
			.dc-switch input:checked + .dc-switch-ui::after{transform:translate(16px,-50%)}

			/* optional: make the label text participate as a flex item (even when it's a text node) */
			.dc-switch{ line-height:0; }
			.dc-switch .dc-switch-text{ display:inline-flex; align-items:center; height:28px; line-height:28px; }
			.dc-switch .dc-switch-text::before{ content:attr(data-text); line-height:28px; }

			/* canvas */
			.dc-canvas{width:100%;min-height:740px;position:relative;margin-top:.5rem}
			.dc-canvas svg{width:100%;height:100%;display:block;touch-action:none}

			/* readonly */
			.dc-canvas.dc-readonly{pointer-events:none;cursor:default}
			.dc-btn.legend-disabled{opacity:.6;pointer-events:none;filter:grayscale(12%)}

			/* tooth base */
			.tooth-rect{fill:#fff;stroke:#64748b;stroke-width:1}
			.tooth .tooth-rect{filter:drop-shadow(0 .5px .5px rgba(0,0,0,.08))}
			.tooth.selected .tooth-rect{stroke:#6366f1;stroke-width:2}

			/* surfaces */
			.surf{cursor:pointer;fill-opacity:.001;stroke-linejoin:round}
			.surf.hover:not([data-marked="1"]){fill:#94a3b8;fill-opacity:.18;stroke:#6366f1;stroke-width:1.4;stroke-opacity:.9}
			.body-hit{cursor:pointer;fill:#000;fill-opacity:.001;stroke:transparent;pointer-events:all}
			.dc-hint{font-size:.75rem;padding:.15rem .45rem;border:1px dashed #cbd5e1;border-radius:999px;color:#6b7280;background:#f8fafc}
			.dc-wrap[data-theme="dark"] .dc-hint{border-color:#334155;color:#9ca3af;background:#0b1220}

			/* quadrants */
			.quad-axis{stroke:#9ca3af;stroke-width:1;stroke-dasharray:4 3;opacity:.9}
			.quad-pill{font-size:.78rem;fill:#374151}
			.quad-bg{fill:#e5e7eb;rx:10;ry:10}

			/* tooth states */
			.state-healthy .tooth-rect{fill:#f8fafc}
			.state-caries .tooth-rect{fill:#fee2e2;stroke:#ef4444}
			.state-missing .tooth-rect{fill:#f3f4f6;stroke:#9ca3af;stroke-dasharray:3 2}
			.state-crown .tooth-rect{fill:#fff7ed;stroke:#f59e0b}
			.state-implant .tooth-rect{fill:#eff6ff;stroke:#3b82f6}

			/* chip */
			.chip{pointer-events:none;font-size:10px;fill:#111827;display:none}
			.chip-bg{fill:#e5e7eb;rx:3;ry:3}

			/* tooltip */
			.dc-tip{position:fixed;pointer-events:none;background:#111827;color:#fff;font-size:12px;padding:.2rem .4rem;border-radius:.35rem;transform:translate(-50%,calc(-100% - 8px));display:none;z-index:9999}
			.dc-tip::after{content:"";position:absolute;left:50%;top:100%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#111827}

			/* palette tints (restorative only) */
			.dc-wrap .dc-btn[data-tool].tool-healthy{ background:#f8fafc; border-color:#e5e7eb }
			.dc-wrap .dc-btn[data-tool].tool-caries{  background:#fff5f5; border-color:#ffe4e6 }
			.dc-wrap .dc-btn[data-tool].tool-filled{  background:#f0fdf4; border-color:#dcfce7 }
			.dc-wrap .dc-btn[data-tool].tool-missing{ background:#f3f4f6; border-color:#e5e7eb }
			.dc-wrap .dc-btn[data-tool].tool-crown{   background:#fff7ed; border-color:#ffedd5 }
			.dc-wrap .dc-btn[data-tool].tool-implant{ background:#eff6ff; border-color:#dbeafe }

			/* dark theme tweaks */
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
			.dc-wrap[data-theme="dark"] .quad-axis{stroke:#64748b;opacity:.85}
			.dc-wrap .dc-btn[data-tool].active{border-color:#4f46e5;box-shadow:0 0 0 2px rgba(79,70,229,.25);}

			/* print */
			@media print{
				.dc-toolbar,.dc-tip{display:none!important}
				.dc-wrap,.dc-canvas,body{background:#fff!important;color:#000!important}
				.dc-canvas{min-height:0!important}
				.dc-canvas svg{width:100%!important;height:auto!important}
			}
			.dc-row.dc-controls [data-role="surfaces-toggle"]{
				display: inline-flex;
				align-items: center;
				gap: .35rem;
				height: 28px;
				line-height: 28px;
				transform: translateY(3px);   /* tweak 3px, vertical-align doesn't work */
			}
			.dc-row.dc-controls [data-role="surfaces-toggle"] .dc-switch-ui{
				position: static !important;  /* or: position:relative; top:0 */
			}
		`;

		const s = document.createElement('style');
		s.id = 'dc-styles';
		s.textContent = css;
		document.head.appendChild(s);
	}

	/* =======================  UTILS  ======================= */
	const el = (t, a = {}, ...kids) => { const n = document.createElement(t); for (const k in a) n.setAttribute(k, a[k]); kids.forEach(c => n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)); return n; };
	const svgEl = (t, a = {}) => { const n = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) n.setAttribute(k, a[k]); return n; };
	const toTitleCase = s => window.frappe?.utils?.to_title_case ? window.frappe.utils.to_title_case(s) : String(s || '').replace(/\b\w/g, m => m.toUpperCase());
	const shortLabel = x => ({ healthy: '', caries: 'Caries', filled: 'Filled', missing: 'Missing', crown: 'Crown', implant: 'Implant' })[x] || x;
	const isEmptyObj = (o) => !o || (typeof o === 'object' && !Array.isArray(o) && Object.keys(o).length === 0);

	/* =======================  CONSTANTS  ======================= */
	const SHAPES = {
		incisor: (w, h) => `M ${.15 * w},0 Q ${.50 * w},${.05 * h} ${.85 * w},0 Q ${.95 * w},${.35 * h} ${.70 * w},${.85 * h} Q ${.50 * w},${.98 * h} ${.30 * w},${.85 * h} Q ${.05 * w},${.35 * h} ${.15 * w},0 Z`,
		canine: (w, h) => `M ${.20 * w},0 Q ${.50 * w},${.08 * h} ${.80 * w},0 Q ${.95 * w},${.40 * h} ${.65 * w},${.92 * h} Q ${.50 * w},${1.00 * h} ${.35 * w},${.92 * h} Q ${.05 * w},${.40 * h} ${.20 * w},0 Z`,
		premolar: (w, h) => `M ${.12 * w},${.05 * h} Q ${.50 * w},0 ${.88 * w},${.05 * h} Q ${.98 * w},${.45 * h} ${.75 * w},${.90 * h} Q ${.50 * w},${1.02 * h} ${.25 * w},${.90 * h} Q ${.02 * w},${.45 * h} ${.12 * w},${.05 * h} Z`,
		molar: (w, h) => `M ${.10 * w},${.10 * h} Q ${.50 * w},${-.02 * h} ${.90 * w},${.10 * h} Q ${1.02 * w},${.52 * h} ${.80 * w},${.92 * h} Q ${.50 * w},${1.08 * h} ${.20 * w},${.92 * h} Q ${-.02 * w},${.52 * h} ${.10 * w},${.10 * h} Z`
	};
	const typeOf = fdi => { const n = Number(fdi) % 10; return (n === 1 || n === 2) ? 'incisor' : (n === 3) ? 'canine' : (n === 4 || n === 5) ? 'premolar' : 'molar'; };

	const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
	const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
	const UPPER_PEDO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
	const LOWER_PEDO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];

	const FDI_TO_UNIV = {
		18: 1, 17: 2, 16: 3, 15: 4, 14: 5, 13: 6, 12: 7, 11: 8, 21: 9, 22: 10, 23: 11, 24: 12, 25: 13, 26: 14, 27: 15, 28: 16,
		38: 17, 37: 18, 36: 19, 35: 20, 34: 21, 33: 22, 32: 23, 31: 24, 41: 25, 42: 26, 43: 27, 44: 28, 45: 29, 46: 30, 47: 31, 48: 32
	};
	const FDI_TO_UNIV_PEDO = { 55: 'A', 54: 'B', 53: 'C', 52: 'D', 51: 'E', 61: 'F', 62: 'G', 63: 'H', 64: 'I', 65: 'J', 75: 'K', 74: 'L', 73: 'M', 72: 'N', 71: 'O', 81: 'P', 82: 'Q', 83: 'R', 84: 'S', 85: 'T' };

	function labelForToothFDI(fdi, numbering, isPedo) {
		const sys = String(numbering || 'FDI').toUpperCase();
		if (sys === 'UNIVERSAL') return isPedo ? (FDI_TO_UNIV_PEDO[fdi] || String(fdi)) : String(FDI_TO_UNIV[fdi] || fdi);
		return String(fdi);
	}

	/* =======================  GEOM UTILS  ======================= */
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
	function arcTable(poly) { const s = [0]; for (let i = 1; i < poly.length; i++) { const dx = poly[i].x - poly[i - 1].x, dy = poly[i].y - poly[i - 1].y; s.push(s[i - 1] + Math.hypot(dx, dy)) } return { poly, s, L: s[s.length - 1] } }
	function pointAtArclen(tab, dist) {
		const { poly, s, L } = tab; if (dist <= 0) return { ...poly[0], ang: 0 };
		if (dist >= L) { const n = poly.length - 1, dx = poly[n].x - poly[n - 1].x, dy = poly[n].y - poly[n - 1].y; return { ...poly[n], ang: Math.atan2(dy, dx) } }
		let lo = 0, hi = s.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; (s[m] < dist ? lo = m : hi = m) }
		const t = (dist - s[lo]) / ((s[hi] - s[lo]) || 1), x = poly[lo].x + t * (poly[hi].x - poly[lo].x), y = poly[lo].y + t * (poly[hi].y - poly[lo].y);
		const dx = poly[hi].x - poly[lo].x, dy = poly[hi].y - poly[lo].y; return { x, y, ang: Math.atan2(dy, dx) };
	}
	function widthForFDI(baseW, fdi) { const t = typeOf(fdi); return t === 'incisor' ? baseW * 0.78 : t === 'canine' ? baseW * 0.90 : t === 'premolar' ? baseW * 0.98 : baseW * 1.05 }
	function archPositionsWeighted(fdis, ctrlPts, totalW, gapPx) {
		const table = arcTable(sampleCR(ctrlPts, 120));
		const halfs = fdis.map(f => widthForFDI(totalW / 16, f) / 2);
		const centers = []; let cur = halfs[0]; centers.push(cur);
		for (let i = 1; i < fdis.length; i++) { cur += halfs[i - 1] + (gapPx || 0) + halfs[i]; centers.push(cur) }
		const required = centers[centers.length - 1] || 1, margin = Math.max(halfs[0], halfs[halfs.length - 1]) + 10;
		const usable = Math.max(10, table.L - 2 * margin); const posScale = usable / required; const layoutScale = Math.min(1, posScale);
		const positions = centers.map(c => { const p = pointAtArclen(table, margin + c * posScale); return { x: p.x, y: p.y, rot: (p.ang * 180 / Math.PI) } });
		return { positions, layoutScale };
	}

	/* theme */
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
	const _fallbackDebounce = (fn, ms) => { let t = null; return function (...a) { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); }; };
	const debounce = (fn, ms) => (window.frappe?.utils?.debounce ? window.frappe.utils.debounce(fn, ms) : _fallbackDebounce(fn, ms));

	class DentalChart {
		constructor(target, opts = {}) {
			this.root = (typeof target === 'string') ? document.querySelector(target) : target;
			if (!this.root) throw new Error('DentalChart: target not found');
			this.root.classList.add('dc-wrap');

			this.opts = Object.assign({
				width: 920,
				height: 740,
				toothW: 48,
				toothH: 60,
				archTightness: 0.92,
				gapPx: 10,
				autoFit: true,
				minScale: 0.96,
				useSurfaceToggle: true,
				startSurfaceMode: false,
				theme: 'auto',
				initial: {},
				showQuadrantAxes: true,
				quadrantSpread: 60,
				quadPill: { padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 },
				quadrantLabels: ['Upper Right', 'Upper Left', 'Lower Right', 'Lower Left'],
				quadrantAxisStyle: { stroke: '#9ca3af', width: 1, dash: '4 3', opacity: .9 },
				palette: ['caries', 'filled', 'crown', 'implant', 'missing', 'healthy'],

				readOnly: 'auto',
				bindToFrappe: true,
				storeField: 'observation_store',
				autoSave: false,
				saveDebounceMs: 600,

				preset: 'anatomic',
				numbering: 'FDI',

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

			// form/doc tracking
			this._docKey = null;
			this._lastPushedJson = null;

			this.setTheme(this.opts.theme);

			this._debouncedAutoSave = debounce(() => this.save(), this.opts.saveDebounceMs);

			this._readOnly = this._initReadonly();
			this._mount();

			if (this.opts.bindToFrappe) {
				this._loadFromForm();
				this._startFormAutoSync();
			}
		}

		/* ===== PRESET RESOLVER ===== */
		_presetConfig() {
			const p = String(this.opts.preset || 'anatomic').toLowerCase();
			if (p === 'pedo') return { upper: UPPER_PEDO, lower: LOWER_PEDO, isPedo: true, straight: false, showSurfaces: true };
			if (p === 'restorative') return { upper: UPPER, lower: LOWER, isPedo: false, straight: true, showSurfaces: true };
			if (p === 'ortho') return { upper: UPPER, lower: LOWER, isPedo: false, straight: true, showSurfaces: false };
			return { upper: UPPER, lower: LOWER, isPedo: false, straight: false, showSurfaces: true };
		}

		/* ===== PUBLIC STATE ===== */
		getValue() { return this.getState(); }
		getState() { return JSON.parse(JSON.stringify(this.state)); }
		setValue(next) { this.setState(next); }
		setState(next) {
			const clean = (next && typeof next === 'string') ? this._safeParse(next) : next;
			const data = (clean && typeof clean === 'object' && !Array.isArray(clean)) ? clean : {};
			const sig = this._stateSig(data);
			if (sig === this._stateHash) return;
			this._stateHash = sig;
			this.state = JSON.parse(JSON.stringify(data || {}));
			if (this.svg) this._redrawStates();
			this._emit();
		}

		save() {
			if (!this.opts.bindToFrappe || !window.cur_frm) return;
			try {
				const frm = window.cur_frm, field = this.opts.storeField;
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

				if (typeof frm.set_value === 'function') frm.set_value(field, toWrite);
				else { frm.doc[field] = toWrite; if (typeof frm.dirty === 'function') frm.dirty(); }
				this._lastPushedJson = JSON.stringify(valObj || {});
			} catch (e) { }
		}

		/* ===== THEME ===== */
		setTheme(mode) {
			this._themeModeExplicit = mode || 'light';
			if (this._themeModeExplicit === 'auto') this._startThemeAutoSync();
			else { this._stopThemeAutoSync(); this.root.setAttribute('data-theme', this._themeModeExplicit === 'dark' ? 'dark' : 'light'); }
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
		_clearSurfaceMarksOnly() {
			Object.keys(this.state || {}).forEach(k => {
				if (!/^\d+$/.test(k)) return;
				if (this.state[k]?.surfaces) this.state[k].surfaces = {};
			});
			this._stateHash = this._stateSig(this.state);
			this._emit();
		}
		_emit() {
			if (typeof this.opts.onChange === 'function') { try { this.opts.onChange(this.getState()); } catch (e) { } }
			if (this.opts.autoSave && !this._readOnly) { this._debouncedAutoSave(); }
		}
		_ensureTip() {
			if (!document.getElementById('dc-tip')) {
				const tip = el('div', { id: 'dc-tip', class: 'dc-tip' });
				document.body.appendChild(tip);
			}
		}

		/* ===== MOUNT ===== */
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

		/* ===== DATA INSPECTION / COUNTS ===== */
		_hasAnyDentalToothState() {
			const st = this.state || {};
			for (const k in st) { if (!/^\d+$/.test(k)) continue; const t = st[k]; if (t && t.state && t.state !== 'healthy') return true; }
			return false;
		}
		_countSurfaceMarks() {
			let marks = 0, teeth = 0;
			const st = this.state || {};
			for (const k in st) {
				if (!/^\d+$/.test(k)) continue;
				const s = st[k]?.surfaces;
				if (!s || typeof s !== 'object') continue;
				const n = Object.keys(s).filter(sk => s[sk]).length;
				if (n) { marks += n; teeth++; }
			}
			return { marks, teeth };
		}
		_hasAnyDentalData() {
			if (this._hasAnyDentalToothState()) return true;
			return this._countSurfaceMarks().marks > 0;
		}

		_isSurfaceTool(name) { return !!name && !['healthy', 'missing'].includes(String(name)); }
		_isSurfaceToolSelected() { return this._isSurfaceTool(this.currentTool); }

		/* ===== PROMPT (frappe.ui.Dialog) ===== */
		_confirmSwitch({ title, messageHTML, onKeep, onClear, onCancel }) {
			if (!window.frappe || !window.frappe.ui || !window.frappe.ui.Dialog) {
				try { onKeep && onKeep(); } catch { } return;
			}
			const d = new frappe.ui.Dialog({ title, static: true });
			d.$body.html(`
				<div style="line-height:1.5;font-size:13px;">${messageHTML}</div>
				<div style="display:flex;gap:.5rem;margin-top:1rem;flex-wrap:wrap">
					<button class="btn btn-primary" data-act="keep">Keep & Switch</button>
					<button class="btn btn-danger"  data-act="clear">Clear & Switch</button>
					<button class="btn btn-default" data-act="cancel">Cancel</button>
				</div>
			`);
			const close = () => d.hide();
			d.$body.find('[data-act="keep"]').on('click', () => { try { onKeep && onKeep(); } finally { close(); } });
			d.$body.find('[data-act="clear"]').on('click', () => { try { onClear && onClear(); } finally { close(); } });
			d.$body.find('[data-act="cancel"]').on('click', () => { try { onCancel && onCancel(); } finally { close(); } });
			d.show();
		}
		/* ===== TOOLBAR (two rows, centered) ===== */
		_renderToolbar() {
			const saveUI = () => {
				this.state._ui = Object.assign({}, this.state._ui, {
					preset: this.opts.preset,
					numbering: this.opts.numbering,
					surfaceMode: !!this.surfaceMode,
				});
				this._stateHash = this._stateSig(this.state);
				this._emit();
			};

			// Bootstrap once from saved UI
			if (!this._uiBootstrapped && this.state && this.state._ui) {
				const u = this.state._ui || {};
				if (u.preset) this.opts.preset = u.preset;
				if (u.numbering) this.opts.numbering = u.numbering;
				if (typeof u.surfaceMode === 'boolean') this.surfaceMode = !!u.surfaceMode;
				this._uiBootstrapped = true;
			}

			// palette
			const dentalPalette = ['caries', 'filled', 'crown', 'implant', 'missing', 'healthy'];
			this.opts.palette = dentalPalette;
			if (!this.opts.palette.includes(this.currentTool)) this.currentTool = 'healthy';

			// skeleton
			const bar = el('div', { class: 'dc-toolbar' });
			const rowTop = el('div', { class: 'dc-row dc-controls' });
			const rowBottom = el('div', { class: 'dc-row dc-palette' });
			bar.append(rowTop, rowBottom);
			this._toolButtons = {};

			// palette row
			const buildPalette = () => {
				this._toolButtons = {};
				rowBottom.innerHTML = '';
				(this.opts.palette || []).forEach(name => {
					const b = el('button', { class: 'dc-btn tool-' + name, 'data-tool': name, type: 'button' }, toTitleCase(name));
					if (name === this.currentTool) b.classList.add('active');
					b.addEventListener('click', () => {
						if (b.disabled) return;
						this.currentTool = name;
						rowBottom.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
						b.classList.add('active');
						this._applySurfaceInteractivity();
						this._syncSurfaceToolDisables();
						saveUI();
					});
					this._toolButtons[name] = b;
					rowBottom.appendChild(b);
				});
			};
			buildPalette();

			/* Surface-mode switch */
			const surfId = 'dc-surfaces-' + Math.random().toString(36).slice(2, 8);
			const surfLabel = el('label', { class: 'dc-switch', 'data-role': 'surfaces-toggle', for: surfId });
			const surfInput = el('input', { type: 'checkbox', id: surfId, role: 'switch' });
			const surfUI = el('span', { class: 'dc-switch-ui' });
			const surfTxt = el('span', { class: 'dc-switch-txt' }, 'Surface Marks');
			surfLabel.append(surfInput, surfUI, surfTxt);

			const isOrtho = String(this.opts.preset || 'anatomic').toLowerCase() === 'ortho';
			if (isOrtho) {
				this.surfaceMode = false; surfInput.checked = false; surfInput.disabled = true;
				surfLabel.style.opacity = '.6';
				this._applySurfaceInteractivity();
			} else {
				surfInput.checked = !!this.surfaceMode; surfInput.disabled = false; surfLabel.style.opacity = '';
			}

			const syncSurface = () => {
				surfInput.checked = !!this.surfaceMode;
				this._syncSurfaceToolDisables();
				saveUI();
			};
			surfInput.addEventListener('change', () => {
				this.surfaceMode = !!surfInput.checked;
				if (this.surfaceMode) {
					if (this.currentTool === 'healthy' || this.currentTool === 'missing') {
						this.currentTool = null;
						rowBottom.querySelectorAll('.dc-btn[data-tool]').forEach(x => x.classList.remove('active'));
					}
				} else if (!this.currentTool) {
					this.currentTool = 'healthy';
					this._toolButtons?.healthy?.classList.add('active');
				}
				this._applySurfaceInteractivity();
				syncSurface();
			});

			/* Preset select */
			const presetSel = el('select', { class: 'dc-btn', 'data-role': 'preset', title: 'Chart Preset' });
			['anatomic', 'pedo', 'restorative', 'ortho'].forEach(p => {
				const opt = el('option', { value: p }, p[0].toUpperCase() + p.slice(1));
				if (String(this.opts.preset || 'anatomic').toLowerCase() === p) opt.selected = true;
				presetSel.appendChild(opt);
			});
			presetSel.addEventListener('change', () => {
				const nextPreset = presetSel.value;
				const goingToOrtho = String(nextPreset).toLowerCase() === 'ortho';

				const proceed = () => {
					this.opts.preset = nextPreset;
					saveUI();
					this.setPreset(this.opts.preset);
				};

				if (goingToOrtho && this._countSurfaceMarks().marks > 0) {
					const { marks, teeth } = this._countSurfaceMarks();
					this._confirmSwitch({
						title: __('Switch to Ortho'),
						messageHTML: `
							<p>Ortho preset doesn’t support per-surface marks. Your ${marks} surface marks on ${teeth} teeth will be hidden.</p>
							<ul style="margin:.5rem 0 0 1rem;">
								<li><b>Keep & Switch</b>: hide surface marks (switching back restores them).</li>
								<li><b>Clear & Switch</b>: delete all surface marks now (tooth-level states remain).</li>
								<li><b>Cancel</b>.</li>
							</ul>
						`,
						onKeep: proceed,
						onClear: () => { this._clearSurfaceMarksOnly(); this._redrawStates(); try { this.save && this.save(); } catch { }; proceed(); },
						onCancel: () => { presetSel.value = this.opts.preset; }
					});
				} else {
					proceed();
				}
			});

			/* Numbering select */
			const numberingSel = el('select', { class: 'dc-btn', 'data-role': 'numbering', title: 'Numbering System' });
			['FDI', 'Universal'].forEach(n => {
				const opt = el('option', { value: n }, n);
				if (String(this.opts.numbering || 'FDI').toUpperCase() === n.toUpperCase()) opt.selected = true;
				numberingSel.appendChild(opt);
			});
			numberingSel.addEventListener('change', () => {
				this.opts.numbering = numberingSel.value; saveUI(); this.setNumbering(this.opts.numbering);
			});

			// controls on the top row
			rowTop.append(presetSel, numberingSel, surfLabel);

			// hint
			const hint = el('span', { class: 'dc-hint', style: 'display:none' }, 'Select a surface tool');
			rowTop.appendChild(hint);
			this._surfaceHint = hint;

			// read-only: hide surface toggle; keep selects disabled
			if (this._readOnly) {
				surfLabel.style.display = 'none';
				presetSel.disabled = true; numberingSel.disabled = true;
			}

			this._syncSurfaceToolDisables();
			return bar;
		}

		_syncSurfaceToolDisables() {
			if (!this._toolButtons || typeof this._toolButtons !== 'object') return;
			if (this._readOnly) {
				Object.values(this._toolButtons).forEach(b => { if (!b) return; b.disabled = true; b.setAttribute('aria-disabled', 'true'); b.classList.add('legend-disabled'); b.classList.remove('disabled'); });
				return;
			}
			Object.values(this._toolButtons).forEach(b => { if (!b) return; b.classList.remove('legend-disabled'); b.removeAttribute('aria-disabled'); if (!['healthy', 'missing'].includes(b.getAttribute('data-tool'))) { b.disabled = false; b.classList.remove('disabled'); } });
			const dis = !!this.surfaceMode;
			['healthy', 'missing'].forEach(name => { const btn = this._toolButtons[name]; if (!btn) return; btn.disabled = dis; btn.setAttribute('aria-disabled', dis ? 'true' : 'false'); btn.classList.toggle('disabled', dis); });
			Object.entries(this._toolButtons).forEach(([name, btn]) => { btn.classList.toggle('active', !!this.currentTool && this.currentTool === name); });
		}

		_renderSVG() {
			const containerW = this.root.clientWidth || 0;
			const W = Math.max(720, containerW || this.opts.width || 920);
			const H = this.opts.height || 740;

			const cfg = this._presetConfig();
			const UPPER_SET = cfg.upper, LOWER_SET = cfg.lower, straight = !!cfg.straight;

			const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });
			const cx = W / 2;

			let upperCtrl, lowerCtrl;
			if (!straight) {
				const k = this.opts.archTightness || 1;
				upperCtrl = [{ x: cx - W * (.36 * k), y: H * .39 }, { x: cx - W * (.18 * k), y: H * .30 }, { x: cx, y: H * .27 }, { x: cx + W * (.18 * k), y: H * .30 }, { x: cx + W * (.36 * k), y: H * .39 }];
				lowerCtrl = [{ x: cx - W * (.36 * k), y: H * .71 }, { x: cx - W * (.18 * k), y: H * .80 }, { x: cx, y: H * .83 }, { x: cx + W * (.18 * k), y: H * .80 }, { x: cx + W * (.36 * k), y: H * .71 }];
			} else {
				const yU = H * .35, yL = H * .75, span = W * .76;
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

			// delegated click for surfaces
			this._onSvgClick && this.svg.removeEventListener('click', this._onSvgClick, false);
			this._onSvgClick = (e) => {
				if (!this.surfaceMode || this._readOnly) return;
				const t = e.target;
				if (!(t instanceof SVGElement) || !t.classList.contains('surf')) return;
				if (!this.currentTool || this.currentTool === 'healthy' || this.currentTool === 'missing') return;

				const toothG = t.closest('g.tooth'); if (!toothG) return;
				const fdi = +toothG.getAttribute('data-tooth');
				const surfKey = t.dataset?.surfKey || t.getAttribute('data-surf-key') || t.getAttribute('data-surfkey');
				if (!surfKey) return;

				this._applyTool(fdi, String(surfKey).toUpperCase());
				e.stopPropagation();
			};
			this.svg.addEventListener('click', this._onSvgClick, false);

			return el('div', { class: 'dc-canvas', style: `min-height:${H}px` }, svg);
		}

		_renderQuadrants(svg, upperCtrl, lowerCtrl) {
			const labels = this.opts.quadrantLabels || ['UR', 'UL', 'LL', 'LR'];
			const spread = Number(this.opts.quadrantSpread || 0);
			const pillCfg = Object.assign({ padX: 10, padY: 6, radius: 10, minW: 90, minH: 20 }, this.opts.quadPill || {});

			const u0 = upperCtrl[0], u1 = upperCtrl[upperCtrl.length - 1];
			const l0 = lowerCtrl[0], l1 = lowerCtrl[lowerCtrl.length - 1];

			const makePill = (x, y, text) => {
				const w = Math.max(pillCfg.minW, pillCfg.padX * 2 + text.length * 7.2);
				const h = Math.max(pillCfg.minH, pillCfg.padY * 2 + 12);
				const g = svgEl('g', { transform: `translate(${x},${y})` });
				const bg = svgEl('rect', { class: 'quad-bg', x: -w / 2, y: -h / 2, width: w, height: h, rx: pillCfg.radius, ry: pillCfg.radius });
				const tx = svgEl('text', { class: 'quad-pill', 'text-anchor': 'middle', x: 0, y: 4 }); tx.textContent = text;
				g.append(bg, tx); svg.appendChild(g);
			};
			makePill(u0.x - spread, u0.y - spread, labels[0]);
			makePill(u1.x + spread, u1.y - spread, labels[1]);
			makePill(l0.x - spread, l0.y + spread, labels[2]);
			makePill(l1.x + spread, l1.y + spread, labels[3]);
		}
		_showQuadrantPills() { if (this.opts.showQuadrants === false) return false; if (this.opts.showQuadrantLabels === false) return false; return true; }
		_renderQuadrantAxes(svg, W, H, upperCtrl, lowerCtrl) {
			const st = Object.assign({ stroke: '#9ca3af', width: 1, dash: '4 3', opacity: .9 }, this.opts.quadrantAxisStyle || {});
			const cx = W / 2;
			const v = svgEl('line', { x1: cx, x2: cx, y1: H * .18, y2: H * .92, class: 'quad-axis' });
			const hy = (upperCtrl[0].y + lowerCtrl[0].y) / 2;
			const h = svgEl('line', { x1: W * .06, x2: W * .94, y1: hy, y2: hy, class: 'quad-axis' });
			[v, h].forEach(line => { if (st.stroke) line.setAttribute('stroke', st.stroke); if (st.width != null) line.setAttribute('stroke-width', String(st.width)); if (st.dash) line.setAttribute('stroke-dasharray', st.dash); if (st.opacity != null) line.setAttribute('opacity', String(st.opacity)); });
			svg.insertBefore(v, svg.firstChild); svg.insertBefore(h, svg.firstChild);
		}

		_applySurfaceInteractivity() {
			// Only allow interactivity if: Surface mode + surface tool chosen + not read-only
			const canInteract = !!this.surfaceMode && this._isSurfaceToolSelected() && !this._readOnly;

			// keep a flag for tooltip / hover handlers
			this._surfaceHoverOn = canInteract;

			this._allSurfaces.forEach(r => {
				r.setAttribute('pointer-events', canInteract ? 'all' : 'none');
				if (!canInteract) r.classList.remove('hover');
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
			g.appendChild(chipG);
			g.appendChild(label);

			hits.forEach(r => this._allSurfaces.push(r));

			const tip = document.getElementById('dc-tip');
			g.addEventListener('pointerover', (e) => {
				if (!this._surfaceHoverOn) return;
				const n = e.target;
				if (n.classList?.contains('surf') && n.getAttribute('data-marked') !== '1') { n.classList.add('hover'); n.style.removeProperty('fill-opacity'); }
				if (tip) { const t = this._tooltipFor(e, fdi); if (t) { tip.textContent = t; tip.style.display = 'block'; } }
			});
			g.addEventListener('pointermove', (e) => { if (!this.surfaceMode || !tip) return; const r = e.target.getBoundingClientRect(); tip.style.left = (r.left + r.width / 2) + 'px'; tip.style.top = (r.top) + 'px'; });
			g.addEventListener('pointerout', (e) => { const n = e.target; if (n.classList?.contains('surf')) { n.classList.remove('hover'); if (n.getAttribute('data-marked') !== '1') n.style.removeProperty('fill-opacity'); } if (tip) tip.style.display = 'none'; });

			bodyHit.addEventListener('click', () => {
				if (this._readOnly) return;

				// If Surface Mode is ON but no surface tool is selected, ignore body clicks
				if (this.surfaceMode && !this._isSurfaceToolSelected()) return;

				this._applyTool(fdi, null);
			});

			g._chip = chipG; g._chipText = chipTx; g._chipBg = chipBg; g._rect = body; g._cells = [...hits];
			return g;
		}

		_makeSurfaceHits(w, h) {
			const cfg = this._presetConfig();
			if (cfg && cfg.showSurfaces === false) return [];
			const pad = Math.max(2, Math.round(Math.min(w, h) * 0.06));
			const r = Math.max(3, Math.round(Math.min(w, h) * 0.10));
			const arr = [];
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));                            // B
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: h - (h * .28) - pad, width: w - 2 * pad, height: h * .28, rx: r, ry: r }));                 // L
			arr.push(svgEl('rect', { class: 'surf', x: pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r }));                     // M
			arr.push(svgEl('rect', { class: 'surf', x: w - (w * .28) - pad, y: (h * .28) + pad, width: w * .28, height: h * .44, rx: r, ry: r }));           // D
			arr.push(svgEl('rect', { class: 'surf center', x: w * .30, y: h * .30, width: w * .40, height: h * .40, rx: r, ry: r }));                  // O
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

		_stateSig(obj) { try { return JSON.stringify(obj || {}); } catch { return ''; } }

		_redrawStates() {
			if (!this.svg) return;
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
					const rr = cell.dataset?.rx || '4';
					cell.setAttribute('rx', rr); cell.setAttribute('ry', rr);
					const k = cell.dataset?.surfKey?.toUpperCase();
					const mark = k ? T.surfaces?.[k] : null;

					if (isMissing) { cell.removeAttribute('data-marked'); cell.style.cssText = ''; return; }

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

		/* ===== Read-only handling ===== */
		_initReadonly() {
			if (this.opts.readOnly === 'auto') return this._computeReadonlyFromEnv();
			return !!this.opts.readOnly;
		}
		_computeReadonlyFromEnv() {
			const ds = window.cur_frm?.doc?.docstatus;
			if (typeof ds === 'number') return ds === 1;
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
			this._roTimer = setInterval(() => { const next = this._computeReadonlyFromEnv(); if (next !== this._readOnly) this.setReadOnly(next); }, 900);
		}
		setReadOnly(flag) {
			const next = !!flag; this._readOnly = next;
			this.root.classList.toggle('dc-edit', !next);
			const surfToggle = this.root.querySelector('[data-role="surfaces-toggle"]');
			if (surfToggle) surfToggle.style.display = next ? 'none' : '';
			if (this._toolButtons) {
				Object.values(this._toolButtons).forEach(btn => { if (!btn) return; btn.disabled = next; btn.setAttribute('aria-disabled', next ? 'true' : 'false'); btn.classList.toggle('legend-disabled', next); if (!next) btn.classList.remove('legend-disabled'); });
			}
			const cnv = this.root.querySelector('.dc-canvas'); if (cnv) cnv.classList.toggle('dc-readonly', next);
			this._applySurfaceInteractivity();
			this._syncSurfaceToolDisables();
		}

		/* ===== Form binding ===== */
		_safeParse(x) { if (!x) return {}; if (typeof x === 'object') return x; try { const v = JSON.parse(x); return (v && typeof v === 'object') ? v : {}; } catch { return {} } }
		_fieldTypeOf(frm, fieldname) { try { const df = frm.get_docfield ? frm.get_docfield(fieldname, frm.doc.name) : null; return df ? df.fieldtype : null; } catch { return null; } }
		_curDocKey() { const f = window.cur_frm; if (!f || !f.doctype || !f.doc?.name) return null; return `${f.doctype}:${f.doc.name}`; }
		_readStoreFromForm() { const f = window.cur_frm, field = this.opts.storeField; if (!f) return {}; const raw = f.doc ? f.doc[field] : {}; return this._safeParse(raw); }
		_loadFromForm() {
			if (!this.opts.bindToFrappe || !window.cur_frm) return;
			const key = this._curDocKey(); if (!key) return;
			const store = this._readStoreFromForm(); const storeJson = JSON.stringify(store || {});

			if (key !== this._docKey) {
				this._docKey = key;
				if (isEmptyObj(store)) this.setState({}); else this.setState(store);
				this._lastPulledJson = storeJson;
				if (this.opts.readOnly === 'auto') this.setReadOnly(this._computeReadonlyFromEnv());
				return;
			}
			if (!isEmptyObj(store)) {
				if (storeJson !== this._lastPulledJson && storeJson !== this._lastPushedJson) {
					this.setState(store);
					this._lastPulledJson = storeJson;
				}
			}
		}
		_startFormAutoSync() { if (this._formTimer) clearInterval(this._formTimer); this._formTimer = setInterval(() => this._loadFromForm(), 800); }

		/* ===== Renderer setters (only preset/numbering now) ===== */
		setPreset(preset) {
			const p = String(preset || 'anatomic').toLowerCase();
			if (!['anatomic', 'pedo', 'restorative', 'ortho'].includes(p)) return;
			this.opts.preset = p;
			this._mount();
			this._redrawStates();
		}
		setNumbering(system) {
			const s = String(system || 'FDI').toUpperCase();
			this.opts.numbering = (s === 'UNIVERSAL') ? 'Universal' : 'FDI';
			this._mount();
			this._redrawStates();
		}
	}

	// Export
	window.DentalChart = DentalChart;
})();
