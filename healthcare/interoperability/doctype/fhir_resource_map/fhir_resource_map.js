// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

/* eslint-disable */

// =========================================================
// Constants & Configuration
// =========================================================

const API_METHODS = {
	load_structure_definition_elements:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.load_structure_definition_elements",
	resolve_fhir_values:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.resolve_fhir_values",
	preview_fhir_resource:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.preview_fhir_resource",
	validate_fhir_mapping:
		"healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.validate_fhir_mapping",
};

const SKIP_FIELDTYPES = new Set([
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Fold",
]);

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
			frm._elements_map_state = {
				search: "",
				filterRequired: false,
				filterChoice: false,
				filterMapped: false,
				filterUnmapped: false,
			};
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
		state.filterRequired = false;
		state.filterChoice = false;
		state.filterMapped = false;
		state.filterUnmapped = false;
	},
};

// =========================================================
// Form Buttons
// =========================================================

const FormButtons = {
	setup(frm) {
		frm.clear_custom_buttons();
		this._addLoadStructureDefinitionButton(frm);
		this._addValidateMappingButton(frm);
		this._addResolvedValuesButton(frm);
		this._addPreviewButton(frm);
	},

	_addLoadStructureDefinitionButton(frm) {
		frm.add_custom_button(__("Load Structure Definition"), async () => {
			if (!frm.doc.base_structure_definition) {
				frappe.throw(__("Please select Base Structure Definition"));
			}

			frm.disable_save();
			try {
				const res = await frappe.call({
					method: API_METHODS.load_structure_definition_elements,
					args: { fhir_resource_map: frm.doc.name },
					freeze: true,
					freeze_message: __("Loading Structure Definition..."),
				});

				const elements = res.message || [];
				if (!elements.length) {
					frappe.msgprint(__("No elements found."));
					return;
				}

				frm.clear_table("element_maps");
				for (const row of elements) {
					const child = frm.add_child("element_maps");
					Object.assign(child, row);
				}

				frm.refresh_field("element_maps");
				ElementsMapUI.render(frm);
			} finally {
				frm.enable_save();
			}
		});
	},

	_addValidateMappingButton(frm) {
		frm.add_custom_button(
			__("Validate Mapping"),
			async () => {
				if (!frm.doc.name || frm.is_new()) {
					frappe.msgprint({
						title: __("Save Required"),
						message: __("Please save the document before validating."),
						indicator: "orange",
					});
					return;
				}

				if (frm.is_dirty()) {
					frappe.msgprint({
						title: __("Unsaved Changes"),
						message: __("Please save the document before validating."),
						indicator: "orange",
					});
					return;
				}

				const res = await frappe.call({
					method: API_METHODS.validate_fhir_mapping,
					args: { fhir_resource_map: frm.doc.name },
					freeze: true,
					freeze_message: __("Validating mapping..."),
				});

				Dialogs.showValidationResults(res.message || {});
			},
			__("Actions"),
		);
	},

	_addResolvedValuesButton(frm) {
		frm.add_custom_button(
			__("Get Resolved Values"),
			async () => {
				const primaryDoctype = this._getPrimaryDoctype(frm);
				if (!primaryDoctype) return;

				const primaryName = await Dialogs.promptPrimaryName(primaryDoctype);
				if (!primaryName) return;

				const res = await frappe.call({
					method: API_METHODS.resolve_fhir_values,
					args: {
						fhir_resource_map: frm.doc.name,
						primary_name: primaryName,
					},
					freeze: true,
					freeze_message: __("Resolving values..."),
				});

				Dialogs.showJson(__("Resolved Values"), res.message || {});
			},
			__("Actions"),
		);
	},

	_addPreviewButton(frm) {
		frm.add_custom_button(
			__("Preview FHIR Resource"),
			async () => {
				const primaryDoctype = this._getPrimaryDoctype(frm);
				if (!primaryDoctype) return;

				const primaryName = await Dialogs.promptPrimaryName(primaryDoctype);
				if (!primaryName) return;

				const response = await frappe.call({
					method: API_METHODS.preview_fhir_resource,
					args: {
						fhir_resource_map: frm.doc.name,
						primary_name: primaryName,
					},
					freeze: true,
					freeze_message: __("Building FHIR preview..."),
				});

				Dialogs.showFhirPreview(frm, response.message || response);
			},
			__("Actions"),
		);
	},

	_getPrimaryDoctype(frm) {
		const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
		if (!primaryDoctype) {
			frappe.msgprint({
				title: __("Missing config"),
				message: __("Set Primary DocType first."),
				indicator: "red",
			});
			return null;
		}
		return primaryDoctype;
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
		const state = FormState.getState(frm);

		wrapper.empty();
		wrapper.append(`
			<div class="elements-map-root">
				<div class="elements-map-toolbar-slot"></div>
				<div class="elements-map-table-slot"></div>
			</div>
		`);

		const toolbarSlot = wrapper.find(".elements-map-toolbar-slot");
		toolbarSlot.append(this._buildToolbar(state));
		this._bindToolbarEvents(frm, wrapper, state);
	},

	_renderTable(frm) {
		const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
		if (!wrapper) return;

		const state = FormState.getState(frm);
		const rows = (frm.doc.element_maps || []).map(this._normalizeRow);
		const filtered = this._applyFilters(rows, state);

		const tableSlot = wrapper.find(".elements-map-table-slot");
		tableSlot.empty();
		tableSlot.append(this._buildTable(frm, filtered));
		this._bindRowEvents(frm, wrapper);
	},

	_normalizeRow(row) {
		const fhirPath = String(row.fhir_path || "");
		const min = Utils.toInt(row.min);
		const pointer = Utils.safeJsonParse(String(row.value_pointer || "").trim());

		const isMapped =
			!!pointer &&
			typeof pointer === "object" &&
			!!String(pointer.kind || "").trim();

		return {
			...row,
			_ui_required: min >= 1,
			_ui_choice: fhirPath.includes("[x]"),
			_ui_mapped: isMapped,
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

		if (state.filterRequired) out = out.filter(r => r._ui_required);
		if (state.filterChoice) out = out.filter(r => r._ui_choice);
		if (state.filterMapped) out = out.filter(r => r._ui_mapped);
		if (state.filterUnmapped) out = out.filter(r => !r._ui_mapped);

		return out;
	},

	_buildToolbar(state) {
		const filters = [
			{
				class: "filter-required",
				label: "Required",
				checked: state.filterRequired,
			},
			{ class: "filter-choice", label: "Choice", checked: state.filterChoice },
			{ class: "filter-mapped", label: "Mapped", checked: state.filterMapped },
			{
				class: "filter-unmapped",
				label: "Unmapped",
				checked: state.filterUnmapped,
			},
		];

		const filterHtml = filters
			.map(
				f => `
				<label class="checkbox" style="margin:0;">
					<input type="checkbox" class="elements-map-${f.class}" ${f.checked ? "checked" : ""}/>
					<span style="margin-left:6px;">${f.label}</span>
				</label>
			`,
			)
			.join("");

		return $(`
			<div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
				<div style="flex:1; min-width:260px;">
					<input type="text" class="form-control elements-map-search"
						placeholder="Search path / datatype / short / mapping"
						value="${Utils.escapeHtml(state.search)}" />
				</div>
				${filterHtml}
				<button class="btn btn-default btn-sm elements-map-clear">Clear</button>
			</div>
		`);
	},

	_bindToolbarEvents(frm, wrapper, state) {
		const root = wrapper.find(".elements-map-root");

		root.find(".elements-map-search").on(
			"input",
			frappe.utils.debounce(e => {
				state.search = e.target.value || "";
				this._renderTable(frm);
			}, 120),
		);

		root.find(".elements-map-filter-required").on("change", e => {
			state.filterRequired = !!e.target.checked;
			this._renderTable(frm);
		});

		root.find(".elements-map-filter-choice").on("change", e => {
			state.filterChoice = !!e.target.checked;
			this._renderTable(frm);
		});

		root.find(".elements-map-filter-mapped").on("change", e => {
			state.filterMapped = !!e.target.checked;
			if (state.filterMapped) state.filterUnmapped = false;
			root.find(".elements-map-filter-unmapped").prop(
				"checked",
				state.filterUnmapped,
			);
			this._renderTable(frm);
		});

		root.find(".elements-map-filter-unmapped").on("change", e => {
			state.filterUnmapped = !!e.target.checked;
			if (state.filterUnmapped) state.filterMapped = false;
			root.find(".elements-map-filter-mapped").prop(
				"checked",
				state.filterMapped,
			);
			this._renderTable(frm);
		});

		root.find(".elements-map-clear").on("click", () => {
			FormState.resetFilters(frm);

			root.find(".elements-map-search").val("");
			root.find(".elements-map-filter-required").prop("checked", false);
			root.find(".elements-map-filter-choice").prop("checked", false);
			root.find(".elements-map-filter-mapped").prop("checked", false);
			root.find(".elements-map-filter-unmapped").prop("checked", false);

			this._renderTable(frm);
		});
	},

	_buildTable(frm, rows) {
		if (!rows.length) {
			return $(
				`<div class="text-muted" style="padding:12px;">No rows match filters.</div>`,
			);
		}

		const body = rows.map(r => this._buildTableRow(frm, r)).join("");

		return $(`
			<table class="table table-bordered table-hover" style="margin:0;">
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
			? `<div class="text-muted" style="font-size:12px; margin-top:4px;">${Utils.escapeHtml(
					r._ui_short,
			  )}</div>`
			: "";

		return `
			<tr class="elements-map-row" data-rowname="${Utils.escapeHtml(
				r.name,
			)}" style="cursor:pointer;">
				<td style="width:44%;">
					<div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
						<div style="font-weight:600;">${Utils.escapeHtml(r.fhir_path)}</div>
						<div>${pills}</div>
					</div>
					${hint}
				</td>
				<td style="width:14%;">${Utils.escapeHtml(r._ui_datatype || "")}</td>
				<td style="width:8%;">${Utils.escapeHtml(String(r._ui_min))}</td>
				<td style="width:8%;">${Utils.escapeHtml(String(r._ui_max || ""))}</td>
				<td style="width:26%;">${this._getMappingSummary(frm, r)}</td>
			</tr>
		`;
	},

	_bindRowEvents(frm, wrapper) {
		wrapper
			.find(".elements-map-row")
			.off("click")
			.on("click", async e => {
				const rowname = $(e.currentTarget).attr("data-rowname");
				if (!rowname) return;

				const row = (frm.doc.element_maps || []).find(r => r.name === rowname);
				if (!row) return;

				await MappingDialog.open(frm, row);
			});
	},

	_pill(text) {
		return `<span class="indicator-pill gray" style="margin-left:6px;">${Utils.escapeHtml(
			text,
		)}</span>`;
	},

	_getMappingSummary(frm, row) {
		const pointer = row._ui_pointer;
		if (!pointer || typeof pointer !== "object") {
			return `<span class="text-muted">Click to map</span>`;
		}

		const kind = String(pointer.kind || "").trim();

		if (kind === "field") {
			let label = String(pointer.source_key || "source_key");
			try {
				const sourcesIndex = SourcesHelper.buildIndex(frm);
				const dt = sourcesIndex?.[pointer.source_key]?.doctype;
				if (dt) {
					label = pointer.source_key === "primary" ? `${dt} (Primary)` : dt;
				}
			} catch (e) {}
			return `<span class="text-muted">${Utils.escapeHtml(
				label,
			)}</span> → ${Utils.escapeHtml(pointer.fieldname || "")}`;
		}

		if (kind === "fixed") {
			return `<span class="text-muted">Fixed</span>`;
		}

		return `<span class="text-muted">Mapped</span>`;
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
		this._setupDialogEvents(frm, dialog, sourcesIndex, pointer);

		dialog.show();

		this._applyVisibility(dialog);
		this._setInitialSourceKey(dialog, pointer, pointerKind);
		await this._refreshFieldOptions(dialog, sourcesIndex);
		this._appendKeyboardHint(dialog);
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
				options: "\nFrappe Field\nFixed",
				default: this._getMappingTypeDefault(pointer),
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

	_getMappingTypeDefault(pointer) {
		const kind = String(pointer.kind || "").trim();
		if (kind === "field") return "Frappe Field";
		if (kind === "fixed") return "Fixed";
		return "";
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

		if (dialog.$wrapper) {
			dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_clear", () => {
				if (frm._active_mapping_dialog === dialog) {
					frm._active_mapping_dialog = null;
					frm._active_mapping_row = null;
				}
			});
		}
	},

	_setupDialogEvents(frm, dialog, sourcesIndex, pointer) {
		const mappingTypeField = dialog.fields_dict?.mapping_type;
		if (mappingTypeField) {
			mappingTypeField.df.change = async () => {
				this._applyVisibility(dialog);
				await this._refreshFieldOptions(dialog, sourcesIndex);
			};
		}

		const sourceKeyField = dialog.fields_dict?.source_key;
		if (sourceKeyField) {
			sourceKeyField.df.change = async () => {
				await this._refreshFieldOptions(dialog, sourcesIndex);
			};
		}
	},

	_setInitialSourceKey(dialog, pointer, pointerKind) {
		if (pointerKind === "field") {
			const existingKey = String(pointer.source_key || "").trim();
			const label = dialog.__from_source_key_to_label?.[existingKey];
			if (label) dialog.set_value("source_key", label);
		}
	},

	_handleApply(frm, dialog, row, sourcesIndex, isChoice) {
		const mappingType = String(dialog.get_value("mapping_type") || "").trim();
		const selectedLabel = String(dialog.get_value("source_key") || "").trim();
		const sourceKey =
			(dialog.__source_label_to_key || {})[selectedLabel] ||
			SourcesHelper.resolveDefaultKey({}, sourcesIndex) ||
			"";

		let newPointer = null;

		if (mappingType === "Frappe Field") {
			const selected = String(dialog.get_value("frappe_field") || "").trim();
			const fieldname = selected.includes("|")
				? selected.split("|")[0].trim()
				: selected;

			if (sourceKey && fieldname) {
				newPointer = { kind: "field", source_key: sourceKey, fieldname };
			}
		} else if (mappingType === "Fixed") {
			const raw = String(dialog.get_value("fixed_value") || "").trim();
			if (raw) {
				newPointer = { kind: "fixed", value: Utils.parseJsonOrString(raw) };
			}
		}

		const defaultRaw = String(dialog.get_value("default_value") || "").trim();
		if (newPointer && defaultRaw) {
			newPointer.default = Utils.parseJsonOrString(defaultRaw);
		}

		row.value_pointer = newPointer ? JSON.stringify(newPointer) : "";
		row.mapping_type = mappingType || "";
		row.frappe_field =
			mappingType === "Frappe Field"
				? String(dialog.get_value("frappe_field") || "")
				: "";
		row.fixed_value =
			mappingType === "Fixed"
				? String(dialog.get_value("fixed_value") || "")
				: "";
		row.expression = "";
		row.json_path = "";
		row.default_value = String(dialog.get_value("default_value") || "") || "";

		if (isChoice) {
			const newFhirPath = String(dialog.get_value("fhir_path") || "").trim();
			const newDatatype = String(dialog.get_value("datatype") || "").trim();
			if (newFhirPath) row.fhir_path = newFhirPath;
			if (newDatatype) row.datatype = newDatatype;
		}

		frm.dirty();
		frm.refresh_field("element_maps");
		ElementsMapUI.render(frm);

		dialog.hide();
	},

	_applyVisibility(dialog) {
		const mappingType = String(dialog.get_value("mapping_type") || "").trim();

		this._setFieldHidden(dialog, "source_key", true);
		this._setFieldHidden(dialog, "frappe_field", true);
		this._setFieldHidden(dialog, "fixed_value", true);
		this._setFieldHidden(dialog, "default_value", !mappingType);

		if (mappingType === "Frappe Field") {
			this._setFieldHidden(dialog, "source_key", false);
			this._setFieldHidden(dialog, "frappe_field", false);
		} else if (mappingType === "Fixed") {
			this._setFieldHidden(dialog, "fixed_value", false);
		}
	},

	_setFieldHidden(dialog, fieldname, hidden) {
		const field = dialog.fields_dict?.[fieldname];
		if (!field) return;
		field.df.hidden = hidden ? 1 : 0;
		field.refresh();
	},

	async _refreshFieldOptions(dialog, sourcesIndex) {
		const mappingType = String(dialog.get_value("mapping_type") || "").trim();

		if (mappingType !== "Frappe Field") {
			this._setSelectOptions(dialog, "frappe_field", [""]);
			dialog.__resolved_from_source_key = "";
			return;
		}

		const selectedLabel = String(dialog.get_value("source_key") || "").trim();
		const labelToKey = dialog.__source_label_to_key || {};
		const sourceKey =
			labelToKey[selectedLabel] ||
			SourcesHelper.resolveDefaultKey({}, sourcesIndex) ||
			"";

		dialog.__resolved_from_source_key = sourceKey;

		const doctype = String(sourcesIndex[sourceKey]?.doctype || "").trim();
		if (!doctype) {
			this._setSelectOptions(dialog, "frappe_field", [""]);
			return;
		}

		await frappe.model.with_doctype(doctype);
		const meta = frappe.get_meta(doctype);
		const optionLines = await FieldOptionsBuilder.build(meta);
		this._setSelectOptions(dialog, "frappe_field", optionLines);
	},

	_setSelectOptions(dialog, fieldname, options) {
		const field = dialog.fields_dict?.[fieldname];
		if (!field) return;
		field.df.options = (options || [""]).join("\n");
		field.refresh();
	},

	_appendKeyboardHint(dialog) {
		try {
			const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
			const modifier = isMac ? "⌘" : "Ctrl";

			const $footer = dialog.$wrapper?.find(".modal-footer");
			if (!$footer || !$footer.length) return;

			$footer.find(".fhir-map-kb-hint").remove();
			$footer.prepend(
				$(
					`<div class="text-muted fhir-map-kb-hint" style="margin-right:auto; font-size:12px; padding-left:4px;">
						${modifier} ↑ / ${modifier} ↓ to navigate
					</div>`,
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
		const fields = Array.isArray(meta?.fields) ? meta.fields : [];

		for (const df of fields) {
			if (!df || !df.fieldname) continue;
			if (SKIP_FIELDTYPES.has(df.fieldtype)) continue;

			const fieldname = String(df.fieldname || "").trim();
			const fieldLabel = String(df.label || df.fieldname || "").trim();

			if (df.fieldtype === "Table") {
				const childOptions = await this._buildChildTableOptions(
					df,
					fieldname,
					fieldLabel,
				);
				optionLines.push(...childOptions);
				continue;
			}

			optionLines.push(`${fieldname}|${fieldLabel} (${fieldname})`);
		}

		return this._dedupe(optionLines);
	},

	async _buildChildTableOptions(df, parentFieldname, parentLabel) {
		const options = [];
		const childDoctype = String(df.options || "").trim();
		if (!childDoctype) return options;

		await frappe.model.with_doctype(childDoctype);
		const childMeta = frappe.get_meta(childDoctype);
		const childFields = Array.isArray(childMeta?.fields) ? childMeta.fields : [];

		for (const childDf of childFields) {
			if (!childDf || !childDf.fieldname) continue;
			if (SKIP_FIELDTYPES.has(childDf.fieldtype)) continue;

			const childFieldname = String(childDf.fieldname || "").trim();
			if (!childFieldname) continue;

			const childLabel = String(childDf.label || childDf.fieldname || "").trim();
			const value = `${parentFieldname}.${childFieldname}`;
			const label = `${parentLabel} → ${childLabel} (${value})`;

			options.push(`${value}|${label}`);
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
		if (primaryDoctype) {
			sourcesIndex["primary"] = { doctype: primaryDoctype, is_primary: 1 };
		}

		const rows = Array.isArray(frm.doc.sources) ? frm.doc.sources : [];
		for (const row of rows) {
			const key = String(row.source_key || "").trim();
			const dt = String(row.source_doctype || row.doctype || "").trim();
			if (!key || !dt) continue;
			sourcesIndex[key] = { doctype: dt, is_primary: 0 };
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
// Keyboard Navigation
// =========================================================

const KeyboardNavigation = {
	attach(frm, dialog) {
		this.detach(frm);

		const handler = e => {
			if (frm._active_mapping_dialog !== dialog) return;

			const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
			const modifierPressed = isMac ? e.metaKey : e.ctrlKey;
			if (!modifierPressed) return;

			const tag = (e.target?.tagName || "").toLowerCase();
			if (tag === "input" || tag === "textarea" || tag === "select") return;

			const $t = $(e.target);
			if ($t.closest(".ace_editor, .CodeMirror, .cm-editor").length) return;

			if (e.key === "ArrowUp") {
				e.preventDefault();
				this._navigate(frm, -1).catch(() => {});
			}

			if (e.key === "ArrowDown") {
				e.preventDefault();
				this._navigate(frm, +1).catch(() => {});
			}
		};

		frm._mapping_keydown_handler = handler;
		document.addEventListener("keydown", handler, true);

		if (dialog.$wrapper) {
			dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_cleanup", () => {
				this.detach(frm);
			});
		}
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
			if (!rows.length) return;

			const currentRow = frm._active_mapping_row;
			if (!currentRow) return;

			const currentIndex = rows.findIndex(r => r.name === currentRow.name);
			if (currentIndex < 0) return;

			const nextIndex = currentIndex + delta;
			if (nextIndex < 0 || nextIndex >= rows.length) return;

			const nextRow = rows[nextIndex];
			if (!nextRow) return;

			await MappingDialog._closeActive(frm);

			if (seq !== frm._mapping_nav_seq) return;

			await MappingDialog.open(frm, nextRow);
		} finally {
			frm._mapping_nav_busy = false;
		}
	},
};

// =========================================================
// Dialogs
// =========================================================

const Dialogs = {
	async promptPrimaryName(primaryDoctype) {
		return new Promise(resolve => {
			frappe.prompt(
				[
					{
						fieldtype: "Link",
						fieldname: "primary_name",
						label: __("Primary Document Name"),
						options: primaryDoctype,
						reqd: 1,
					},
				],
				values => {
					const primaryName =
						values && values.primary_name
							? String(values.primary_name).trim()
							: "";
					resolve(primaryName);
				},
				__("Select Primary Document"),
				__("Resolve"),
			);
		});
	},

	showJson(title, obj) {
		const pretty = Utils.safePrettyJson(obj);
		frappe.msgprint({
			title,
			message: `<pre style="max-height:60vh; overflow:auto">${Utils.escapeHtml(
				pretty,
			)}</pre>`,
			wide: true,
		});
	},

	showValidationResults(result) {
		const { is_valid, errors, warnings, error_count, warning_count } = result;

		const dialog = new frappe.ui.Dialog({
			title: __("Mapping Validation Results"),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "results_html" }],
			primary_action_label: __("Close"),
			primary_action: () => dialog.hide(),
		});

		dialog.show();

		const wrapper = dialog.get_field("results_html").$wrapper;
		wrapper.html(
			this._renderValidationResultsHtml(
				is_valid,
				errors,
				warnings,
				error_count,
				warning_count,
			),
		);
	},

	_renderValidationResultsHtml(
		is_valid,
		errors,
		warnings,
		error_count,
		warning_count,
	) {
		const statusHtml = is_valid
			? `<div class="mb-4">
				<span class="indicator-pill green">
					${__("Mapping is Valid")}
				</span>
			</div>`
			: `<div class="mb-4">
				<span class="indicator-pill red">
					${__("Mapping has Issues")}
				</span>
			</div>`;

		const summaryHtml = `
			<div class="mb-4" style="display:flex; gap:16px;">
				<div>
					<span class="text-danger font-weight-bold">${error_count}</span>
					<span class="text-muted">${__("Errors")}</span>
				</div>
				<div>
					<span class="text-warning font-weight-bold">${warning_count}</span>
					<span class="text-muted">${__("Warnings")}</span>
				</div>
			</div>
		`;

		let errorsHtml = "";
		if (errors && errors.length) {
			const errorItems = errors
				.map(e => {
					const path = e.fhir_path || e.source_key || "";
					const pathBadge = path
						? `<span class="badge badge-light mr-2">${Utils.escapeHtml(
								path,
						  )}</span>`
						: "";
					return `
						<div class="validation-item validation-error mb-2 p-2" style="background: var(--bg-red); border-radius: 4px;">
							<div style="display:flex; align-items:flex-start; gap:8px;">
								<span class="indicator red" style="margin-top:4px;"></span>
								<div>
									${pathBadge}
									<span>${Utils.escapeHtml(e.message || "")}</span>
									<div class="text-muted small mt-1">${Utils.escapeHtml(e.type || "")}</div>
								</div>
							</div>
						</div>
					`;
				})
				.join("");

			errorsHtml = `
				<div class="mb-4">
					<h6 class="text-danger">${__("Errors")}</h6>
					${errorItems}
				</div>
			`;
		}

		let warningsHtml = "";
		if (warnings && warnings.length) {
			const warningItems = warnings
				.map(w => {
					const path = w.fhir_path || w.source_key || "";
					const pathBadge = path
						? `<span class="badge badge-light mr-2">${Utils.escapeHtml(
								path,
						  )}</span>`
						: "";
					return `
						<div class="validation-item validation-warning mb-2 p-2" style="background: var(--bg-orange); border-radius: 4px;">
							<div style="display:flex; align-items:flex-start; gap:8px;">
								<span class="indicator orange" style="margin-top:4px;"></span>
								<div>
									${pathBadge}
									<span>${Utils.escapeHtml(w.message || "")}</span>
									<div class="text-muted small mt-1">${Utils.escapeHtml(w.type || "")}</div>
								</div>
							</div>
						</div>
					`;
				})
				.join("");

			warningsHtml = `
				<div class="mb-4">
					<h6 class="text-warning">${__("Warnings")}</h6>
					${warningItems}
				</div>
			`;
		}

		let noIssuesHtml = "";
		if (!errors?.length && !warnings?.length) {
			noIssuesHtml = `
				<div class="text-muted text-center p-4">
					<i class="fa fa-check-circle text-success fa-2x mb-2"></i>
					<div>${__("No issues found!")}</div>
				</div>
			`;
		}

		return `
			<div class="validation-results">
				${statusHtml}
				${summaryHtml}
				<hr/>
				${errorsHtml}
				${warningsHtml}
				${noIssuesHtml}
			</div>
		`;
	},

	showFhirPreview(frm, payload) {
		const resource =
			payload && (payload.resource || payload.fhir_resource || payload);
		const sourceIssues = (payload && payload.source_issues) || [];
		const valueIssues = (payload && payload.value_issues) || [];

		const errors = [
			...sourceIssues.map(x => `source: ${x.source_key}: ${x.error}`),
			...valueIssues.map(x => `value: ${x.fhir_path}: ${x.error}`),
		];
		const warnings = (payload && payload.compile_warnings) || [];
		const prettyJson = Utils.safePrettyJson(resource);

		const dialog = new frappe.ui.Dialog({
			title: __("FHIR Resource Preview"),
			size: "extra-large",
			fields: [
				{ fieldtype: "HTML", fieldname: "summary_html" },
				{ fieldtype: "HTML", fieldname: "json_html" },
			],
			primary_action_label: __("Copy JSON"),
			primary_action: () => Utils.copyToClipboard(prettyJson),
			secondary_action_label: __("Close"),
			secondary_action: () => dialog.hide(),
		});

		dialog.show();

		const summaryWrapper = dialog.get_field("summary_html").$wrapper;
		summaryWrapper.html(this._renderSummaryHtml(errors, warnings));

		const jsonWrapper = dialog.get_field("json_html").$wrapper;
		jsonWrapper.html(this._renderJsonBlockHtml(prettyJson));

		jsonWrapper.off("click.fhir_copy_inline");
		jsonWrapper.on("click.fhir_copy_inline", '[data-action="copy-inline"]', () => {
			Utils.copyToClipboard(prettyJson);
		});
	},

	_renderSummaryHtml(errors, warnings) {
		const errorHtml =
			errors && errors.length
				? `<div class="mb-2"><span class="indicator red">${__("Errors")}</span>
				   <ul class="mt-2">${errors
						.map(
							e =>
								`<li class="text-danger">${Utils.escapeHtml(
									String(e),
								)}</li>`,
						)
						.join("")}</ul></div>`
				: `<div class="mb-2"><span class="indicator green">${__(
						"Errors",
				  )}</span> <span class="text-muted">${__("None")}</span></div>`;

		const warningHtml =
			warnings && warnings.length
				? `<div class="mb-2"><span class="indicator orange">${__(
						"Warnings",
				  )}</span>
				   <ul class="mt-2">${warnings
						.map(
							w =>
								`<li class="text-warning">${Utils.escapeHtml(
									String(w),
								)}</li>`,
						)
						.join("")}</ul></div>`
				: `<div class="mb-2"><span class="indicator green">${__(
						"Warnings",
				  )}</span> <span class="text-muted">${__("None")}</span></div>`;

		return `<div>${errorHtml}${warningHtml}<hr/></div>`;
	},

	_renderJsonBlockHtml(prettyJson) {
		const escaped = Utils.escapeHtml(prettyJson || "");
		return `
			<div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
				<div class="text-muted">${__("Generated JSON")}</div>
				<button class="btn btn-xs btn-default" data-action="copy-inline">${__("Copy")}</button>
			</div>
			<pre class="small"
				style="max-height: 60vh; overflow:auto; background: var(--control-bg); border: 1px solid var(--border-color); padding: 12px; border-radius: 8px;"
			>${escaped}</pre>
		`;
	},
};

// =========================================================
// Utilities
// =========================================================

const Utils = {
	safeJsonParse(text) {
		try {
			if (!text) return null;
			return JSON.parse(text);
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

	safePrettyJson(obj) {
		try {
			return JSON.stringify(obj ?? {}, null, 2);
		} catch (e) {
			return JSON.stringify(
				{ error: "Could not stringify JSON", details: String(e) },
				null,
				2,
			);
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

	async copyToClipboard(text) {
		try {
			await navigator.clipboard.writeText(text || "");
			frappe.show_alert({
				message: __("Copied to clipboard"),
				indicator: "green",
			});
		} catch (e) {
			frappe.utils.copy_to_clipboard(text || "");
		}
	},
};
