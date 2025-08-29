import { ref } from 'vue'

export function useQidoWadoStack() {
	const imageIds = ref([])
	const sopByIndex = ref([])

	async function loadSeries({
		baseUrl, studyUID, seriesUID, username, password, fallbackObjectUIDs,
	}) {
		const root = baseUrl.replace(/\/+$/, '')
		const qidoRoot = root.endsWith('/dicom-web') ? root : `${root}/dicom-web`

		const url = `${qidoRoot}/instances?` +
			`StudyInstanceUID=${encodeURIComponent(studyUID)}&` +
			`SeriesInstanceUID=${encodeURIComponent(seriesUID)}&` +
			`includefield=00080018&includefield=00200013` // SOP Instance UID & Instance Number

		const headers = { Accept: 'application/dicom+json' }
		if (username && password) headers.Authorization = 'Basic ' + btoa(`${username}:${password}`)

		const resp = await fetch(url, { headers })
		if (!resp.ok) throw new Error(`QIDO-RS failed (${resp.status})`)
		const rows = await resp.json()

		const items = rows.map(r => ({
			sop: r['00080018']?.Value?.[0],
			inst: Number(r['00200013']?.Value?.[0]),
		})).filter(x => !!x.sop)

		items.sort((a, b) => {
			const ai = Number.isFinite(a.inst) ? a.inst : Number.MAX_SAFE_INTEGER
			const bi = Number.isFinite(b.inst) ? b.inst : Number.MAX_SAFE_INTEGER
			return ai === bi ? a.sop.localeCompare(b.sop) : ai - bi
		})

		const toUri = (sop) =>
			`wadouri:${root}/wado?requestType=WADO` +
			`&studyUID=${encodeURIComponent(studyUID)}` +
			`&seriesUID=${encodeURIComponent(seriesUID)}` +
			`&objectUID=${encodeURIComponent(sop)}` +
			`&contentType=application/dicom`

		const ids = items.map(it => toUri(it.sop))
		if (!ids.length && Array.isArray(fallbackObjectUIDs) && fallbackObjectUIDs.length) {
			ids.push(...fallbackObjectUIDs.map(toUri))
		}

		imageIds.value = ids
		sopByIndex.value = ids.map(id => {
			const q = id.split('?')[1] || ''
			return new URLSearchParams(q).get('objectUID') || ''
		})
		return ids
	}

	return { imageIds, sopByIndex, loadSeries }
}
