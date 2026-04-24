<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useSidecar } from '@/composables/useSidecar'
import { useAccountStore } from '@/stores/accounts'
import { useContentStore } from '@/stores/content'
import { useAnalyticsStore } from '@/stores/analytics'
import {
  Zap, Play, Loader2, CheckCircle2, XCircle, Clock,
  TrendingUp, Lightbulb, FileText, Send, MessageSquare,
  BarChart3, RefreshCw, Eye, Image as ImageIcon,
  Plus, X, Pause, Target, Compass, Brain,
} from 'lucide-vue-next'

const { callSidecar } = useSidecar()
const accountStore = useAccountStore()
const contentStore = useContentStore()
const analyticsStore = useAnalyticsStore()

const selectedAccount = ref('')
const niche = ref('')
const autoPublish = ref(true)
const autoReply = ref(false)
const manualReview = ref(false)
const running = ref(false)
const statusMessage = ref('')
const cronExpression = ref('0 10 * * *')

const aiApiKey = ref('')
const aiBaseUrl = ref('')
const aiModel = ref('gpt-4o-mini')
const assetFolder = ref('')
const pexelsApiKey = ref('')

// Strategy state
const strategyMode = ref<'explore' | 'exploit' | 'auto'>('auto')
const newDirectionName = ref('')
const newDirectionKeywords = ref('')

interface ContentDirection {
  id: string
  name: string
  keywords: string[]
  phase: string
  posts_count: number
  avg_views: number
  avg_engagement: number
  direction_score: number
  created_at: string
  last_posted: string
}

interface AccountStrategy {
  account_id: string
  directions: ContentDirection[]
  mode: string
  exploit_top_n: number
  explore_posts_per_direction: number
  min_data_posts: number
  evaluation_hours: number
}

const strategy = ref<AccountStrategy | null>(null)

interface ContentItemResult {
  title: string
  body: string
  tags: string[]
  score: number
  status: 'published' | 'failed' | 'pending_review'
  message: string
  image_paths: string[]
  direction_id: string
  direction_name: string
}

interface PipelineResult {
  success: boolean
  stages_completed: string[]
  topics_suggested: string[]
  content_generated: number
  content_published: number
  comments_replied: number
  message: string
  items: ContentItemResult[]
}

interface PipelineStatus {
  running: boolean
  last_run: string
  last_result: string
  generated_count: number
  published_count: number
  stage: string
}

const lastResult = ref<PipelineResult | null>(null)
const pipelineStatus = ref<PipelineStatus | null>(null)
const scheduledPipeline = ref(false)

const stageIcons: Record<string, any> = {
  '数据采集': BarChart3,
  '数据分析': TrendingUp,
  '热点探索': TrendingUp,
  '智能选题': Lightbulb,
  '内容生成': FileText,
  '图片获取': ImageIcon,
  '自动发布': Send,
  '评论管理': MessageSquare,
}

const allStages = ['数据采集', '数据分析', '热点探索', '智能选题', '内容生成', '图片获取', '自动发布', '评论管理']

const directionNames = computed(() =>
  (strategy.value?.directions || []).map(d => d.name)
)

const modeLabels: Record<string, string> = {
  explore: '探索模式',
  exploit: '深耕模式',
  auto: '自动模式',
}

const modeDescriptions: Record<string, string> = {
  explore: '为所有方向均匀生成内容，用于测试',
  exploit: '聚焦表现最好的方向集中发力',
  auto: '先探索后深耕，数据驱动自动切换',
}

function phaseLabel(phase: string): string {
  const map: Record<string, string> = {
    exploring: '探索中',
    evaluating: '评估中',
    exploiting: '深耕中',
    paused: '已暂停',
  }
  return map[phase] || phase
}

function phaseColor(phase: string): string {
  const map: Record<string, string> = {
    exploring: 'var(--color-primary)',
    evaluating: 'var(--color-warning)',
    exploiting: 'var(--color-success)',
    paused: 'var(--color-text-tertiary)',
  }
  return map[phase] || 'var(--color-text-secondary)'
}

onMounted(async () => {
  await accountStore.fetchAccounts()
  if (accountStore.accounts.length > 0) {
    selectedAccount.value = accountStore.accounts[0].id
    await loadStrategy()
  }
  try {
    const s = await invoke<any>('get_settings')
    aiApiKey.value = s.ai_api_key || ''
    aiBaseUrl.value = s.ai_base_url || ''
    aiModel.value = s.ai_model || 'gpt-4o-mini'
    assetFolder.value = s.asset_folder || ''
    pexelsApiKey.value = s.pexels_api_key || ''
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
})

async function loadStrategy() {
  if (!selectedAccount.value) return
  try {
    const resp = await callSidecar<AccountStrategy>(
      `/strategy/get/${selectedAccount.value}`,
      { method: 'GET' },
    )
    strategy.value = resp
    strategyMode.value = (resp.mode as any) || 'auto'
  } catch {
    strategy.value = null
  }
}

async function addDirection() {
  const name = newDirectionName.value.trim()
  if (!name || !selectedAccount.value) return
  try {
    const kw = newDirectionKeywords.value.trim()
    const params = new URLSearchParams({ name })
    if (kw) params.set('keywords', kw)
    await callSidecar(`/strategy/add_direction/${selectedAccount.value}?${params}`)
    newDirectionName.value = ''
    newDirectionKeywords.value = ''
    await loadStrategy()
  } catch (e: any) {
    statusMessage.value = e?.message || '添加方向失败'
  }
}

async function removeDirection(dirId: string) {
  if (!selectedAccount.value) return
  try {
    await callSidecar(`/strategy/remove_direction/${selectedAccount.value}?direction_id=${dirId}`)
    await loadStrategy()
  } catch (e: any) {
    statusMessage.value = e?.message || '删除方向失败'
  }
}

async function toggleDirection(dirId: string) {
  if (!selectedAccount.value) return
  try {
    await callSidecar(`/strategy/toggle_direction/${selectedAccount.value}?direction_id=${dirId}`)
    await loadStrategy()
  } catch (e: any) {
    statusMessage.value = e?.message || '切换状态失败'
  }
}

async function setMode(mode: 'explore' | 'exploit' | 'auto') {
  if (!selectedAccount.value) return
  strategyMode.value = mode
  try {
    await callSidecar(`/strategy/set_mode/${selectedAccount.value}?mode=${mode}`)
    await loadStrategy()
  } catch (e: any) {
    statusMessage.value = e?.message || '设置模式失败'
  }
}

async function evaluateDirections() {
  if (!selectedAccount.value) return
  try {
    const resp = await callSidecar<any>(
      `/strategy/evaluate/${selectedAccount.value}`,
    )
    if (resp.success) {
      statusMessage.value = resp.message || '评估完成'
      await loadStrategy()
    } else {
      statusMessage.value = resp.message || '评估失败'
    }
  } catch (e: any) {
    statusMessage.value = e?.message || '评估失败'
  }
}

async function runPipeline() {
  if (!selectedAccount.value) {
    statusMessage.value = '请先选择一个账号'
    return
  }
  if (!aiApiKey.value) {
    statusMessage.value = '请先在设置中配置 AI API Key'
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
        manual_review: manualReview.value,
        api_key: aiApiKey.value,
        base_url: aiBaseUrl.value,
        model: aiModel.value,
        asset_folder: assetFolder.value,
        pexels_api_key: pexelsApiKey.value,
        strategy_mode: strategyMode.value,
        content_directions: directionNames.value,
      },
    })
    lastResult.value = result
    statusMessage.value = result.message

    if (result.items && result.items.length > 0) {
      const now = new Date().toISOString()
      for (const item of result.items) {
        const itemId = `pl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        try {
          await contentStore.addContent({
            id: itemId,
            account_id: selectedAccount.value,
            title: item.title,
            body: item.body,
            tags: item.tags.map(t => `#${t}`).join(' '),
            images: (item.image_paths || []).join(','),
            scheduled_at: null,
            status: item.status === 'published' ? 'published' : item.status === 'pending_review' ? 'pending' : 'failed',
            created_at: now,
          })
        } catch (e) {
          console.error('Failed to save pipeline item to queue:', e)
        }

        if (item.status === 'published' || item.status === 'pending_review') {
          try {
            await invoke('add_note_stats', {
              stats: {
                id: `ns_${itemId}`,
                account_id: selectedAccount.value,
                note_url: '',
                title: item.title,
                views: 0,
                likes: 0,
                collects: 0,
                comments: 0,
                shares: 0,
                collected_at: now,
              },
            })
          } catch (e) {
            console.error('Failed to save note stats:', e)
          }
        }
      }
    }

    await loadStrategy()
  } catch (e: any) {
    statusMessage.value = e?.message || '管线执行失败'
  } finally {
    running.value = false
  }
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
        manual_review: manualReview.value,
        api_key: aiApiKey.value,
        base_url: aiBaseUrl.value,
        model: aiModel.value,
        asset_folder: assetFolder.value,
        pexels_api_key: pexelsApiKey.value,
        strategy_mode: strategyMode.value,
        content_directions: directionNames.value,
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

function statusColor(status: string): string {
  if (status === 'published') return 'var(--color-success)'
  if (status === 'failed') return 'var(--color-danger)'
  return 'var(--color-warning)'
}

function statusText(status: string): string {
  if (status === 'published') return '已发布'
  if (status === 'failed') return '发布失败'
  return '待审核'
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
          <select v-model="selectedAccount" @change="loadStrategy">
            <option value="" disabled>选择账号</option>
            <option v-for="acc in accountStore.accounts" :key="acc.id" :value="acc.id">
              {{ acc.nickname }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label>备用领域（无方向时使用）</label>
          <input v-model="niche" placeholder="如：美妆护肤、数码科技、美食探店..." />
        </div>
      </div>
      <div class="config-row">
        <label class="toggle-field">
          <input type="checkbox" v-model="autoPublish" />
          <span>自动发布（生成后自动获取图片并发布）</span>
        </label>
        <label class="toggle-field">
          <input type="checkbox" v-model="manualReview" />
          <Eye :size="13" :stroke-width="1.5" />
          <span>人工审核（生成后暂停，等待确认）</span>
        </label>
        <label class="toggle-field">
          <input type="checkbox" v-model="autoReply" />
          <span>自动回复评论（开发中）</span>
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

    <!-- Strategy Panel -->
    <section class="strategy-panel">
      <div class="strategy-header">
        <h2 class="section-title">
          <Brain :size="16" :stroke-width="1.5" />
          内容策略
        </h2>
        <button class="btn-secondary" @click="evaluateDirections" :disabled="!selectedAccount">
          <BarChart3 :size="14" :stroke-width="1.5" />
          评估方向
        </button>
      </div>

      <!-- Mode Selector -->
      <div class="mode-selector">
        <button
          v-for="m in (['auto', 'explore', 'exploit'] as const)"
          :key="m"
          class="mode-btn"
          :class="{ active: strategyMode === m }"
          @click="setMode(m)"
        >
          <Compass v-if="m === 'explore'" :size="14" :stroke-width="1.5" />
          <Target v-else-if="m === 'exploit'" :size="14" :stroke-width="1.5" />
          <Brain v-else :size="14" :stroke-width="1.5" />
          <span class="mode-name">{{ modeLabels[m] }}</span>
          <span class="mode-desc">{{ modeDescriptions[m] }}</span>
        </button>
      </div>

      <!-- Directions -->
      <div class="directions-section">
        <h3 class="subsection-title">内容方向</h3>
        <div class="add-direction">
          <input
            v-model="newDirectionName"
            placeholder="方向名称，如：通勤穿搭"
            @keyup.enter="addDirection"
          />
          <input
            v-model="newDirectionKeywords"
            placeholder="关键词（逗号分隔，可选）"
            class="keywords-input"
          />
          <button class="btn-secondary btn-sm" @click="addDirection" :disabled="!newDirectionName.trim()">
            <Plus :size="14" :stroke-width="1.5" />
            添加
          </button>
        </div>

        <div v-if="strategy && strategy.directions.length > 0" class="direction-cards">
          <div
            v-for="dir in strategy.directions"
            :key="dir.id"
            class="direction-card"
            :class="{ paused: dir.phase === 'paused' }"
          >
            <div class="dir-header">
              <span class="dir-name">{{ dir.name }}</span>
              <span class="dir-phase" :style="{ color: phaseColor(dir.phase) }">
                {{ phaseLabel(dir.phase) }}
              </span>
            </div>
            <div v-if="dir.keywords.length > 0" class="dir-keywords">
              <span v-for="kw in dir.keywords" :key="kw" class="kw-chip">{{ kw }}</span>
            </div>
            <div class="dir-stats">
              <div class="dir-stat">
                <span class="dir-stat-val">{{ dir.posts_count }}</span>
                <span class="dir-stat-lbl">已发</span>
              </div>
              <div class="dir-stat">
                <span class="dir-stat-val">{{ dir.avg_views > 0 ? Math.round(dir.avg_views) : '—' }}</span>
                <span class="dir-stat-lbl">均阅读</span>
              </div>
              <div class="dir-stat">
                <span class="dir-stat-val">{{ dir.avg_engagement > 0 ? dir.avg_engagement.toFixed(1) + '%' : '—' }}</span>
                <span class="dir-stat-lbl">互动率</span>
              </div>
              <div class="dir-stat">
                <span class="dir-stat-val" :style="{ color: dir.direction_score > 60 ? 'var(--color-success)' : '' }">
                  {{ dir.direction_score > 0 ? dir.direction_score.toFixed(0) : '—' }}
                </span>
                <span class="dir-stat-lbl">得分</span>
              </div>
            </div>
            <div class="dir-actions">
              <button class="btn-icon" @click="toggleDirection(dir.id)" :title="dir.phase === 'paused' ? '恢复' : '暂停'">
                <Play v-if="dir.phase === 'paused'" :size="13" :stroke-width="1.5" />
                <Pause v-else :size="13" :stroke-width="1.5" />
              </button>
              <button class="btn-icon btn-icon-danger" @click="removeDirection(dir.id)" title="删除">
                <X :size="13" :stroke-width="1.5" />
              </button>
            </div>
          </div>
        </div>
        <div v-else class="empty-directions">
          <p>尚未配置内容方向。添加 3-5 个方向开始探索，或直接输入"备用领域"使用单领域模式。</p>
        </div>
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

    <!-- Generated Content Results -->
    <section v-if="lastResult && lastResult.items && lastResult.items.length > 0" class="section">
      <h2 class="section-title">
        <FileText :size="16" :stroke-width="1.5" />
        生成内容
      </h2>
      <div class="content-queue">
        <div v-for="(item, i) in lastResult.items" :key="i" class="queue-card">
          <div class="queue-header">
            <div>
              <h3 class="queue-title">{{ item.title }}</h3>
              <span v-if="item.direction_name" class="queue-direction">{{ item.direction_name }}</span>
            </div>
            <div class="score-badge" :style="{ color: scoreColor(item.score) }">
              <span class="score-value">{{ item.score }}</span>
              <span class="score-label">{{ scoreLabel(item.score) }}</span>
            </div>
          </div>
          <p class="queue-body">{{ item.body.slice(0, 120) }}{{ item.body.length > 120 ? '...' : '' }}</p>
          <div class="queue-tags">
            <span v-for="tag in item.tags" :key="tag" class="tag">#{{ tag }}</span>
          </div>
          <div class="queue-footer">
            <span class="item-status" :style="{ color: statusColor(item.status) }">
              {{ statusText(item.status) }}
            </span>
            <span v-if="item.message && item.status === 'failed'" class="item-error">{{ item.message }}</span>
            <span v-if="item.image_paths && item.image_paths.length > 0" class="item-images">
              <ImageIcon :size="12" :stroke-width="1.5" />
              {{ item.image_paths.length }} 张图片
            </span>
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
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary.scheduled { color: var(--color-success); border-color: var(--color-success); }

.btn-sm {
  padding: 5px 10px;
  font-size: 12px;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.btn-icon:hover { background: var(--color-surface-hover); }
.btn-icon-danger:hover { color: var(--color-danger); border-color: var(--color-danger); }

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

/* Strategy Panel */
.strategy-panel {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
}

.strategy-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.mode-selector {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border-radius: 8px;
  border: 1.5px solid var(--color-border);
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
}

.mode-btn:hover { border-color: var(--color-primary); }

.mode-btn.active {
  border-color: var(--color-primary);
  background: rgba(0, 122, 255, 0.06);
}

.mode-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.mode-desc {
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-align: center;
}

.subsection-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
}

.add-direction {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.add-direction input {
  flex: 1;
  padding: 6px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: transparent;
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.add-direction input:focus { border-color: var(--color-primary); }

.keywords-input {
  max-width: 200px;
}

.direction-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.direction-card {
  border: 0.5px solid var(--color-border);
  border-radius: 9px;
  padding: 12px;
  background: var(--color-bg);
  transition: all 0.15s;
}

.direction-card.paused {
  opacity: 0.55;
}

.dir-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.dir-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.dir-phase {
  font-size: 11px;
  font-weight: 600;
}

.dir-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.kw-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(0, 122, 255, 0.08);
  color: var(--color-primary);
}

.dir-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-bottom: 8px;
}

.dir-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dir-stat-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.dir-stat-lbl {
  font-size: 10px;
  color: var(--color-text-tertiary);
}

.dir-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

.empty-directions {
  text-align: center;
  padding: 16px;
  color: var(--color-text-tertiary);
  font-size: 13px;
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

.queue-direction {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(0, 122, 255, 0.08);
  color: var(--color-primary);
  margin-top: 4px;
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

.queue-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 0.5px solid var(--color-border);
}

.item-status {
  font-size: 12px;
  font-weight: 600;
}

.item-error {
  font-size: 11px;
  color: var(--color-danger);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-images {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--color-text-tertiary);
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
