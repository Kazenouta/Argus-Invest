/**
 * Market overview store.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketApi } from '@/api'

export const useMarketStore = defineStore('market', () => {
  // 大盘成交额（亿元）
  const volume = ref<{ amount: number; change_pct: number; date: string } | null>(null)
  // 涨跌停
  const ztDt = ref<{ zt_count: number; dt_count: number; date: string } | null>(null)
  // 融资余额（亿元）
  const margin = ref<{ balance: number; change: number; change_pct: number; date: string } | null>(null)
  // 北向资金/融资情绪
  const northFlow = ref<{ net_buy: number; direction: string; date: string } | null>(null)
  // 散户情绪（融资余额变化方向）
  const breadth = ref<{ rzye: number; change_pct: number; signal: string; date: string } | null>(null)
  const updatedAt = ref<string | null>(null)
  const loading = ref(false)

  async function loadOverview() {
    loading.value = true
    try {
      const res = await marketApi.overview()
      const d = res.data
      volume.value = d.market_volume
      ztDt.value = d.zt_dt
      margin.value = d.margin
      northFlow.value = d.north_flow
      breadth.value = d.breadth
      updatedAt.value = d.updated_at
    } finally {
      loading.value = false
    }
  }

  return { volume, ztDt, margin, northFlow, breadth, updatedAt, loading, loadOverview }
})
