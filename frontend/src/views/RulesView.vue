<template>
  <div class="rules-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>规则库</span>
          <div class="header-right">
            <el-tag type="info" size="small">{{ library?.version || 'v1' }}</el-tag>
            <el-button type="default" size="small" @click="reset">重置为默认</el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!library || library.rules.length === 0" description="规则库为空" />

      <div v-for="(group, cat) in groupedRules" :key="cat" class="rule-section">
        <h4 class="section-title">{{ categoryName(cat) }}</h4>
        <div class="rule-list">
          <div v-for="rule in group" :key="rule.rule_id" class="rule-card" :class="rule.risk_level">
            <div class="rule-header">
              <code class="rule-id">{{ rule.rule_id }}</code>
              <strong class="rule-title">{{ rule.title }}</strong>
              <el-tag :type="riskType(rule.risk_level)" size="small">{{ rule.risk_level }}</el-tag>
              <el-tag :type="rule.enabled ? 'success' : 'info'" size="small" style="margin-left:auto">
                {{ rule.enabled ? '✅ 启用' : '❌ 禁用' }}
              </el-tag>
            </div>
            <p class="rule-desc">{{ rule.description }}</p>
            <div v-if="Object.keys(rule.params).length > 0" class="rule-params">
              <span v-for="(v, k) in rule.params" :key="k" class="param-tag">
                {{ k }}: {{ v }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { RuleLibrary } from '@/types'

const library = ref<RuleLibrary | null>(null)

const categoryMap: Record<string, string> = {
  position: '🏛️ 仓位管理规则',
  top_signal: '📈 顶部信号规则',
  trailing: '🔄 移动止盈规则',
  sudden_news: '⚠️ 突发利空规则',
}

const categoryName = (cat: string) => categoryMap[cat] || cat

function riskType(r: string) {
  return { critical: 'danger', high: 'warning', medium: 'info', low: 'success' }[r] || 'info'
}

const groupedRules = computed(() => {
  if (!library.value) return {}
  const g: Record<string, any[]> = {}
  for (const rule of library.value.rules) {
    if (!g[rule.category]) g[rule.category] = []
    g[rule.category].push(rule)
  }
  return g
})

async function loadRules() {
  const res = await import('@/api').then(m => m.rulesApi.get())
  library.value = res.data
}

async function reset() {
  await import('@/api').then(m => m.rulesApi.reset())
  await loadRules()
  ElMessage.success('已重置为默认规则')
}

onMounted(loadRules)
</script>

<style scoped lang="scss">
.rules-page { padding: 0; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  width: 100%;

  .header-right {
    display: flex;
    gap: 10px;
    align-items: center;
  }
}

.rule-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rule-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 16px;
  border-left-width: 4px;

  &.critical { border-left-color: #f56c6c; }
  &.high { border-left-color: #e6a23c; }
  &.medium { border-left-color: #909399; }
  &.low { border-left-color: #67c23a; }

  .rule-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }

  .rule-id {
    font-size: 12px;
    background: #f5f7fa;
    padding: 1px 6px;
    border-radius: 4px;
    color: #909399;
  }

  .rule-title {
    font-size: 14px;
    font-weight: 600;
  }

  .rule-desc {
    font-size: 13px;
    color: #606266;
    margin: 0 0 8px;
    line-height: 1.5;
  }

  .rule-params {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;

    .param-tag {
      font-size: 12px;
      background: #f0f2f5;
      padding: 2px 8px;
      border-radius: 4px;
      color: #409EFF;
    }
  }
}
</style>
