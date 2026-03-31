/**
 * Global app store.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { healthApi } from '@/api'

export const useAppStore = defineStore('app', () => {
  const systemReady = ref(false)
  const dataDirOk = ref(false)

  async function checkHealth() {
    try {
      const res = await healthApi.check()
      systemReady.value = res.data.status === 'ok'
      dataDirOk.value = res.data.dirs_ready ?? false
    } catch {
      systemReady.value = false
      dataDirOk.value = false
    }
  }

  return { systemReady, dataDirOk, checkHealth }
})
