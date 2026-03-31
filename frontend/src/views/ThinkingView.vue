<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import type { ThinkingRecord } from '@/types'

const store = usePortfolioStore()
const showForm = ref(false)
const newRecord = ref<Partial<ThinkingRecord>>({
  thinking_time: new Date().toISOString().slice(0, 16),
  ticker: '', ticker_name: '', content: '', source: 'manual',
})

onMounted(() => store.loadThinking())

async function submit() {
  await store.addThinking(newRecord.value as ThinkingRecord)
  showForm.value = false
  newRecord.value = { thinking_time: new Date().toISOString().slice(0, 16),
    ticker: '', ticker_name: '', content: '', source: 'manual' }
}
</script>

<template>
  <div class="page">
    <h2>盘中思考</h2>

    <div class="toolbar">
      <button @click="showForm = !showForm">{{ showForm ? '取消' : '记录思考' }}</button>
    </div>

    <div v-if="showForm" class="form-card">
      <div class="form-row">
        <input v-model="newRecord.thinking_time" type="datetime-local" />
        <input v-model="newRecord.ticker" placeholder="关联股票（可选）" />
        <input v-model="newRecord.ticker_name" placeholder="股票名称" />
      </div>
      <textarea v-model="newRecord.content" placeholder="思考内容：判断依据、大盘观察、大佬观点..." rows="5" />
      <button @click="submit" style="margin-top:0.5rem">保存</button>
    </div>

    <div class="list">
      <div v-for="r in store.thinking" :key="r.id" class="card">
        <div class="card-header">
          <span class="time">{{ r.thinking_time }}</span>
          <span v-if="r.ticker" class="ticker">{{ r.ticker }} {{ r.ticker_name }}</span>
          <span class="source">{{ r.source }}</span>
        </div>
        <p class="content">{{ r.content }}</p>
        <div v-if="r.action" class="action">关联操作：{{ r.action }}</div>
      </div>
      <div v-if="store.thinking.length === 0" class="empty">暂无思考记录</div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 1.5rem; }
.toolbar { margin-bottom: 1rem; }
button { padding: 0.5rem 1rem; cursor: pointer; }
.form-card { background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
.form-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; flex-wrap: wrap; }
.form-row input, textarea { padding: 0.4rem; border: 1px solid #ccc; border-radius: 4px; }
textarea { width: 100%; box-sizing: border-box; }
.card { border: 1px solid #eee; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.card-header { display: flex; gap: 1rem; align-items: center; margin-bottom: 0.5rem; font-size: 0.85rem; }
.time { color: #888; }
.ticker { background: #e3f2fd; color: #1565c0; padding: 0.1rem 0.4rem; border-radius: 4px; }
.source { color: #aaa; }
.content { margin: 0.5rem 0; white-space: pre-wrap; }
.action { font-size: 0.85rem; color: #555; }
.empty { color: #888; text-align: center; padding: 2rem; }
</style>
