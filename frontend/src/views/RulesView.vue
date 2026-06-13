<template>
  <div class="rules-page">
    <div class="page-header">
      <h2 class="page-title">规则库</h2>
      <p class="page-desc">
        当前共 <strong>{{ allRules.length }}</strong> 条规则，按分类组织。
        <el-button size="small" text type="primary" @click="loadRules" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </p>
    </div>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="4" animated />
    </div>

    <template v-else>
      <div v-for="group in groupedRules" :key="group.category" class="rule-section">
        <h3 class="section-title">
          <span class="section-icon">{{ categoryIcon(group.category) }}</span>
          {{ group.label }}
          <span class="section-count">{{ group.rules.length }}</span>
        </h3>

        <div class="rules-grid">
          <div
            v-for="rule in group.rules"
            :key="rule.rule_id"
            class="rule-card"
            :class="[rule.risk_level, { disabled: !rule.enabled }]"
          >
            <div class="rule-header">
              <code class="rule-id">{{ rule.rule_id }}</code>
              <el-switch
                v-model="rule.enabled"
                size="small"
                @change="toggleRule(rule)"
              />
            </div>
            <h4 class="rule-title">{{ rule.title }}</h4>
            <p class="rule-desc">{{ rule.description }}</p>

            <div class="rule-meta">
              <el-tag
                :type="riskTagType(rule.risk_level)"
                size="small"
                effect="plain"
              >
                {{ riskLabel(rule.risk_level) }}
              </el-tag>

              <el-popover
                v-if="rule.params && Object.keys(rule.params).length"
                placement="bottom"
                :width="260"
                trigger="click"
              >
                <template #reference>
                  <el-button size="small" text type="info" class="params-btn">
                    <el-icon><InfoFilled /></el-icon> 参数
                  </el-button>
                </template>
                <pre class="params-json">{{ JSON.stringify(rule.params, null, 2) }}</pre>
              </el-popover>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, InfoFilled } from '@element-plus/icons-vue'
import { rulesApi } from '@/api'
import { ElMessage } from 'element-plus'

interface Rule {
  rule_id: string
  category: string
  title: string
  description: string
  params: Record<string, unknown>
  risk_level: string
  enabled: boolean
}

const CATEGORY_MAP: Record<string, { label: string; icon: string }> = {
  position: { label: '仓位管理', icon: '📊' },
  top_signal: { label: '见顶信号', icon: '🔔' },
  bottom_signal: { label: '见底信号', icon: '🌱' },
  trailing: { label: '移动止盈', icon: '📈' },
  sudden_news: { label: '突发利空', icon: '⚠️' },
  trading_behavior: { label: '交易行为约束', icon: '🚫' },
}

const allRules = ref<Rule[]>([])
const loading = ref(false)

const groupedRules = computed(() => {
  const groups: Record<string, { category: string; label: string; rules: Rule[] }> = {}

  for (const rule of allRules.value) {
    const cat = rule.category || 'other'
    if (!groups[cat]) {
      groups[cat] = {
        category: cat,
        label: CATEGORY_MAP[cat]?.label || cat,
        rules: [],
      }
    }
    groups[cat].rules.push(rule)
  }

  return Object.values(groups)
})

function categoryIcon(cat: string) {
  return CATEGORY_MAP[cat]?.icon || '📋'
}

function riskTagType(level: string) {
  return { critical: 'danger', major: 'warning', high: 'warning', medium: '', low: 'success' }[level] || 'info'
}

function riskLabel(level: string) {
  return { critical: '严重', major: '重要', high: '高风险', medium: '中等', low: '低' }[level] || level
}

async function loadRules() {
  loading.value = true
  try {
    const res = await rulesApi.get()
    allRules.value = res.data.rules || []
  } catch {
    ElMessage.error('加载规则库失败')
  } finally {
    loading.value = false
  }
}

async function toggleRule(rule: Rule) {
  try {
    await rulesApi.update(rule.rule_id, { enabled: rule.enabled })
    ElMessage.success(`${rule.title} 已${rule.enabled ? '启用' : '禁用'}`)
  } catch {
    rule.enabled = !rule.enabled
    ElMessage.error('操作失败')
  }
}

onMounted(loadRules)
</script>

<style scoped lang="scss">
.rules-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px;
}

.page-desc {
  font-size: 13px;
  color: #909399;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;

  strong {
    color: #409eff;
  }
}

.loading-wrap {
  padding: 20px 0;
}

.rule-section {
  margin-bottom: 28px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 6px;

  .section-icon {
    font-size: 16px;
  }

  .section-count {
    font-size: 12px;
    color: #909399;
    font-weight: 400;
    background: #f0f2f5;
    padding: 1px 8px;
    border-radius: 10px;
  }
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 10px;
}

.rule-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 16px;
  border-left-width: 4px;
  transition: box-shadow 0.2s, opacity 0.2s;

  &:hover {
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
  }

  &.disabled {
    opacity: 0.55;
  }

  &.critical { border-left-color: #f56c6c; }
  &.major,
  &.high     { border-left-color: #e6a23c; }
  &.medium    { border-left-color: #409eff; }
  &.low       { border-left-color: #67c23a; }
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.rule-id {
  font-size: 11px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  color: #909399;
  font-family: monospace;
}

.rule-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px;
}

.rule-desc {
  font-size: 12px;
  color: #606266;
  margin: 0 0 10px;
  line-height: 1.55;
}

.rule-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.params-btn {
  font-size: 12px;
  padding: 0 4px;
  height: auto;
}

.params-json {
  font-size: 11px;
  color: #303133;
  background: #f9fafb;
  padding: 8px 10px;
  border-radius: 6px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
}
</style>
