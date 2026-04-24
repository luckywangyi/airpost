<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSidecar } from '@/composables/useSidecar'
import { useAnalyticsStore } from '@/stores/analytics'
import { useAccountStore } from '@/stores/accounts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { TrendingUp, Eye, Heart, Bookmark } from 'lucide-vue-next'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const { callSidecar } = useSidecar()
const analyticsStore = useAnalyticsStore()
const accountStore = useAccountStore()
const selectedAccount = ref<string>('')
const collecting = ref(false)
const collectMessage = ref('')

onMounted(async () => {
  await accountStore.fetchAccounts()
  if (accountStore.accounts.length > 0) {
    selectedAccount.value = accountStore.accounts[0].id
  }
  await analyticsStore.fetchStats()
})

async function handleCollectData() {
  if (!selectedAccount.value) return
  collecting.value = true
  collectMessage.value = ''
  try {
    const result = await callSidecar<{
      success: boolean
      message: string
      stats: Array<{
        note_url: string
        title: string
        views: number
        likes: number
        collects: number
        comments: number
        shares: number
      }>
    }>(`/scraper/collect_stats?account_id=${selectedAccount.value}`)

    if (!result.success) {
      collectMessage.value = result.message || '采集失败'
      return
    }

    if (result.stats.length > 0) {
      for (const stat of result.stats) {
        try {
          await invoke('add_note_stats', {
            stats: {
              id: `${selectedAccount.value}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
              account_id: selectedAccount.value,
              note_url: stat.note_url || '',
              title: stat.title || '',
              views: stat.views || 0,
              likes: stat.likes || 0,
              collects: stat.collects || 0,
              comments: stat.comments || 0,
              shares: stat.shares || 0,
              collected_at: new Date().toISOString(),
            },
          })
        } catch (e) {
          console.error('Failed to save stat:', e)
        }
      }
      await analyticsStore.fetchStats(selectedAccount.value)
      collectMessage.value = `成功采集 ${result.stats.length} 条笔记数据`
    } else {
      collectMessage.value = result.message || '未找到笔记数据'
    }
  } catch (e: any) {
    collectMessage.value = e?.message || '采集失败，请确保 Sidecar 已启动'
    console.error('Failed to collect data:', e)
  } finally {
    collecting.value = false
    if (collectMessage.value) {
      setTimeout(() => { collectMessage.value = '' }, 8000)
    }
  }
}

const filteredStats = computed(() => {
  if (!selectedAccount.value) return analyticsStore.stats
  return analyticsStore.stats.filter(s => s.account_id === selectedAccount.value)
})

const totalViews = computed(() => filteredStats.value.reduce((s, n) => s + n.views, 0))
const totalLikes = computed(() => filteredStats.value.reduce((s, n) => s + n.likes, 0))
const totalCollects = computed(() => filteredStats.value.reduce((s, n) => s + n.collects, 0))

const barChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: filteredStats.value.slice(0, 10).map(s => s.title.slice(0, 8) || '未命名'),
    axisLabel: { fontSize: 11, color: '#6e6e73' },
    axisLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 11, color: '#6e6e73' },
    splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
  },
  series: [
    {
      name: '浏览',
      type: 'bar',
      data: filteredStats.value.slice(0, 10).map(s => s.views),
      itemStyle: { color: '#007aff', borderRadius: [3, 3, 0, 0] },
      barWidth: 18,
    },
    {
      name: '点赞',
      type: 'bar',
      data: filteredStats.value.slice(0, 10).map(s => s.likes),
      itemStyle: { color: '#ff4757', borderRadius: [3, 3, 0, 0] },
      barWidth: 18,
    },
  ],
}))

const topNotes = computed(() =>
  [...filteredStats.value].sort((a, b) => b.views - a.views).slice(0, 5)
)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">数据分析</h1>
      <div class="header-tools">
        <select v-model="selectedAccount" class="filter-select">
          <option value="">全部账号</option>
          <option v-for="acc in accountStore.accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname }}
          </option>
        </select>
        <button
          class="btn-secondary"
          :disabled="collecting || !selectedAccount"
          @click="handleCollectData"
        >
          {{ collecting ? '采集中...' : '采集数据' }}
        </button>
      </div>
    </header>

    <div v-if="collectMessage" class="collect-msg" :class="{ error: collectMessage.includes('失败') || collectMessage.includes('未登录') }">
      {{ collectMessage }}
    </div>

    <div class="stat-row">
      <div class="stat-card">
        <Eye :size="18" :stroke-width="1.5" class="stat-icon-blue" />
        <div class="stat-info">
          <span class="stat-value">{{ totalViews.toLocaleString() }}</span>
          <span class="stat-label">总浏览量</span>
        </div>
      </div>
      <div class="stat-card">
        <Heart :size="18" :stroke-width="1.5" class="stat-icon-red" />
        <div class="stat-info">
          <span class="stat-value">{{ totalLikes.toLocaleString() }}</span>
          <span class="stat-label">总点赞</span>
        </div>
      </div>
      <div class="stat-card">
        <Bookmark :size="18" :stroke-width="1.5" class="stat-icon-yellow" />
        <div class="stat-info">
          <span class="stat-value">{{ totalCollects.toLocaleString() }}</span>
          <span class="stat-label">总收藏</span>
        </div>
      </div>
    </div>

    <section class="section">
      <h2 class="section-title">
        <TrendingUp :size="16" :stroke-width="1.5" />
        笔记表现
      </h2>
      <div class="chart-container">
        <VChart
          v-if="filteredStats.length > 0"
          :option="barChartOption"
          autoresize
          style="height: 260px"
        />
        <div v-else class="empty-chart">暂无数据</div>
      </div>
    </section>

    <section class="section">
      <h2 class="section-title">Top 笔记</h2>
      <div class="top-list">
        <div v-for="(note, i) in topNotes" :key="note.id" class="top-item">
          <span class="top-rank">{{ i + 1 }}</span>
          <span class="top-title">{{ note.title || '未命名' }}</span>
          <span class="top-views">{{ note.views.toLocaleString() }} 浏览</span>
        </div>
        <div v-if="topNotes.length === 0" class="empty-chart">暂无数据</div>
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
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--color-text-primary);
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-select {
  padding: 5px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
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

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.collect-msg {
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(52, 199, 89, 0.1);
  color: var(--color-success);
  font-size: 13px;
  margin-bottom: 16px;
  text-align: center;
}

.collect-msg.error {
  background: rgba(255, 149, 0, 0.1);
  color: var(--color-warning);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  box-shadow: 0 0.5px 1px rgba(0, 0, 0, 0.04);
}

.stat-icon-blue { color: var(--color-info); }
.stat-icon-red { color: var(--color-primary); }
.stat-icon-yellow { color: var(--color-warning); }

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-secondary);
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

.chart-container {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
}

.empty-chart {
  padding: 40px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.top-list {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 0.5px solid var(--color-border);
}

.top-item:last-child {
  border-bottom: none;
}

.top-rank {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.top-title {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-views {
  font-size: 12px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
</style>
