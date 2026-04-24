import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
    },
    {
      path: '/accounts',
      name: 'accounts',
      component: () => import('@/views/Accounts.vue'),
    },
    {
      path: '/content',
      name: 'content',
      component: () => import('@/views/ContentQueue.vue'),
    },
    {
      path: '/content/editor/:id?',
      name: 'content-editor',
      component: () => import('@/views/ContentEditor.vue'),
    },
    {
      path: '/comments',
      name: 'comments',
      component: () => import('@/views/Comments.vue'),
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('@/views/Analytics.vue'),
    },
    {
      path: '/pipeline',
      name: 'pipeline',
      component: () => import('@/views/Pipeline.vue'),
    },
    {
      path: '/scheduler',
      name: 'scheduler',
      component: () => import('@/views/Scheduler.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
    },
  ],
})

export default router
