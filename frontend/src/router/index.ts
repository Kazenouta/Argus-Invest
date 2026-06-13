import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/layout/index.vue'),
      children: [
        {
          path: '/',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
        },
        {
          path: '/portfolio',
          component: () => import('@/views/PortfolioRouter.vue'),
          children: [
            {
              path: '',
              name: 'portfolio-main',
              component: () => import('@/views/PortfolioView.vue'),
            },
            {
              path: 'watchlist',
              name: 'portfolio-watchlist',
              component: () => import('@/views/WatchlistView.vue'),
            },
          ],
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
        {
          path: '/kv',
          name: 'kv',
          component: () => import('@/views/KvRouter.vue'),
          children: [
            {
              path: 'guolei',
              name: 'kv-guolei',
              component: () => import('@/views/KvGuoleiView.vue'),
            },
          ],
        },
      ],
    },
  ],
})

export default router
