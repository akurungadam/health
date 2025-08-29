import { ref } from 'vue'
import { init as initDicomImageLoader } from '@cornerstonejs/dicom-image-loader'

let ready = false

export function useDicomLoader() {
	const isReady = ref(ready)

	function ensure({ username, password } = {}) {
		if (ready) return
		initDicomImageLoader({
			useWebWorkers: true,
			beforeSend: (xhr) => {
				if (username && password) {
					xhr.setRequestHeader('Authorization', 'Basic ' + btoa(`${username}:${password}`))
				}
			},
		})
		ready = true
		isReady.value = true
	}

	return { isReady, ensure }
}
