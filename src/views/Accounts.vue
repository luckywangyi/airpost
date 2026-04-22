<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAccountStore, type Account } from '@/stores/accounts'
import { useSidecar } from '@/composables/useSidecar'
import { Plus, Wifi, WifiOff, Trash2, RefreshCw } from 'lucide-vue-next'

const { callSidecar } = useSidecar()
const accountStore = useAccountStore()
const showAddDialog = ref(false)
const loginLoading = ref<string | null>(null)
const newNickname = ref('')
const newProxy = ref('')

onMounted(() => {
  accountStore.fetchAccounts()
})

function generateId(): string {
  return crypto.randomUUID()
}

async function handleAdd() {
  if (!newNickname.value.trim()) return
  const account: Account = {
    id: generateId(),
    nickname: newNickname.value.trim(),
    cookie_path: '',
    proxy: newProxy.value.trim() || null,
    status: 'active',
    last_login: '',
    daily_post_limit: 5,
  }
  await accountStore.addAccount(account)
  newNickname.value = ''
  newProxy.value = ''
  showAddDialog.value = false
}

async function handleDelete(id: string) {
  await accountStore.deleteAccount(id)
}

async function handleLogin(account: Account) {
  loginLoading.value = account.id
  try {
    const result = await callSidecar<{ success: boolean; message: string; nickname: string }>('/account/login', {
      body: { account_id: account.id, proxy: account.proxy },
    })
    if (result.success) {
      await accountStore.updateAccount({
        ...account,
        last_login: new Date().toISOString(),
        nickname: result.nickname || account.nickname,
      })
    }
  } catch (e) {
    console.error('Login failed:', e)
  } finally {
    loginLoading.value = null
  }
}

async function handleCheckStatus(account: Account) {
  try {
    const result = await callSidecar<{ valid: boolean }>(`/account/check_status?account_id=${account.id}`)
    await accountStore.updateAccount({
      ...account,
      status: result.valid ? 'active' : 'expired',
    })
  } catch (e) {
    console.error('Status check failed:', e)
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'active': return { label: '正常', cls: 'badge-success' }
    case 'banned': return { label: '封禁', cls: 'badge-danger' }
    case 'expired': return { label: '过期', cls: 'badge-warning' }
    default: return { label: status, cls: '' }
  }
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">账号管理</h1>
      <button class="btn-primary" @click="showAddDialog = true">
        <Plus :size="16" :stroke-width="1.5" />
        添加账号
      </button>
    </header>

    <div class="account-grid">
      <div
        v-for="account in accountStore.accounts"
        :key="account.id"
        class="account-card"
      >
        <div class="card-header">
          <div class="avatar">{{ account.nickname.charAt(0) }}</div>
          <div class="card-info">
            <span class="card-name">{{ account.nickname }}</span>
            <span :class="['badge', statusBadge(account.status).cls]">
              {{ statusBadge(account.status).label }}
            </span>
          </div>
        </div>

        <div class="card-meta">
          <div class="meta-row">
            <span class="meta-label">代理</span>
            <span class="meta-value">{{ account.proxy || '直连' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">日限</span>
            <span class="meta-value">{{ account.daily_post_limit }} 条/天</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">最后登录</span>
            <span class="meta-value">{{ account.last_login || '—' }}</span>
          </div>
        </div>

        <div class="card-actions">
          <button class="btn-icon" title="登录" @click="handleLogin(account)" :disabled="loginLoading === account.id">
            <Wifi :size="15" :stroke-width="1.5" />
          </button>
          <button class="btn-icon" title="检查状态" @click="handleCheckStatus(account)">
            <RefreshCw :size="15" :stroke-width="1.5" />
          </button>
          <button class="btn-icon danger" title="删除" @click="handleDelete(account.id)">
            <Trash2 :size="15" :stroke-width="1.5" />
          </button>
        </div>
      </div>

      <button
        v-if="accountStore.accounts.length === 0"
        class="add-card"
        @click="showAddDialog = true"
      >
        <Plus :size="24" :stroke-width="1.5" />
        <span>添加第一个账号</span>
      </button>
    </div>

    <!-- Add Account Dialog -->
    <Teleport to="body">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog">
          <h3 class="dialog-title">添加账号</h3>
          <div class="form-field">
            <label>账号昵称</label>
            <input v-model="newNickname" placeholder="输入昵称" />
          </div>
          <div class="form-field">
            <label>代理地址 (可选)</label>
            <input v-model="newProxy" placeholder="http://user:pass@ip:port" />
          </div>
          <div class="dialog-actions">
            <button class="btn-secondary" @click="showAddDialog = false">取消</button>
            <button class="btn-primary" @click="handleAdd">添加</button>
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
  transition: background 0.15s;
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
  transition: background 0.15s;
}

.btn-secondary:hover {
  background: var(--color-surface-hover);
}

.account-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.account-card {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 0.5px 1px rgba(0, 0, 0, 0.04);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  width: fit-content;
}

.badge-success {
  background: rgba(52, 199, 89, 0.12);
  color: var(--color-success);
}

.badge-danger {
  background: rgba(255, 59, 48, 0.12);
  color: var(--color-danger);
}

.badge-warning {
  background: rgba(255, 149, 0, 0.12);
  color: var(--color-warning);
}

.card-meta {
  margin-bottom: 12px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
}

.meta-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.meta-value {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.card-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 0.5px solid var(--color-border);
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

.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  border: 1.5px dashed var(--color-border);
  border-radius: 10px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.add-card:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
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

.form-field input {
  width: 100%;
  padding: 7px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
  transition: border-color 0.15s;
}

.form-field input:focus {
  border-color: var(--color-primary);
}

.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
