<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  Users,
  FileText,
  MessageSquare,
  BarChart3,
  Clock,
  Settings2,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const navGroups = [
  {
    label: '概览',
    items: [
      { name: '数据看板', icon: LayoutDashboard, path: '/dashboard' },
    ],
  },
  {
    label: '运营',
    items: [
      { name: '账号管理', icon: Users, path: '/accounts' },
      { name: '内容队列', icon: FileText, path: '/content' },
      { name: '评论管理', icon: MessageSquare, path: '/comments' },
    ],
  },
  {
    label: '分析',
    items: [
      { name: '数据分析', icon: BarChart3, path: '/analytics' },
      { name: '任务调度', icon: Clock, path: '/scheduler' },
    ],
  },
]

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar">
    <div class="drag-region" data-tauri-drag-region />

    <nav class="nav-content">
      <div v-for="group in navGroups" :key="group.label" class="nav-group">
        <div class="group-label">{{ group.label }}</div>
        <button
          v-for="item in group.items"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="navigate(item.path)"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.5" />
          <span>{{ item.name }}</span>
        </button>
      </div>
    </nav>

    <div class="nav-footer">
      <button
        class="nav-item"
        :class="{ active: isActive('/settings') }"
        @click="navigate('/settings')"
      >
        <Settings2 :size="18" :stroke-width="1.5" />
        <span>设置</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  min-width: 220px;
  height: 100%;
  background: var(--color-sidebar);
  border-right: 0.5px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.drag-region {
  height: 30px;
  min-height: 30px;
  -webkit-app-region: drag;
}

.nav-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.nav-group {
  margin-bottom: 16px;
}

.group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0 8px;
  margin-bottom: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  text-align: left;
}

.nav-item:hover {
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: var(--color-surface);
  color: var(--color-primary);
  font-weight: 500;
}

.nav-footer {
  padding: 8px 12px 12px;
  border-top: 0.5px solid var(--color-border);
}
</style>
