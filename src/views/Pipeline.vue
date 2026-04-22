<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSidecar } from '@/composables/useSidecar'
import { useAccountStore } from '@/stores/accounts'
import {
  Zap, Play, Loader2, CheckCircle2, XCircle, Clock,
  TrendingUp, Lightbulb, FileText, Send, MessageSquare,
  BarChart3, RefreshCw,
} from 'lucide-vue-next'

const { callSidecar } = useSidecar()
const accountStore = useAccountStore()

const selectedAccount = ref('')
const niche = ref('')
const autoPublish = ref(false)
const autoReply = ref(false)
const running = ref(false)
const statusMessage = ref('')
const cronExpression = ref('0 10 * * *')

interface PipelineResult {
  success: boolean
  stages_completed: string[]
  topics_suggested: string[]
  content_generated: number
  content_published: number
  comments_replied: number
  message: string
}

interface PipelineStatus {
  running: boolean
  last_run: string
  last_result: string
  generated_count: number
  published_count: number
  stage: string
}

interface QueueItem {
  title: string
  body: string
  tags: string[]
  score: number
}

const lastResult = ref<PipelineResult | null>(null)
const pipelineStatus = ref<PipelineStatus | null>(null)
const contentQueue = ref<QueueItem[]>([])
const scheduledPipeline = ref(false)

const stageIcons: Record<string, any> = {
  '数据采集': BarChart3,
  '数据分析': TrendingUp,
  '热点探索': TrendingUp,
  '智能选题': Lightbulb,
  '内容生成': FileText,
  '自动发布': Send,
  '评论管理': MessageSquare,
}

const allStages = ['数据采集', '数据分析', '热点探索', '智能选题', '内容生成', '自动发布', '评论管理']

onMounted(async () => {
  await accountStore.fetchAccounts()
  if (accountStore.accounts.length > 0) {
    selectedAccount.value = accountStore.accounts[0].id
  }
})

async function runPipeline() {
  if (!selectedAccount.value) {
    statusMessage.value = '请先选择一个账号'
    return
  }
  running.value = true
  statusMessage.value = '管线启动中...'
  lastResult.value = null

  try {
    const result = await callSidecar<PipelineResult>('/pipeline/run', {
      body: {
        account_id: selectedAccount.value,
        niche: niche.value,
        auto_publish: autoPublish.value,
        auto_reply: autoReply.value,
      },
    })
    lastResult.value = result
    statusMessage.value = result.message

    await fetchQueue()
  } catch (e: any) {
    statusMessage.value = e?.message || '管线执行失败'
  } finally {
    running.value = false
  }
}

async function fetchQueue() {
  if (!selectedAccount.value) return
  try {
    const resp = await callSidecar<{ items: QueueItem[] }>(
      `/pipeline/queue/${selectedAccount.value}`,
      { method: 'GET' },
    )
    contentQueue.value = resp.items || []
  } catch { /* empty */ }
}

async function fetchStatus() {
  if (!selectedAccount.value) return
  try {
    const resp = await callSidecar<PipelineStatus>(
      `/pipeline/status/${selectedAccount.value}`,
      { method: 'GET' },
    )
    pipelineStatus.value = resp
  } catch { /* empty */ }
}

async function schedulePipeline() {
  if (!selectedAccount.value) return
  try {
    await callSidecar('/scheduler/pipeline', {
      body: {
        account_id: selectedAccount.value,
        niche: niche.value,
        cron_expression: cronExpression.value,
        auto_publish: autoPublish.value,
        auto_reply: autoReply.value,
      },
    })
    scheduledPipeline.value = true
    statusMessage.value = `智能管线已设定为 ${cronExpression.value} 定时执行`
  } catch (e: any) {
    statusMessage.value = e?.message || '调度设置失败'
  }
}

function scoreColor(score: number): string {
  if (score >= 80) return 'var(--color-success)'
  if (score >= 60) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

function scoreLabel(score: number): string {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '中等'
  if (score >= 60) return '及格'
  return '待优化'
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">
        <Zap :size="22" :stroke-width="1.5" style="color: var(--color-warning)" />
        智能管线
      </h1>
      <div class="header-actions">
        <button class="btn-secondary" @click="fetchStatus">
          <RefreshCw :size="14" :stroke-width="1.5" />
          刷新状态
        </button>
        <button
          class="btn-primary"
          :disabled="running || !selectedAccount"
          @click="runPipeline"
        >
          <Loader2 v-if="running" :size="14" :stroke-width="1.5" class="spin" />
          <Play v-else :size="14" :stroke-width="1.5" />
          {{ running ? '运行中...' : '立即执行' }}
        </button>
      </div>
    </header>

    <div v-if="statusMessage" class="status-bar" :class="{ error: statusMessage.includes('失败') }">
      {{ statusMessage }}
    </div>

    <!-- Config Panel -->
    <section class="config-panel">
      <div class="config-row">
        <div class="form-field">
          <label>运营账号</label>
          <select v-model="selectedAccount">
            <option value="" disabled>选择账号</option>
            <option v-for="acc in accountStore.accounts" :key="acc.id" :value="acc.id">
              {{ acc.nickname }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label>内容领域</label>
          <input v-model="niche" placeholder="如：美妆护肤、数码科技、美食探店..." />
        </div>
      </div>
      <div class="config-row">
        <label class="toggle-field">
          <input type="checkbox" v-model="autoPublish" />
          <span>自动发布（评分≥75分自动发布）</span>
        </label>
        <label class="toggle-field">
          <input type="checkbox" v-model="autoReply" />
          <span>自动回复评论</span>
        </label>
      </div>
      <div class="config-row schedule-row">
        <div class="form-field">
          <label>定时表达式</label>
          <input v-model="cronExpression" placeholder="0 10 * * *" />
          <span class="field-hint">分 时 日 月 周 (默认每天10点)</span>
        </div>
        <button
          class="btn-secondary"
          :class="{ scheduled: scheduledPipeline }"
          @click="schedulePipeline"
        >
          <Clock :size="14" :stroke-width="1.5" />
          {{ scheduledPipeline ? '已设定' : '设为定时' }}
        </button>
      </div>
    </section>

    <!-- Pipeline Stages -->
    <section v-if="lastResult" class="stages-section">
      <h2 class="section-title">执行阶段</h2>
      <div class="stages-track">
        <div
          v-for="stage in allStages"
          :key="stage"
          class="stage-node"
          :class="{
            completed: lastResult.stages_completed.includes(stage),
            skipped: !lastResult.stages_completed.includes(stage),
          }"
        >
          <div class="stage-icon">
            <CheckCircle2 v-if="lastResult.stages_completed.includes(stage)" :size="16" :stroke-width="1.5" />
            <XCircle v-else :size="16" :stroke-width="1.5" />
          </div>
          <span class="stage-label">{{ stage }}</span>
        </div>
      </div>
    </section>

    <!-- Suggested Topics -->
    <section v-if="lastResult && lastResult.topics_suggested.length > 0" class="section">
      <h2 class="section-title">
        <Lightbulb :size="16" :stroke-width="1.5" />
        智能选题推荐
      </h2>
      <div class="topic-list">
        <div v-for="(topic, i) in lastResult.topics_suggested" :key="i" class="topic-chip">
          <span class="topic-num">{{ i + 1 }}</span>
          {{ topic }}
        </div>
      </div>
    </section>

    <!-- Generated Content Queue -->
    <section v-if="contentQueue.length > 0" class="section">
      <h2 class="section-title">
        <FileText :size="16" :stroke-width="1.5" />
        生成内容（待审核）
      </h2>
      <div class="content-queue">
        <div v-for="(item, i) in contentQueue" :key="i" class="queue-card">
          <div class="queue-header">
            <h3 class="queue-title">{{ item.title }}</h3>
            <div class="score-badge" :style="{ color: scoreColor(item.score) }">
              <span class="score-value">{{ item.score }}</span>
              <span class="score-label">{{ scoreLabel(item.score) }}</span>
            </div>
          </div>
          <p class="queue-body">{{ item.body.slice(0, 120) }}{{ item.body.length > 120 ? '...' : '' }}</p>
          <div class="queue-tags">
            <span v-for="tag in item.tags" :key="tag" class="tag">#{{ tag }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Pipeline Stats -->
    <section v-if="pipelineStatus" class="section">
      <h2 class="section-title">
        <BarChart3 :size="16" :stroke-width="1.5" />
        累计统计
      </h2>
      <div class="mini-stats">
        <div class="mini-stat">
          <span class="mini-value">{{ pipelineStatus.generated_count }}</span>
          <span class="mini-label">已生成</span>
        </div>
        <div class="mini-stat">
          <span class="mini-value">{{ pipelineStatus.published_count }}</span>
          <span class="mini-label">已发布</span>
        </div>
        <div class="mini-stat">
          <span class="mini-value">{{ pipelineStatus.last_run ? pipelineStatus.last_run.slice(5, 16).replace('T', ' ') : '—' }}</span>
          <span class="mini-label">上次运行</span>
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--color-text-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 16px;
  border-radius: 7px;
  border: none;
  background: var(--color-primary);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: 7px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-secondary:hover { background: var(--color-surface-hover); }
.btn-secondary.scheduled { color: var(--color-success); border-color: var(--color-success); }

.status-bar {
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(52, 199, 89, 0.1);
  color: var(--color-success);
  font-size: 13px;
  margin-bottom: 16px;
  text-align: center;
}

.status-bar.error {
  background: rgba(255, 59, 48, 0.1);
  color: var(--color-danger);
}

.config-panel {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
}

.config-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  align-items: flex-end;
}

.config-row:last-child { margin-bottom: 0; }

.form-field {
  flex: 1;
}

.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.form-field input, .form-field select {
  width: 100%;
  padding: 7px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.form-field input:focus, .form-field select:focus {
  border-color: var(--color-primary);
}

.field-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
  display: block;
}

.toggle-field {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.toggle-field input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: var(--color-primary);
}

.schedule-row {
  align-items: flex-end;
}

.schedule-row .btn-secondary {
  white-space: nowrap;
  margin-bottom: 0;
}

.section {
  margin-bottom: 20px;
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

.stages-section {
  margin-bottom: 20px;
}

.stages-track {
  display: flex;
  gap: 4px;
  overflow-x: auto;
}

.stage-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  flex: 1;
  min-width: 80px;
  transition: all 0.2s;
}

.stage-node.completed {
  background: rgba(52, 199, 89, 0.08);
  border-color: rgba(52, 199, 89, 0.3);
}

.stage-node.completed .stage-icon { color: var(--color-success); }
.stage-node.skipped .stage-icon { color: var(--color-text-tertiary); }

.stage-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-align: center;
}

.topic-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--color-text-primary);
}

.topic-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-queue {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.queue-card {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 14px;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.queue-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.3;
}

.score-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.score-value {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.score-label {
  font-size: 10px;
  font-weight: 500;
}

.queue-body {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-bottom: 8px;
}

.queue-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  font-size: 11px;
  color: var(--color-primary);
  background: rgba(0, 122, 255, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
}

.mini-stats {
  display: flex;
  gap: 20px;
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  flex: 1;
}

.mini-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.mini-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin {
  animation: spin 1s linear infinite;
}
</style>
