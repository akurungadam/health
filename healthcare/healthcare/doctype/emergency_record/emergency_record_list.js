// Emergency Record — indicator + exact-hex flag in list view
(function () {
  function normalizeHex(raw) {
    if (!raw) return null;
    let c = String(raw).trim();
    if (/^[0-9a-f]{6}$/i.test(c)) c = "#" + c;
    if (/^#[0-9a-f]{3}$/i.test(c)) {
      c = "#" + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
    }
    return /^#[0-9a-f]{6}$/i.test(c) ? c.toUpperCase() : null;
  }

  // Map arbitrary hex to the closest Frappe token for the left indicator pill
  function toIndicatorToken(raw) {
    if (!raw) return "grey";
    const named = String(raw).trim().toLowerCase();
    if (["red","orange","yellow","green","blue","purple","grey","gray"].includes(named)) {
      return named === "gray" ? "grey" : named;
    }
    const hex = normalizeHex(raw);
    if (!hex) return "grey";

    const r = parseInt(hex.slice(1,3), 16);
    const g = parseInt(hex.slice(3,5), 16);
    const b = parseInt(hex.slice(5,7), 16);

    // quick bins
    if (r >= 200 && g < 130 && b < 130) return "red";
    if (r >= 220 && g >= 120 && b < 100) return "orange";
    if (r >= 220 && g >= 200 && b < 140) return "yellow";
    if (g >= 170 && r < 150 && b < 150)  return "green";
    if (b >= 170 && r < 150 && g < 150)  return "blue";
    if (r >= 150 && b >= 150)            return "grey";
    return "grey";
  }

  // Tiny flag with exact hex (no CSS file)
  function hexFlag(raw) {
    const hex = normalizeHex(raw);
    const c = frappe.utils.escape_html(hex || "gray");
    return `<span style="
      display:inline-block;width:8px;height:14px;background:${c};
      margin-right:6px;vertical-align:baseline;
      clip-path:polygon(0 0,100% 0,100% 100%,50% 80%,0 100%);
      box-shadow:0 0 0 1px rgba(0,0,0,.12) inset;"></span>`;
  }

  frappe.listview_settings["Emergency Record"] = {
    has_indicator_for_draft: true,
    add_fields: ["triage_color", "triage_level"],

    get_indicator(doc) {
      const label = doc.triage_level || "Triage";
      const token = toIndicatorToken(doc.triage_color);
      const filter = doc.triage_level ? `triage_level,=,${doc.triage_level}` : null;
      return [label, token, filter];
    },

    formatters: {
      // prefix exact-hex flag next to the subject so you see the true color
      name(value, df, options, doc) {
        if (!doc) return value || "";
        return hexFlag(doc.triage_color) + frappe.format(value, df, options, doc);
      },
      // if you use a custom subject field instead of name:
      patient_details(value, df, options, doc) {
        if (!doc) return value || "";
        return hexFlag(doc.triage_color) + frappe.format(value, df, options, doc);
      },
    },
  };
})();
