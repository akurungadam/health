import { onMounted, onBeforeUnmount } from 'vue'

export function useViewerKeys(elRef, { next, prev, first, last, togglePlay, exitFullscreenIf }) {
  function onKeyDown(e) {
    if (document.activeElement !== elRef.value) return
    const handled = ['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End',' ','Escape']
    if (handled.includes(e.key)) e.preventDefault()
    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown': next(); break
      case 'ArrowLeft':
      case 'ArrowUp':   prev(); break
      case 'Home':      first(); break
      case 'End':       last(); break
      case ' ':         togglePlay(); break
      case 'Escape':    exitFullscreenIf && exitFullscreenIf(); break
    }
  }
  onMounted(() => elRef.value?.addEventListener('keydown', onKeyDown))
  onBeforeUnmount(() => elRef.value?.removeEventListener('keydown', onKeyDown))
}
