<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { Minus, Square, X } from 'lucide-vue-next'
import Sidebar from '@/components/Sidebar.vue'
import { useSidecar } from '@/composables/useSidecar'

const { start } = useSidecar()
const appWindow = getCurrentWindow()

function minimize() { appWindow.minimize() }
function toggleMaximize() { appWindow.toggleMaximize() }
function close() { appWindow.hide() }

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
    <div class="main-wrapper">
      <div class="titlebar">
        <div class="titlebar-spacer" data-tauri-drag-region />
        <div class="window-controls">
          <button class="win-btn" @click="minimize" title="最小化">
            <Minus :size="14" :stroke-width="1.5" />
          </button>
          <button class="win-btn" @click="toggleMaximize" title="最大化">
            <Square :size="11" :stroke-width="1.8" />
          </button>
          <button class="win-btn win-close" @click="close" title="关闭">
            <X :size="14" :stroke-width="1.5" />
          </button>
        </div>
      </div>
      <main class="main-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.titlebar {
  height: 38px;
  min-height: 38px;
  display: flex;
  align-items: center;
  background: var(--color-surface);
  border-bottom: 0.5px solid var(--color-border);
  user-select: none;
}

.titlebar-spacer {
  flex: 1;
  height: 100%;
  -webkit-app-region: drag;
}

.window-controls {
  display: flex;
  -webkit-app-region: no-drag;
  height: 100%;
}

.win-btn {
  width: 46px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.win-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--color-text-primary);
}

.win-close:hover {
  background: #e81123;
  color: white;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: var(--color-surface);
}
</style>
