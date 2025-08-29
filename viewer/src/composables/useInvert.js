import { ref } from 'vue'

export function useInvert(vpGetter) {
	const invertOn = ref(false)
	async function toggle() {
		const v = vpGetter(); if (!v?.getProperties || !v?.setProperties) return
		const props = v.getProperties() || {}
		const next = !props.invert
		v.setProperties({ ...props, invert: next })
		invertOn.value = next
		await v.render?.()
	}
	return { invertOn, toggle }
}
