import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

/**
 * Mounts the OT Calendar app.
 * Accepts either a selector string or an element, OR an options object like:
 *   { el: '#ot-calendar-root', scheduleName: 'OT-SCH-0001', initialDate: 'YYYY-MM-DD' }
 * If no props provided, App.vue will read from cur_frm (your current flow).
 */
window.OTCalendarMount = function (arg = '#ot-calendar-root') {
  let el, scheduleName, initialDate

  if (typeof arg === 'string' || arg instanceof HTMLElement) {
    el = arg
  } else if (arg && typeof arg === 'object') {
    el = arg.el || '#ot-calendar-root'
    scheduleName = arg.scheduleName
    initialDate = arg.initialDate
  } else {
    el = '#ot-calendar-root'
  }

  const root = typeof el === 'string' ? document.querySelector(el) : el
  if (!root) { console.warn('OTCalendarMount: element not found', el); return }

  // hot remount safe
  if (root.__ot_app__) { root.__ot_app__.unmount(); root.innerHTML = '' }

  const app = createApp(App, { scheduleName, initialDate })
  app.mount(root)
  root.__ot_app__ = app
}
