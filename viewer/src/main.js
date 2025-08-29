import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import DICOMViewer from './components/DICOMViewer.vue'
import './index.css'
import { init as cornerstoneInit } from '@cornerstonejs/core'

// Configure routes
const routes = [
	{
		path: '/',
		component: DICOMViewer,
		props: (route) => {
			// Parse query parameters
			const params = {
				studyUID: route.query.studyUID,
				seriesUID: route.query.seriesUID,
				objectUID: route.query.objectUID,
				pacsBaseUrl: route.query.pacs_base_url,
				pacsUsername: route.query.pacs_username,
				pacsPassword: route.query.pacs_password
			};

			return params;
		}
	},
	// Catch-all: render DICOMViewer for any route, so it loads by default even on subpaths
	{
		path: '/:pathMatch(.*)*',
		component: DICOMViewer,
		props: (route) => ({
			studyUID: route.query.studyUID,
			seriesUID: route.query.seriesUID,
			objectUID: route.query.objectUID,
			pacsBaseUrl: route.query.pacs_base_url,
			pacsUsername: route.query.pacs_username,
			pacsPassword: route.query.pacs_password
		})
	}
]

// Create router instance
const router = createRouter({
	history: createWebHistory(),
	routes
})

async function bootstrap() {
	await cornerstoneInit()

	const app = createApp(App)
	app.use(router)
	app.mount('#app')
}

bootstrap()
