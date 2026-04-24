<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { MessageSquare, Reply, Bot } from 'lucide-vue-next'
import { useSidecar } from '@/composables/useSidecar'
import { useAccountStore } from '@/stores/accounts'

const { callSidecar } = useSidecar()
const accountStore = useAccountStore()
const aiApiKey = ref('')
const aiBaseUrl = ref('')
const aiModel = ref('gpt-4o-mini')

interface CommentItem {
  id: string
  accountName: string
  noteTitle: string
  user: string
  text: string
  time: string
  replied: boolean
  replyText?: string
}

const comments = ref<CommentItem[]>([])
const filterStatus = ref<'all' | 'pending' | 'replied'>('all')
const replyingId = ref<string | null>(null)
const replyDraft = ref('')

const checking = ref(false)
const selectedAccount = ref('')
const noteUrl = ref('')

onMounted(async () => {
  accountStore.fetchAccounts()
  try {
    const s = await invoke<Record<string, unknown>>('get_settings')
    aiApiKey.value = (s.ai_api_key as string) || ''
    aiBaseUrl.value = (s.ai_base_url as string) || ''
    aiModel.value = (s.ai_model as string) || 'gpt-4o-mini'
  } catch {
    // settings not available
  }
})

function startReply(id: string) {
  replyingId.value = id
  replyDraft.value = ''
}

function cancelReply() {
  replyingId.value = null
  replyDraft.value = ''
}

async function handleCheckComments() {
  if (!selectedAccount.value || !noteUrl.value) return
  checking.value = true
  try {
    const result = await callSidecar<{
      success: boolean
      comments: Array<{ user: string; text: string; time: string }>
    }>(`/comment/check?account_id=${selectedAccount.value}&note_url=${encodeURIComponent(noteUrl.value)}`)
    if (result.success) {
      comments.value = result.comments.map((c, i) => ({
        id: `${Date.now()}-${i}`,
        accountName: accountStore.accounts.find(a => a.id === selectedAccount.value)?.nickname || '',
        noteTitle: '',
        user: c.user,
        text: c.text,
        time: c.time,
        replied: false,
      }))
    }
  } catch (e) {
    console.error('Failed to check comments:', e)
  } finally {
    checking.value = false
  }
}

async function handleAiReply(commentId: string) {
  const c = comments.value.find(c => c.id === commentId)
  if (!c) return
  try {
    const params = new URLSearchParams({
      comment_text: c.text,
      tone: '友好',
      ...(aiApiKey.value && { api_key: aiApiKey.value }),
      ...(aiBaseUrl.value && { base_url: aiBaseUrl.value }),
      ...(aiModel.value && { model: aiModel.value }),
    })
    const result = await callSidecar<{ success: boolean; reply: string }>(
      `/ai/generate_reply?${params.toString()}`,
    )
    if (result.success) {
      replyDraft.value = result.reply
    }
  } catch (e) {
    console.error('AI reply failed:', e)
  }
}

async function submitReply(id: string) {
  const c = comments.value.find(c => c.id === id)
  if (!c || !replyDraft.value) return
  try {
    await callSidecar('/comment/reply', {
      body: {
        account_id: selectedAccount.value,
        note_url: noteUrl.value,
        comment_user: c.user,
        reply_text: replyDraft.value,
      },
    })
    c.replied = true
    c.replyText = replyDraft.value
  } catch (e) {
    console.error('Reply failed:', e)
  }
  replyingId.value = null
  replyDraft.value = ''
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">评论管理</h1>
      <div class="filter-group">
        <button
          :class="['filter-btn', { active: filterStatus === 'all' }]"
          @click="filterStatus = 'all'"
        >全部</button>
        <button
          :class="['filter-btn', { active: filterStatus === 'pending' }]"
          @click="filterStatus = 'pending'"
        >待回复</button>
        <button
          :class="['filter-btn', { active: filterStatus === 'replied' }]"
          @click="filterStatus = 'replied'"
        >已回复</button>
      </div>
    </header>

    <div class="check-bar">
      <select v-model="selectedAccount" class="filter-select">
        <option value="" disabled>选择账号</option>
        <option v-for="acc in accountStore.accounts" :key="acc.id" :value="acc.id">{{ acc.nickname }}</option>
      </select>
      <input v-model="noteUrl" class="url-input" placeholder="输入笔记 URL" />
      <button
        class="btn-primary"
        :disabled="checking || !selectedAccount || !noteUrl"
        @click="handleCheckComments"
      >
        {{ checking ? '检查中...' : '检查评论' }}
      </button>
    </div>

    <div v-if="comments.length === 0" class="empty-state">
      <MessageSquare :size="40" :stroke-width="1" />
      <p>暂无评论数据</p>
      <span class="empty-hint">评论会在自动巡检后显示在这里</span>
    </div>

    <div v-else class="comment-list">
      <div v-for="c in comments" :key="c.id" class="comment-card">
        <div class="comment-header">
          <span class="comment-user">{{ c.user }}</span>
          <span class="comment-source">{{ c.accountName }} · {{ c.noteTitle }}</span>
          <span class="comment-time">{{ c.time }}</span>
        </div>
        <div class="comment-text">{{ c.text }}</div>

        <div v-if="c.replied && c.replyText" class="reply-preview">
          <Reply :size="12" :stroke-width="1.5" />
          <span>{{ c.replyText }}</span>
        </div>

        <div v-if="replyingId === c.id" class="reply-box">
          <textarea
            v-model="replyDraft"
            placeholder="输入回复内容..."
            rows="2"
          />
          <div class="reply-actions">
            <button class="btn-secondary btn-sm" @click="cancelReply">取消</button>
            <button class="btn-ai btn-sm" @click="handleAiReply(c.id)">
              <Bot :size="13" :stroke-width="1.5" />
              AI 生成
            </button>
            <button class="btn-primary btn-sm" @click="submitReply(c.id)">发送</button>
          </div>
        </div>

        <div v-else-if="!c.replied" class="comment-actions">
          <button class="btn-secondary btn-sm" @click="startReply(c.id)">
            <Reply :size="13" :stroke-width="1.5" />
            回复
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

.filter-group {
  display: flex;
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  overflow: hidden;
}

.filter-btn {
  padding: 5px 12px;
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.filter-btn.active {
  background: var(--color-primary);
  color: white;
}

.filter-btn:hover:not(.active) {
  background: var(--color-surface-hover);
}

.check-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.filter-select {
  padding: 5px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
  width: 150px;
}

.url-input {
  flex: 1;
  padding: 5px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.url-input:focus,
.filter-select:focus {
  border-color: var(--color-primary);
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

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.comment-card {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 0.5px 1px rgba(0, 0, 0, 0.04);
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.comment-user {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.comment-source {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.comment-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-left: auto;
}

.comment-text {
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.5;
  margin-bottom: 8px;
}

.reply-preview {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.reply-box {
  margin-top: 8px;
}

.reply-box textarea {
  width: 100%;
  padding: 8px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  font-family: inherit;
  outline: none;
  resize: none;
}

.reply-box textarea:focus {
  border-color: var(--color-primary);
}

.reply-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 6px;
}

.comment-actions {
  display: flex;
  gap: 6px;
}

.btn-sm {
  padding: 4px 10px !important;
  font-size: 12px !important;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 4px;
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
  display: flex;
  align-items: center;
  gap: 4px;
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

.btn-ai {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 7px;
  border: 0.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-info);
  font-size: 13px;
  cursor: pointer;
}

.btn-ai:hover {
  background: var(--color-surface-hover);
}
</style>
