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

  // ── 初始化：页面加载时，只读缓存显示（不自动刷新）──────────────
  async function initOverview() {
    try {
      const [aiRes, overviewRes] = await Promise.all([
        marketApi.aiOverviewCache(),
        marketApi.overviewCache(),
      ])
      if (aiRes.data) {
        aiOverview.value = aiRes.data
        updatedAt.value = aiRes.data?.更新时间 || null
      }
      if (overviewRes.data) {
        const d = overviewRes.data
        volume.value = d.market_volume || null
        ztDt.value = d.zt_dt || null
        margin.value = d.margin || null
        northFlow.value = d.north_flow || null
        breadth.value = d.breadth || null
        updatedAt.value = d.updated_at || updatedAt.value
      }
    } catch {
      // 缓存读取失败，静默继续
    }
  }

  // ── 刷新：显式刷新时调用，显示 loading ──────────────────────────────
  async function loadOverview() {
    loading.value = true
    try {
      // AI 接口最多等 15 秒，超时则降级到缓存
      const res = await Promise.race([
        marketApi.aiOverview(),
        new Promise<any>((_, reject) => setTimeout(() => reject(new Error('timeout')), 15000)),
      ])
      aiOverview.value = res.data
      updatedAt.value = res.data?.更新时间 || new Date().toISOString()
    } catch {
      // 超时或失败：从缓存读取
      try {
        const cache = await marketApi.aiOverviewCache()
        if (cache.data) {
          aiOverview.value = cache.data
          updatedAt.value = cache.data?.更新时间 || null
        }
      } catch {
        // 缓存也失败，静默
      }
    } finally {
      loading.value = false
    }
  }

  async function loadOverviewLegacy() {
    try {
      const res = await marketApi.overview()
      const d = res.data
      volume.value = d.market_volume
      ztDt.value = d.zt_dt
      margin.value = d.margin
      northFlow.value = d.north_flow
      breadth.value = d.breadth
      updatedAt.value = d.updated_at
    } catch {
      // 静默失败，数据来自缓存
    }
  }

  return {
    aiOverview, volume, ztDt, margin, northFlow, breadth, updatedAt, loading,
    initOverview, loadOverview, loadOverviewLegacy,
  }
})
