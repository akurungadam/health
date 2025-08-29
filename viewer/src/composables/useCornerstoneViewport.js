import { ref, onBeforeUnmount } from 'vue'
import { RenderingEngine, Enums as CSEnums } from '@cornerstonejs/core'

export function useCornerstoneViewport(renderingEngineId, viewportId) {
	const engine = ref(null)

	async function enable(element) {
		const re = new RenderingEngine(renderingEngineId)
		re.enableElement({
			viewportId,
			element,
			type: CSEnums.ViewportType.STACK,
			defaultOptions: { background: [0, 0, 0] },
		})
		engine.value = re
		re.getViewport(viewportId)?.resize()
	}

	function vp() {
		return engine.value?.getViewport(viewportId) ?? null
	}

	function resize() {
		const v = vp(); if (v) { v.resize(); v.render?.() }
	}

	function withVp(fn) {
		const v = vp(); if (!v) return
		return fn(v)
	}

	onBeforeUnmount(() => {
		try { engine.value?.disableElement(viewportId) } catch { console.error("Viewport Unmount: disableElement") }
		try { engine.value?.destroy() } catch { console.error("Viewport Unmount: destroy") }
		engine.value = null
	})

	return { enable, vp, resize, withVp }
}
