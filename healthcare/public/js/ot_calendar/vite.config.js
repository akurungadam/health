import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'
import Components from 'unplugin-vue-components/vite'
import IconsResolver from 'unplugin-icons/resolver'

export default defineConfig({
  plugins: [
    vue(),
    Components({ resolvers: [IconsResolver({ prefix: false })] }),
    Icons({ compiler: 'vue3', autoInstall: false }),
  ],
  build: {
    lib: {
      entry: 'src/app.js',
      name: 'OTCalendarApp',
      formats: ['iife'],
      fileName: () => 'app.js',
    },
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // keep CSS at /dist/style.css for your doctype loader
        assetFileNames: (info) =>
          info.name && info.name.endsWith('.css')
            ? 'style.css'
            : 'assets/[name][extname]',
      },
    },
  },
  resolve: { alias: [{ find: /^~icons\//, replacement: 'virtual:icons/' }] },
  define: {
    'process.env.NODE_ENV': '"production"',
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false,
  },
})
