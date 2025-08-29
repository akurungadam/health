import { onMounted, onBeforeUnmount } from 'vue'

export function useWheelSliceScroll(elRef, { onNext, onPrev }) {
	function onWheel(e) {
		e.preventDefault()
		if (e.deltaY > 0) onNext()
		else onPrev()
	}
	onMounted(() => elRef.value?.addEventListener('wheel', onWheel, { passive: false }))
	onBeforeUnmount(() => elRef.value?.removeEventListener('wheel', onWheel))
}
