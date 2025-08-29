import { ref, onMounted, onBeforeUnmount } from 'vue'

export function useFullscreenOn(elRef, { onChange } = {}) {
	const isFullscreen = ref(false)

	async function enter() {
		const el = elRef.value; if (!el) return
		try { await el.requestFullscreen?.({ navigationUI: 'hide' }) } catch { console.error("requestFullscreen failed") }
	}

	async function exit() {
		if (document.fullscreenElement !== elRef.value) { isFullscreen.value = false; return }
		try { await document.exitFullscreen?.() } catch { console.error("exitFullscreen failed") }
		finally { isFullscreen.value = false }
	}

	function handleChange() {
		const now = document.fullscreenElement === elRef.value
		isFullscreen.value = now
		onChange && onChange(now)
	}

	onMounted(() => {
		document.addEventListener('fullscreenchange', handleChange)
		document.addEventListener('webkitfullscreenchange', handleChange)
	})
	onBeforeUnmount(() => {
		document.removeEventListener('fullscreenchange', handleChange)
		document.removeEventListener('webkitfullscreenchange', handleChange)
	})

	return { isFullscreen, enter, exit }
}
