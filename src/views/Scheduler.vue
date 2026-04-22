<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSidecar } from '@/composables/useSidecar'
import { useAccountStore } from '@/stores/accounts'
import { Clock, Plus, Trash2, Play, Pause } from 'lucide-vue-next'

const { callSidecar } = useSidecar()
const accountStore = useAccountStore()

interface ScheduledJob {
  id: string
  name: string
  type: string
  cron: string
  nextRun: string
  enabled: boolean
}

const jobs = ref<ScheduledJob[]>([])
const showAddDialog = ref(false)
const newJobType = ref('publish')
const newJobCron = ref('0 12 * * *')
const selectedAccount = ref('')
const newJobName = ref('')

async function fetchJobs() {
  try {
    const result = await callSidecar<
      Array<{ id: string; name: string; next_run: string | null; trigger: string }>
    >('/scheduler/jobs', { method: 'GET' })
    jobs.value = result.map((j) => ({
      id: j.id,
      name: j.name,
      type: j.name.split('_')[0] || 'publish',
      cron: j.trigger,
      nextRun: j.next_run || '',
      enabled: true,
    }))
  } catch (e) {
    console.error('Failed to fetch jobs:', e)
  }
}

async function handleAddJob() {
  if (!newJobType.value || !newJobCron.value) return
  const taskId = `task_${Date.now()}`
  try {
    await callSidecar('/scheduler/add', {
      body: {
        task_id: taskId,
        task_type: newJobType.value,
        cron_expression: newJobCron.value,
        params: { account_id: selectedAccount.value },
      },
    })
    await fetchJobs()
    showAddDialog.value = false
  } catch (e) {
    console.error('Failed to add job:', e)
  }
}

async function handleRemoveJob(id: string) {
  try {
    await callSidecar(`/scheduler/remove/${id}`, { method: 'DELETE' })
    await fetchJobs()
  } catch (e) {
    console.error('Failed to remove job:', e)
  }
}

onMounted(() => {
  fetchJobs()
  accountStore.fetchAccounts()
})

function typeLabel(type: string) {
  switch (type) {
    case 'publish': return '定时发布'
    case 'check_comments': return '评论巡检'
    case 'collect_stats': return '数据采集'
    default: return type
  }
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">任务调度</h1>
      <button class="btn-primary" @click="showAddDialog = true">
        <Plus :size="16" :stroke-width="1.5" />
        添加任务
      </button>
    </header>

    <div v-if="jobs.length === 0" class="empty-state">
      <Clock :size="40" :stroke-width="1" />
      <p>暂无定时任务</p>
      <span class="empty-hint">添加定时任务来自动运行发布、评论巡检等操作</span>
    </div>

    <div v-else class="job-list">
      <div v-for="job in jobs" :key="job.id" class="job-item">
        <div class="job-indicator" :class="{ active: job.enabled }" />
        <div class="job-info">
          <span class="job-name">{{ job.name }}</span>
          <div class="job-meta">
            <span class="job-type">{{ typeLabel(job.type) }}</span>
            <span class="job-cron">{{ job.cron }}</span>
            <span v-if="job.nextRun" class="job-next">下次: {{ job.nextRun }}</span>
          </div>
        </div>
        <div class="job-actions">
          <button class="btn-icon" :title="job.enabled ? '暂停' : '启用'">
            <component :is="job.enabled ? Pause : Play" :size="14" :stroke-width="1.5" />
          </button>
          <button class="btn-icon danger" title="删除" @click="handleRemoveJob(job.id)">
            <Trash2 :size="14" :stroke-width="1.5" />
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog">
          <h3 class="dialog-title">添加定时任务</h3>
          <div class="form-field">
            <label>任务类型</label>
            <select v-model="newJobType">
              <option value="publish">定时发布</option>
              <option value="check_comments">评论巡检</option>
              <option value="collect_stats">数据采集</option>
            </select>
          </div>
          <div class="form-field">
            <label>关联账号</label>
            <select v-model="selectedAccount">
              <option value="">全部账号</option>
              <option v-for="acc in accountStore.accounts" :key="acc.id" :value="acc.id">
                {{ acc.nickname }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label>Cron 表达式</label>
            <input v-model="newJobCron" placeholder="0 12 * * *" />
            <span class="field-hint">分 时 日 月 周</span>
          </div>
          <div class="dialog-actions">
            <button class="btn-secondary" @click="showAddDialog = false">取消</button>
            <button class="btn-primary" @click="handleAddJob">添加</button>
          </div>
        </div>
      </div>
    </Teleport>
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
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-secondary {
  padding: 6px 14px;
  border-radius: 7px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
}

.btn-secondary:hover {
  background: var(--color-surface-hover);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 60px 20px;
  color: var(--color-text-tertiary);
}

.empty-state p {
  font-size: 14px;
  margin-top: 4px;
}

.empty-hint {
  font-size: 12px;
}

.job-list {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}

.job-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 0.5px solid var(--color-border);
}

.job-item:last-child {
  border-bottom: none;
}

.job-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  flex-shrink: 0;
}

.job-indicator.active {
  background: var(--color-success);
}

.job-info {
  flex: 1;
  min-width: 0;
}

.job-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.job-meta {
  display: flex;
  gap: 10px;
  margin-top: 2px;
}

.job-type, .job-cron, .job-next {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.job-actions {
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
}

.btn-icon:hover {
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.btn-icon.danger:hover {
  color: var(--color-danger);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.dialog {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 24px;
  width: 380px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--color-text-primary);
}

.form-field {
  margin-bottom: 12px;
}

.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.form-field input,
.form-field select {
  width: 100%;
  padding: 7px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.form-field input:focus,
.form-field select:focus {
  border-color: var(--color-primary);
}

.field-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 3px;
  display: block;
}

.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
