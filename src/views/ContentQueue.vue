<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useContentStore, type ContentItem } from '@/stores/content'
import { useAccountStore } from '@/stores/accounts'
import { useSidecar } from '@/composables/useSidecar'
import { Plus, Trash2, Send, Clock, CheckCircle2, XCircle, Image } from 'lucide-vue-next'

const router = useRouter()
const contentStore = useContentStore()
const accountStore = useAccountStore()
const { callSidecar } = useSidecar()
const publishingId = ref<string | null>(null)
const errorMessage = ref('')

onMounted(async () => {
  await Promise.all([contentStore.fetchQueue(), accountStore.fetchAccounts()])
  await contentStore.resetStalePublishing()
})

function getAccountName(id: string): string {
  const acc = accountStore.accounts.find(a => a.id === id)
  return acc?.nickname || id.slice(0, 8)
}

function statusInfo(status: string) {
  switch (status) {
    case 'pending': return { label: '待发布', cls: 'badge-warning', icon: Clock }
    case 'publishing': return { label: '发布中', cls: 'badge-info', icon: Send }
    case 'published': return { label: '已发布', cls: 'badge-success', icon: CheckCircle2 }
    case 'failed': return { label: '失败', cls: 'badge-danger', icon: XCircle }
    default: return { label: status, cls: '', icon: Clock }
  }
}

function imageCount(images: string): number {
  if (!images) return 0
  return images.split(',').filter(Boolean).length
}

async function handlePublish(item: ContentItem) {
  publishingId.value = item.id
  errorMessage.value = ''
  await contentStore.updateStatus(item.id, 'publishing')
  try {
    const result = await callSidecar<{ success: boolean; message: string; note_url: string }>('/publish/post', {
      body: {
        account_id: item.account_id,
        title: item.title,
        body: item.body,
        tags: item.tags.split(/\s+/).filter(Boolean).map(t => t.replace(/^#/, '')),
        image_paths: item.images ? item.images.split(',').filter(Boolean) : [],
      },
    })
    if (result.success) {
      await contentStore.updateStatus(item.id, 'published')
    } else {
      errorMessage.value = result.message || '发布失败'
      await contentStore.updateStatus(item.id, 'failed')
      setTimeout(() => { errorMessage.value = '' }, 5000)
    }
  } catch (e: any) {
    errorMessage.value = e?.message || '发布失败，请确保 Sidecar 已启动且账号已登录'
    await contentStore.updateStatus(item.id, 'failed')
    setTimeout(() => { errorMessage.value = '' }, 5000)
  } finally {
    publishingId.value = null
  }
}

function canEdit(status: string): boolean {
  return status !== 'published'
}

function handleEdit(item: { id: string; status: string }) {
  if (canEdit(item.status)) {
    router.push(`/content/editor/${item.id}`)
  }
}

async function handleDelete(id: string) {
  await contentStore.deleteContent(id)
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">内容队列</h1>
      <button class="btn-primary" @click="router.push('/content/editor')">
        <Plus :size="16" :stroke-width="1.5" />
        新建内容
      </button>
    </header>

    <div v-if="errorMessage" class="error-bar">{{ errorMessage }}</div>

    <div v-if="contentStore.queue.length === 0" class="empty-state">
      <Image :size="40" :stroke-width="1" class="empty-icon" />
      <p>还没有内容</p>
      <button class="btn-primary" @click="router.push('/content/editor')">创建第一条内容</button>
    </div>

    <div v-else class="content-list">
      <div
        v-for="item in contentStore.queue"
        :key="item.id"
        class="content-item"
        :class="{ clickable: canEdit(item.status) }"
        @click="handleEdit(item)"
      >
        <div class="item-main">
          <div class="item-title">{{ item.title || '无标题' }}</div>
          <div class="item-meta">
            <span class="meta-account">{{ getAccountName(item.account_id) }}</span>
            <span v-if="item.scheduled_at" class="meta-schedule">
              <Clock :size="12" :stroke-width="1.5" />
              {{ item.scheduled_at }}
            </span>
            <span v-if="imageCount(item.images) > 0" class="meta-images">
              <Image :size="12" :stroke-width="1.5" />
              {{ imageCount(item.images) }} 张图
            </span>
          </div>
        </div>

        <span :class="['badge', statusInfo(item.status).cls]">
          <component :is="statusInfo(item.status).icon" :size="12" :stroke-width="1.5" />
          {{ statusInfo(item.status).label }}
        </span>

        <div class="item-actions" @click.stop>
          <button
            v-if="item.status !== 'published'"
            class="btn-icon"
            title="立即发布"
            :disabled="publishingId === item.id"
            @click="handlePublish(item)"
          >
            <Send :size="14" :stroke-width="1.5" />
          </button>
          <button class="btn-icon danger" title="删除" @click="handleDelete(item.id)">
            <Trash2 :size="14" :stroke-width="1.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 24px 28px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--color-text-primary);
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 7px;
  border: none;
  background: var(--color-primary);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 20px;
  color: var(--color-text-tertiary);
}

.empty-icon {
  color: var(--color-text-tertiary);
}

.empty-state p {
  font-size: 14px;
}

.content-list {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}

.content-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 0.5px solid var(--color-border);
  transition: background 0.1s;
}

.content-item:last-child {
  border-bottom: none;
}

.content-item.clickable {
  cursor: pointer;
}

.content-item:hover {
  background: var(--color-surface-hover);
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  gap: 10px;
  margin-top: 3px;
}

.meta-account, .meta-schedule, .meta-images {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.badge {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-warning {
  background: rgba(255, 149, 0, 0.12);
  color: var(--color-warning);
}

.badge-info {
  background: rgba(0, 122, 255, 0.12);
  color: var(--color-info);
}

.badge-success {
  background: rgba(52, 199, 89, 0.12);
  color: var(--color-success);
}

.badge-danger {
  background: rgba(255, 59, 48, 0.12);
  color: var(--color-danger);
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 0.5px solid var(--color-border);
  background: transparent;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.btn-icon:hover {
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.btn-icon.danger:hover {
  color: var(--color-danger);
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-bar {
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(255, 59, 48, 0.1);
  color: var(--color-danger);
  font-size: 13px;
  margin-bottom: 16px;
  text-align: center;
}
</style>
