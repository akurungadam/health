// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

/* eslint-disable */

// =========================================================
// Constants & Configuration
// =========================================================

const API_METHODS = {
	get_elements_from_structure_definitions:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.get_elements_from_structure_definitions",
	generate_fhir_resource:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.generate_fhir_resource",
};

const SKIP_FIELDTYPES = new Set([
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Fold",
]);

// Element-table filters. One definition drives the toolbar, its bindings, the
// reset and the row predicate, so a filter is added/changed in a single place.
const ELEMENT_FILTERS = [
	{
		key: "filterRequired",
		cls: "required",
		label: "Required",
		test: r => r._ui_required,
	},
	{ key: "filterChoice", cls: "choice", label: "Choice", test: r => r._ui_choice },
	{
		key: "filterMapped",
		cls: "mapped",
		label: "Mapped",
		test: r => r._ui_mapped,
		excludes: "filterUnmapped",
	},
	{
		key: "filterUnmapped",
		cls: "unmapped",
		label: "Unmapped",
		test: r => !r._ui_mapped,
		excludes: "filterMapped",
	},
];

const ELEMENTS_MAP_STYLES = `
.fhir-em-toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.fhir-em-search-wrap { flex: 1; min-width: 260px; }
.fhir-em-toolbar .fhir-em-filter { margin: 0; }
.fhir-em-toolbar .fhir-em-filter span { margin-left: 6px; }
.fhir-em-table { margin: 0; }
.fhir-em-empty { padding: 12px; }
.elements-map-row { cursor: pointer; }
.fhir-em-pathwrap { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.fhir-em-pathname { font-weight: 600; }
.fhir-em-hint { font-size: 12px; margin-top: 4px; }
.fhir-em-col-path { width: 44%; }
.fhir-em-col-dt { width: 14%; }
.fhir-em-col-min, .fhir-em-col-max { width: 8%; }
.fhir-em-col-map { width: 26%; }
.fhir-em-pill { margin-left: 6px; }
.fhir-map-kb-hint { margin-right: auto; font-size: 12px; padding-left: 4px; }
`;

// =========================================================
// Form Events
// =========================================================

frappe.ui.form.on("FHIR Resource Map", {
	refresh(frm) {
		FormState.init(frm);
		FormButtons.setup(frm);
		ElementsMapUI.render(frm);
	},

	base_structure_definition(frm) {
		ElementsMapUI.render(frm);
	},

	element_maps_add(frm) {
		ElementsMapUI.render(frm);
	},

	element_maps_remove(frm) {
		ElementsMapUI.render(frm);
	},

	on_unload(frm) {
		KeyboardNavigation.detach(frm);
	},
});

// =========================================================
// Form State Management
// =========================================================

const FormState = {
	init(frm) {
		if (!frm._elements_map_state) {
			const state = { search: "" };
			for (const f of ELEMENT_FILTERS) state[f.key] = false;
			frm._elements_map_state = state;
		}

		frm._elements_map_ui_built = frm._elements_map_ui_built || false;
		frm._active_mapping_dialog = frm._active_mapping_dialog || null;
		frm._active_mapping_row = frm._active_mapping_row || null;
		frm._mapping_nav_busy = frm._mapping_nav_busy ?? false;
		frm._mapping_nav_seq = frm._mapping_nav_seq ?? 0;
		frm._mapping_keydown_handler = frm._mapping_keydown_handler || null;
	},

	getState(frm) {
		return frm._elements_map_state;
	},

	resetFilters(frm) {
		const state = this.getState(frm);
		state.search = "";
		for (const f of ELEMENT_FILTERS) state[f.key] = false;
	},
};

// =========================================================
// Form Buttons
// =========================================================

const FormButtons = {
	setup(frm) {
		frm.clear_custom_buttons();
		frm.add_custom_button(__("Load from Profile"), () =>
			this._loadFromProfile(frm),
		);
		frm.add_custom_button(__("Preview FHIR Resource"), () =>
			PreviewDialog.open(frm),
		);
	},

	async _loadFromProfile(frm) {
		if (!this._hasProfileSource(frm)) {
			frappe.throw(
				__("Please add at least one FHIR Profile before loading elements."),
			);
		}

		const saveMessage = __(
			"Please save the FHIR Resource Map before loading elements from profile.",
		);
		if (!this._requireSaved(frm, saveMessage)) return;

		frm.disable_save();
		try {
			await this._loadElements(frm);
		} finally {
			frm.enable_save();
		}
	},

	async _loadElements(frm) {
		const res = await frappe.call({
			method: API_METHODS.get_elements_from_structure_definitions,
			args: { fhir_resource_map: frm.doc.name },
			freeze: true,
			freeze_message: __("Loading elements from profile..."),
		});

		const elements = res.message || [];
		if (!elements.length) {
			frappe.msgprint(__("No elements found."));
			return;
		}

		frm.clear_table("element_maps");
		for (const row of elements) {
			Object.assign(frm.add_child("element_maps"), row);
		}

		frm.refresh_field("element_maps");
		ElementsMapUI.render(frm);
		frappe.show_alert({
			message: __("FHIR elements loaded from profile."),
			indicator: "green",
		});
	},

	_hasProfileSource(frm) {
		return (frm.doc.profiles || []).some(
			row =>
				String(row.fhir_structure_definition || "").trim() ||
				String(row.fhir_profile || "").trim(),
		);
	},

	_requireSaved(frm, saveMessage) {
		if (frm.is_new() || !frm.doc.name) {
			frappe.msgprint({
				title: __("Save Required"),
				message: saveMessage,
				indicator: "orange",
			});
			return false;
		}

		if (frm.is_dirty()) {
			frappe.msgprint({
				title: __("Unsaved Changes"),
				message: __("Please save changes first."),
				indicator: "orange",
			});
			return false;
		}

		return true;
	},
};

// =========================================================
// Elements Map UI
// =========================================================

const ElementsMapUI = {
	render(frm) {
		const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
		if (!wrapper) return;

		if (!frm._elements_map_ui_built) {
			this._buildInitialUI(frm, wrapper);
			frm._elements_map_ui_built = true;
		}

		this._renderTable(frm);
	},

	_buildInitialUI(frm, wrapper) {
		this._injectStyles();

		wrapper.empty();
		wrapper.append(`
			<div class="elements-map-root">
				<div class="elements-map-toolbar-slot"></div>
				<div class="elements-map-table-slot"></div>
			</div>
		`);

		wrapper
			.find(".elements-map-toolbar-slot")
			.append(this._buildToolbar(FormState.getState(frm)));
		this._bindToolbarEvents(frm, wrapper);
	},

	_injectStyles() {
		if (document.getElementById("fhir-em-styles")) return;
		const style = document.createElement("style");
		style.id = "fhir-em-styles";
		style.textContent = ELEMENTS_MAP_STYLES;
		document.head.appendChild(style);
	},

	_renderTable(frm) {
		const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
		if (!wrapper) return;

		const rows = (frm.doc.element_maps || []).map(this._normalizeRow);
		const filtered = this._applyFilters(rows, FormState.getState(frm));

		const tableSlot = wrapper.find(".elements-map-table-slot");
		tableSlot.empty();
		tableSlot.append(this._buildTable(frm, filtered));
		this._bindRowEvents(frm, wrapper);
	},

	_normalizeRow(row) {
		const pointer = Utils.safeJsonParse(String(row.value_pointer || "").trim());
		const min = Utils.toInt(row.min);

		return {
			...row,
			_ui_required: min >= 1,
			_ui_choice: String(row.fhir_path || "").includes("[x]"),
			_ui_mapped:
				!!pointer &&
				typeof pointer === "object" &&
				!!String(pointer.kind || "").trim(),
			_ui_pointer: pointer,
			_ui_min: min,
			_ui_max: String(row.max || "").trim(),
			_ui_datatype: String(row.datatype || "").trim(),
			_ui_short: String(row.short || "").trim(),
		};
	},

	_applyFilters(rows, state) {
		let out = rows;

		if (state.search) {
			const q = state.search.toLowerCase();
			out = out.filter(r =>
				[r.fhir_path, r.datatype, r.short, r.value_pointer].some(field =>
					String(field || "")
						.toLowerCase()
						.includes(q),
				),
			);
		}

		for (const f of ELEMENT_FILTERS) {
			if (state[f.key]) out = out.filter(f.test);
		}

		return out;
	},

	_buildToolbar(state) {
		const filterHtml = ELEMENT_FILTERS.map(
			f => `
				<label class="checkbox fhir-em-filter">
					<input type="checkbox" class="elements-map-filter-${f.cls}" ${
						state[f.key] ? "checked" : ""
					}/>
					<span>${f.label}</span>
				</label>
			`,
		).join("");

		return $(`
			<div class="fhir-em-toolbar">
				<div class="fhir-em-search-wrap">
					<input type="text" class="form-control elements-map-search"
						placeholder="Search path / datatype / short / mapping"
						value="${Utils.escapeHtml(state.search)}" />
				</div>
				${filterHtml}
				<button class="btn btn-default btn-sm elements-map-clear">Clear</button>
			</div>
		`);
	},

	_bindToolbarEvents(frm, wrapper) {
		const root = wrapper.find(".elements-map-root");
		const state = FormState.getState(frm);

		root.find(".elements-map-search").on(
			"input",
			frappe.utils.debounce(e => {
				state.search = e.target.value || "";
				this._renderTable(frm);
			}, 120),
		);

		for (const f of ELEMENT_FILTERS) {
			root.find(`.elements-map-filter-${f.cls}`).on("change", e => {
				state[f.key] = !!e.target.checked;
				// mapped / unmapped are mutually exclusive
				if (f.excludes && state[f.key]) {
					state[f.excludes] = false;
					const other = ELEMENT_FILTERS.find(x => x.key === f.excludes);
					if (other)
						root.find(`.elements-map-filter-${other.cls}`).prop(
							"checked",
							false,
						);
				}
				this._renderTable(frm);
			});
		}

		root.find(".elements-map-clear").on("click", () => {
			FormState.resetFilters(frm);
			root.find(".elements-map-search").val("");
			for (const f of ELEMENT_FILTERS) {
				root.find(`.elements-map-filter-${f.cls}`).prop("checked", false);
			}
			this._renderTable(frm);
		});
	},

	_buildTable(frm, rows) {
		if (!rows.length) {
			return $(
				`<div class="text-muted fhir-em-empty">No rows match filters.</div>`,
			);
		}

		const body = rows.map(r => this._buildTableRow(frm, r)).join("");

		return $(`
			<table class="table table-bordered table-hover fhir-em-table">
				<thead>
					<tr>
						<th>FHIR Path</th>
						<th>Datatype</th>
						<th>Min</th>
						<th>Max</th>
						<th>Mapping</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);
	},

	_buildTableRow(frm, r) {
		const pills = [
			r._ui_required ? this._pill("Required") : "",
			r._ui_choice ? this._pill("Choice") : "",
			r._ui_mapped ? this._pill("Mapped") : this._pill("Unmapped"),
		].join("");

		const hint = r._ui_short
			? `<div class="text-muted fhir-em-hint">${Utils.escapeHtml(
					r._ui_short,
			  )}</div>`
			: "";

		return `
			<tr class="elements-map-row" data-rowname="${Utils.escapeHtml(r.name)}">
				<td class="fhir-em-col-path">
					<div class="fhir-em-pathwrap">
						<div class="fhir-em-pathname">${Utils.escapeHtml(r.fhir_path)}</div>
						<div>${pills}</div>
					</div>
					${hint}
				</td>
				<td class="fhir-em-col-dt">${Utils.escapeHtml(r._ui_datatype || "")}</td>
				<td class="fhir-em-col-min">${Utils.escapeHtml(String(r._ui_min))}</td>
				<td class="fhir-em-col-max">${Utils.escapeHtml(String(r._ui_max || ""))}</td>
				<td class="fhir-em-col-map">${this._getMappingSummary(frm, r)}</td>
			</tr>
		`;
	},

	_bindRowEvents(frm, wrapper) {
		wrapper
			.find(".elements-map-row")
			.off("click")
			.on("click", async e => {
				const rowname = $(e.currentTarget).attr("data-rowname");
				const row = (frm.doc.element_maps || []).find(r => r.name === rowname);
				if (row) await MappingDialog.open(frm, row);
			});
	},

	_pill(text) {
		return `<span class="indicator-pill gray fhir-em-pill">${Utils.escapeHtml(
			text,
		)}</span>`;
	},

	_getMappingSummary(frm, row) {
		const pointer = row._ui_pointer;
		if (!pointer || typeof pointer !== "object") {
			return `<span class="text-muted">Click to map</span>`;
		}

		const kind = String(pointer.kind || "").trim();

		if (kind === "fixed") return `<span class="text-muted">Fixed</span>`;
		if (kind === "expression") return `<span class="text-muted">Expression</span>`;
		if (kind !== "field") return `<span class="text-muted">Mapped</span>`;

		const fieldname = Utils.escapeHtml(pointer.fieldname || "");

		if (pointer.reference_type) {
			return `<span class="text-muted">Reference → ${Utils.escapeHtml(
				pointer.reference_type,
			)}</span> · ${fieldname}`;
		}

		const mapHint = pointer.map
			? ` <span class="text-muted">· mapped codes</span>`
			: "";
		return `<span class="text-muted">${Utils.escapeHtml(
			this._sourceLabel(frm, pointer.source_key),
		)}</span> → ${fieldname}${mapHint}`;
	},

	_sourceLabel(frm, sourceKey) {
		try {
			const dt = SourcesHelper.buildIndex(frm)?.[sourceKey]?.doctype;
			if (dt) return sourceKey === "primary" ? `${dt} (Primary)` : dt;
		} catch (e) {}
		return String(sourceKey || "source_key");
	},
};

// =========================================================
// Mapping Dialog
// =========================================================

const MappingDialog = {
	async open(frm, row) {
		await this._closeActive(frm);

		const sourcesIndex = SourcesHelper.buildIndex(frm);
		const pointer =
			Utils.safeJsonParse(String(row.value_pointer || "").trim()) || {};
		const pointerKind = String(pointer.kind || "").trim();
		const sourceSelect = SourcesHelper.buildSelectData(sourcesIndex);
		const defaultKey = SourcesHelper.resolveDefaultKey(pointer, sourcesIndex);
		const defaultLabel = sourceSelect.keyToLabel[defaultKey] || "";
		const isChoice = String(row.fhir_path || "").includes("[x]");

		const dialog = new frappe.ui.Dialog({
			title: __("Map FHIR Element"),
			fields: this._buildFields(row, pointer, defaultLabel, isChoice),
			primary_action_label: __("Apply"),
			primary_action: () =>
				this._handleApply(frm, dialog, row, sourcesIndex, isChoice),
		});

		this._initDialogState(frm, dialog, sourceSelect, row);
		this._setupDialogEvents(frm, dialog, sourcesIndex);

		dialog.show();

		this._applyVisibility(dialog);
		this._setInitialSourceKey(dialog, pointer, pointerKind);
		await this._refreshFieldOptions(dialog, sourcesIndex);
		this._appendKeyboardHint(dialog);
	},

	_val(dialog, fieldname) {
		return String(dialog.get_value(fieldname) || "").trim();
	},

	_buildFields(row, pointer, defaultLabel, isChoice) {
		return [
			{
				fieldtype: "Data",
				fieldname: "fhir_path",
				label: "FHIR Path",
				default: row.fhir_path,
				read_only: isChoice ? 0 : 1,
			},
			{
				fieldtype: "Data",
				fieldname: "datatype",
				label: "Datatype",
				default: row.datatype || "",
				read_only: isChoice ? 0 : 1,
			},
			{ fieldtype: "Section Break", label: __("Mapping") },
			{
				fieldtype: "Select",
				fieldname: "mapping_type",
				label: "Mapping Type",
				options: "\nFrappe Field\nFixed\nReference\nExpression",
				default: this._getMappingTypeDefault(pointer, row),
			},
			{
				fieldtype: "Select",
				fieldname: "source_key",
				label: "Source",
				options: "",
				default: defaultLabel,
			},
			{
				fieldtype: "Select",
				fieldname: "frappe_field",
				label: "Frappe Field",
				options: "",
				default: String(pointer.fieldname || row.frappe_field || ""),
			},
			{
				fieldtype: "Data",
				fieldname: "reference_type",
				label: "Reference Resource Type",
				description: __(
					"FHIR resource the reference points to, e.g. Patient, Organization.",
				),
				default: this._defaultReferenceType(pointer, row),
			},
			{
				fieldtype: "Select",
				fieldname: "reference_display_field",
				label: "Display Field (optional)",
				options: "",
				default: String(pointer.display_field || ""),
			},
			{
				fieldtype: "Code",
				fieldname: "expression",
				label: "Expression",
				options: "Python",
				description: __(
					"Python expression; 'doc' is the source document. e.g. doc.codification_table[0].code",
				),
				default:
					pointer.kind === "expression"
						? String(pointer.expression || "")
						: row.expression || "",
			},
			{
				fieldtype: "Code",
				fieldname: "fixed_value",
				label: "Fixed Value",
				options: "JSON",
				default:
					pointer.kind === "fixed"
						? Utils.safeJsonStringify(pointer.value ?? null)
						: row.fixed_value || "",
			},
			{
				fieldtype: "Code",
				fieldname: "value_map",
				label: "Value Map (optional)",
				options: "JSON",
				description: __(
					'Translate a local value to a FHIR code, e.g. {"Male": "male", "Female": "female", "*": "unknown"} ("*" = fallback).',
				),
				default: pointer.map ? Utils.safeJsonStringify(pointer.map) : "",
			},
			{
				fieldtype: "Code",
				fieldname: "default_value",
				label: "Default Value (optional)",
				options: "JSON",
				default:
					pointer.default !== undefined
						? Utils.safeJsonStringify(pointer.default)
						: row.default_value || "",
			},
		];
	},

	_getMappingTypeDefault(pointer, row) {
		const kind = String(pointer.kind || "").trim();
		const datatype = String((row && row.datatype) || "")
			.trim()
			.toLowerCase();

		if (pointer.reference_type || (kind === "field" && datatype === "reference"))
			return "Reference";
		if (kind === "field") return "Frappe Field";
		if (kind === "fixed") return "Fixed";
		if (kind === "expression") return "Expression";
		// unmapped element whose datatype is a reference -> pre-select Reference
		return datatype === "reference" ? "Reference" : "";
	},

	_defaultReferenceType(pointer, row) {
		if (pointer && pointer.reference_type) return String(pointer.reference_type);

		const raw = String((row && row.target_profiles) || "").trim();
		if (!raw) return "";

		let data;
		try {
			data = JSON.parse(raw);
		} catch (e) {
			data = raw;
		}
		const url = Array.isArray(data) ? data[0] : data;
		if (!url) return "";

		return String(url).replace(/\/+$/, "").split("/").pop().trim();
	},

	_fieldValue(raw) {
		const value = String(raw || "").trim();
		return value.includes("|") ? value.split("|")[0].trim() : value;
	},

	_applyValueMap(dialog, pointer) {
		const parsed = Utils.safeJsonParse(this._val(dialog, "value_map"));
		if (
			parsed &&
			typeof parsed === "object" &&
			!Array.isArray(parsed) &&
			Object.keys(parsed).length
		) {
			pointer.map = parsed;
		}
	},

	_initDialogState(frm, dialog, sourceSelect, row) {
		dialog.__source_label_to_key = sourceSelect.labelToKey;
		dialog.__from_source_key_to_label = sourceSelect.keyToLabel;

		const sourceField = dialog.fields_dict?.source_key;
		if (sourceField) {
			sourceField.df.options = sourceSelect.labels.join("\n");
			sourceField.refresh();
		}

		frm._active_mapping_dialog = dialog;
		frm._active_mapping_row = row;

		KeyboardNavigation.attach(frm, dialog);

		dialog.$wrapper?.one("hidden.bs.modal.fhir_map_nav_clear", () => {
			if (frm._active_mapping_dialog === dialog) {
				frm._active_mapping_dialog = null;
				frm._active_mapping_row = null;
			}
		});
	},

	_setupDialogEvents(frm, dialog, sourcesIndex) {
		const refresh = async () => {
			this._applyVisibility(dialog);
			await this._refreshFieldOptions(dialog, sourcesIndex);
		};

		if (dialog.fields_dict?.mapping_type)
			dialog.fields_dict.mapping_type.df.change = refresh;
		if (dialog.fields_dict?.source_key) {
			dialog.fields_dict.source_key.df.change = () =>
				this._refreshFieldOptions(dialog, sourcesIndex);
		}
	},

	_setInitialSourceKey(dialog, pointer, pointerKind) {
		if (pointerKind !== "field" && pointerKind !== "expression") return;
		const label =
			dialog.__from_source_key_to_label?.[
				String(pointer.source_key || "").trim()
			];
		if (label) dialog.set_value("source_key", label);
	},

	_resolveSourceKey(dialog, sourcesIndex) {
		const selectedLabel = this._val(dialog, "source_key");
		return (
			(dialog.__source_label_to_key || {})[selectedLabel] ||
			SourcesHelper.resolveDefaultKey({}, sourcesIndex) ||
			""
		);
	},

	_handleApply(frm, dialog, row, sourcesIndex, isChoice) {
		const mappingType = this._val(dialog, "mapping_type");
		const sourceKey = this._resolveSourceKey(dialog, sourcesIndex);
		const fieldname = this._fieldValue(dialog.get_value("frappe_field"));

		let newPointer = null;

		if (mappingType === "Frappe Field" && sourceKey && fieldname) {
			newPointer = { kind: "field", source_key: sourceKey, fieldname };
			this._applyValueMap(dialog, newPointer);
		} else if (mappingType === "Reference" && sourceKey && fieldname) {
			newPointer = { kind: "field", source_key: sourceKey, fieldname };

			const referenceType = this._val(dialog, "reference_type");
			if (referenceType) newPointer.reference_type = referenceType;

			const displayField = this._fieldValue(
				dialog.get_value("reference_display_field"),
			);
			if (displayField) newPointer.display_field = displayField;
		} else if (mappingType === "Expression") {
			const expression = this._val(dialog, "expression");
			if (expression)
				newPointer = { kind: "expression", source_key: sourceKey, expression };
		} else if (mappingType === "Fixed") {
			const raw = this._val(dialog, "fixed_value");
			if (raw)
				newPointer = { kind: "fixed", value: Utils.parseJsonOrString(raw) };
		}

		const defaultRaw = this._val(dialog, "default_value");
		if (newPointer && defaultRaw)
			newPointer.default = Utils.parseJsonOrString(defaultRaw);

		row.value_pointer = newPointer ? JSON.stringify(newPointer) : "";
		row.mapping_type = mappingType || "";
		row.frappe_field =
			mappingType === "Frappe Field" || mappingType === "Reference"
				? String(dialog.get_value("frappe_field") || "")
				: "";
		row.fixed_value =
			mappingType === "Fixed"
				? String(dialog.get_value("fixed_value") || "")
				: "";
		row.expression =
			mappingType === "Expression"
				? String(dialog.get_value("expression") || "")
				: "";
		row.default_value = String(dialog.get_value("default_value") || "");

		if (mappingType === "Reference") row.datatype = "Reference";

		if (isChoice) {
			const newFhirPath = this._val(dialog, "fhir_path");
			const newDatatype = this._val(dialog, "datatype");
			if (newFhirPath) row.fhir_path = newFhirPath;
			if (newDatatype) row.datatype = newDatatype;
		}

		frm.dirty();
		frm.refresh_field("element_maps");
		ElementsMapUI.render(frm);

		dialog.hide();
	},

	// fields shown per mapping type; everything else is hidden
	_VISIBLE_FIELDS: {
		"Frappe Field": ["source_key", "frappe_field", "value_map"],
		Reference: [
			"source_key",
			"frappe_field",
			"reference_type",
			"reference_display_field",
		],
		Expression: ["source_key", "expression"],
		Fixed: ["fixed_value"],
	},

	_applyVisibility(dialog) {
		const mappingType = this._val(dialog, "mapping_type");
		const visible = new Set(this._VISIBLE_FIELDS[mappingType] || []);

		for (const fieldname of [
			"source_key",
			"frappe_field",
			"reference_type",
			"reference_display_field",
			"expression",
			"fixed_value",
			"value_map",
		]) {
			this._setFieldHidden(dialog, fieldname, !visible.has(fieldname));
		}
		this._setFieldHidden(dialog, "default_value", !mappingType);
	},

	_setFieldHidden(dialog, fieldname, hidden) {
		const field = dialog.fields_dict?.[fieldname];
		if (!field) return;
		field.df.hidden = hidden ? 1 : 0;
		field.refresh();
	},

	async _refreshFieldOptions(dialog, sourcesIndex) {
		const mappingType = this._val(dialog, "mapping_type");
		const usesField = mappingType === "Frappe Field" || mappingType === "Reference";
		const usesSource = usesField || mappingType === "Expression";

		if (!usesSource) {
			dialog.__resolved_from_source_key = "";
			this._setFieldOptions(dialog, [""], false);
			return;
		}

		dialog.__resolved_from_source_key = this._resolveSourceKey(
			dialog,
			sourcesIndex,
		);

		// Expression maps the whole row via 'doc'; no field dropdown needed.
		const doctype = usesField
			? String(
					sourcesIndex[dialog.__resolved_from_source_key]?.doctype || "",
			  ).trim()
			: "";
		if (!doctype) {
			this._setFieldOptions(dialog, [""], false);
			return;
		}

		await frappe.model.with_doctype(doctype);
		const optionLines = await FieldOptionsBuilder.build(frappe.get_meta(doctype));
		this._setFieldOptions(dialog, optionLines, mappingType === "Reference");
	},

	_setFieldOptions(dialog, optionLines, includeDisplayField) {
		this._setSelectOptions(dialog, "frappe_field", optionLines);
		this._setSelectOptions(
			dialog,
			"reference_display_field",
			includeDisplayField ? optionLines : [""],
		);
	},

	_setSelectOptions(dialog, fieldname, options) {
		const field = dialog.fields_dict?.[fieldname];
		if (!field) return;
		field.df.options = (options || [""]).join("\n");
		field.refresh();
	},

	_appendKeyboardHint(dialog) {
		try {
			const modifier = /Mac|iPhone|iPad|iPod/.test(navigator.platform)
				? "⌘"
				: "Ctrl";
			const $footer = dialog.$wrapper?.find(".modal-footer");
			if (!$footer || !$footer.length) return;

			$footer.find(".fhir-map-kb-hint").remove();
			$footer.prepend(
				$(
					`<div class="text-muted fhir-map-kb-hint">${modifier} ↑ / ${modifier} ↓ to navigate</div>`,
				),
			);
		} catch (e) {}
	},

	async _closeActive(frm) {
		const d = frm._active_mapping_dialog;
		if (!d) return;

		await this._hideAndWait(d);

		frm._active_mapping_dialog = null;
		frm._active_mapping_row = null;
	},

	_hideAndWait(dialog) {
		return new Promise(resolve => {
			try {
				if (!dialog.$wrapper || !dialog.$wrapper.length) return resolve();
				dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_hide", () =>
					resolve(),
				);
				dialog.hide();
			} catch (e) {
				resolve();
			}
		});
	},
};

// =========================================================
// Field Options Builder
// =========================================================

const FieldOptionsBuilder = {
	async build(meta) {
		const optionLines = ["", "name|Name (name)"];

		for (const df of meta?.fields || []) {
			if (!df?.fieldname || SKIP_FIELDTYPES.has(df.fieldtype)) continue;

			const fieldname = String(df.fieldname).trim();
			const fieldLabel = String(df.label || df.fieldname).trim();

			if (df.fieldtype === "Table") {
				optionLines.push(
					...(await this._buildChildTableOptions(df, fieldname, fieldLabel)),
				);
			} else {
				optionLines.push(`${fieldname}|${fieldLabel} (${fieldname})`);
			}
		}

		return this._dedupe(optionLines);
	},

	async _buildChildTableOptions(df, parentFieldname, parentLabel) {
		const childDoctype = String(df.options || "").trim();
		if (!childDoctype) return [];

		await frappe.model.with_doctype(childDoctype);
		const childMeta = frappe.get_meta(childDoctype);

		const options = [];
		for (const childDf of childMeta?.fields || []) {
			if (!childDf?.fieldname || SKIP_FIELDTYPES.has(childDf.fieldtype)) continue;

			const value = `${parentFieldname}.${String(childDf.fieldname).trim()}`;
			const childLabel = String(childDf.label || childDf.fieldname).trim();
			options.push(`${value}|${parentLabel} → ${childLabel} (${value})`);
		}

		return options;
	},

	_dedupe(optionLines) {
		const seen = new Set();
		const out = [];
		let addedBlank = false;

		for (const line of optionLines || []) {
			if (!line) {
				if (!addedBlank) out.push("");
				addedBlank = true;
				continue;
			}

			const value = String(line).split("|")[0].trim();
			if (!value || seen.has(value)) continue;

			seen.add(value);
			out.push(line);
		}

		return out;
	},
};

// =========================================================
// Sources Helper
// =========================================================

const SourcesHelper = {
	buildIndex(frm) {
		const sourcesIndex = {};

		const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
		if (primaryDoctype)
			sourcesIndex["primary"] = { doctype: primaryDoctype, is_primary: 1 };

		for (const row of frm.doc.sources || []) {
			const key = String(row.source_key || "").trim();
			const dt = String(row.source_doctype || row.doctype || "").trim();
			if (key && dt) sourcesIndex[key] = { doctype: dt, is_primary: 0 };
		}

		return sourcesIndex;
	},

	buildSelectData(sourcesIndex) {
		const labels = [""];
		const labelToKey = {};
		const keyToLabel = {};

		const entries = Object.entries(sourcesIndex).sort((a, b) => {
			const ap = a[0] === "primary" ? 0 : 1;
			const bp = b[0] === "primary" ? 0 : 1;
			if (ap !== bp) return ap - bp;
			return String(a[1].doctype || "").localeCompare(String(b[1].doctype || ""));
		});

		for (const [key, info] of entries) {
			const dt = String(info.doctype || "").trim();
			if (!dt) continue;

			const label = key === "primary" ? `${dt} (Primary)` : dt;
			labels.push(label);
			labelToKey[label] = key;
			keyToLabel[key] = label;
		}

		return { labels, labelToKey, keyToLabel };
	},

	resolveDefaultKey(pointer, sourcesIndex) {
		const desired = String(pointer?.source_key || "").trim();
		if (desired && sourcesIndex[desired]) return desired;
		if (sourcesIndex.primary) return "primary";
		return Object.keys(sourcesIndex)[0] || "";
	},
};

// =========================================================
// Keyboard Navigation (Ctrl/⌘ + ↑/↓ between mapping rows)
// =========================================================

const KeyboardNavigation = {
	attach(frm, dialog) {
		this.detach(frm);

		const handler = e => {
			if (frm._active_mapping_dialog !== dialog) return;

			const modifierPressed = /Mac|iPhone|iPad|iPod/.test(navigator.platform)
				? e.metaKey
				: e.ctrlKey;
			if (!modifierPressed) return;

			const tag = (e.target?.tagName || "").toLowerCase();
			if (tag === "input" || tag === "textarea" || tag === "select") return;
			if ($(e.target).closest(".ace_editor, .CodeMirror, .cm-editor").length)
				return;

			if (e.key === "ArrowUp") {
				e.preventDefault();
				this._navigate(frm, -1).catch(() => {});
			} else if (e.key === "ArrowDown") {
				e.preventDefault();
				this._navigate(frm, +1).catch(() => {});
			}
		};

		frm._mapping_keydown_handler = handler;
		document.addEventListener("keydown", handler, true);

		dialog.$wrapper?.one("hidden.bs.modal.fhir_map_nav_cleanup", () =>
			this.detach(frm),
		);
	},

	detach(frm) {
		const handler = frm._mapping_keydown_handler;
		if (!handler) return;

		try {
			document.removeEventListener("keydown", handler, true);
		} catch (e) {}

		frm._mapping_keydown_handler = null;
	},

	async _navigate(frm, delta) {
		if (frm._mapping_nav_busy) return;
		frm._mapping_nav_busy = true;

		const seq = ++frm._mapping_nav_seq;

		try {
			const rows = frm.doc.element_maps || [];
			const currentRow = frm._active_mapping_row;
			if (!rows.length || !currentRow) return;

			const currentIndex = rows.findIndex(r => r.name === currentRow.name);
			const nextRow = rows[currentIndex + delta];
			if (currentIndex < 0 || !nextRow) return;

			await MappingDialog._closeActive(frm);
			if (seq !== frm._mapping_nav_seq) return;

			await MappingDialog.open(frm, nextRow);
		} finally {
			frm._mapping_nav_busy = false;
		}
	},
};

// =========================================================
// Preview Dialog
// =========================================================

const PreviewDialog = {
	async open(frm) {
		if (!this._canPreview(frm)) return;

		const docname = await this._promptPrimaryDocument(frm);
		if (!docname) return;

		const result = await this._generate(frm, docname);
		if (result && result.resource) this._show(result.resource, result.issues || []);
	},

	_canPreview(frm) {
		if (
			!FormButtons._requireSaved(
				frm,
				__("Please save the FHIR Resource Map before previewing."),
			)
		) {
			return false;
		}

		if (!String(frm.doc.primary_doctype || "").trim()) {
			frappe.msgprint({
				title: __("Primary DocType Required"),
				message: __("Set a Primary DocType before previewing."),
				indicator: "orange",
			});
			return false;
		}

		return true;
	},

	_promptPrimaryDocument(frm) {
		return new Promise(resolve => {
			frappe.prompt(
				[
					{
						fieldtype: "Link",
						fieldname: "docname",
						label: __("{0} to Preview", [frm.doc.primary_doctype]),
						options: frm.doc.primary_doctype,
						reqd: 1,
					},
				],
				values => resolve(String(values.docname || "").trim()),
				__("Preview FHIR Resource"),
				__("Generate"),
			);
		});
	},

	async _generate(frm, docname) {
		const res = await frappe.call({
			method: API_METHODS.generate_fhir_resource,
			args: { resource_map_name: frm.doc.name, docname },
			freeze: true,
			freeze_message: __("Generating FHIR resource..."),
		});
		return res.message;
	},

	_show(resource, issues) {
		const json = Utils.safeJsonStringify(resource);

		const dialog = new frappe.ui.Dialog({
			title: __("FHIR Resource Preview"),
			size: "large",
			fields: [
				{ fieldtype: "HTML", fieldname: "issues_html" },
				{
					fieldtype: "Code",
					fieldname: "resource_json",
					label: __("Resource"),
					options: "JSON",
					read_only: 1,
				},
			],
			primary_action_label: __("Copy"),
			primary_action: () => {
				frappe.utils.copy_to_clipboard(json);
				dialog.hide();
			},
		});

		dialog.fields_dict.issues_html.$wrapper.html(this._issuesHtml(issues));
		dialog.show();
		dialog.set_value("resource_json", json);
	},

	_issuesHtml(issues) {
		if (!issues || !issues.length) return "";

		const items = issues
			.map(issue => `<li>${Utils.escapeHtml(issue)}</li>`)
			.join("");
		return `
			<div class="alert alert-warning" role="alert">
				<strong>${__("Generated with {0} issue(s):", [issues.length])}</strong>
				<ul class="mb-0 mt-2">${items}</ul>
			</div>
		`;
	},
};

// =========================================================
// Utilities
// =========================================================

const Utils = {
	safeJsonParse(text) {
		try {
			return text ? JSON.parse(text) : null;
		} catch (e) {
			return null;
		}
	},

	safeJsonStringify(value) {
		try {
			return JSON.stringify(value, null, 2);
		} catch (e) {
			return String(value);
		}
	},

	parseJsonOrString(text) {
		try {
			return JSON.parse(text);
		} catch (e) {
			return text;
		}
	},

	toInt(v) {
		const n = Number(v);
		return Number.isFinite(n) ? Math.trunc(n) : 0;
	},

	escapeHtml(s) {
		return frappe.utils.escape_html(String(s || ""));
	},
};
