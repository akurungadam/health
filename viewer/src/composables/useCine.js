import { ref, onBeforeUnmount } from 'vue'

export function useCine(nextFn, fps = 12) {
    const isPlaying = ref(false)
    let t = null

    function stop() { if (t) clearInterval(t); t = null; isPlaying.value = false }
    function start() { stop(); t = setInterval(() => nextFn(), Math.max(10, Math.floor(1000 / fps))); isPlaying.value = true }
    function toggle() { isPlaying.value ? stop() : start() }

    onBeforeUnmount(stop)
    return { isPlaying, start, stop, toggle }
}
