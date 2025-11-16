<template>
  <div class="rtv-card" :class="{ dark, freeze }"
    :style="{ '--lane-count': String(lanesComputed.length), '--hour-px': hourHeight + 'px', '--slot-px': slotPx + 'px' }">
    <!-- Header -->
    <div class="rtv-header">
      <div class="rtv-corner">{{ title || 'Schedule' }}</div>
      <div class="rtv-lanes">
        <div v-for="lane in lanesComputed" :key="lane.id" class="rtv-lane-title">{{ lane.title }}</div>
      </div>
    </div>

    <!-- Body -->
    <div class="rtv-body" :style="{ height: trackHeightPx + 'px' }">
      <!-- Time axis -->
      <div class="rtv-axis" :style="{ height: trackHeightPx + 'px' }">
        <div v-for="m in hourMarks" :key="m.key" class="rtv-tick" :style="{ top: m.top + '%' }">
          <span class="rtv-hour">{{ m.label }}</span>
        </div>
        <!-- Current time indicator on axis (dashed) -->
        <div v-if="showNowLine" class="rtv-nowline-axis" :style="{ top: nowPct + '%' }"></div>
      </div>

      <!-- Lanes Grid -->
      <div class="rtv-grid" :style="{ height: trackHeightPx + 'px' }">
        <div v-for="lane in lanesComputed" :key="lane.id" class="rtv-col">
          <div class="rtv-track" :data-lane="lane.id" :style="{ height: trackHeightPx + 'px' }">
            <!-- hour lines -->
            <div v-for="m in hourMarks" :key="m.key" class="rtv-rowline" :style="{ top: m.top + '%' }"></div>

            <!-- current time solid line per lane -->
            <!-- <div v-if="showNowLine" class="rtv-nowline" :style="{ top: nowPct + '%' }"></div> -->

            <!-- Events -->
            <div v-for="evt in lane.events" :key="evt.id" class="rtv-evt" :class="{ fasting: isFasting(evt) }"
              :style="eventStyle(evt)" :title="tooltipText(evt)" @mousedown.stop="onDragStart($event, lane.id, evt)"
              @touchstart.stop.prevent="onDragStart($event, lane.id, evt)">
              <div v-if="resizable && editable" class="rtv-handle rtv-handle-t"
                @mousedown.stop="onResizeStart($event, lane.id, evt, 'start')"
                @touchstart.stop.prevent="onResizeStart($event, lane.id, evt, 'start')"></div>

              <!-- 3-line, clamped. IMPORTANT: no inner title attributes so the native tooltip is always the full event one. -->
              <div class="rtv-label">
                <div class="rtv-topline">
                  <strong>{{ timeRange(evt) }}</strong>
                  <span v-if="evt.procedure || evt.template"> · {{ evt.procedure || evt.template }}</span>
                  <span v-if="isFasting(evt)" class="rtv-chip rtv-chip--fasting" aria-label="Fasting">Fasting</span>
                </div>
                <div class="rtv-main">
                  {{ evt.patient_name || evt.patient }}
                  <span v-if="evt.patient_age || evt.patient_gender"> · {{ [evt.patient_age,
                  evt.patient_gender].filter(Boolean).join('/') }}</span>
                  <span v-if="evt.patient_contact"> · {{ evt.patient_contact }}</span>
                </div>
                <div class="rtv-prac oneline">
                  {{ (evt.practitioner_name || '').trim() }}
                  <span v-if="evt.practitioner_contact"> · {{ evt.practitioner_contact }}</span>
                </div>
              </div>

              <div v-if="resizable && editable" class="rtv-handle rtv-handle-b"
                @mousedown.stop="onResizeStart($event, lane.id, evt, 'end')"
                @touchstart.stop.prevent="onResizeStart($event, lane.id, evt, 'end')"></div>
            </div>

            <!-- Ghost during DnD/resize -->
            <div v-if="ghost && String(ghost.laneId) === String(lane.id)" class="rtv-ghost"
              :class="{ invalid: invalidDrop }" :style="{ top: ghost.top + '%', bottom: ghost.bottom + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, reactive, watchEffect, onMounted, onBeforeUnmount, nextTick } from 'vue'

/* ======================= Props / Emits ======================= */
const props = defineProps({
  date: { type: String, required: true },                 // "YYYY-MM-DD"
  resources: { type: Array, default: () => [] },          // [{ id, title }]
  events: { type: Array, default: () => [] },             // [{ id, resourceId, start, end, ... }]
  startHour: { type: Number, default: 6 },
  endHour: { type: Number, default: 22 },
  minuteStep: { type: Number, default: 15 },
  editable: { type: Boolean, default: true },
  resizable: { type: Boolean, default: true },
  dark: { type: Boolean, default: false },
  hourHeight: { type: Number, default: 72 },
  freeze: { type: Boolean, default: false },
  title: { type: String, default: 'Schedule' },
})
const emit = defineEmits(['event-update'])

/* ======================= Time & Geometry Helpers ======================= */
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n))
const step = computed(() => Math.max(1, +props.minuteStep || 15))
const slotPx = computed(() => (props.hourHeight / 60) * step.value)
const dayStartMin = computed(() => (Number(props.startHour) || 0) * 60)
const dayEndMin = computed(() => (Number(props.endHour) || 0) * 60)
const totalMin = computed(() => Math.max(1, dayEndMin.value - dayStartMin.value))
const trackHeightPx = computed(() => Math.round((totalMin.value / 60) * props.hourHeight))

const baseYMD = () => (props.date || '2000-01-01').split('-').map(Number)
const parse = (val) => {
  if (val instanceof Date) return new Date(val)
  if (typeof val === 'number') return new Date(val)
  if (typeof val === 'string') {
    const m = val.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0), 0)
    const t = new Date(val); if (!isNaN(t)) return t
  }
  return new Date()
}
const minutesFromMidnight = (dt) => { const d = parse(dt); return d.getHours() * 60 + d.getMinutes() }
const snapMinutes = (min) => Math.round(min / step.value) * step.value
const mkDateFromRel = (minFromStart) => {
  const [y, m, d] = baseYMD()
  const mins = Math.round(minFromStart)
  const hh = Math.floor(mins / 60)
  const mm = mins % 60
  return new Date(y, m - 1, d, hh, mm, 0, 0)
}
const posPercent = (dt) => clamp(((minutesFromMidnight(dt) - dayStartMin.value) / totalMin.value) * 100, 0, 100)
const styleFromRange = (start, end) => {
  const top = posPercent(start)
  const endPct = posPercent(end)
  const bottom = clamp(100 - endPct, 0, 100)
  return { top: `${top}%`, bottom: `${bottom}%` }
}

/* ======================= Axis ======================= */
const hourMarks = computed(() => {
  const out = []
  for (let h = props.startHour; h <= props.endHour; h++) {
    const m = h * 60
    const top = ((m - dayStartMin.value) / totalMin.value) * 100
    out.push({ key: 'h' + h, top: clamp(top, 0, 100), label: String(h).padStart(2, '0') + ':00' })
  }
  return out
})

/* ======================= Labels & Tooltips ======================= */
const timeRange = (evt) => {
  const s = String(evt.start).split(' ')[1]?.slice(0, 5) || ''
  const e = String(evt.end).split(' ')[1]?.slice(0, 5) || ''
  return `${s}–${e}`
}
const timeProcTitle = (evt) => {
  const parts = [timeRange(evt)]
  const proc = evt.procedure || evt.template
  if (proc) parts.push(proc)
  return parts.join(' · ')
}
const patientLineTitle = (evt) => {
  const bits = [evt.patient_name || evt.patient]
  const demo = [evt.patient_age, evt.patient_gender].filter(Boolean).join('/')
  if (demo) bits.push(demo)
  if (evt.patient_contact) bits.push(evt.patient_contact)
  return bits.join(' · ')
}
const practitionerLineTitle = (evt) => {
  const bits = [(evt.practitioner_name || '').trim()]
  if (evt.practitioner_contact) bits.push(evt.practitioner_contact)
  return bits.join(' · ')
}
const tooltipText = (evt) => {
  const lines = [timeProcTitle(evt), patientLineTitle(evt), practitionerLineTitle(evt)].filter(Boolean)
  if (isFasting(evt)) {
    // put the fasting marker on the first line, same as the UI chip
    lines[0] = lines[0] ? `${lines[0]} · Fasting` : 'Fasting'
  }
  return lines.join('\n')
}
const eventStyle = (evt) => {
  const base = styleFromRange(evt.start, evt.end)
  if (evt.color) return { ...base, backgroundColor: evt.color, borderColor: evt.color, color: '#111827' }
  // darker fallback when no color
  return { ...base, backgroundColor: '#94a3b8', borderColor: '#64748b' }
}

const isFasting = (evt) => Boolean(Number(evt.fasting_required || 0))

/* ======================= Lanes & Events ======================= */
const lanesCache = ref([])
function computeLanes() {
  const map = new Map()
  for (const r of props.resources || []) {
    map.set(String(r.id), { id: String(r.id), title: r.title ?? String(r.id), events: [] })
  }
  for (const e of props.events || []) {
    const laneId = String(e.resourceId ?? 'Unassigned')
    if (!map.has(laneId)) map.set(laneId, { id: laneId, title: laneId, events: [] })
    map.get(laneId).events.push({
      id: String(e.id), resourceId: laneId, title: e.title || '', start: e.start, end: e.end, color: e.color || null,
      practitioner: e.practitioner || e.primary_practitioner || '',
      practitioner_name: e.practitioner_name || e.primary_practitioner_name || '',
      practitioner_contact: e.practitioner_contact || e.primary_practitioner_contact || '',
      patient: e.patient || '', patient_name: e.patient_name || '', patient_age: e.patient_age || '',
      patient_gender: e.patient_gender || e.gender || '', patient_contact: e.patient_contact || '',
      service_unit_type: e.service_unit_type || '', procedure: e.procedure || '', template: e.template || '',
      fasting_required: Number(e.fasting_required || 0),
    })
  }
  const lanes = Array.from(map.values())
  for (const L of lanes) L.events.sort((a, b) => parse(a.start) - parse(b.start) || parse(a.end) - parse(b.end))
  lanes.sort((a, b) => String(a.title).localeCompare(String(b.title)))
  return lanes
}

const interacting = ref(false)
watchEffect(() => { if (props.freeze || interacting.value) return; lanesCache.value = computeLanes() })
const lanesComputed = computed(() => lanesCache.value)

/* ======================= Current Time (Now) Line ======================= */
const nowPct = ref(0)
const showNowLine = computed(() => {
  const todayStr = new Date().toISOString().slice(0, 10)
  if (props.date !== todayStr) return false
  const mins = new Date().getHours() * 60 + new Date().getMinutes()
  return mins >= dayStartMin.value && mins <= dayEndMin.value
})
function updateNowPct() {
  const now = new Date()
  const mins = now.getHours() * 60 + now.getMinutes()
  const pct = ((mins - dayStartMin.value) / totalMin.value) * 100
  nowPct.value = clamp(pct, 0, 100)
}
let nowTimer

/* ======================= DnD / Resize ======================= */
const laneRects = []
const laneTrackEl = (laneId) => document.querySelector(`.rtv-track[data-lane="${String(laneId)}"]`)
function buildLaneRects() {
  laneRects.length = 0
  for (const lane of lanesComputed.value) {
    const el = laneTrackEl(lane.id); if (!el) continue
    const r = el.getBoundingClientRect()
    laneRects.push({ id: String(lane.id), left: r.left, right: r.right, top: r.top, bottom: r.bottom, height: r.height })
  }
}
const laneAt = (clientX) => {
  const pad = 8
  return laneRects.find(r => clientX >= r.left + pad && clientX <= r.right - pad)?.id
    || laneRects.find(r => clientX >= r.left && clientX <= r.right)?.id
    || null
}
const pxPerMinute = (laneId) => {
  const el = laneTrackEl(laneId); if (!el) return 1
  return el.getBoundingClientRect().height / totalMin.value
}

const dragging = reactive({ id: null, lane: null, offsetMin: 0, durationMin: 0 })
const resizing = reactive({ id: null, lane: null, edge: null })
const ghost = ref(null) // { laneId, top, bottom }
const invalidDrop = ref(false)
const originalTimes = reactive({ id: null, start: null, end: null })

const laneEvents = (laneId) => (lanesComputed.value.find(l => String(l.id) === String(laneId))?.events) || []
const eventById = (laneId, id) => laneEvents(laneId).find(e => String(e.id) === String(id))
const overlaps = (aS, aE, bS, bE) => Math.max(parse(aS).getTime(), parse(bS).getTime()) < Math.min(parse(aE).getTime(), parse(bE).getTime())
function violatesConstraints(targetLaneId, candidate, selfId) {
  // same-lane overlap
  for (const ev of laneEvents(targetLaneId)) {
    if (String(ev.id) === String(selfId)) continue
    if (overlaps(candidate.start, candidate.end, ev.start, ev.end)) return true
  }
  // practitioner / patient across all lanes
  for (const lane of lanesComputed.value) {
    for (const ev of lane.events) {
      if (String(ev.id) === String(selfId)) continue
      if (!overlaps(candidate.start, candidate.end, ev.start, ev.end)) continue
      if (candidate.practitioner && ev.practitioner && candidate.practitioner === ev.practitioner) return true
      if (candidate.patient && ev.patient && candidate.patient === ev.patient) return true
    }
  }
  return false
}

const alignToDate = (relMin) => mkDateFromRel(dayStartMin.value + clamp(snapMinutes(relMin), 0, totalMin.value))
let moveRAF = 0
function onMove(ev) {
  if (!dragging.id && !resizing.id) return
  const clientX = 'touches' in ev ? ev.touches[0].clientX : ev.clientX
  const clientY = 'touches' in ev ? ev.touches[0].clientY : ev.clientY
  if (moveRAF) return
  moveRAF = requestAnimationFrame(() => { moveRAF = 0; _onMoveCore(clientX, clientY) })
}
function _onMoveCore(clientX, clientY) {
  const originLane = dragging.id ? dragging.lane : (resizing.id ? resizing.lane : null)
  if (!originLane) return

  const targetLane = dragging.id ? (laneAt(clientX) || originLane) : originLane
  const baseEl = laneTrackEl(targetLane); if (!baseEl) return
  const rect = baseEl.getBoundingClientRect()
  const ppm = pxPerMinute(targetLane)
  const y = clamp(clientY - rect.top, 0, rect.height)
  const relMin = y / ppm

  if (dragging.id) {
    const evt = eventById(originLane, dragging.id); if (!evt) return
    let newStartRel = relMin - dragging.offsetMin
    let newEndRel = newStartRel + dragging.durationMin
    newStartRel = clamp(newStartRel, 0, totalMin.value - 1)
    newEndRel = clamp(newEndRel, 1, totalMin.value)
    const s = alignToDate(newStartRel), e2 = alignToDate(newEndRel)

    const candidate = { start: s, end: e2, practitioner: evt.practitioner, patient: evt.patient }
    invalidDrop.value = violatesConstraints(targetLane, candidate, dragging.id)

    const st = styleFromRange(s, e2)
    ghost.value = { laneId: String(targetLane), top: parseFloat(st.top), bottom: parseFloat(st.bottom) }
  } else if (resizing.id) {
    const evt = eventById(originLane, resizing.id); if (!evt) return
    let rel = clamp(relMin, 0, totalMin.value)

    if (resizing.edge === 'start') {
      const limit = minutesFromMidnight(evt.end) - dayStartMin.value - 1
      rel = clamp(rel, 0, limit)
      const s = alignToDate(rel)
      const candidate = { start: s, end: evt.end, practitioner: evt.practitioner, patient: evt.patient }
      invalidDrop.value = violatesConstraints(originLane, candidate, resizing.id)
      const st = styleFromRange(s, evt.end)
      ghost.value = { laneId: String(originLane), top: parseFloat(st.top), bottom: parseFloat(st.bottom) }
    } else {
      const limit = minutesFromMidnight(evt.start) - dayStartMin.value + 1
      rel = Math.max(rel, limit)
      const e2 = alignToDate(rel)
      const candidate = { start: evt.start, end: e2, practitioner: evt.practitioner, patient: evt.patient }
      invalidDrop.value = violatesConstraints(originLane, candidate, resizing.id)
      const st = styleFromRange(evt.start, e2)
      ghost.value = { laneId: String(originLane), top: parseFloat(st.top), bottom: parseFloat(st.bottom) }
    }
  }
}
function onUp() {
  try {
    if (!(dragging.id || resizing.id)) return
    const originLane = dragging.id ? dragging.lane : resizing.lane
    const id = dragging.id || resizing.id
    const targetLane = ghost.value?.laneId || originLane

    const evt = eventById(originLane, id)
    const topPct = Number(ghost.value?.top || 0)
    const bottomPct = Number(ghost.value?.bottom || 0)
    const total = totalMin.value
    const startRel = Math.round((topPct / 100) * total)
    const endRel = total - Math.round((bottomPct / 100) * total)
    const s = alignToDate(startRel), e2 = alignToDate(endRel)

    if (invalidDrop.value) {
      if (evt && originalTimes.id === id) { evt.start = originalTimes.start; evt.end = originalTimes.end }
      if (window.frappe?.msgprint) window.frappe.msgprint('Overlap not allowed at that time.')
      return
    }

    const y = props.date
    const iso = (d) => `${y} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:00`
    emit('event-update', { id, resourceId: targetLane, start: iso(s), end: iso(e2) })
  } finally {
    dragging.id = dragging.lane = null
    resizing.id = resizing.lane = resizing.edge = null
    ghost.value = null
    invalidDrop.value = false
    originalTimes.id = originalTimes.start = originalTimes.end = null
    interacting.value = false
    unbindMoveEnd()
  }
}
function bindMoveEnd() {
  if (bindMoveEnd.bound) return
  bindMoveEnd.bound = true
  window.addEventListener('mousemove', onMove, { passive: false })
  window.addEventListener('mouseup', onUp, { passive: true })
  window.addEventListener('touchmove', onMove, { passive: false })
  window.addEventListener('touchend', onUp, { passive: true })
}
bindMoveEnd.bound = false
function unbindMoveEnd() {
  if (!bindMoveEnd.bound) return
  bindMoveEnd.bound = false
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  window.removeEventListener('touchmove', onMove)
  window.removeEventListener('touchend', onUp)
}

function onDragStart(e, laneId, evt) {
  if (!props.editable) return
  interacting.value = true
  originalTimes.id = evt.id
  originalTimes.start = parse(evt.start)
  originalTimes.end = parse(evt.end)

  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
  const el = laneTrackEl(laneId); if (!el) return
  const rect = el.getBoundingClientRect()
  const ppm = pxPerMinute(laneId)
  const grabY = clamp(clientY - rect.top, 0, rect.height)
  const grabMin = grabY / ppm
  const startRel = minutesFromMidnight(evt.start) - dayStartMin.value

  dragging.id = evt.id
  dragging.lane = laneId
  dragging.offsetMin = grabMin - startRel
  dragging.durationMin = (parse(evt.end) - parse(evt.start)) / 60000

  const st = styleFromRange(evt.start, evt.end)
  ghost.value = { laneId: String(laneId), top: parseFloat(st.top), bottom: parseFloat(st.bottom) }
  nextTick(buildLaneRects)
  bindMoveEnd()
}
function onResizeStart(e, laneId, evt, edge) {
  if (!props.resizable) return
  interacting.value = true
  originalTimes.id = evt.id
  originalTimes.start = parse(evt.start)
  originalTimes.end = parse(evt.end)

  resizing.id = evt.id
  resizing.lane = laneId
  resizing.edge = edge

  const st = styleFromRange(evt.start, evt.end)
  ghost.value = { laneId: String(laneId), top: parseFloat(st.top), bottom: parseFloat(st.bottom) }
  nextTick(buildLaneRects)
  bindMoveEnd()
}

/* ======================= Lifecycle ======================= */
onMounted(() => {
  buildLaneRects()
  window.addEventListener('resize', buildLaneRects)
  bindMoveEnd()
  updateNowPct()
  nowTimer = setInterval(updateNowPct, 30000)
})

onBeforeUnmount(() => {
  unbindMoveEnd()
  window.removeEventListener('resize', buildLaneRects)
  try { clearInterval(nowTimer) } catch { }
})
</script>

<style scoped>
/* layout vars */
.rtv-card {
  --axis-w: 88px;
  /* prevent 06:00 clipping */
  --lane-gap: 8px;
  --grid-bg: #fff;
  --text: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --fasting-color: #4b5563;
  /* dark grey stripe */
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  color: var(--text);
  overflow: hidden;
  user-select: none;
}

.rtv-card.dark {
  --grid-bg: #0f141b;
  --text: #d6dee9;
  --muted: #9aa7b3;
  --line: #1f2a37;
  --fasting-color: #9ca3af;
  /* lighter grey on dark */
  background: transparent;
  border-color: #1f2a37;
}

.rtv-header {
  display: grid;
  grid-template-columns: var(--axis-w) repeat(var(--lane-count), 1fr);
  gap: var(--lane-gap);
  padding: 8px;
  align-items: center;
}

.rtv-corner {
  font-weight: 700;
  font-size: 13px;
  color: var(--text)
}

.rtv-lanes {
  display: contents
}

.rtv-lane-title {
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: 600;
  font-size: 12px;
  color: var(--text);
  text-align: center;
  padding: 4px 0;
}

.rtv-body {
  display: grid;
  grid-template-columns: var(--axis-w) 1fr;
  gap: var(--lane-gap);
  padding: 8px;
}

.rtv-axis {
  position: relative;
  background: transparent;
  border-right: 1px solid var(--line);
  padding-top: 6px;
}

.rtv-grid {
  display: grid;
  grid-template-columns: repeat(var(--lane-count), 1fr);
  gap: var(--lane-gap);
  background: transparent;
}

.rtv-track {
  position: relative;
  background: var(--grid-bg);
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
}

.rtv-rowline {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--line);
  pointer-events: none;
}

.rtv-tick {
  position: absolute;
  left: 0;
  right: 0;
  height: 0;
}

.rtv-hour {
  position: absolute;
  right: 8px;
  transform: translateY(-50%);
  font-size: 11px;
  color: var(--muted);
}

.rtv-tick:first-child .rtv-hour {
  transform: translateY(0);
}

/* Event */
.rtv-evt {
  position: absolute;
  left: 8px;
  right: 8px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 4px 8px;
  display: block;
  box-sizing: border-box;
  touch-action: none;
  background-clip: padding-box;
  overflow: hidden;
  min-height: 20px;
}

/* Fasting */
.rtv-chip {
  display: inline-block;
  margin-left: 6px;
  margin-bottom: 3px;
  padding: 0 6px;
  height: 16px;
  line-height: 16px;
  font-size: 10px;
  font-weight: 600;
  border-radius: 9999px;
  border: 1px solid #111111;
  /* light gray */
  color: #111111;
  /* near-black */
  vertical-align: middle;
}

.rtv-card.dark .rtv-chip {
  background: #374151;
  /* slate-700 */
  color: #e5e7eb;
  /* gray-200 */
}

/* Label rows */
.rtv-label {
  width: 100%;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.rtv-topline {
  font-weight: 700;
  margin-bottom: 2px;
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rtv-main,
.rtv-prac.oneline,
.rtv-prac {
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Resize handles */
.rtv-handle {
  position: absolute;
  left: 6px;
  right: 6px;
  height: 6px;
  cursor: ns-resize;
}

.rtv-handle-t {
  top: -2px
}

.rtv-handle-b {
  bottom: -2px
}

/* Ghost */
.rtv-ghost {
  position: absolute;
  left: 8px;
  right: 8px;
  background: #dbeafe;
  border: 1px solid #93c5fd;
  border-radius: 10px;
  pointer-events: none;
  opacity: .7;
  will-change: top, bottom;
}

.rtv-ghost.invalid {
  background: #fee2e2;
  border-color: #fca5a5
}

/* Now line */
.rtv-nowline {
  position: absolute;
  left: 4px;
  right: 4px;
  height: 0;
  border-top: 2px solid #ef4444;
  pointer-events: none;
}

.rtv-nowline-axis {
  position: absolute;
  left: 0;
  right: 0;
  height: 0;
  border-top: 2px dashed #ef4444;
  pointer-events: none;
}
</style>
