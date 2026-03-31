/**
 * Portfolio store.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { portfolioApi, tradesApi, thinkingApi, weaknessApi, rulesApi } from '@/api'
import type { PortfolioRecord, PortfolioSnapshot, TradeRecord, ThinkingRecord } from '@/types'

export const usePortfolioStore = defineStore('portfolio', () => {
  const positions = ref<PortfolioRecord[]>([])
  const snapshot = ref<PortfolioSnapshot | null>(null)
  const trades = ref<TradeRecord[]>([])
  const thinking = ref<ThinkingRecord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadPortfolio(asOfDate?: string) {
    loading.value = true
    error.value = null
    try {
      const [pfRes, snapRes] = await Promise.all([
        portfolioApi.list(asOfDate),
        portfolioApi.snapshot(asOfDate),
      ])
      positions.value = pfRes.data
      snapshot.value = snapRes.data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function uploadPortfolio(records: PortfolioRecord[]) {
    await portfolioApi.upload(records)
    await loadPortfolio()
  }

  async function loadTrades(params?: { start_date?: string; end_date?: string; ticker?: string }) {
    const res = await tradesApi.list(params)
    trades.value = res.data
  }

  async function addTrade(trade: TradeRecord) {
    await tradesApi.add(trade)
    await loadTrades()
  }

  async function loadThinking(params?: { start_date?: string; end_date?: string; ticker?: string }) {
    const res = await thinkingApi.list(params)
    thinking.value = res.data
  }

  async function addThinking(record: ThinkingRecord) {
    await thinkingApi.add(record)
    await loadThinking()
  }

  return {
    positions, snapshot, trades, thinking,
    loading, error,
    loadPortfolio, uploadPortfolio,
    loadTrades, addTrade,
    loadThinking, addThinking,
  }
})
