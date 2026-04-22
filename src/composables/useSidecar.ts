import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const DEFAULT_PORT = 18765
const sidecarUrl = ref(`http://127.0.0.1:${DEFAULT_PORT}`)
const sidecarRunning = ref(false)
const lastError = ref('')

export function useSidecar() {
  async function start(port?: number) {
    const p = port || DEFAULT_PORT
    sidecarUrl.value = `http://127.0.0.1:${p}`

    try {
      await invoke('start_sidecar', { port: p })
      sidecarRunning.value = true
    } catch {
      // Tauri command failed (e.g. dev mode path issue) - check if sidecar is already running externally
      try {
        const resp = await fetch(`${sidecarUrl.value}/health`)
        if (resp.ok) {
          sidecarRunning.value = true
          return
        }
      } catch {
        // sidecar not reachable
      }
      console.warn('Sidecar not available. Start it manually: cd sidecar && python main.py')
    }
  }

  async function stop() {
    try {
      await invoke('stop_sidecar')
      sidecarRunning.value = false
    } catch {
      console.warn('Failed to stop sidecar via Tauri')
    }
  }

  async function ensureRunning(): Promise<string> {
    if (sidecarRunning.value) return sidecarUrl.value

    // Try health check on default URL first (manually started sidecar)
    try {
      const resp = await fetch(`${sidecarUrl.value}/health`)
      if (resp.ok) {
        sidecarRunning.value = true
        return sidecarUrl.value
      }
    } catch {
      // not running, try to start via Tauri
    }

    await start()
    return sidecarUrl.value
  }

  async function callSidecar<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {},
  ): Promise<T> {
    const base = await ensureRunning()

    if (!sidecarRunning.value) {
      lastError.value = 'Sidecar 未运行，请先在终端启动：cd sidecar && python main.py'
      throw new Error(lastError.value)
    }

    const url = `${base}${path}`
    const resp = await fetch(url, {
      method: options.method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      lastError.value = `请求失败 (${resp.status}): ${text}`
      throw new Error(lastError.value)
    }
    lastError.value = ''
    return resp.json()
  }

  return {
    sidecarUrl,
    sidecarRunning,
    lastError,
    start,
    stop,
    ensureRunning,
    callSidecar,
  }
}
