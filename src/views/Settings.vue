<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { Save, Key, Globe, Clock, Cpu } from 'lucide-vue-next'

interface AppSettings {
  sidecar_port: number
  auto_start: boolean
  ai_provider: string
  ai_api_key: string
  default_proxy: string | null
  comment_check_interval: number
  data_collect_interval: number
}

const settings = ref<AppSettings>({
  sidecar_port: 18765,
  auto_start: false,
  ai_provider: 'openai',
  ai_api_key: '',
  default_proxy: null,
  comment_check_interval: 30,
  data_collect_interval: 480,
})

const saving = ref(false)
const saved = ref(false)

onMounted(async () => {
  try {
    settings.value = await invoke<AppSettings>('get_settings')
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
})

async function handleSave() {
  saving.value = true
  try {
    await invoke('save_settings', { settings: settings.value })
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e) {
    console.error('Failed to save settings:', e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1 class="page-title">设置</h1>
      <button class="btn-primary" :disabled="saving" @click="handleSave">
        <Save :size="14" :stroke-width="1.5" />
        {{ saved ? '已保存' : '保存' }}
      </button>
    </header>

    <div class="settings-sections">
      <section class="settings-group">
        <h2 class="group-title">
          <Key :size="16" :stroke-width="1.5" />
          AI 配置
        </h2>
        <div class="group-card">
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">AI 服务</span>
              <span class="label-desc">选择文案生成使用的 AI 服务</span>
            </div>
            <select v-model="settings.ai_provider">
              <option value="openai">OpenAI</option>
              <option value="tongyi">通义千问</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">API Key</span>
              <span class="label-desc">AI 服务的 API 密钥</span>
            </div>
            <input
              v-model="settings.ai_api_key"
              type="password"
              placeholder="sk-..."
            />
          </div>
        </div>
      </section>

      <section class="settings-group">
        <h2 class="group-title">
          <Globe :size="16" :stroke-width="1.5" />
          网络
        </h2>
        <div class="group-card">
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">默认代理</span>
              <span class="label-desc">新建账号使用的默认代理地址</span>
            </div>
            <input
              v-model="settings.default_proxy"
              placeholder="http://ip:port"
            />
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">Sidecar 端口</span>
              <span class="label-desc">Python 后端服务端口</span>
            </div>
            <input
              v-model.number="settings.sidecar_port"
              type="number"
              min="1024"
              max="65535"
            />
          </div>
        </div>
      </section>

      <section class="settings-group">
        <h2 class="group-title">
          <Clock :size="16" :stroke-width="1.5" />
          定时任务
        </h2>
        <div class="group-card">
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">评论巡检间隔</span>
              <span class="label-desc">每隔多少分钟检查一次评论区</span>
            </div>
            <div class="input-with-unit">
              <input v-model.number="settings.comment_check_interval" type="number" min="5" />
              <span class="unit">分钟</span>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">数据采集间隔</span>
              <span class="label-desc">每隔多少分钟采集一次笔记数据</span>
            </div>
            <div class="input-with-unit">
              <input v-model.number="settings.data_collect_interval" type="number" min="60" />
              <span class="unit">分钟</span>
            </div>
          </div>
        </div>
      </section>

      <section class="settings-group">
        <h2 class="group-title">
          <Cpu :size="16" :stroke-width="1.5" />
          系统
        </h2>
        <div class="group-card">
          <div class="setting-row">
            <div class="setting-label">
              <span class="label-text">开机自启</span>
              <span class="label-desc">系统启动时自动运行助手</span>
            </div>
            <label class="toggle">
              <input v-model="settings.auto_start" type="checkbox" />
              <span class="toggle-slider" />
            </label>
          </div>
        </div>
      </section>
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
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.settings-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-group {
}

.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.group-card {
  background: var(--color-surface);
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 0.5px solid var(--color-border);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.label-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.label-desc {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.setting-row input,
.setting-row select {
  width: 200px;
  padding: 5px 8px;
  border: 0.5px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}

.setting-row input:focus,
.setting-row select:focus {
  border-color: var(--color-primary);
}

.input-with-unit {
  display: flex;
  align-items: center;
  gap: 6px;
}

.input-with-unit input {
  width: 80px;
}

.unit {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.toggle {
  position: relative;
  width: 40px;
  height: 22px;
  cursor: pointer;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 11px;
  transition: background 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 0.5px 2px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s;
}

.toggle input:checked + .toggle-slider {
  background: var(--color-success);
}

.toggle input:checked + .toggle-slider::before {
  transform: translateX(18px);
}
</style>
