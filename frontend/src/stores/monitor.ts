/**
 * Monitor store.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { monitorApi } from '@/api'

export interface MonitorEvent {
  ticker: string
  name: string
  indicator: string
  signal: string
  value: number
  threshold_desc: string
  message: string
  triggered_at: string
}

export interface IndicatorValue {
  ticker: string
  name: string
  date: string
  close: number
  change_pct: number
  volume_ratio: number
  rsi14: number | null
  rsi6: number | null
  boll_upper: number | null
  boll_lower: number | null
  ma5: number | null
  ma20: number | null
  ma60: number | null
}

export const useMonitorStore = defineStore('monitor', () => {
  const events = ref<MonitorEvent[]>([])
  const indicators = ref<IndicatorValue[]>([])
  const lastCheckedAt = ref<string | null>(null)
  const loading = ref(false)

  async function loadEvents() {
    loading.value = true
    try {
      const res = await monitorApi.events()
      console.debug('[monitor] loadEvents response:', res.data)
      events.value = res.data ?? []
    } catch {
      events.value = []
    } finally {
      loading.value = false
    }
  }

  /** 从本地存储加载上次检查结果（不重新计算，用于页面刷新后展示） */
  async function loadLastResult() {
    loading.value = true
    try {
      const res = await monitorApi.lastResult()
      console.debug('[monitor] loadLastResult response:', res.data)
      const data = res.data
      if (data?.status === 'ok') {
        events.value = data.events ?? []
        indicators.value = data.indicators ?? []
        lastCheckedAt.value = data.checked_at ?? null
        return data
      }
    } catch (err) {
      console.error('[monitor] loadLastResult error:', err)
    } finally {
      loading.value = false
    }
    return null
  }

  async function runCheck() {
    loading.value = true
    // Clear previous results immediately so UI shows fresh state
    events.value = []
    indicators.value = []
    try {
      const res = await monitorApi.check()
      const data = res.data
      console.debug('[monitor] check result:', data)
      events.value = data?.events ?? []
      indicators.value = data?.indicators ?? []
      lastCheckedAt.value = data?.checked_at ?? null
    } catch (err) {
      console.error('[monitor] check failed:', err)
      events.value = []
      indicators.value = []
    } finally {
      loading.value = false
    }
  }

  return { events, indicators, lastCheckedAt, loading, loadEvents, loadLastResult, runCheck }
})
