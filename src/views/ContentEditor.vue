<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useContentStore, type ContentItem } from '@/stores/content'
import { useAccountStore } from '@/stores/accounts'
import { useSidecar } from '@/composables/useSidecar'
import { ArrowLeft, Sparkles, Upload, X, TrendingUp } from 'lucide-vue-next'

const router = useRouter()
const { callSidecar } = useSidecar()
const contentStore = useContentStore()
const accountStore = useAccountStore()

const title = ref('')
const body = ref('')
const tags = ref('')
const selectedAccount = ref('')
const scheduledAt = ref('')
const imagePaths = ref<string[]>([])
const generating = ref(false)
const contentScore = ref(0)
const scoreBreakdown = ref<Record<string, number>>({})

onMounted(() => {
  accountStore.fetchAccounts()
})

function generateId(): string {
  return crypto.randomUUID()
}

async function handleSave() {
  if (!title.value.trim() || !selectedAccount.value) return
  const item: ContentItem = {
    id: generateId(),
    account_id: selectedAccount.value,
    title: title.value.trim(),
    body: body.value.trim(),
    tags: tags.value.trim(),
    images: imagePaths.value.join(','),
    scheduled_at: scheduledAt.value || null,
    status: 'pending',
    created_at: new Date().toISOString(),
  }
  await contentStore.addContent(item)
  router.push('/content')
}

function removeImage(index: number) {
  imagePaths.value.splice(index, 1)
}

async function handleAiGenerate() {
  if (!title.value.trim()) return
  generating.value = true
  try {
    const result = await callSidecar<{
      success: boolean
      title: string
      body: string
      tags: string[]
      score: number
      score_breakdown: Record<string, number>
      message?: string
    }>('/ai/generate', {
      body: {
        topic: title.value.trim(),
        account_id: selectedAccount.value || undefined,
      },
    })
    if (result.success) {
      title.value = result.title
      body.value = result.body
      tags.value = result.tags.map(t => `#${t}`).join(' ')
      contentScore.value = result.score
      scoreBreakdown.value = result.score_breakdown || {}
    }
  } catch (e) {
    console.error('AI generation failed:', e)
  } finally {
    generating.value = false
  }
}

async function handlePublishNow() {
  if (!title.value.trim() || !selectedAccount.value) return
  try {
    const result = await callSidecar<{ success: boolean; message: string; note_url: string }>('/publish/post', {
      body: {
        account_id: selectedAccount.value,
        title: title.value.trim(),
        body: body.value.trim(),
        tags: tags.value.split(/\s+/).filter(Boolean).map(t => t.replace(/^#/, '')),
        image_paths: imagePaths.value,
      },
    })
    if (result.success) {
      router.push('/content')
    }
  } catch (e) {
    console.error('Publish failed:', e)
  }
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <button class="btn-back" @click="router.push('/content')">
        <ArrowLeft :size="18" :stroke-width="1.5" />
      </button>
      <h1 class="page-title">新建内容</h1>
      <div class="header-actions">
        <button class="btn-secondary" :disabled="generating" @click="handleAiGenerate">
          <Sparkles :size="14" :stroke-width="1.5" />
          {{ generating ? '生成中...' : 'AI 生成' }}
        </button>
        <button class="btn-primary" @click="handleSave">保存到队列</button>
      </div>
    </header>

    <div class="editor-layout">
      <div class="editor-main">
        <div class="form-field">
          <label>标题</label>
          <input v-model="title" placeholder="输入笔记标题" maxlength="20" />
          <span class="char-count">{{ title.length }}/20</span>
        </div>

        <div class="form-field">
          <label>正文</label>
          <textarea v-model="body" placeholder="输入笔记内容..." rows="12" />
        </div>

        <div class="form-field">
          <label>标签（空格分隔）</label>
          <input v-model="tags" placeholder="#好物推荐 #生活方式" />
        </div>

        <div class="form-field">
          <label>图片</label>
          <div class="image-area">
            <div v-for="(img, i) in imagePaths" :key="i" class="image-thumb">
              <span class="image-name">{{ img.split(/[\\/]/).pop() }}</span>
              <button class="remove-btn" @click="removeImage(i)">
                <X :size="12" :stroke-width="2" />
              </button>
            </div>
            <div class="upload-placeholder">
              <Upload :size="20" :stroke-width="1.5" />
              <span>添加图片</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="editor-sidebar">
        <div class="form-field">
          <label>发布账号</label>
          <select v-model="selectedAccount">
            <option value="" disabled>选择账号</option>
            <option
              v-for="acc in accountStore.accounts"
              :key="acc.id"
              :value="acc.id"
            >
              {{ acc.nickname }}
            </option>
          </select>
        </div>

        <div class="form-field">
          <label>定时发布</label>
          <input v-model="scheduledAt" type="datetime-local" />
        </div>

        <!-- Content Score Panel -->
        <div v-if="contentScore > 0" class="score-panel">
          <div class="score-header">
            <TrendingUp :size="14" :stroke-width="1.5" />
            <span>内容评分</span>
          </div>
          <div class="score-circle" :class="{ good: contentScore >= 80, mid: contentScore >= 60 && contentScore < 80, low: contentScore < 60 }">
            <span class="score-number">{{ contentScore }}</span>
            <span class="score-max">/100</span>
          </div>
          <div class="score-details">
            <div v-for="(val, key) in scoreBreakdown" :key="key" class="score-item">
              <span class="score-key">{{ key }}</span>
              <span class="score-val">+{{ val }}</span>
            </div>
          </div>
        </div>
      </aside>
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
  gap: 10px;
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--color-text-primary);
  flex: 1;
}

.btn-back {
  width: 32px;
  height: 32px;
  border-radius: 7px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-back:hover {
  background: var(--color-surface-hover);
}

.header-actions {
  display: flex;
  gap: 8px;
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

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 7px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-secondary:hover {
  background: var(--color-surface-hover);
}

.editor-layout {
  display: flex;
  gap: 20px;
}

.editor-main {
  flex: 1;
  min-width: 0;
}

.editor-sidebar {
  width: 240px;
  flex-shrink: 0;
}

.form-field {
  margin-bottom: 16px;
  position: relative;
}

.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 5px;
}

.form-field input,
.form-field select,
.form-field textarea {
  width: 100%;
  padding: 8px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
  resize: vertical;
}

.form-field input:focus,
.form-field select:focus,
.form-field textarea:focus {
  border-color: var(--color-primary);
}

.char-count {
  position: absolute;
  right: 8px;
  top: 32px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.image-area {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.image-thumb {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.image-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  width: 16px;
  height: 16px;
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-btn:hover {
  color: var(--color-danger);
}

.upload-placeholder {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px 24px;
  border: 1.5px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-text-tertiary);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.upload-placeholder:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.score-panel {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 14px;
  margin-top: 8px;
}

.score-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
}

.score-circle {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  margin-bottom: 10px;
}

.score-circle.good .score-number { color: var(--color-success); }
.score-circle.mid .score-number { color: var(--color-warning); }
.score-circle.low .score-number { color: var(--color-danger); }

.score-number {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -1px;
}

.score-max {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.score-details {
  border-top: 0.5px solid var(--color-border);
  padding-top: 8px;
}

.score-item {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}

.score-key {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.score-val {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-success);
}
</style>
