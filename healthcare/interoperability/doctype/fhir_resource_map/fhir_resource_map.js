// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

/* eslint-disable */

frappe.ui.form.on("FHIR Resource Map", {
	refresh(frm) {
		ensure_state(frm);
		add_buttons(frm);
		render_elements_map_html(frm);
	},

	base_structure_definition(frm) {
		render_elements_map_html(frm);
	},

	element_maps_add(frm) {
		render_elements_map_html(frm);
	},

	element_maps_remove(frm) {
		render_elements_map_html(frm);
	},
});

function ensure_state(frm) {
	if (!frm._elements_map_state) frm._elements_map_state = default_state();
	if (frm._active_element_index === undefined) frm._active_element_index = null;
	if (!frm._active_mapping_dialog) frm._active_mapping_dialog = null;
	if (!frm._elements_keydown_handler) frm._elements_keydown_handler = null;
	if (!frm._elements_map_ui_built) frm._elements_map_ui_built = false;
}

function default_state() {
	return {
		search: "",
		filterRequired: false,
		filterChoice: false,
		filterMapped: false,
		filterUnmapped: false,
	};
}

function add_buttons(frm) {
	frm.clear_custom_buttons();

	frm.add_custom_button(__("Load Structure Definition"), async () => {
		if (!frm.doc.base_structure_definition) {
			frappe.throw(__("Please select Base Structure Definition"));
		}

		frm.disable_save();
		try {
			const response = await frappe.call({
				doc: frm.doc,
				method: "get_elements_from_structure_definitions",
				args: { base_structure_definition: frm.doc.base_structure_definition },
				freeze: true,
				freeze_message: __("Loading Structure Definition..."),
			});

			const elements = response.message || [];
			if (!elements.length) {
				frappe.msgprint(
					__("No elements found in the base StructureDefinition / profiles."),
				);
				return;
			}

			frm.clear_table("element_maps");
			for (const row of elements) {
				const child = frm.add_child("element_maps");
				Object.assign(child, row);
			}

			frm.refresh_field("element_maps");
			render_elements_map_html(frm);
		} finally {
			frm.enable_save();
		}
	});

	frm.add_custom_button(__("Compile Mapping"), async () => {
		await frappe.call({ doc: frm.doc, method: "compile_map", freeze: true });
		await frm.reload_doc();
		frappe.show_alert({ message: __("Compiled"), indicator: "green" });
	});

	frm.add_custom_button(__("Preview"), () => open_preview_dialog(frm));
	frm.add_custom_button(__("Preview FHIR Resource"), () =>
		open_fhir_preview_dialog(frm),
	);
}

/* ============================================================
   ELEMENTS MAP HTML
============================================================ */

function render_elements_map_html(frm) {
	const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
	if (!wrapper) return;

	const state =
		frm._elements_map_state || (frm._elements_map_state = default_state());

	if (!frm._elements_map_ui_built) {
		wrapper.empty();

		wrapper.append(`
			<div class="elements-map-root">
				<div class="elements-map-toolbar-slot"></div>
				<div class="elements-map-table-slot"></div>
			</div>
		`);

		const toolbarSlot = wrapper.find(".elements-map-toolbar-slot");
		toolbarSlot.append(build_toolbar(state));

		bind_toolbar_events(frm, wrapper, state);
		frm._elements_map_ui_built = true;
	}

	render_table_only(frm);
}

function render_table_only(frm) {
	const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
	if (!wrapper) return;

	const state = frm._elements_map_state || default_state();

	const rows = (frm.doc.element_maps || []).map(r => normalize_row_for_ui(r));
	const filtered = apply_filters(rows, state);

	const tableSlot = wrapper.find(".elements-map-table-slot");
	tableSlot.empty();
	tableSlot.append(build_table(filtered));

	bind_row_events(frm, wrapper);
}

function normalize_row_for_ui(row) {
	const fhirPath = String(row.fhir_path || "");
	const min = to_int(row.min);

	const pointer = safe_json_parse(String(row.value_pointer || "").trim());
	const isMapped =
		!!pointer && typeof pointer === "object" && !!String(pointer.kind || "").trim();

	return {
		...row,
		_ui_required: min >= 1,
		_ui_choice: fhirPath.includes("[x]"),
		_ui_mapped: isMapped,
		_ui_min: min,
		_ui_max: String(row.max || "").trim(),
		_ui_profile: String(row.profile || "").trim(),
		_ui_datatype: String(row.datatype || "").trim(),
		_ui_short: String(row.short || "").trim(),
		_ui_pointer: pointer,
	};
}

function apply_filters(rows, state) {
	let out = rows;

	if (state.search) {
		const q = state.search.toLowerCase();
		out = out.filter(r => {
			return (
				String(r.fhir_path || "")
					.toLowerCase()
					.includes(q) ||
				String(r.datatype || "")
					.toLowerCase()
					.includes(q) ||
				String(r.short || "")
					.toLowerCase()
					.includes(q) ||
				String(r.profile || "")
					.toLowerCase()
					.includes(q) ||
				String(r.value_pointer || "")
					.toLowerCase()
					.includes(q)
			);
		});
	}

	if (state.filterRequired) out = out.filter(r => r._ui_required);
	if (state.filterChoice) out = out.filter(r => r._ui_choice);
	if (state.filterMapped) out = out.filter(r => r._ui_mapped);
	if (state.filterUnmapped) out = out.filter(r => !r._ui_mapped);

	return out;
}

function build_toolbar(state) {
	return $(`
		<div class="elements-map-toolbar" style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
			<div style="flex:1; min-width:260px;">
				<input type="text" class="form-control elements-map-search"
					placeholder="Search path / datatype / short / profile / mapping"
					value="${escape_html(state.search)}" />
			</div>

			<label class="checkbox" style="margin:0;">
				<input type="checkbox" class="elements-map-filter-required" ${
					state.filterRequired ? "checked" : ""
				}/>
				<span style="margin-left:6px;">Required</span>
			</label>

			<label class="checkbox" style="margin:0;">
				<input type="checkbox" class="elements-map-filter-choice" ${
					state.filterChoice ? "checked" : ""
				}/>
				<span style="margin-left:6px;">Choice</span>
			</label>

			<label class="checkbox" style="margin:0;">
				<input type="checkbox" class="elements-map-filter-mapped" ${
					state.filterMapped ? "checked" : ""
				}/>
				<span style="margin-left:6px;">Mapped</span>
			</label>

			<label class="checkbox" style="margin:0;">
				<input type="checkbox" class="elements-map-filter-unmapped" ${
					state.filterUnmapped ? "checked" : ""
				}/>
				<span style="margin-left:6px;">Unmapped</span>
			</label>

			<button class="btn btn-default btn-sm elements-map-clear-filters">Clear</button>
		</div>
	`);
}

function build_table(rows) {
	if (!rows.length) {
		return $(
			`<div class="text-muted" style="padding:12px;">No rows match the current filters.</div>`,
		);
	}

	const header = `
		<thead>
			<tr>
				<th style="width:44%;">FHIR Path</th>
				<th style="width:14%;">Datatype</th>
				<th style="width:8%;">Min</th>
				<th style="width:8%;">Max</th>
				<th style="width:26%;">Mapping</th>
			</tr>
		</thead>
	`;

	const body = rows
		.map(r => {
			const pills = [
				r._ui_required ? pill("Required") : "",
				r._ui_choice ? pill("Choice") : "",
				r._ui_profile ? pill("Profile") : "",
				r._ui_mapped ? pill("Mapped") : pill("Unmapped"),
			].join("");

			const shortHint = r._ui_short
				? `<div class="text-muted" style="font-size:12px; margin-top:4px;">${escape_html(
						r._ui_short,
				  )}</div>`
				: "";

			const profileHint = r._ui_profile
				? `<div class="text-muted" style="font-size:12px; margin-top:4px;">${escape_html(
						r._ui_profile,
				  )}</div>`
				: "";

			const mappingText = build_mapping_summary_from_row(r);

			return `
				<tr class="elements-map-row" data-rowname="${escape_html(
					r.name,
				)}" style="cursor:pointer;">
					<td>
						<div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
							<div style="font-weight:600;">${escape_html(r.fhir_path)}</div>
							<div>${pills}</div>
						</div>
						${shortHint}
						${profileHint}
					</td>
					<td>${escape_html(r._ui_datatype || "")}</td>
					<td>${escape_html(String(r._ui_min))}</td>
					<td>${escape_html(String(r._ui_max || ""))}</td>
					<td>${mappingText}</td>
				</tr>
			`;
		})
		.join("");

	return $(`
		<div class="elements-map-table-wrap">
			<table class="table table-bordered table-hover" style="margin:0;">
				${header}
				<tbody>${body}</tbody>
			</table>
		</div>
	`);
}

function build_mapping_summary_from_row(row) {
	const pointer = row._ui_pointer;

	if (pointer && typeof pointer === "object" && String(pointer.kind || "").trim()) {
		const kind = String(pointer.kind || "").trim();

		if (kind === "field" || kind === "json") {
			const srcKey = String(pointer.source || "").trim();
			const path = String(pointer.path || "").trim();
			return `<span class="text-muted">${escape_html(
				srcKey || "source",
			)}</span><span> → ${escape_html(path || "")}</span>`;
		}

		if (kind === "fixed") {
			const preview = preview_value(pointer.value);
			return `<span class="text-muted">Fixed</span><span> ${escape_html(
				preview,
			)}</span>`;
		}

		if (kind === "expr") {
			const expr = String(pointer.expr || "").trim();
			const text = expr ? expr.slice(0, 32) + (expr.length > 32 ? "…" : "") : "";
			return `<span class="text-muted">Expression</span><span> ${escape_html(
				text,
			)}</span>`;
		}

		return `<span class="text-muted">Mapped</span>`;
	}

	return `<span class="text-muted">Click to map</span>`;
}

function preview_value(value) {
	if (value === null) return "null";
	if (value === undefined) return "";
	if (typeof value === "string")
		return value.length > 40 ? value.slice(0, 40) + "…" : value;
	try {
		const s = JSON.stringify(value);
		return s.length > 40 ? s.slice(0, 40) + "…" : s;
	} catch (e) {
		return String(value);
	}
}

function pill(text) {
	return `<span class="indicator-pill gray" style="margin-left:6px;">${escape_html(
		text,
	)}</span>`;
}

function bind_toolbar_events(frm, wrapper, state) {
	const root = wrapper.find(".elements-map-root");

	root.find(".elements-map-search").on(
		"input",
		frappe.utils.debounce(e => {
			state.search = e.target.value || "";
			render_table_only(frm);
		}, 120),
	);

	root.find(".elements-map-filter-required").on("change", e => {
		state.filterRequired = !!e.target.checked;
		render_table_only(frm);
	});

	root.find(".elements-map-filter-choice").on("change", e => {
		state.filterChoice = !!e.target.checked;
		render_table_only(frm);
	});

	root.find(".elements-map-filter-mapped").on("change", e => {
		state.filterMapped = !!e.target.checked;
		if (state.filterMapped) state.filterUnmapped = false;
		root.find(".elements-map-filter-unmapped").prop(
			"checked",
			state.filterUnmapped,
		);
		render_table_only(frm);
	});

	root.find(".elements-map-filter-unmapped").on("change", e => {
		state.filterUnmapped = !!e.target.checked;
		if (state.filterUnmapped) state.filterMapped = false;
		root.find(".elements-map-filter-mapped").prop("checked", state.filterMapped);
		render_table_only(frm);
	});

	root.find(".elements-map-clear-filters").on("click", () => {
		Object.assign(state, default_state());
		root.find(".elements-map-search").val("");
		root.find(".elements-map-filter-required").prop("checked", false);
		root.find(".elements-map-filter-choice").prop("checked", false);
		root.find(".elements-map-filter-mapped").prop("checked", false);
		root.find(".elements-map-filter-unmapped").prop("checked", false);
		render_table_only(frm);
	});
}

function bind_row_events(frm, wrapper) {
	wrapper
		.find(".elements-map-row")
		.off("click")
		.on("click", async e => {
			const rowname = $(e.currentTarget).attr("data-rowname");
			if (!rowname) return;

			const row = (frm.doc.element_maps || []).find(r => r.name === rowname);
			if (!row) return;

			await open_mapping_dialog(frm, row);
		});
}

/* ============================================================
   Mapping Dialog (NEW SOURCES SCHEMA)
   - pointer.source = source_key
============================================================ */

async function open_mapping_dialog(frm, row) {
	close_active_dialog(frm);

	const rows = frm.doc.element_maps || [];
	const index = rows.findIndex(r => r.name === row.name);
	frm._active_element_index = index;

	const sourcesIndex = build_sources_index(frm); // keyed by source_key (and primary_source_key)
	const sourceKeysOrdered = build_ordered_source_keys(frm, sourcesIndex);

	const existingPointer =
		safe_json_parse(String(row.value_pointer || "").trim()) || {};
	const positionTitle = build_position_title(rows.length, index);
	const isChoiceRow =
		String(row.fhir_path || "").includes("[x]") ||
		String(row.datatype || "").includes(",");

	const dialog = new frappe.ui.Dialog({
		title: __("Map FHIR Element") + positionTitle,
		fields: [
			{
				fieldtype: "Data",
				fieldname: "fhir_path",
				label: "FHIR Path",
				default: row.fhir_path,
				read_only: isChoiceRow ? 0 : 1,
				description: isChoiceRow
					? __(
							"Choice element: pick a concrete path (e.g. deceasedBoolean, valueString)",
					  )
					: "",
			},
			{
				fieldtype: "Data",
				fieldname: "datatype",
				label: "Datatype",
				default: row.datatype || "",
				read_only: isChoiceRow ? 0 : 1,
				description: isChoiceRow
					? __(
							"Enter the chosen type (e.g. boolean, string, dateTime, Reference, CodeableConcept)",
					  )
					: "",
			},
			{ fieldtype: "Section Break" },
			{
				fieldtype: "Int",
				fieldname: "min",
				label: "Min",
				read_only: 1,
				default: row.min || 0,
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Data",
				fieldname: "max",
				label: "Max",
				read_only: 1,
				default: row.max || "",
			},

			{ fieldtype: "Section Break", label: __("Mapping") },

			{
				fieldtype: "Select",
				fieldname: "mapping_type",
				label: "Mapping Type",
				options: "\nFrappe Field\nFixed\nExpression\nJSON",
				default:
					pointer_kind_to_ui(existingPointer.kind) || row.mapping_type || "",
				change: async () => {
					apply_mapping_type_visibility(dialog);
					await refresh_dialog_field_options(dialog, sourcesIndex);
				},
			},

			{
				fieldtype: "Select",
				fieldname: "source_key",
				label: "Source",
				options: build_source_key_options_for_select(
					sourceKeysOrdered,
					sourcesIndex,
				),
				default: "", // set below (needs display string)
				change: async () => {
					await refresh_dialog_field_options(dialog, sourcesIndex);
				},
			},

			{
				fieldtype: "Select",
				fieldname: "frappe_field",
				label: "Frappe Field",
				options: [""].join("\n"),
				default: String(existingPointer.path || row.frappe_field || ""),
			},

			{
				fieldtype: "Data",
				fieldname: "json_path",
				label: "JSON Path",
				default: String(existingPointer.path || ""),
			},

			{
				fieldtype: "Code",
				fieldname: "expression",
				label: "Expression",
				options: "JavaScript",
				default: String(existingPointer.expr || row.expression || ""),
			},

			{
				fieldtype: "Code",
				fieldname: "fixed_value",
				label: "Fixed Value",
				options: "JSON",
				default:
					row.fixed_value ||
					(existingPointer.kind === "fixed"
						? JSON.stringify(existingPointer.value ?? null)
						: ""),
			},

			{
				fieldtype: "Code",
				fieldname: "default_value",
				label: "Default Value (optional fallback)",
				options: "JSON",
				default:
					existingPointer.default !== undefined
						? JSON.stringify(existingPointer.default)
						: String(row.default_value || ""),
			},
		],

		primary_action_label: __("Apply"),
		primary_action() {
			const values = get_dialog_values_safe(dialog);
			const pointer = build_pointer_from_dialog_values(values);

			const newPath = String(dialog.get_value("fhir_path") || "").trim();
			const newDatatype = String(dialog.get_value("datatype") || "").trim();

			if (isChoiceRow) {
				const validated = validate_choice_resolution(
					row.fhir_path,
					newPath,
					newDatatype,
				);
				if (!validated.ok) {
					frappe.msgprint(validated.message);
					return;
				}
			}

			row.fhir_path = newPath || row.fhir_path;
			row.datatype = newDatatype || row.datatype;

			row.mapping_type = values.mapping_type || "";
			row.frappe_field = values.frappe_field || "";
			row.expression = values.expression || "";
			row.fixed_value = values.fixed_value || "";
			row.default_value = values.default_value || "";
			row.value_pointer = pointer ? JSON.stringify(pointer) : "";

			frm.dirty();
			frm.refresh_field("element_maps");
			render_elements_map_html(frm);

			dialog.hide();
		},
	});

	frm._active_mapping_dialog = dialog;

	// Fix: set default Source select to the DISPLAY value (because options include "(Doctype)")
	const existingSourceKey = String(existingPointer.source || "").trim();
	if (existingSourceKey && sourcesIndex[existingSourceKey]) {
		const dt = String(sourcesIndex[existingSourceKey].doctype || "").trim();
		dialog.set_value(
			"source_key",
			dt ? `${existingSourceKey} (${dt})` : existingSourceKey,
		);
	} else {
		// default to primary
		const dt = String(sourcesIndex["primary"]?.doctype || "").trim();
		dialog.set_value("source_key", dt ? `primary (${dt})` : "primary");
	}

	dialog.show();
	append_shortcut_hint(dialog);
	attach_dialog_lifecycle_cleanup(frm, dialog);
	ensure_global_key_handler(frm);

	apply_mapping_type_visibility(dialog);
	refresh_dialog_field_options(dialog, sourcesIndex);
}

function get_dialog_values_safe(dialog) {
	const displayedField = dialog.get_value("frappe_field") || "";
	const resolvedField = resolve_select_display_to_value(
		dialog,
		"frappe_field",
		displayedField,
	);

	return {
		mapping_type: dialog.get_value("mapping_type") || "",
		source_key: dialog.get_value("source_key") || "",
		frappe_field: resolvedField,
		json_path: dialog.get_value("json_path") || "",
		expression: dialog.get_value("expression") || "",
		fixed_value: dialog.get_value("fixed_value") || "",
		default_value: dialog.get_value("default_value") || "",
	};
}

function pointer_kind_to_ui(kind) {
	if (kind === "field") return "Frappe Field";
	if (kind === "fixed") return "Fixed";
	if (kind === "expr") return "Expression";
	if (kind === "json") return "JSON";
	return "";
}

function build_pointer_from_dialog_values(values) {
	const mappingType = String(values.mapping_type || "").trim();
	const sourceKey = selected_source_key_from_raw(values.source_key);

	let pointer = null;
	if (!mappingType) return null;

	if (mappingType === "Frappe Field") {
		const fieldname = String(values.frappe_field || "").trim();
		if (!sourceKey || !fieldname) return null;
		pointer = { kind: "field", source: sourceKey, path: fieldname };
	}

	if (mappingType === "JSON") {
		const jsonPath = String(values.json_path || "").trim();
		if (!sourceKey || !jsonPath) return null;
		pointer = { kind: "json", source: sourceKey, path: jsonPath };
	}

	if (mappingType === "Expression") {
		const expr = String(values.expression || "").trim();
		if (!expr) return null;
		pointer = { kind: "expr", source: sourceKey || "", expr };
	}

	if (mappingType === "Fixed") {
		const raw = String(values.fixed_value || "").trim();
		if (!raw) return null;
		const fixed = parse_json_or_string_allow_blank_as_null(raw);
		pointer = { kind: "fixed", value: fixed };
	}

	const defaultRaw = String(values.default_value || "").trim();
	if (pointer && defaultRaw) {
		pointer.default = parse_json_or_string_allow_blank_as_null(defaultRaw);
	}

	return pointer;
}

function apply_mapping_type_visibility(dialog) {
	const mappingType = String(dialog.get_value("mapping_type") || "").trim();

	set_dialog_hidden(dialog, "source_key", true);
	set_dialog_hidden(dialog, "frappe_field", true);
	set_dialog_hidden(dialog, "json_path", true);
	set_dialog_hidden(dialog, "expression", true);
	set_dialog_hidden(dialog, "fixed_value", true);

	set_dialog_hidden(dialog, "default_value", !mappingType);

	if (!mappingType) return;

	if (mappingType === "Frappe Field") {
		set_dialog_hidden(dialog, "source_key", false);
		set_dialog_hidden(dialog, "frappe_field", false);
		return;
	}

	if (mappingType === "JSON") {
		set_dialog_hidden(dialog, "source_key", false);
		set_dialog_hidden(dialog, "json_path", false);
		return;
	}

	if (mappingType === "Expression") {
		set_dialog_hidden(dialog, "source_key", false);
		set_dialog_hidden(dialog, "expression", false);
		return;
	}

	if (mappingType === "Fixed") {
		set_dialog_hidden(dialog, "fixed_value", false);
		return;
	}
}

function set_dialog_hidden(dialog, fieldname, hidden) {
	const field = dialog.fields_dict?.[fieldname];
	if (!field) return;
	field.df.hidden = hidden ? 1 : 0;
	field.refresh();
}

function build_source_key_options_for_select(keysOrdered, sourcesIndex) {
	const lines = [""];
	for (const key of keysOrdered) {
		const meta = sourcesIndex[key];
		const dt = String(meta?.doctype || "").trim();
		lines.push(dt ? `${key} (${dt})` : key);
	}
	return lines.join("\n");
}

function selected_source_key_from_display(dialog) {
	const raw = String(dialog.get_value("source_key") || "").trim();
	return selected_source_key_from_raw(raw);
}

function selected_source_key_from_raw(raw) {
	const text = String(raw || "").trim();
	if (!text) return "";
	// "contacts (Contact)" => "contacts"
	const m = text.match(/^(.+?)\s*\(.+\)\s*$/);
	return (m ? m[1] : text).trim();
}

async function refresh_dialog_field_options(dialog, sourcesIndex) {
	const mappingType = String(dialog.get_value("mapping_type") || "").trim();
	const sourceKey = selected_source_key_from_display(dialog);

	if (mappingType !== "Frappe Field") {
		set_select_options_with_value_map(dialog, "frappe_field", [
			{ value: "", label: "" },
		]);
		return;
	}

	if (!sourceKey || !sourcesIndex[sourceKey]) {
		set_select_options_with_value_map(dialog, "frappe_field", [
			{ value: "", label: "" },
		]);
		return;
	}

	const doctype = String(sourcesIndex[sourceKey].doctype || "").trim();
	if (!doctype) {
		set_select_options_with_value_map(dialog, "frappe_field", [
			{ value: "", label: "" },
		]);
		return;
	}

	// Preserve current selection (it might be raw value from existingPointer.path)
	const currentRaw = String(dialog.get_value("frappe_field") || "").trim();
	const currentValue =
		resolve_select_display_to_value(dialog, "frappe_field", currentRaw) ||
		currentRaw;

	const options = await get_doctype_field_options_with_children(doctype);

	set_select_options_with_value_map(dialog, "frappe_field", [
		{ value: "", label: "" },
		...options,
	]);

	// Restore selection using display text
	if (currentValue) {
		const display = resolve_select_value_to_display(
			dialog,
			"frappe_field",
			currentValue,
		);
		if (display) dialog.set_value("frappe_field", display);
	}
}

function set_select_options_with_value_map(dialog, fieldname, options) {
	const field = dialog.fields_dict?.[fieldname];
	if (!field) return;

	const displayToValue = {};
	const valueToDisplay = {};

	const lines = (options || []).map(opt => {
		const value = String(opt.value || "").trim();
		const label = String(opt.label || value || "").trim();
		if (!value && !label) return "";

		const display = label ? `${label} (${value})` : value;

		displayToValue[display] = value;
		valueToDisplay[value] = display;

		return display;
	});

	if (!dialog._select_value_maps) dialog._select_value_maps = {};
	dialog._select_value_maps[fieldname] = { displayToValue, valueToDisplay };

	field.df.options = lines.join("\n");
	field.refresh();
}

function resolve_select_display_to_value(dialog, fieldname, displayOrValue) {
	const maps = dialog._select_value_maps?.[fieldname];
	const raw = String(displayOrValue || "").trim();
	if (!raw) return "";

	if (!maps) return raw;
	if (maps.valueToDisplay[raw]) return raw;

	return maps.displayToValue[raw] || raw;
}

function resolve_select_value_to_display(dialog, fieldname, value) {
	const maps = dialog._select_value_maps?.[fieldname];
	const v = String(value || "").trim();
	if (!v) return "";
	if (!maps) return v;
	return maps.valueToDisplay[v] || v;
}

/* ============================================================
   Sources indexing (NEW SOURCES SCHEMA)
   - sourcesIndex is keyed by source_key
============================================================ */

function build_sources_index(frm) {
	const sourcesIndex = {};

	// Primary source is implicit + reserved key: "primary"
	const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
	if (primaryDoctype) {
		sourcesIndex["primary"] = {
			doctype: primaryDoctype,
			config: { kind: "primary", doctype: primaryDoctype, _is_primary: 1 },
			is_primary: 1,
		};
	}

	// Additional sources come from child table "sources"
	const sources = Array.isArray(frm.doc.sources) ? frm.doc.sources : [];
	for (const s of sources) {
		const key = String(s.source_key || "").trim();
		if (!key) continue;

		const sourceDoctype = String(s.source_doctype || "").trim();
		if (!sourceDoctype) continue;

		const cfg = safe_json_parse(String(s.config || "").trim()) || {};
		sourcesIndex[key] = {
			doctype: sourceDoctype,
			config: cfg,
			is_primary: 0,
		};
	}

	return sourcesIndex;
}

function build_ordered_source_keys(frm, sourcesIndex) {
	const rows = Array.isArray(frm.doc.sources) ? frm.doc.sources : [];
	const primarySourceKey = String(frm.doc.primary_source_key || "patient").trim();

	const idxByKey = {};
	for (const row of rows) {
		const key = String(row.source_key || "").trim();
		if (!key) continue;
		const idx = Number(row.idx || 0);
		if (!idxByKey[key] || idx < idxByKey[key]) idxByKey[key] = idx;
	}

	return Object.keys(sourcesIndex).sort((a, b) => {
		const idxA = idxByKey[a] ?? Number.POSITIVE_INFINITY;
		const idxB = idxByKey[b] ?? Number.POSITIVE_INFINITY;

		if (idxA !== idxB) return idxA - idxB;

		// Primary key first if tie
		if (a === primarySourceKey && b !== primarySourceKey) return -1;
		if (b === primarySourceKey && a !== primarySourceKey) return 1;

		return a.localeCompare(b);
	});
}

/* ============================================================
   DocType field loading (with child table fields)
============================================================ */

async function get_doctype_field_options_with_children(doctype) {
	// Prefer server tree for best labels + child tables
	try {
		const res = await frappe.call({
			method: "healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.get_doctype_field_tree",
			args: { doctype },
		});

		const tree = res.message || null;
		if (tree) {
			const out = [{ value: "name", label: "ID" }];

			for (const f of tree.fields || []) {
				if (!f.fieldname) continue;
				out.push({ value: f.fieldname, label: String(f.label || f.fieldname) });
			}

			for (const t of tree.child_tables || []) {
				const tableField = String(t.table_field || "").trim();
				if (!tableField) continue;

				const tableLabel = String(t.label || tableField).trim();

				for (const cf of t.fields || []) {
					if (!cf.fieldname) continue;
					out.push({
						value: `${tableField}.${cf.fieldname}`,
						label: `${tableLabel} → ${String(cf.label || cf.fieldname)}`,
					});
				}
			}

			return out;
		}
	} catch (e) {
		// fallback below
	}

	// Fallback: client meta
	await frappe.model.with_doctype(doctype);
	const meta = frappe.get_meta(doctype);

	const out = [{ value: "name", label: "ID" }];

	for (const df of meta.fields || []) {
		if (!df.fieldname) continue;
		if (
			[
				"Section Break",
				"Column Break",
				"Tab Break",
				"HTML",
				"Button",
				"Fold",
			].includes(df.fieldtype)
		)
			continue;

		out.push({ value: df.fieldname, label: String(df.label || df.fieldname) });
	}

	return out;
}

/* ============================================================
   Dialog navigation + lifecycle
============================================================ */

function build_position_title(total, index) {
	if (!total || index == null || index < 0) return "";
	return ` <span class="text-muted" style="font-weight:400;">(${
		index + 1
	}/${total})</span>`;
}

function append_shortcut_hint(dialog) {
	const modifier = is_mac() ? "⌘" : "Ctrl";
	dialog.$wrapper.find(".modal-footer").prepend(
		$(`<div class="text-muted" style="margin-right:auto; font-size:12px; padding-left:4px;">
			${modifier} ↑ / ${modifier} ↓ to navigate
		</div>`),
	);
}

function attach_dialog_lifecycle_cleanup(frm, dialog) {
	dialog.$wrapper.on("hidden.bs.modal", () => {
		if (frm._active_mapping_dialog === dialog) {
			frm._active_mapping_dialog = null;
			frm._active_element_index = null;
		}
	});
}

function ensure_global_key_handler(frm) {
	if (frm._elements_keydown_handler) return;

	frm._elements_keydown_handler = e => {
		if (!frm._active_mapping_dialog) return;
		if (!is_modifier_pressed(e)) return;

		const tag = (e.target?.tagName || "").toLowerCase();
		if (tag === "input" || tag === "textarea" || tag === "select") return;

		if (e.key === "ArrowUp") {
			e.preventDefault();
			navigate_dialog(frm, -1);
		}

		if (e.key === "ArrowDown") {
			e.preventDefault();
			navigate_dialog(frm, +1);
		}
	};

	document.addEventListener("keydown", frm._elements_keydown_handler);
}

function navigate_dialog(frm, delta) {
	const rows = frm.doc.element_maps || [];
	if (!rows.length) return;

	const currentIndex = frm._active_element_index;
	if (currentIndex == null || currentIndex < 0) return;

	const nextIndex = currentIndex + delta;
	if (nextIndex < 0 || nextIndex >= rows.length) return;

	const nextRow = rows[nextIndex];
	if (!nextRow) return;

	close_active_dialog(frm);
	open_mapping_dialog(frm, nextRow);
}

function close_active_dialog(frm) {
	const dialog = frm._active_mapping_dialog;
	if (dialog) {
		try {
			dialog.hide();
		} catch (e) {}
	}
	frm._active_mapping_dialog = null;
}

/*======
CHOICE HELPERS
======*/

function validate_choice_resolution(originalPath, newPath, datatype) {
	const original = String(originalPath || "");
	const resolved = String(newPath || "").trim();
	const dt = String(datatype || "").trim();

	if (!original.includes("[x]")) return { ok: true };

	if (!resolved)
		return { ok: false, message: __("FHIR Path is required for choice elements.") };
	if (resolved.includes("[x]"))
		return {
			ok: false,
			message: __("Choice path cannot contain [x]. Pick a concrete path."),
		};

	const prefix = original.split("[x]")[0];
	if (!resolved.startsWith(prefix)) {
		return { ok: false, message: __("Resolved path must start with: ") + prefix };
	}

	const expectedSuffix = choice_suffix_from_datatype(dt);
	if (!expectedSuffix) {
		return {
			ok: false,
			message: __("Datatype looks invalid or unsupported: ") + dt,
		};
	}

	const expectedPath = original.replace("[x]", expectedSuffix);
	if (resolved !== expectedPath) {
		return {
			ok: false,
			message:
				__("Resolved path doesn't match datatype. Expected: ") + expectedPath,
		};
	}

	return { ok: true };
}

function choice_suffix_from_datatype(datatype) {
	const dt = String(datatype || "").trim();
	if (!dt) return "";

	const map = {
		boolean: "Boolean",
		integer: "Integer",
		decimal: "Decimal",
		string: "String",
		uri: "Uri",
		url: "Url",
		canonical: "Canonical",
		date: "Date",
		dateTime: "DateTime",
		time: "Time",
		instant: "Instant",
		base64Binary: "Base64Binary",
		oid: "Oid",
		id: "Id",
		markdown: "Markdown",
		unsignedInt: "UnsignedInt",
		positiveInt: "PositiveInt",
	};

	if (map[dt]) return map[dt];
	if (dt.toLowerCase() === "reference") return "Reference";
	if (dt[0] === dt[0].toUpperCase()) return dt;

	return dt.charAt(0).toUpperCase() + dt.slice(1);
}

/* ============================================================
   Preview (NEW: uses server methods preview_sources + preview_values)
============================================================ */

function open_preview_dialog(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__("Save this document before previewing."));
		return;
	}

	const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
	if (!primaryDoctype) {
		frappe.msgprint(__("Set Primary Source DocType (source_doctype) first."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Preview (Sources + Values)"),
		size: "extra-large",
		fields: [
			{
				fieldtype: "Data",
				fieldname: "primary_doctype",
				label: __("Primary DocType"),
				default: primaryDoctype,
				reqd: 1,
				readonly: 1,
			},
			{
				fieldtype: "Dynamic Link",
				fieldname: "primary_name",
				label: __("Primary Document Name"),
				options: "primary_doctype",
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Int",
				fieldname: "limit",
				label: __("Value rows limit"),
				default: 200,
			},
			{ fieldtype: "Section Break", label: __("Output") },
			{ fieldtype: "HTML", fieldname: "output" },
		],
		primary_action_label: __("Preview"),
		primary_action: async () => {
			const values = dialog.get_values();
			if (!values) return;

			set_preview_dialog_loading(dialog, true);

			try {
				const sourcesRes = await frappe.call({
					doc: frm.doc,
					method: "preview_sources",
					args: { primary_name: values.primary_name },
					freeze: true,
					freeze_message: __("Resolving sources..."),
				});

				const valuesRes = await frappe.call({
					doc: frm.doc,
					method: "preview_values",
					args: {
						primary_name: values.primary_name,
						limit: values.limit || 200,
					},
					freeze: true,
					freeze_message: __("Resolving values..."),
				});
				console.log(sourcesRes, valuesRes);

				render_preview_output(dialog, sourcesRes.message, valuesRes.message);
			} finally {
				set_preview_dialog_loading(dialog, false);
			}
		},
	});

	dialog.show();
	render_preview_output(dialog, null, null);
}

function set_preview_dialog_loading(dialog, isLoading) {
	dialog.set_primary_action(isLoading ? __("Loading...") : __("Preview"));
	dialog.get_primary_btn().prop("disabled", !!isLoading);
}

function render_preview_output(dialog, sourcesPayload, valuesPayload) {
	const wrapper = dialog.fields_dict.output.$wrapper;
	wrapper.empty();

	if (!sourcesPayload && !valuesPayload) {
		wrapper.html(
			`<div class="text-muted">${__(
				"Click Preview to fetch source + value resolution.",
			)}</div>`,
		);
		return;
	}

	const safe = v => frappe.utils.escape_html(String(v ?? ""));

	const sourcesHtml = sourcesPayload
		? `
		<div class="p-3 rounded border" style="margin-bottom:12px;">
			<div style="display:flex; justify-content:space-between; align-items:center;">
				<div class="font-weight-bold">${__("Sources")}</div>
				<div class="text-muted" style="font-size:12px;">${safe(
					sourcesPayload.primary_source_key || "",
				)}</div>
			</div>

			<div class="mt-2">
				<pre style="background:var(--control-bg); padding:10px; border-radius:8px; max-height:260px; overflow:auto; margin:0;">${safe(
					JSON.stringify(sourcesPayload.source_summaries || [], null, 2),
				)}</pre>
			</div>

			${
				(sourcesPayload.errors || []).length
					? `<div class="mt-2">
					 <div class="text-muted" style="font-size:12px; margin-bottom:6px;"><b>${__(
							"Errors",
						)}</b></div>
					 <pre style="background:var(--control-bg); padding:10px; border-radius:8px; max-height:180px; overflow:auto; margin:0;">${safe(
							JSON.stringify(sourcesPayload.errors || [], null, 2),
						)}</pre>
				   </div>`
					: ""
			}
		</div>
	`
		: "";

	const valuesHtml = valuesPayload
		? `
		<div class="p-3 rounded border">
			<div class="font-weight-bold">${__("Values (Element Map Preview)")}</div>
			<div class="mt-2">
				<pre style="background:var(--control-bg); padding:10px; border-radius:8px; max-height:520px; overflow:auto; margin:0;">${safe(
					JSON.stringify(valuesPayload.results || [], null, 2),
				)}</pre>
			</div>
		</div>
	`
		: "";

	wrapper.html(
		`${sourcesHtml}${valuesHtml}` ||
			`<div class="text-muted">${__("No results.")}</div>`,
	);
}

/* ============================================================
   Small utils
============================================================ */

function safe_json_parse(value) {
	if (!value) return null;
	if (typeof value === "object") return value;
	try {
		return JSON.parse(String(value));
	} catch (e) {
		return null;
	}
}

function is_modifier_pressed(e) {
	return !!(e.metaKey || e.ctrlKey);
}

function is_mac() {
	return /Mac|iPhone|iPad|iPod/i.test(navigator.platform);
}

function to_int(value) {
	const n = parseInt(value, 10);
	return Number.isFinite(n) ? n : 0;
}

function escape_html(text) {
	return frappe.utils.escape_html(String(text || ""));
}

function parse_json_or_string_allow_blank_as_null(raw) {
	if (raw === null || raw === undefined) return null;
	const text = String(raw).trim();
	if (text === "") return null;

	try {
		return JSON.parse(text);
	} catch (e) {
		return text;
	}
}

function open_fhir_preview_dialog(frm) {
	const primaryDoctype = (
		frm.doc.primary_doctype ||
		frm.doc.primary_document_type ||
		""
	).trim();

	if (!primaryDoctype) {
		frappe.msgprint("Set Primary Doctype first.");
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Preview FHIR Resource"),
		size: "extra-large",
		fields: [
			{
				fieldtype: "Link",
				fieldname: "primary_name",
				label: __("Primary Document"),
				options: primaryDoctype,
				reqd: 1,
			},
			{
				fieldtype: "Check",
				fieldname: "strict",
				label: __("Strict (fail fast)"),
				default: 1,
			},
			{ fieldtype: "Section Break" },
			{
				fieldtype: "HTML",
				fieldname: "output",
			},
		],
		primary_action_label: __("Run Preview"),
		primary_action: async values => {
			await run_fhir_preview(frm, dialog, values);
		},
	});

	dialog.show();
	render_fhir_preview_output(dialog, { loading: false, empty: true });
}

async function run_fhir_preview(frm, dialog, values) {
	render_fhir_preview_output(dialog, { loading: true });

	try {
		const response = await frm.call("preview_runtime_resource", {
			primary_name: values.primary_name,
			strict: values.strict ? 1 : 0,
		});

		const payload = response.message || {};
		render_fhir_preview_output(dialog, { loading: false, payload });
	} catch (e) {
		render_fhir_preview_output(dialog, {
			loading: false,
			payload: {
				resource: null,
				errors: ["Call failed. See console/logs."],
				warnings: [],
				source_summary: {},
			},
		});
		// eslint-disable-next-line no-console
		console.error(e);
	}
}

function render_fhir_preview_output(dialog, { loading, empty, payload }) {
	const wrapper = dialog.get_field("output").$wrapper;
	wrapper.empty();

	if (empty) {
		wrapper.html(`<div class="text-muted">Pick a document and run preview.</div>`);
		return;
	}

	if (loading) {
		wrapper.html(`<div class="text-muted">Generating…</div>`);
		return;
	}

	const errors = (payload && payload.errors) || [];
	const warnings = (payload && payload.warnings) || [];
	const resource = (payload && payload.resource) || null;
	const sourceSummary = (payload && payload.source_summary) || {};

	const resourceJson = resource ? JSON.stringify(resource, null, 2) : "";

	const html = `
    <div style="display:flex; gap:12px; align-items:flex-start;">
      <div style="flex:1; min-width: 320px;">
        <div style="margin-bottom: 8px;">
          <strong>Source Summary</strong>
          <pre class="small" style="max-height:180px; overflow:auto; background:var(--gray-50); padding:8px; border-radius:8px;">${escapeHtml(
				JSON.stringify(sourceSummary, null, 2),
			)}</pre>
        </div>

        <div style="margin-bottom: 8px;">
          <strong>Errors (${errors.length})</strong>
          <div style="max-height:160px; overflow:auto; background:var(--gray-50); padding:8px; border-radius:8px;">
            ${
				errors.length
					? `<ul style="margin:0; padding-left: 18px;">${errors
							.map(
								e =>
									`<li style="color: var(--red-600);">${escapeHtml(
										e,
									)}</li>`,
							)
							.join("")}</ul>`
					: `<div class="text-muted">None</div>`
			}
          </div>
        </div>

        <div>
          <strong>Warnings (${warnings.length})</strong>
          <div style="max-height:160px; overflow:auto; background:var(--gray-50); padding:8px; border-radius:8px;">
            ${
				warnings.length
					? `<ul style="margin:0; padding-left: 18px;">${warnings
							.map(
								w =>
									`<li style="color: var(--orange-600);">${escapeHtml(
										w,
									)}</li>`,
							)
							.join("")}</ul>`
					: `<div class="text-muted">None</div>`
			}
          </div>
        </div>
      </div>

      <div style="flex:2; min-width: 420px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <strong>FHIR JSON</strong>
          <button class="btn btn-sm btn-default" ${
				resourceJson ? "" : "disabled"
			} data-copy="1">
            Copy
          </button>
        </div>

        <pre style="max-height:520px; overflow:auto; background:var(--gray-50); padding:12px; border-radius:10px; border:1px solid var(--gray-200);">${escapeHtml(
			resourceJson || (errors.length ? "" : "// No resource output"),
		)}</pre>
      </div>
    </div>
  `;

	wrapper.html(html);

	wrapper.find('[data-copy="1"]').on("click", async () => {
		try {
			await navigator.clipboard.writeText(resourceJson);
			frappe.show_alert({ message: __("Copied"), indicator: "green" });
		} catch {
			frappe.msgprint("Copy failed (browser permissions).");
		}
	});
}

function escapeHtml(text) {
	return String(text || "")
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;");
}
