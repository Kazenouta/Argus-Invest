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
      events.value = res.data ?? []
    } catch {
      events.value = []
    } finally {
      loading.value = false
    }
  }

  async function runCheck() {
    loading.value = true
    try {
      const res = await monitorApi.check()
      const data = res.data
      events.value = data.events ?? []
      indicators.value = data.indicators ?? []
      lastCheckedAt.value = data.checked_at ?? null
    } finally {
      loading.value = false
    }
  }

  return { events, indicators, lastCheckedAt, loading, loadEvents, runCheck }
})
