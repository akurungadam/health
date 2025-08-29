import { computed, ref } from 'vue'

export function useStackNavigation(vpGetter, imageIdsRef, sopByIndexRef) {
	const currentIndex = ref(0)
	const currentSOPUID = computed(() => sopByIndexRef.value[currentIndex.value] || '')

	async function setIndex(idx) {
		const v = vpGetter(); const n = imageIdsRef.value.length
		if (!v || !n) return
		const clamped = ((idx % n) + n) % n
		await v.setImageIdIndex(clamped)
		currentIndex.value = clamped
		await v.render?.()
	}

	return {
		currentIndex,
		currentSOPUID,
		next: () => setIndex(currentIndex.value + 1),
		prev: () => setIndex(currentIndex.value - 1),
		first: () => setIndex(0),
		last: () => setIndex(imageIdsRef.value.length - 1),
		setIndex,
	}
}
