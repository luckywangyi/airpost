import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface NoteStats {
  id: string
  account_id: string
  note_url: string
  title: string
  views: number
  likes: number
  collects: number
  comments: number
  shares: number
  collected_at: string
}

export interface TaskLog {
  id: string
  task_type: string
  account_id: string | null
  status: string
  message: string | null
  created_at: string
}

export const useAnalyticsStore = defineStore('analytics', () => {
  const stats = ref<NoteStats[]>([])
  const taskLogs = ref<TaskLog[]>([])
  const loading = ref(false)

  async function fetchStats(accountId?: string) {
    loading.value = true
    try {
      stats.value = await invoke<NoteStats[]>('get_note_stats', {
        accountId: accountId || null,
      })
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchTaskLogs(limit = 50) {
    try {
      taskLogs.value = await invoke<TaskLog[]>('get_task_logs', { limit })
    } catch (e) {
      console.error('Failed to fetch task logs:', e)
    }
  }

  return { stats, taskLogs, loading, fetchStats, fetchTaskLogs }
})
