<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { weaknessApi } from '@/api'
import type { WeaknessProfile } from '@/types'

const profile = ref<WeaknessProfile | null>(null)
const loading = ref(false)

onMounted(loadProfile)

async function loadProfile() {
  loading.value = true
  const res = await weaknessApi.get()
  profile.value = res.data
  loading.value = false
}

async function toggleConfirm(itemId: number, confirmed: boolean) {
  await weaknessApi.confirmItem(itemId, confirmed)
  await loadProfile()
}
</script>

<template>
  <div class="page">
    <h2>弱点画像</h2>

    <div v-if="profile" class="summary">
      <span>版本：{{ profile.version }}</span>
      <span>弱点总数：{{ profile.total_count }}</span>
      <span>严重弱点：{{ profile.critical_count }}</span>
      <span>更新日期：{{ profile.last_updated }}</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div class="list">
      <div v-for="item in profile?.items" :key="item.id" class="card" :class="item.severity">
        <div class="card-header">
          <strong>{{ item.title }}</strong>
          <span class="severity" :class="item.severity">{{ item.severity }}</span>
          <span class="confirmed">{{ item.confirmed ? '✅已确认' : '⏳未确认' }}</span>
        </div>
        <p>{{ item.description }}</p>
        <div class="stats">
          <span>出现 {{ item.occurrence_count }} 次</span>
          <span>平均亏损 {{ item.avg_loss_ratio.toFixed(1) }}%</span>
          <span>最大亏损 {{ item.max_loss_ratio.toFixed(1) }}%</span>
        </div>
        <button v-if="!item.confirmed" @click="toggleConfirm(item.id!, true)">确认纳入</button>
        <button v-else @click="toggleConfirm(item.id!, false)" class="secondary">取消确认</button>
      </div>
      <div v-if="!profile || profile.items.length === 0" class="empty">
        暂无弱点画像，请上传历史交割单进行分析
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 1.5rem; }
.summary { display: flex; gap: 2rem; margin-bottom: 1.5rem; font-size: 0.9rem; background: #f8f9fa; padding: 0.75rem 1rem; border-radius: 6px; }
.loading { color: #888; }
.card { border: 1px solid #eee; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.card-header { display: flex; gap: 1rem; align-items: center; margin-bottom: 0.5rem; }
.severity { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
.severity.critical { background: #ffebee; color: #c62828; }
.severity.high { background: #fff3e0; color: #e65100; }
.severity.medium { background: #fff8e1; color: #f57f17; }
.severity.low { background: #e8f5e9; color: #2e7d32; }
.confirmed { font-size: 0.8rem; color: #888; margin-left: auto; }
.stats { font-size: 0.85rem; color: #666; display: flex; gap: 1rem; margin: 0.5rem 0; }
button { padding: 0.4rem 0.8rem; cursor: pointer; margin-right: 0.5rem; }
.secondary { background: #eee; }
p { margin: 0.5rem 0; }
.empty { color: #888; text-align: center; padding: 2rem; }
</style>
