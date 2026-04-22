import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const sidecarUrl = ref('')
const sidecarRunning = ref(false)

export function useSidecar() {
  async function start(port?: number) {
    try {
      await invoke('start_sidecar', { port })
      sidecarUrl.value = await invoke<string>('get_sidecar_url')
      sidecarRunning.value = true
    } catch (e) {
      console.error('Failed to start sidecar:', e)
      throw e
    }
  }

  async function stop() {
    try {
      await invoke('stop_sidecar')
      sidecarRunning.value = false
    } catch (e) {
      console.error('Failed to stop sidecar:', e)
    }
  }

  async function ensureRunning() {
    if (!sidecarRunning.value) {
      await start()
    }
    return sidecarUrl.value
  }

  async function callSidecar<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {},
  ): Promise<T> {
    const base = await ensureRunning()
    const url = `${base}${path}`
    const resp = await fetch(url, {
      method: options.method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    if (!resp.ok) {
      throw new Error(`Sidecar request failed: ${resp.status}`)
    }
    return resp.json()
  }

  return {
    sidecarUrl,
    sidecarRunning,
    start,
    stop,
    ensureRunning,
    callSidecar,
  }
}
