<template>
	<div class="w-full min-h-screen rounded-xl p-2 bg-slate-50 text-black">
		<div ref="viewportRef" :class="[
			'w-full bg-black rounded-xl outline-none',
			fs.isFullscreen.value ? 'fixed inset-0 z-[2147483647] h-screen' : 'h-[80vh] md:h-[86vh] lg:h-[92vh]'
		]" tabindex="0" :data-viewport-uid="viewportId" :data-rendering-engine-uid="renderingEngineId"></div>

		<!-- Status hidden while in fullscreen -->
		<div v-if="!fs.isFullscreen.value" class="mt-2 text-xs text-slate-600">
			<span v-if="isLoading">Loading…</span>
			<span v-else-if="error" class="text-rose-500">Error: {{ error }}</span>
			<span v-else-if="nav.currentSOPUID">SOP Instance UID: {{ nav.currentSOPUID }}</span>
		</div>

		<!-- Toolbar hidden while in fullscreen -->
		<div v-if="!fs.isFullscreen.value" class="mt-3 rounded-lg border p-2 bg-transparent border-gray-300">
			<div class="flex justify-center gap-2">
				<Button v-for="btn in buttons" :key="btn.id" :title="btn.title" :disabled="isLoading || !!error"
					:class="buttonClass(btn.id)" @click="btn.onClick">
					<component :is="btn.icon" class="w-4 h-4" />
				</Button>
				<Button :title="'Enter Fullscreen'" :disabled="isLoading || !!error" :class="buttonClass('Fullscreen')"
					@click="fs.enter">
					<LucideMaximize2 class="w-4 h-4" />
				</Button>
			</div>
		</div>

		<!-- Float while in fullscreen -->
		<div v-if="fs.isFullscreen.value"
			class="pointer-events-none fixed inset-x-0 top-0 z-[2147483647] flex justify-between p-3 text-white">
			<div class="text-[12px] text-white/80 pointer-events-auto">
				<span v-if="isLoading">Loading…</span>
				<span v-else-if="error" class="text-rose-400">Error: {{ error }}</span>
				<span v-else-if="nav.currentSOPUID">SOP: {{ nav.currentSOPUID }}</span>
			</div>
			<div class="flex gap-2 pointer-events-auto">
				<Button :title="'Exit Fullscreen (Esc)'" :class="fsBtnCls" @click="fs.exit">
					<LucideMinimize2 class="w-4 h-4" />
				</Button>
				<Button :title="'Previous (← / ↑)'" :disabled="isLoading || !!error" :class="fsBtnCls"
					@click="nav.prev">
					<LucideChevronLeft class="w-4 h-4" />
				</Button>
				<Button :title="'Next (→ / ↓)'" :disabled="isLoading || !!error" :class="fsBtnCls" @click="nav.next">
					<LucideChevronRight class="w-4 h-4" />
				</Button>
				<Button :title="'First (Home)'" :disabled="isLoading || !!error" :class="fsBtnCls" @click="nav.first">
					<LucideChevronsLeft class="w-4 h-4" />
				</Button>
				<Button :title="'Last (End)'" :disabled="isLoading || !!error" :class="fsBtnCls" @click="nav.last">
					<LucideChevronsRight class="w-4 h-4" />
				</Button>
				<Button :title="'Play/Pause (Space)'" :disabled="isLoading || !!error" :class="fsBtnClsActive('Play')"
					@click="cine.toggle">
					<component :is="cine.isPlaying.value ? LucidePause : LucidePlay" class="w-4 h-4" />
				</Button>
				<Button :title="'Invert'" :disabled="isLoading || !!error" :class="fsBtnClsActive('Invert')"
					@click="invert.toggle">
					<component :is="invert.invertOn.value ? LucideMoon : LucideSun" class="w-4 h-4" />
				</Button>
				<Button :title="'Reset view'" :disabled="isLoading || !!error" :class="fsBtnCls" @click="resetView">
					<LucideRefreshCw class="w-4 h-4" />
				</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { Button } from 'frappe-ui'
import * as cornerstone from '@cornerstonejs/core'
import {
	useDicomLoader,
	useCornerstoneViewport,
	useQidoWadoStack,
	useStackNavigation,
	useCine,
	useInvert,
	useFullscreenOn,
	useWheelSliceScroll,
	useViewerKeys
} from '../viewer-composables.js'

// lucide
import LucideChevronLeft from '~icons/lucide/chevron-left'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucideChevronsLeft from '~icons/lucide/chevrons-left'
import LucideChevronsRight from '~icons/lucide/chevrons-right'
import LucidePlay from '~icons/lucide/play'
import LucidePause from '~icons/lucide/pause'
import LucideSun from '~icons/lucide/sun'
import LucideMoon from '~icons/lucide/moon'
import LucideRefreshCw from '~icons/lucide/refresh-cw'
import LucideMaximize2 from '~icons/lucide/maximize-2'
import LucideMinimize2 from '~icons/lucide/minimize-2'

const props = defineProps({
	pacsBaseUrl: { type: String, required: true },
	pacsUsername: { type: String, required: true },
	pacsPassword: { type: String, required: true },
	studyUID: { type: String, required: true },
	seriesUID: { type: String, required: true },
	objectUID: { type: [String, Array], required: true },
})

const renderingEngineId = 'dicomRenderingEngine'
const viewportId = 'dicomViewport'
const viewportRef = ref(null)

const isLoading = ref(true)
const error = ref(null)

const dicom = useDicomLoader()
const cs = useCornerstoneViewport(renderingEngineId, viewportId)
const stack = useQidoWadoStack()
const nav = useStackNavigation(cs.vp, stack.imageIds, stack.sopByIndex)
const cine = useCine(nav.next, 12)
const invert = useInvert(cs.vp)
const fs = useFullscreenOn(viewportRef, {
	onChange: () => requestAnimationFrame(() => cs.resize())
})
useWheelSliceScroll(viewportRef, { onNext: nav.next, onPrev: nav.prev })
useViewerKeys(viewportRef, {
	next: nav.next, prev: nav.prev, first: nav.first, last: nav.last,
	togglePlay: cine.toggle, exitFullscreenIf: () => fs.isFullscreen.value && fs.exit()
})

const buttons = computed(() => ([
	{ id: 'Prev', title: 'Previous (← / ↑)', icon: LucideChevronLeft, onClick: nav.prev },
	{ id: 'Next', title: 'Next (→ / ↓)', icon: LucideChevronRight, onClick: nav.next },
	{ id: 'First', title: 'First (Home)', icon: LucideChevronsLeft, onClick: nav.first },
	{ id: 'Last', title: 'Last (End)', icon: LucideChevronsRight, onClick: nav.last },
	{ id: 'Play', title: 'Play/Pause (Space)', icon: cine.isPlaying.value ? LucidePause : LucidePlay, onClick: cine.toggle },
	{ id: 'Invert', title: 'Invert', icon: invert.invertOn.value ? LucideMoon : LucideSun, onClick: invert.toggle },
	{ id: 'Reset', title: 'Reset view', icon: LucideRefreshCw, onClick: resetView },
]))

function buttonClass(id) {
	const base =
		'!h-9 !w-9 p-0 flex items-center justify-center !rounded-md ' +
		'!bg-white !text-black !border !border-gray-300 hover:!bg-gray-50 ' +
		'focus:!outline-none focus:!ring-1 focus:!ring-gray-900 ' +
		'disabled:opacity-50 disabled:pointer-events-none'
	const isActive =
		(id === 'Play' && cine.isPlaying.value) || (id === 'Invert' && invert.invertOn.value)
	const active = '!border-gray-900 !ring-1 !ring-gray-900'
	return isActive ? `${base} ${active}` : base
}

const fsBtnCls =
	'!h-9 !w-9 p-0 flex items-center justify-center !rounded-md !bg-white/10 !text-white ' +
	'!border !border-white/20 hover:!bg-white/15 focus:!outline-none focus:!ring-1 focus:!ring-white/40 ' +
	'disabled:opacity-50 disabled:pointer-events-none'
function fsBtnClsActive(id) {
	const active = '!border-white !ring-1 !ring-white/70'
	return ((id === 'Play' && cine.isPlaying.value) || (id === 'Invert' && invert.invertOn.value))
		? `${fsBtnCls} ${active}` : fsBtnCls
}

async function resetView() {
	const v = cs.vp(); if (!v) return
	v.resetCamera?.()
	await v.render?.()
}

onMounted(async () => {
	try {
		if (!props.studyUID || !props.seriesUID || !props.pacsBaseUrl) {
			throw new Error('Required DICOM or PACS parameters are missing')
		}
		await cornerstone.init()
		dicom.ensure({ username: props.pacsUsername, password: props.pacsPassword })

		const el = viewportRef.value
		if (!el) throw new Error('Viewport element not found')
		await cs.enable(el)

		const fallback = Array.isArray(props.objectUID) ? props.objectUID : (props.objectUID ? [props.objectUID] : [])
		const ids = await stack.loadSeries({
			baseUrl: props.pacsBaseUrl,
			studyUID: props.studyUID,
			seriesUID: props.seriesUID,
			username: props.pacsUsername,
			password: props.pacsPassword,
			fallbackObjectUIDs: fallback,
		})
		if (!ids.length) throw new Error('No images found for this study/series')

		await cs.vp()?.setStack(ids)
		await nav.first()
		cs.resize()
		el.focus()
	} catch (err) {
		error.value = `Failed to load DICOM viewer: ${err.message}`
		cine.stop()
		// eslint-disable-next-line no-console
		console.error('DICOMViewer error:', err)
	} finally {
		isLoading.value = false
	}
})

onBeforeUnmount(() => {
	cine.stop()
})
</script>
