/**
 * Market overview store.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketApi } from '@/api'

export interface AiMarketOverview {
  成交额: { value: string; 趋势描述: string; 历史分位: string; 信号: string }
  涨跌停: { value: string; 变化描述: string; 信号: string }
  融资余额: { value: string; 变化描述: string; 信号: string }
  散户情绪: { 描述: string; 信号: string }
  资金流入行业: [string, string, string]
  资金流出行业: [string, string, string]
  综合信号: string
  更新时间: string
  error?: string
  _raw_search?: Record<string, unknown>
}

export const useMarketStore = defineStore('market', () => {
  // AI 概览数据
  const aiOverview = ref<AiMarketOverview | null>(null)
  // 传统数据（备用）
  const volume = ref<{ amount: number; change_pct: number; date: string } | null>(null)
  const ztDt = ref<{ zt_count: number; dt_count: number; date: string } | null>(null)
  const margin = ref<{ balance: number; change: number; change_pct: number; date: string } | null>(null)
  const northFlow = ref<{ net_buy: number; direction: string; date: string } | null>(null)
  const breadth = ref<{ rzye: number; change_pct: number; signal: string; date: string } | null>(null)
  const updatedAt = ref<string | null>(null)
  const loading = ref(false)

  async function loadOverview() {
    loading.value = true
    try {
      const res = await marketApi.aiOverview()
      aiOverview.value = res.data
      updatedAt.value = res.data?.更新时间 || new Date().toISOString()
    } finally {
      loading.value = false
    }
  }

  async function loadOverviewLegacy() {
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

  return {
    aiOverview, volume, ztDt, margin, northFlow, breadth, updatedAt, loading,
    loadOverview, loadOverviewLegacy,
  }
})
