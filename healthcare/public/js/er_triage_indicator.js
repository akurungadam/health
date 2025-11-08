// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

(function () {
  "use strict";
  if (window.__ER_TITLE_FLAG_PATCHED__) return;
  window.__ER_TITLE_FLAG_PATCHED__ = true;

  const cache = Object.create(null);
  const pending = Object.create(null);

  function safe_color(c) {
    if (!c) return null;
    c = String(c).trim();
    return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(c) || /^[a-z]+$/i.test(c) ? c : null;
  }

  function is_er_field(df) {
    return (
      df &&
      (df.fieldname === "emergency_record" ||
        (df.fieldtype === "Link" && df.options === "Emergency Record"))
    );
  }

  // --- ER resolver: value -> doc.emergency_record -> any ER Link on form
  function resolve_er(frm, hinted_value, ctrl) {
    if (hinted_value) return hinted_value;
    if (frm?.doc?.emergency_record) return frm.doc.emergency_record;
    if (frm?.fields_dict) {
      for (const k in frm.fields_dict) {
        const f = frm.fields_dict[k];
        const df = f && f.df;
        if (is_er_field(df)) {
          const v = (f.get_value && f.get_value()) || (frm.doc && frm.doc[df.fieldname]);
          if (v) return v;
        }
      }
    }
    if (ctrl?.get_value) return ctrl.get_value();
    return null;
  }

  // --- build vertical badge (with bottom notch)
  function make_flag(color, er_name) {
    const c = frappe.utils.escape_html(safe_color(color) || "gray");
    const flag = document.createElement("span");
    flag.className = "er-title-flag";
    flag.dataset.erFor = er_name || "";
    flag.style.cssText = [
      "display:inline-block",
      "width:12px",
      "height:18px",
      `background:${c}`,
      "margin-right:8px",
      "vertical-align:middle",
      "clip-path:polygon(0 0,100% 0,100% 100%,50% 80%,0 100%)",
      "box-shadow:0 0 0 1px rgba(0,0,0,.1) inset"
    ].join(";");
    return flag;
  }

  function title_text_element(frm) {
    const $wrap = $(frm.page.wrapper);
    return (
      $wrap.find(".page-title .title-text")[0] ||
      $wrap.find(".page-title")[0] ||
      $wrap.find(".title-text")[0] ||
      null
    );
  }

  function clear_title_flag(frm) {
    const t = title_text_element(frm);
    if (!t || !t.parentNode) return;
    t.parentNode.querySelectorAll(".er-title-flag").forEach(el => el.remove());
  }

  function upsertFlag(frm, er_name) {
    if (!frm || !frm.page || !er_name) return false;
    const t = title_text_element(frm);
    if (!t || !t.parentNode) return false;

    // remove previous
    clear_title_flag(frm);

    const color = cache[er_name] || "gray";
    const flag = make_flag(color, er_name);
    t.parentNode.insertBefore(flag, t);
    return true;
  }

  function repaint_flag(er_name) {
    const color = safe_color(cache[er_name]) || "gray";
    document
      .querySelectorAll(`.er-title-flag[data-er-for="${CSS.escape(er_name)}"]`)
      .forEach(el => (el.style.background = color));
  }

  async function hydrate_color(er_name) {
    if (!er_name || pending[er_name] || (er_name in cache)) return;
    pending[er_name] = true;
    try {
      const er = await frappe.db.get_value("Emergency Record", er_name, ["triage_color", "triage_level"]);
      const m = er?.message || {};
      let color = safe_color(m.triage_color);
      if (!color && m.triage_level) {
        const tl = await frappe.db.get_value("Triage Level", m.triage_level, "color");
        color = safe_color(tl?.message?.color);
      }
      cache[er_name] = color || null;
      repaint_flag(er_name);
    } catch (e) {
      cache[er_name] = null;
      console.warn("[ER triage] fetch failed:", e);
    } finally {
      delete pending[er_name];
    }
  }

  function schedule_flag(frm, hinted_value, ctrl, tries = 10) {
    if (tries <= 0) return;
    const er_name = resolve_er(frm, hinted_value, ctrl);

    // if no ER on this form, ensure ANY leftover flag is removed and stop
    if (!er_name) {
      clear_title_flag(frm);
      return;
    }

    const ok = upsertFlag(frm, er_name);
    if (!ok) {
      setTimeout(() => schedule_flag(frm, hinted_value, ctrl, tries - 1), 100);
    } else if (!(er_name in cache)) {
      hydrate_color(er_name);
    }
  }

  // --- Patch ControlLink to react to ER link fields
  function patch_control_link() {
    if (!(frappe?.ui?.form?.ControlLink)) {
      return void setTimeout(patch_control_link, 120);
    }
    const Ctrl = frappe.ui.form.ControlLink;
    if (Ctrl.__er_title_flag_patched) return;

    const orig_set = Ctrl.prototype.set_formatted_input;
    Ctrl.prototype.set_formatted_input = function (value) {
      if (typeof orig_set === "function") orig_set.call(this, value);
      try {
        if (cur_frm) {
          if (is_er_field(this.df)) {
            // ER changed -> show/update flag
            schedule_flag(cur_frm, value, this);
          } else {
            // non-ER field changed -> if no ER on this form, clear any flag
            schedule_flag(cur_frm, null, null, 1);
          }
        }
      } catch (e) {
        console.warn("[ER triage] set_formatted_input error:", e);
      }
    };

    const orig_make = Ctrl.prototype.make_input;
    Ctrl.prototype.make_input = function () {
      const out = orig_make ? orig_make.call(this) : undefined;
      try {
        if (cur_frm) {
          if (is_er_field(this.df)) {
            const v = (this.get_value && this.get_value()) || cur_frm.doc[this.df.fieldname];
            schedule_flag(cur_frm, v, this);
          } else {
            // as each field mounts, if there's no ER on this form, ensure cleared
            schedule_flag(cur_frm, null, null, 1);
          }
        }
      } catch (e) {
        console.warn("[ER triage] make_input error:", e);
      }
      return out;
    };

    Ctrl.__er_title_flag_patched = true;
    console.log("ER triage vertical flag patch active (with cleanup)");
  }

  // --- Also hook Form.refresh to clean up on forms without ER
  function patch_form_refresh() {
    if (!(frappe?.ui?.form?.Form)) {
      return void setTimeout(patch_form_refresh, 120);
    }
    const FormCls = frappe.ui.form.Form;
    if (FormCls.__er_title_flag_form_patched) return;

    const orig_refresh = FormCls.prototype.refresh;
    FormCls.prototype.refresh = function () {
      const res = orig_refresh ? orig_refresh.apply(this, arguments) : undefined;
      try {
        // If current form has no ER anywhere, remove any leftover flag in its title
        const er_name = resolve_er(this, null, null);
        if (!er_name) clear_title_flag(this);
      } catch (e) {
        console.warn("[ER triage] refresh cleanup error:", e);
      }
      return res;
    };

    FormCls.__er_title_flag_form_patched = true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      patch_control_link();
      patch_form_refresh();
    });
  } else {
    patch_control_link();
    patch_form_refresh();
  }
  $(document).on("frappe-after-ajax", () => {
    patch_control_link();
    patch_form_refresh();
    // final sweep: if the freshly rendered form has no ER, clear any flag
    if (window.cur_frm) {
      const er_name = resolve_er(cur_frm, null, null);
      if (!er_name) clear_title_flag(cur_frm);
    }
  });
})();
