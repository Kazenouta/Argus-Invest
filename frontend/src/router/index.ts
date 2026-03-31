import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: () => import('@/views/PortfolioView.vue'),
    },
    {
      path: '/trades',
      name: 'trades',
      component: () => import('@/views/TradesView.vue'),
    },
    {
      path: '/thinking',
      name: 'thinking',
      component: () => import('@/views/ThinkingView.vue'),
    },
    {
      path: '/weakness',
      name: 'weakness',
      component: () => import('@/views/WeaknessView.vue'),
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('@/views/RulesView.vue'),
    },
  ],
})

export default router
