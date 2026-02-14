// .vitepress/theme/index.ts
import DefaultTheme from 'vitepress/theme'
import mediumZoom from 'medium-zoom'
import { onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import './custom.css'

export default {
  extends: DefaultTheme,
  setup() {
    const route = useRoute()
    
    const initZoom = () => {
      // Initialize zoom on all images in the document body
      // We use a slight delay or nextTick to ensure DOM is ready
      mediumZoom('.vp-doc img', { 
        background: 'var(--vp-c-bg)',
        margin: 24,
        scrollOffset: 0
      })
    }
    
    onMounted(() => {
      initZoom()
    })
    
    watch(
      () => route.path,
      () => nextTick(() => initZoom())
    )
  }
}
