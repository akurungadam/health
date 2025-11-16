<template>
  <div class="ot-nav">
    <div class="ot-left">
      <button class="ot-btn" @click="goPrev" title="Previous Day">◀</button>
      <div class="ot-date">{{ viewDateLabel }}</div>
      <button class="ot-btn" @click="goNext" :disabled="!canGoNext" title="Next Day">▶</button>
    </div>
    <div class="ot-right">
      <span v-if="usingSchedule" class="ot-badge">Entries are Editable</span>
      <span v-else class="ot-badge muted">Entries are Read-Only</span>
    </div>
  </div>

  <ResourceTimeline
    v-if="schedule"
    :key="'rt-' + viewDate + '-' + eventsKey + '-' + (isDark ? 'dark' : 'light')"
    :freeze="freezing"
    :date="viewDate"
    :resources="resources"
    :events="events"
    :startHour="6"
    :endHour="22"
    :minuteStep="5"
    :editable="editable"
    :resizable="editable"
    :dark="isDark"
    @event-update="onEventUpdate"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import ResourceTimeline from './ResourceTimeline.vue'

const fd = window.frappe?.datetime

/* ------------ state ------------ */
const getDocName = () =>
  window.cur_frm?.doc?.name || new URL(location.href).searchParams.get('name')

const schedule = ref(null)
const viewDate = ref(null)
const events = ref([])
const usingSchedule = ref(false)
const serverCanEdit = ref(false)
const freezing = ref(false)
const eventsKey = ref(0)

/* ------------ reactive theme ------------ */
function computeDeskTheme() {
  const boot = (window.frappe?.boot?.desk_theme || '').toLowerCase()
  const ls = (localStorage.getItem('desk_theme') || '').toLowerCase()
  const attr = (document.documentElement.getAttribute('data-theme') || '').toLowerCase()
  const bodyDark = document.body?.classList?.contains('dark') || false
  return boot.includes('dark') || ls.includes('dark') || attr.includes('dark') || bodyDark
}
const isDark = ref(computeDeskTheme())

let mo
function attachThemeObservers() {
  try {
    mo = new MutationObserver(() => { isDark.value = computeDeskTheme() })
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] })
    mo.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] })
  } catch { }
  window.addEventListener('storage', onStorageTheme, false)
}
function detachThemeObservers() {
  try { mo?.disconnect() } catch { }
  window.removeEventListener('storage', onStorageTheme, false)
}
function onStorageTheme(e) {
  if (e.key === 'desk_theme') isDark.value = computeDeskTheme()
}
/* remount timeline on theme flip so CSS vars/layout fully apply */
watch(isDark, async () => { eventsKey.value++; await nextTick() })

/* ------------ derived ------------ */
const schedDateISO = computed(() => schedule.value ? String(schedule.value.schedule_date || '').slice(0, 10) : null)
const viewDateLabel = computed(() => viewDate.value ? fd?.str_to_user(viewDate.value) : '')

const resources = computed(() => {
  const set = new Map()
  for (const e of events.value || []) {
    const id = String(e.resourceId || 'Unassigned')
    if (!set.has(id)) set.set(id, { id, title: id })
  }
  return Array.from(set.values()).sort((a, b) => String(a.title).localeCompare(String(b.title)))
})

const editable = computed(() => !!serverCanEdit.value)

/* today-only-future (client guard; server rechecks) */
const isFutureStartAllowed = (startStr) => {
  if (!usingSchedule.value) return false
  const today = fd?.get_today?.()
  if (!today || viewDate.value !== today) return true
  const nowTime = fd?.now_time?.()
  if (!nowTime) return true
  const t = (startStr.split(' ')[1] || '00:00:00')
  return t > nowTime
}

/* ------------ I/O ------------ */
async function fetchSchedule() {
  const name = getDocName()
  if (!name) return
  const { message } = await frappe.call({
    method: 'healthcare.healthcare.doctype.ot_schedule.ot_schedule.get_schedule_entries',
    args: { schedule_name: name }
  })
  schedule.value = message
  viewDate.value = String(message?.schedule_date || '').slice(0, 10)
}

let dayToken = 0
async function fetchDayEvents(dayISO) {
  const name = getDocName()
  if (!name || !dayISO) return
  const token = ++dayToken
  const { message } = await frappe.call({
    method: 'healthcare.healthcare.doctype.ot_schedule.ot_schedule.get_day_events',
    args: { schedule_name: name, date: dayISO }
  })
  if (token !== dayToken) return
  usingSchedule.value = (message?.source === 'schedule')
  serverCanEdit.value = !!message?.can_edit
  events.value = message?.events || []
  eventsKey.value++
}

/* ------------ nav ------------ */
const canGoNext = computed(() => !!viewDate.value && !!schedDateISO.value && viewDate.value < schedDateISO.value)

async function goPrev() {
  if (!viewDate.value) return
  viewDate.value = fd?.add_days(viewDate.value, -1)
  await nextTick(); await fetchDayEvents(viewDate.value)
}

async function goNext() {
  if (!canGoNext.value) return
  viewDate.value = fd?.add_days(viewDate.value, +1)
  await nextTick(); await fetchDayEvents(viewDate.value)
}

/* ------------ DnD ------------ */
async function onEventUpdate({ id, start, end, resourceId }) {
  if (!editable.value) {
    frappe?.msgprint?.(__("Editing is allowed only on this schedule's date (and if unlocked)."))
    return
  }
  if (!isFutureStartAllowed(start)) {
    frappe?.msgprint?.(__('Pick a time later than now for today.'))
    return
  }
  try {
    freezing.value = true
    await frappe.call({
      method: 'healthcare.healthcare.doctype.ot_schedule.ot_schedule.move_entry',
      args: { entry_name: id, planned_start: start, planned_end: end, service_unit: resourceId }
    })
    await frappe.call({
      method: 'healthcare.healthcare.doctype.ot_schedule.ot_schedule.reorder_entries',
      args: { schedule_name: getDocName() }
    })
    await fetchDayEvents(viewDate.value)
    await fetchSchedule()
  } catch (e) {
    console.error(e)
    frappe?.msgprint?.(e.message || 'Update failed')
  } finally {
    freezing.value = false
  }
}

/* ------------ boot ------------ */
onMounted(async () => {
  attachThemeObservers()
  await fetchSchedule()
  await fetchDayEvents(viewDate.value)

  // (optional) realtime refresh if other users mutate the doc
  if (frappe?.realtime?.on && getDocName()) {
    frappe.realtime.on(`doc_update:${getDocName()}`, () => {
      fetchSchedule()
      fetchDayEvents(viewDate.value)
    })
  }
})
onBeforeUnmount(() => {
  detachThemeObservers()
})
</script>

<style scoped>
.ot-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 12px
}

.ot-left {
  display: flex;
  align-items: center;
  gap: 12px
}

.ot-right {
  margin-left: auto
}

.ot-btn {
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer
}

.ot-btn[disabled] {
  opacity: .5;
  cursor: not-allowed
}

.ot-date {
  font-weight: 600
}

.ot-badge {
  margin-left: .5rem;
  font-size: .75rem;
  padding: .1rem .4rem;
  border-radius: .375rem;
  background: #eef2ff;
  border: 1px solid #c7d2fe
}

.ot-badge.muted {
  background: #f3f4f6;
  border-color: #e5e7eb
}
</style>
