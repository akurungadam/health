// ER triage vertical badge flag to the LEFT of the form title
// Robust across doctypes (e.g., Observation), clears reliably when ER is absent.
// No CSS files. Works on Frappe v14–v16.

(function () {
  "use strict";
  if (window.__ER_TITLE_FLAG_PATCHED__) return;
  window.__ER_TITLE_FLAG_PATCHED__ = true;

  const cache = Object.create(null);
  const pending = Object.create(null);

  function safeColor(c) {
    if (!c) return null;
    c = String(c).trim();
    return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(c) || /^[a-z]+$/i.test(c) ? c : null;
  }

  function isERField(df) {
    return !!(
      df &&
      (df.fieldname === "emergency_record" ||
        (df.fieldtype === "Link" && df.options === "Emergency Record"))
    );
  }

  // Resolve ER from: explicit value -> doc.emergency_record -> any ER Link on form -> control value
  function resolveER(frm, hintedValue, ctrl) {
    if (hintedValue) return hintedValue;
    if (frm?.doc?.emergency_record) return frm.doc.emergency_record;
    if (frm?.fields_dict) {
      for (const k in frm.fields_dict) {
        const f = frm.fields_dict[k];
        const df = f && f.df;
        if (isERField(df)) {
          const v = (f.get_value && f.get_value()) || (frm.doc && frm.doc[df.fieldname]);
          if (v) return v;
        }
      }
    }
    if (ctrl?.get_value) return ctrl.get_value();
    return null;
  }

  function titleTextEl(frm) {
    const $wrap = $(frm.page?.wrapper);
    return (
      $wrap.find(".page-title .title-text")[0] ||
      $wrap.find(".page-title")[0] ||
      $wrap.find(".title-text")[0] ||
      null
    );
  }

  function clearTitleFlag(frm) {
    const t = titleTextEl(frm);
    if (!t || !t.parentNode) return;
    t.parentNode.querySelectorAll(".er-title-flag").forEach((el) => el.remove());
  }

  function makeFlag(color, erName) {
    const c = frappe.utils.escape_html(safeColor(color) || "gray");
    const flag = document.createElement("span");
    flag.className = "er-title-flag";
    flag.dataset.erFor = erName || "";
    flag.style.cssText = [
      "display:inline-block",
      "width:10px",
      "height:18px",
      `background:${c}`,
      "margin-right:8px",
      "vertical-align:middle",
      "clip-path:polygon(0 0,100% 0,100% 100%,50% 85%,0 100%)",
      "box-shadow:0 0 0 1px rgba(0,0,0,.1) inset"
    ].join(";");
    return flag;
  }

  function upsertFlag(frm, erName) {
    if (!frm || !frm.page || !erName) return false;
    const t = titleTextEl(frm);
    if (!t || !t.parentNode) return false;

    // Always start clean
    clearTitleFlag(frm);

    const color = cache[erName] || "gray";
    const flag = makeFlag(color, erName);
    t.parentNode.insertBefore(flag, t);
    return true;
  }

  function repaintFlag(erName) {
    const color = safeColor(cache[erName]) || "gray";
    document
      .querySelectorAll(`.er-title-flag[data-er-for="${CSS.escape(erName)}"]`)
      .forEach((el) => (el.style.background = color));
  }

  async function hydrateColor(erName) {
    if (!erName || pending[erName] || (erName in cache)) return;
    pending[erName] = true;
    try {
      const er = await frappe.db.get_value("Emergency Record", erName, [
        "triage_color",
        "triage_level",
      ]);
      const m = er?.message || {};
      let color = safeColor(m.triage_color);
      if (!color && m.triage_level) {
        const tl = await frappe.db.get_value("Triage Level", m.triage_level, "color");
        color = safeColor(tl?.message?.color);
      }
      cache[erName] = color || null;
      repaintFlag(erName);
    } catch (e) {
      cache[erName] = null;
      console.warn("[ER triage] fetch failed:", e);
    } finally {
      delete pending[erName];
    }
  }

  // Retries title insertion (handles Observation / lazy title renders)
  function scheduleFlag(frm, hintedValue, ctrl, tries = 16) {
    if (!frm) return;
    // If no ER, ensure cleared and stop early.
    const erName = resolveER(frm, hintedValue, ctrl);
    if (!erName) {
      clearTitleFlag(frm);
      return;
    }

    const ok = upsertFlag(frm, erName);
    if (!ok) {
      if (tries > 0) setTimeout(() => scheduleFlag(frm, hintedValue, ctrl, tries - 1), 120);
      return;
    }

    if (!(erName in cache)) hydrateColor(erName);
  }

  // Patch ControlLink to react on ER link fields
  function patchControlLink() {
    if (!(frappe?.ui?.form?.ControlLink)) return void setTimeout(patchControlLink, 120);
    const Ctrl = frappe.ui.form.ControlLink;
    if (Ctrl.__er_title_flag_patched) return;

    const orig_set = Ctrl.prototype.set_formatted_input;
    Ctrl.prototype.set_formatted_input = function (value) {
      if (typeof orig_set === "function") orig_set.call(this, value);
      try {
        if (!cur_frm) return;
        if (isERField(this.df)) {
          scheduleFlag(cur_frm, value, this);
        } else {
          // Any other field changed → if no ER, clear
          scheduleFlag(cur_frm, null, null, 1);
        }
      } catch (e) {
        console.warn("[ER triage] set_formatted_input error:", e);
      }
    };

    const orig_make = Ctrl.prototype.make_input;
    Ctrl.prototype.make_input = function () {
      const out = orig_make ? orig_make.call(this) : undefined;
      try {
        if (!cur_frm) return;
        if (isERField(this.df)) {
          const v = (this.get_value && this.get_value()) || cur_frm.doc[this.df.fieldname];
          scheduleFlag(cur_frm, v, this);
        } else {
          scheduleFlag(cur_frm, null, null, 1);
        }
      } catch (e) {
        console.warn("[ER triage] make_input error:", e);
      }
      return out;
    };

    Ctrl.__er_title_flag_patched = true;
    console.log("✅ ER triage title flag patch active");
  }

  // Patch Form lifecycle to clear early and re-evaluate after render
  function patchFormLifecycle() {
    if (!(frappe?.ui?.form?.Form)) return void setTimeout(patchFormLifecycle, 120);
    const FormCls = frappe.ui.form.Form;
    if (FormCls.__er_title_flag_form_patched) return;

    const orig_refresh = FormCls.prototype.refresh;
    FormCls.prototype.refresh = function () {
      // Clear immediately to avoid “sticking” when switching to a doc without ER
      clearTitleFlag(this);
      const res = orig_refresh ? orig_refresh.apply(this, arguments) : undefined;

      // After refresh, try to place (will no-op if no ER)
      setTimeout(() => scheduleFlag(this, null, null, 8), 0);
      return res;
    };

    const orig_onload_post_render = FormCls.prototype.onload_post_render;
    FormCls.prototype.onload_post_render = function () {
      const res = orig_onload_post_render ? orig_onload_post_render.apply(this, arguments) : undefined;
      // After the layout is fully drawn, try again (covers “sometimes” cases)
      setTimeout(() => scheduleFlag(this, null, null, 8), 0);
      return res;
    };

    // Some doctypes update title after save; re-evaluate
    const orig_after_save = FormCls.prototype.after_save;
    FormCls.prototype.after_save = function () {
      const res = orig_after_save ? orig_after_save.apply(this, arguments) : undefined;
      setTimeout(() => scheduleFlag(this, null, null, 6), 0);
      return res;
    };

    FormCls.__er_title_flag_form_patched = true;
  }

  // As a final safety net, observe the title container; when it changes, re-evaluate
  function installTitleObserver() {
    if (!window.MutationObserver) return;
    const attach = () => {
      if (!cur_frm || !cur_frm.page || !cur_frm.page.wrapper) return;
      const wrap = cur_frm.page.wrapper;
      if (wrap.__erObserver) return;

      const observer = new MutationObserver(() => {
        // Each DOM change around the title → try once; no heavy retries here
        scheduleFlag(cur_frm, null, null, 1);
      });
      const node = $(wrap).find(".page-head, .page-title, .title-text").get(0) || wrap;
      observer.observe(node, { childList: true, subtree: true, attributes: true });
      wrap.__erObserver = observer;
    };

    // Try now and on each desk ajax swap
    attach();
    $(document).on("frappe-after-ajax", attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      patchControlLink();
      patchFormLifecycle();
      installTitleObserver();
    });
  } else {
    patchControlLink();
    patchFormLifecycle();
    installTitleObserver();
  }

  $(document).on("frappe-after-ajax", () => {
    // New form mounted → clean first, then attempt insert
    if (window.cur_frm) {
      clearTitleFlag(cur_frm);
      scheduleFlag(cur_frm, null, null, 10);
    }
  });
})();
