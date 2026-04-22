<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAccountStore } from '@/stores/accounts'
import { useContentStore } from '@/stores/content'
import { useAnalyticsStore } from '@/stores/analytics'
import { useSidecar } from '@/composables/useSidecar'
import { Users, FileText, Send, MessageSquare, Activity, Zap } from 'lucide-vue-next'

const router = useRouter()
const { callSidecar, sidecarRunning } = useSidecar()
const accountStore = useAccountStore()
const contentStore = useContentStore()
const analyticsStore = useAnalyticsStore()

const pipelineGenerated = ref(0)
const pipelinePublished = ref(0)

const accountCount = computed(() => accountStore.accounts.length)
const pendingContent = computed(() => contentStore.queue.filter(c => c.status === 'pending').length)
const publishedToday = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return contentStore.queue.filter(c => c.status === 'published' && c.created_at.startsWith(today)).length
})
const pendingComments = computed(() => 0)

const statCards = computed(() => [
  { label: '账号总数', value: accountCount.value, icon: Users, color: 'var(--color-info)' },
  { label: '待发布内容', value: pendingContent.value, icon: FileText, color: 'var(--color-warning)' },
  { label: '今日已发布', value: publishedToday.value, icon: Send, color: 'var(--color-success)' },
  { label: '管线已生成', value: pipelineGenerated.value, icon: Zap, color: 'var(--color-warning)' },
])

async function fetchPipelineStats() {
  if (accountStore.accounts.length === 0) return
  for (const acc of accountStore.accounts) {
    try {
      const resp = await callSidecar<{ running: boolean; generated_count: number; published_count: number }>(
        `/pipeline/status/${acc.id}`, { method: 'GET' }
      )
      pipelineGenerated.value += resp.generated_count
      pipelinePublished.value += resp.published_count
    } catch { /* ignore */ }
  }
}

onMounted(async () => {
  await Promise.all([
    accountStore.fetchAccounts(),
    contentStore.fetchQueue(),
    analyticsStore.fetchTaskLogs(20),
  ])
  fetchPipelineStats()
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">数据看板</h1>
    </header>

    <div class="stat-grid">
      <div v-for="card in statCards" :key="card.label" class="stat-card">
        <div class="stat-icon" :style="{ color: card.color }">
          <component :is="card.icon" :size="20" :stroke-width="1.5" />
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ card.value }}</span>
          <span class="stat-label">{{ card.label }}</span>
        </div>
      </div>
    </div>

    <section class="quick-actions">
      <button class="action-card" @click="router.push('/pipeline')">
        <Zap :size="20" :stroke-width="1.5" style="color: var(--color-warning)" />
        <span class="action-label">运行智能管线</span>
        <span class="action-desc">数据采集 → 分析 → 选题 → 生成</span>
      </button>
      <button class="action-card" @click="router.push('/content/editor')">
        <FileText :size="20" :stroke-width="1.5" style="color: var(--color-primary)" />
        <span class="action-label">新建内容</span>
        <span class="action-desc">AI 辅助创作笔记</span>
      </button>
    </section>

    <section class="section">
      <h2 class="section-title">
        <Activity :size="16" :stroke-width="1.5" />
        最近活动
      </h2>
      <div class="activity-list">
        <div
          v-if="analyticsStore.taskLogs.length === 0"
          class="empty-state"
        >
          暂无活动记录
        </div>
        <div
          v-for="log in analyticsStore.taskLogs"
          :key="log.id"
          class="activity-item"
        >
          <div class="activity-dot" :class="log.status" />
          <div class="activity-content">
            <span class="activity-type">{{ log.task_type }}</span>
            <span class="activity-msg">{{ log.message || '—' }}</span>
          </div>
          <span class="activity-time">{{ log.created_at }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page {
  padding: 24px 28px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--color-text-primary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 28px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  box-shadow: 0 0.5px 1px rgba(0, 0, 0, 0.04);
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.03);
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.5px;
  color: var(--color-text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 1px;
}

.section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.activity-list {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 0.5px solid var(--color-border);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  flex-shrink: 0;
}

.activity-dot.success {
  background: var(--color-success);
}

.activity-dot.error {
  background: var(--color-danger);
}

.activity-dot.running {
  background: var(--color-warning);
}

.activity-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.activity-type {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.activity-msg {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 16px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.action-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.action-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-top: 4px;
}

.action-desc {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
