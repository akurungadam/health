// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

/* eslint-disable */

frappe.ui.form.on("FHIR Resource Map", {
	refresh(frm) {
		init_state(frm);
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

	on_unload(frm) {
		try {
			detach_keyboard_navigation(frm);
		} catch (e) {}
	},
});

function init_state(frm) {
	if (!frm._elements_map_state) {
		frm._elements_map_state = {
			search: "",
			filterRequired: false,
			filterChoice: false,
			filterMapped: false,
			filterUnmapped: false,
		};
	}

	if (!frm._elements_map_ui_built) frm._elements_map_ui_built = false;

	if (!frm._active_mapping_dialog) frm._active_mapping_dialog = null;
	if (!frm._active_mapping_row) frm._active_mapping_row = null;

	if (frm._mapping_nav_busy === undefined) frm._mapping_nav_busy = false;
	if (frm._mapping_nav_seq === undefined) frm._mapping_nav_seq = 0;
	if (!frm._mapping_keydown_handler) frm._mapping_keydown_handler = null;
}

function add_buttons(frm) {
	frm.clear_custom_buttons();

	frm.add_custom_button(__("Load Structure Definition"), async () => {
		if (!frm.doc.base_structure_definition) {
			frappe.throw(__("Please select Base Structure Definition"));
		}

		frm.disable_save();
		try {
			const res = await frappe.call({
				doc: frm.doc,
				method: "get_elements_from_structure_definitions",
				args: { base_structure_definition: frm.doc.base_structure_definition },
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
			render_elements_map_html(frm);
		} finally {
			frm.enable_save();
		}
	});

	frm.add_custom_button(__("Resolve Sources"), async () => {
		const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
		if (!primaryDoctype) {
			frappe.msgprint({
				title: __("Missing config"),
				message: __("Set Primary DocType first."),
				indicator: "red",
			});
			return;
		}

		const primaryName = await prompt_primary_name(primaryDoctype);
		if (!primaryName) return;

		const res = await frappe.call({
			doc: frm.doc,
			method: "resolve_values_runtime",
			args: {
				primary_name: primaryName,
				include_docs: 0,
			},
			freeze: true,
			freeze_message: __("Resolving sources..."),
		});

		const out = res.message || {};
		console.log("resolve_sources_runtime:", out);

		frappe.msgprint({
			title: __("Resolved Sources"),
			message: `<pre style="max-height:60vh; overflow:auto">${frappe.utils.escape_html(
				JSON.stringify(out, null, 2),
			)}</pre>`,
			wide: true,
		});
	});

	frm.add_custom_button(__("Preview FHIR Resource"), async () => {
		const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
		if (!primaryDoctype) {
			frappe.msgprint({
				title: __("Missing config"),
				message: __("Set Primary DocType first."),
				indicator: "red",
			});
			return;
		}

		const primaryName = await prompt_primary_name(primaryDoctype);
		if (!primaryName) return;

		const response = await frappe.call({
			method: "healthcare.interoperability.doctype.fhir_resource_map.fhir_resource_map.build_resource_from_compiled",
			args: {
				fhir_resource_map: frm.doc.name,
				primary_name: primaryName,
			},
			freeze: true,
			freeze_message: __("Building FHIR preview..."),
		});

		const payload = response.message || response;
		show_fhir_preview_dialog(frm, payload);
	});
}

async function prompt_primary_name(primaryDoctype) {
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
}

/* ============================================================
   ELEMENTS MAP HTML
============================================================ */

function render_elements_map_html(frm) {
	const wrapper = frm.fields_dict.elements_map_html?.$wrapper;
	if (!wrapper) return;

	const state = frm._elements_map_state;

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

	const state = frm._elements_map_state;

	const rows = (frm.doc.element_maps || []).map(normalize_row_for_ui);
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
		_ui_pointer: pointer,
		_ui_min: min,
		_ui_max: String(row.max || "").trim(),
		_ui_datatype: String(row.datatype || "").trim(),
		_ui_short: String(row.short || "").trim(),
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
		<div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
			<div style="flex:1; min-width:260px;">
				<input type="text" class="form-control elements-map-search"
					placeholder="Search path / datatype / short / mapping"
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

			<button class="btn btn-default btn-sm elements-map-clear">Clear</button>
		</div>
	`);
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

	root.find(".elements-map-clear").on("click", () => {
		state.search = "";
		state.filterRequired = false;
		state.filterChoice = false;
		state.filterMapped = false;
		state.filterUnmapped = false;

		root.find(".elements-map-search").val("");
		root.find(".elements-map-filter-required").prop("checked", false);
		root.find(".elements-map-filter-choice").prop("checked", false);
		root.find(".elements-map-filter-mapped").prop("checked", false);
		root.find(".elements-map-filter-unmapped").prop("checked", false);

		render_table_only(frm);
	});
}

function build_table(rows) {
	if (!rows.length) {
		return $(
			`<div class="text-muted" style="padding:12px;">No rows match filters.</div>`,
		);
	}

	const body = rows
		.map(r => {
			const pills = [
				r._ui_required ? pill("Required") : "",
				r._ui_choice ? pill("Choice") : "",
				r._ui_mapped ? pill("Mapped") : pill("Unmapped"),
			].join("");

			const hint = r._ui_short
				? `<div class="text-muted" style="font-size:12px; margin-top:4px;">${escape_html(
						r._ui_short,
				  )}</div>`
				: "";

			return `
				<tr class="elements-map-row" data-rowname="${escape_html(
					r.name,
				)}" style="cursor:pointer;">
					<td style="width:44%;">
						<div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
							<div style="font-weight:600;">${escape_html(r.fhir_path)}</div>
							<div>${pills}</div>
						</div>
						${hint}
					</td>
					<td style="width:14%;">${escape_html(r._ui_datatype || "")}</td>
					<td style="width:8%;">${escape_html(String(r._ui_min))}</td>
					<td style="width:8%;">${escape_html(String(r._ui_max || ""))}</td>
					<td style="width:26%;">${mapping_summary(r)}</td>
				</tr>
			`;
		})
		.join("");

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
   Mapping dialog (Field + Fixed)
============================================================ */

async function open_mapping_dialog(frm, row) {
	await close_active_dialog(frm);

	const sourcesIndex = build_sources_index(frm);

	const pointer = safe_json_parse(String(row.value_pointer || "").trim()) || {};
	const pointerKind = String(pointer.kind || "").trim();

	const sourceSelect = build_source_select_data(sourcesIndex);
	const defaultKey = resolve_from_source_key_default(pointer, sourcesIndex);
	const defaultLabel = sourceSelect.keyToLabel[defaultKey] || "";

	const dialog = new frappe.ui.Dialog({
		title: __("Map FHIR Element"),
		fields: [
			{
				fieldtype: "Data",
				fieldname: "fhir_path",
				label: "FHIR Path",
				default: row.fhir_path,
				read_only: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "datatype",
				label: "Datatype",
				default: row.datatype || "",
				read_only: 1,
			},
			{ fieldtype: "Section Break", label: __("Mapping") },

			{
				fieldtype: "Select",
				fieldname: "mapping_type",
				label: "Mapping Type",
				options: "\nFrappe Field\nFixed",
				default:
					pointerKind === "field"
						? "Frappe Field"
						: pointerKind === "fixed"
						  ? "Fixed"
						  : "",
				change: async () => {
					apply_mapping_type_visibility(dialog);
					await refresh_field_options(dialog, sourcesIndex);
				},
			},

			{
				fieldtype: "Select",
				fieldname: "source_key",
				label: "Source",
				options: sourceSelect.labels.join("\n"),
				default: defaultLabel,
				change: async () => {
					await refresh_field_options(dialog, sourcesIndex);
				},
			},

			{
				fieldtype: "Select",
				fieldname: "frappe_field",
				label: "Frappe Field",
				options: [""].join("\n"),
				default: String(pointer.fieldname || row.frappe_field || ""),
			},

			{
				fieldtype: "Code",
				fieldname: "fixed_value",
				label: "Fixed Value",
				options: "JSON",
				default:
					pointer.kind === "fixed"
						? safe_json_stringify(pointer.value ?? null)
						: row.fixed_value || "",
			},
			{
				fieldtype: "Code",
				fieldname: "default_value",
				label: "Default Value (optional)",
				options: "JSON",
				default:
					pointer.default !== undefined
						? safe_json_stringify(pointer.default)
						: row.default_value || "",
			},
		],

		primary_action_label: __("Apply"),
		primary_action() {
			const mappingType = String(dialog.get_value("mapping_type") || "").trim();

			const selectedLabel = String(dialog.get_value("source_key") || "").trim();
			const sourceKey =
				(dialog.__source_label_to_key || {})[selectedLabel] ||
				resolve_from_source_key_default(pointer, sourcesIndex) ||
				"";

			let newPointer = null;

			if (mappingType === "Frappe Field") {
				const selected = String(dialog.get_value("frappe_field") || "").trim();
				// handles both "dob|Date of birth (dob)" and plain "dob"
				const fieldname = selected.includes("|")
					? selected.split("|")[0].trim()
					: selected;

				if (sourceKey && fieldname) {
					newPointer = {
						kind: "field",
						source_key: sourceKey,
						fieldname: fieldname,
					};
				}
			} else if (mappingType === "Fixed") {
				const raw = String(dialog.get_value("fixed_value") || "").trim();
				if (raw)
					newPointer = { kind: "fixed", value: parse_json_or_string(raw) };
			}

			const defaultRaw = String(dialog.get_value("default_value") || "").trim();
			if (newPointer && defaultRaw)
				newPointer.default = parse_json_or_string(defaultRaw);

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

			// nuked features
			row.expression = "";
			row.json_path = "";

			row.default_value = String(dialog.get_value("default_value") || "") || "";

			frm.dirty();
			frm.refresh_field("element_maps");
			render_elements_map_html(frm);

			dialog.hide();
		},
	});

	dialog.__source_label_to_key = sourceSelect.labelToKey;
	dialog.__from_source_key_to_label = sourceSelect.keyToLabel;

	frm._active_mapping_dialog = dialog;
	frm._active_mapping_row = row;

	attach_keyboard_navigation(frm, dialog);

	if (dialog.$wrapper) {
		dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_clear", () => {
			if (frm._active_mapping_dialog === dialog) {
				frm._active_mapping_dialog = null;
				frm._active_mapping_row = null;
			}
		});
	}

	dialog.show();

	apply_mapping_type_visibility(dialog);

	if (pointerKind === "field") {
		const existingKey = String(pointer.source_key || "").trim();
		const label = dialog.__from_source_key_to_label?.[existingKey];
		if (label) dialog.set_value("source_key", label);
	}

	refresh_field_options(dialog, sourcesIndex);
	append_keyboard_hint(dialog);
}

function apply_mapping_type_visibility(dialog) {
	const mappingType = String(dialog.get_value("mapping_type") || "").trim();

	set_dialog_hidden(dialog, "source_key", true);
	set_dialog_hidden(dialog, "frappe_field", true);
	set_dialog_hidden(dialog, "fixed_value", true);

	// show default_value only when mapping type selected
	set_dialog_hidden(dialog, "default_value", !mappingType);

	if (!mappingType) return;

	if (mappingType === "Frappe Field") {
		set_dialog_hidden(dialog, "source_key", false);
		set_dialog_hidden(dialog, "frappe_field", false);
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

async function refresh_field_options(dialog, sourcesIndex) {
	const mappingType = String(dialog.get_value("mapping_type") || "").trim();
	if (mappingType !== "Frappe Field") {
		set_select_options(dialog, "frappe_field", [""]);
		dialog.__resolved_from_source_key = "";
		return;
	}

	const selectedLabel = String(dialog.get_value("source_key") || "").trim();
	const labelToKey = dialog.__source_label_to_key || {};
	const sourceKey =
		labelToKey[selectedLabel] ||
		resolve_from_source_key_default({}, sourcesIndex) ||
		"";

	dialog.__resolved_from_source_key = sourceKey;

	const doctype = String(sourcesIndex[sourceKey]?.doctype || "").trim();
	if (!doctype) {
		set_select_options(dialog, "frappe_field", [""]);
		return;
	}

	// Load meta
	await frappe.model.with_doctype(doctype);
	const meta = frappe.get_meta(doctype);

	// Build options with labels + child table expansion
	const optionLines = await build_field_option_lines_with_labels_and_children(meta);

	set_select_options(dialog, "frappe_field", optionLines);
}

async function build_field_option_lines_with_labels_and_children(meta) {
	const optionLines = [""];

	const skipFieldtypes = new Set([
		"Section Break",
		"Column Break",
		"Tab Break",
		"HTML",
		"Button",
		"Fold",
	]);

	// Always include docname
	optionLines.push(`name|Name (name)`);

	const fields = Array.isArray(meta?.fields) ? meta.fields : [];

	for (const df of fields) {
		if (!df || !df.fieldname) continue;
		if (skipFieldtypes.has(df.fieldtype)) continue;

		const fieldname = String(df.fieldname || "").trim();
		const fieldLabel = String(df.label || df.fieldname || "").trim();

		// Child table expansion
		if (df.fieldtype === "Table") {
			const childDoctype = String(df.options || "").trim();
			if (!childDoctype) continue;

			await frappe.model.with_doctype(childDoctype);
			const childMeta = frappe.get_meta(childDoctype);
			const childFields = Array.isArray(childMeta?.fields)
				? childMeta.fields
				: [];

			for (const childDf of childFields) {
				if (!childDf || !childDf.fieldname) continue;
				if (skipFieldtypes.has(childDf.fieldtype)) continue;

				const childFieldname = String(childDf.fieldname || "").trim();
				if (!childFieldname) continue;

				const childLabel = String(
					childDf.label || childDf.fieldname || "",
				).trim();

				// ✅ value must be the real path you want to store
				const value = `${fieldname}.${childFieldname}`;

				// ✅ label is only for display
				const label = `${fieldLabel} → ${childLabel} (${value})`;

				optionLines.push(`${value}|${label}`);
			}

			continue;
		}

		// Normal field
		const label = `${fieldLabel} (${fieldname})`;
		optionLines.push(`${fieldname}|${label}`);
	}

	return dedupe_select_option_lines(optionLines);
}

function dedupe_select_option_lines(optionLines) {
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
		if (!value) continue;

		if (seen.has(value)) continue;
		seen.add(value);

		out.push(line);
	}

	return out;
}

function set_select_options(dialog, fieldname, options) {
	const field = dialog.fields_dict?.[fieldname];
	if (!field) return;
	field.df.options = (options || [""]).join("\n");
	field.refresh();
}

/* ============================================================
   Sources index (minimal)
============================================================ */

function build_sources_index(frm) {
	const sourcesIndex = {};

	const primaryDoctype = String(frm.doc.primary_doctype || "").trim();
	if (primaryDoctype) {
		sourcesIndex["primary"] = { doctype: primaryDoctype, is_primary: 1 };
	}

	const rows = Array.isArray(frm.doc.sources) ? frm.doc.sources : [];
	for (const row of rows) {
		const key = String(row.source_key || "").trim();
		const dt = String(row.source_doctype || "").trim();
		if (!key || !dt) continue;
		sourcesIndex[key] = { doctype: dt, is_primary: 0 };
	}

	return sourcesIndex;
}

function build_source_select_data(sourcesIndex) {
	const labels = [""];
	const labelToKey = {};
	const keyToLabel = {};

	const entries = Object.entries(sourcesIndex);

	entries.sort((a, b) => {
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
}

function resolve_from_source_key_default(pointer, sourcesIndex) {
	const desired = String(pointer?.source_key || "").trim();
	if (desired && sourcesIndex[desired]) return desired;
	if (sourcesIndex.primary) return "primary";
	return Object.keys(sourcesIndex)[0] || "";
}

/* ============================================================
   Keyboard navigation (Cmd/Ctrl + Up/Down)
============================================================ */

function attach_keyboard_navigation(frm, dialog) {
	detach_keyboard_navigation(frm);

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
			navigate_mapping_dialog(frm, -1).catch(() => {});
		}

		if (e.key === "ArrowDown") {
			e.preventDefault();
			navigate_mapping_dialog(frm, +1).catch(() => {});
		}
	};

	frm._mapping_keydown_handler = handler;

	document.addEventListener("keydown", handler, true);

	if (dialog.$wrapper) {
		dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_cleanup", () => {
			detach_keyboard_navigation(frm);
		});
	}
}

function detach_keyboard_navigation(frm) {
	const handler = frm._mapping_keydown_handler;
	if (!handler) return;

	try {
		document.removeEventListener("keydown", handler, true);
	} catch (e) {}

	frm._mapping_keydown_handler = null;
}

async function navigate_mapping_dialog(frm, delta) {
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

		await close_active_dialog(frm);

		if (seq !== frm._mapping_nav_seq) return;

		await open_mapping_dialog(frm, nextRow);
	} finally {
		frm._mapping_nav_busy = false;
	}
}

async function close_active_dialog(frm) {
	const d = frm._active_mapping_dialog;
	if (!d) return;

	await hide_dialog_and_wait(d);

	frm._active_mapping_dialog = null;
	frm._active_mapping_row = null;
}

function hide_dialog_and_wait(dialog) {
	return new Promise(resolve => {
		try {
			if (!dialog.$wrapper || !dialog.$wrapper.length) return resolve();

			dialog.$wrapper.one("hidden.bs.modal.fhir_map_nav_hide", () => resolve());
			dialog.hide();
		} catch (e) {
			resolve();
		}
	});
}

function append_keyboard_hint(dialog) {
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
}

/* ============================================================
   Tiny helpers
============================================================ */

function mapping_summary(row) {
	const pointer = row._ui_pointer;
	if (!pointer || typeof pointer !== "object") {
		return `<span class="text-muted">Click to map</span>`;
	}

	const kind = String(pointer.kind || "").trim();

	if (kind === "field") {
		let label = String(pointer.source_key || "source_key");
		try {
			const sourcesIndex = build_sources_index(cur_frm);
			const dt = sourcesIndex?.[pointer.source_key]?.doctype;
			if (dt) label = pointer.source_key === "primary" ? `${dt} (Primary)` : dt;
		} catch (e) {}
		return `<span class="text-muted">${escape_html(label)}</span> → ${escape_html(
			pointer.fieldname || "",
		)}`;
	}

	if (kind === "fixed") return `<span class="text-muted">Fixed</span>`;

	return `<span class="text-muted">Mapped</span>`;
}

function pill(text) {
	return `<span class="indicator-pill gray" style="margin-left:6px;">${escape_html(
		text,
	)}</span>`;
}

function safe_json_parse(text) {
	try {
		if (!text) return null;
		return JSON.parse(text);
	} catch (e) {
		return null;
	}
}

function safe_json_stringify(value) {
	try {
		return JSON.stringify(value, null, 2);
	} catch (e) {
		return String(value);
	}
}

function parse_json_or_string(text) {
	try {
		return JSON.parse(text);
	} catch (e) {
		return text;
	}
}

function to_int(v) {
	const n = Number(v);
	return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function escape_html(s) {
	return frappe.utils.escape_html(String(s || ""));
}

/* ============================================================
   FHIR preview dialog
============================================================ */

function show_fhir_preview_dialog(frm, payload) {
	const resource = payload && (payload.resource || payload.fhir_resource || payload);
	const errors = (payload && payload.errors) || [];
	const warnings = (payload && payload.warnings) || [];

	const prettyJson = safe_pretty_json(resource);

	const dialog = new frappe.ui.Dialog({
		title: __("FHIR Resource Preview"),
		size: "extra-large",
		fields: [
			{ fieldtype: "HTML", fieldname: "summary_html" },
			{ fieldtype: "HTML", fieldname: "json_html" },
		],
		primary_action_label: __("Copy JSON"),
		primary_action: () => copy_to_clipboard(prettyJson),
		secondary_action_label: __("Close"),
		secondary_action: () => dialog.hide(),
	});

	dialog.show();

	const summaryWrapper = dialog.get_field("summary_html").$wrapper;
	summaryWrapper.html(render_summary_html(errors, warnings));

	const jsonWrapper = dialog.get_field("json_html").$wrapper;
	jsonWrapper.html(render_json_block_html(prettyJson));

	// ✅ bind inline copy button (it existed but did nothing before)
	jsonWrapper.off("click.fhir_copy_inline");
	jsonWrapper.on("click.fhir_copy_inline", '[data-action="copy-inline"]', () => {
		copy_to_clipboard(prettyJson);
	});
}

function render_summary_html(errors, warnings) {
	const errorHtml =
		errors && errors.length
			? `<div class="mb-2"><span class="indicator red">${__("Errors")}</span>
		   <ul class="mt-2">${errors
				.map(
					e =>
						`<li class="text-danger">${frappe.utils.escape_html(
							String(e),
						)}</li>`,
				)
				.join("")}</ul></div>`
			: `<div class="mb-2"><span class="indicator green">${__(
					"Errors",
			  )}</span> <span class="text-muted">${__("None")}</span></div>`;

	const warningHtml =
		warnings && warnings.length
			? `<div class="mb-2"><span class="indicator orange">${__("Warnings")}</span>
		   <ul class="mt-2">${warnings
				.map(
					w =>
						`<li class="text-warning">${frappe.utils.escape_html(
							String(w),
						)}</li>`,
				)
				.join("")}</ul></div>`
			: `<div class="mb-2"><span class="indicator green">${__(
					"Warnings",
			  )}</span> <span class="text-muted">${__("None")}</span></div>`;

	return `<div>${errorHtml}${warningHtml}<hr/></div>`;
}

function render_json_block_html(prettyJson) {
	const escaped = frappe.utils.escape_html(prettyJson || "");
	return `
		<div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
			<div class="text-muted">${__("Generated JSON")}</div>
			<button class="btn btn-xs btn-default" data-action="copy-inline">${__("Copy")}</button>
		</div>
		<pre class="small"
			style="max-height: 60vh; overflow:auto; background: var(--control-bg); border: 1px solid var(--border-color); padding: 12px; border-radius: 8px;"
		>${escaped}</pre>
	`;
}

function safe_pretty_json(obj) {
	try {
		return JSON.stringify(obj ?? {}, null, 2);
	} catch (e) {
		return JSON.stringify(
			{ error: "Could not stringify JSON", details: String(e) },
			null,
			2,
		);
	}
}

async function copy_to_clipboard(text) {
	try {
		await navigator.clipboard.writeText(text || "");
		frappe.show_alert({ message: __("Copied to clipboard"), indicator: "green" });
	} catch (e) {
		frappe.utils.copy_to_clipboard(text || "");
	}
}
