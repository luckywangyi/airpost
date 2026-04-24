import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface ContentItem {
  id: string
  account_id: string
  title: string
  body: string
  tags: string
  images: string
  scheduled_at: string | null
  status: string
  created_at: string
}

export const useContentStore = defineStore('content', () => {
  const queue = ref<ContentItem[]>([])
  const loading = ref(false)

  async function fetchQueue() {
    loading.value = true
    try {
      queue.value = await invoke<ContentItem[]>('get_content_queue')
    } catch (e) {
      console.error('Failed to fetch content queue:', e)
    } finally {
      loading.value = false
    }
  }

  async function resetStalePublishing() {
    const stale = queue.value.filter(i => i.status === 'publishing')
    for (const item of stale) {
      await updateStatus(item.id, 'pending')
    }
  }

  async function addContent(item: ContentItem) {
    try {
      await invoke('add_content', { item })
      await fetchQueue()
    } catch (e) {
      console.error('Failed to add content:', e)
      throw e
    }
  }

  async function updateContent(item: ContentItem) {
    try {
      await invoke('update_content', { item })
      await fetchQueue()
    } catch (e) {
      console.error('Failed to update content:', e)
      throw e
    }
  }

  async function updateStatus(id: string, status: string) {
    try {
      await invoke('update_content_status', { id, status })
      await fetchQueue()
    } catch (e) {
      console.error('Failed to update content status:', e)
      throw e
    }
  }

  async function deleteContent(id: string) {
    try {
      await invoke('delete_content', { id })
      await fetchQueue()
    } catch (e) {
      console.error('Failed to delete content:', e)
      throw e
    }
  }

  return { queue, loading, fetchQueue, resetStalePublishing, addContent, updateContent, updateStatus, deleteContent }
})
