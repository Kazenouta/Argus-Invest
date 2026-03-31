<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { rulesApi } from '@/api'
import type { RuleLibrary } from '@/types'

const library = ref<RuleLibrary | null>(null)
const loading = ref(false)

onMounted(loadRules)

async function loadRules() {
  loading.value = true
  const res = await rulesApi.get()
  library.value = res.data
  loading.value = false
}

async function resetRules() {
  await rulesApi.reset()
  await loadRules()
}

const categoryMap: Record<string, string> = {
  position: '仓位管理',
  top_signal: '顶部信号',
  trailing: '移动止盈',
  sudden_news: '突发利空',
}

function groupByCategory(rules: any[]) {
  const grouped: Record<string, any[]> = {}
  for (const rule of rules) {
    if (!grouped[rule.category]) grouped[rule.category] = []
    grouped[rule.category].push(rule)
  }
  return grouped
}
</script>

<template>
  <div class="page">
    <h2>规则库</h2>

    <div class="toolbar">
      <button @click="resetRules">重置为默认规则</button>
      <span class="version" v-if="library">版本 {{ library.version }} · 更新于 {{ library.last_updated }}</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-for="(rules, cat) in (library ? groupByCategory(library.rules) : {})" :key="cat" class="section">
      <h3>{{ categoryMap[cat as string] || cat }}</h3>
      <div class="rule-list">
        <div v-for="rule in rules" :key="rule.rule_id" class="rule-card" :class="rule.risk_level">
          <div class="rule-header">
            <strong>{{ rule.rule_id }}</strong>
            <span class="title">{{ rule.title }}</span>
            <span class="risk" :class="rule.risk_level">{{ rule.risk_level }}</span>
            <span class="enabled">{{ rule.enabled ? '✅' : '❌' }}</span>
          </div>
          <p>{{ rule.description }}</p>
          <div class="params" v-if="Object.keys(rule.params).length > 0">
            <span v-for="(v, k) in rule.params" :key="k" class="param">{{ k }}: {{ v }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="library && library.rules.length === 0" class="empty">规则库为空</div>
  </div>
</template>

<style scoped>
.page { padding: 1.5rem; }
.toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
.version { color: #888; font-size: 0.85rem; }
button { padding: 0.5rem 1rem; cursor: pointer; }
.loading { color: #888; }
.section { margin-bottom: 2rem; }
.section h3 { border-bottom: 2px solid #eee; padding-bottom: 0.5rem; margin-bottom: 1rem; }
.rule-card { border: 1px solid #eee; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
.rule-card.critical { border-left: 4px solid #c62828; }
.rule-card.high { border-left: 4px solid #e65100; }
.rule-card.medium { border-left: 4px solid #f57f17; }
.rule-card.low { border-left: 4px solid #2e7d32; }
.rule-header { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.5rem; }
.title { font-weight: 600; }
.risk { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
.risk.critical { background: #ffebee; color: #c62828; }
.risk.high { background: #fff3e0; color: #e65100; }
.risk.medium { background: #fff8e1; color: #f57f17; }
.risk.low { background: #e8f5e9; color: #2e7d32; }
.enabled { margin-left: auto; }
.params { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem; }
.param { background: #f5f5f5; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
p { margin: 0.25rem 0 0.5rem; font-size: 0.9rem; color: #555; }
.empty { color: #888; text-align: center; padding: 2rem; }
</style>
