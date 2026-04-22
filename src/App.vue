<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import { useSidecar } from '@/composables/useSidecar'

const { start } = useSidecar()

onMounted(async () => {
  try {
    await start()
  } catch {
    console.warn('Sidecar not started - run Python sidecar manually if needed')
  }
})
</script>

<template>
  <div class="app-layout">
    <Sidebar />
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: var(--color-surface);
}
</style>
