import { io } from 'socket.io-client'
import { socketio_port } from '../../../../sites/common_site_config.json'

// Temporary stubs – prevent deep imports into frappe-ui internals
// FIXME
const getCachedResource = () => null
const getCachedListResource = () => null

export function initSocket() {
	let host = window.location.hostname
	let siteName = window.site_name || host
	let port = window.location.port ? `:${socketio_port}` : ''
	let protocol = port ? 'http' : 'https'
	let url = `${protocol}://${host}${port}/${siteName}`

	let socket = io(url, {
		withCredentials: true,
		reconnectionAttempts: 5,
	})

	socket.on('refetch_resource', (data) => {
		if (data.cache_key) {
			let resource =
				getCachedResource(data.cache_key) ||
				getCachedListResource(data.cache_key)

			if (resource) {
				resource.reload()
			}
		}
	})

	return socket
}
