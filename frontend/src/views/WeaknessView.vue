<template>
  <div class="weakness-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>弱点画像</span>
          <div class="header-right">
            <el-tag type="info">{{ profile?.version || 'v1' }}</el-tag>
            <el-tag type="warning" size="small">{{ stats.total }} 个弱点</el-tag>
            <el-tag v-if="stats.critical > 0" type="danger" size="small">
              ⚠ {{ stats.critical }} 个严重
            </el-tag>
            <el-tag type="success" size="small">{{ stats.confirmed }} 个已确认</el-tag>
          </div>
        </div>
      </template>

      <el-empty v-if="!profile || profile.items.length === 0" description="暂无弱点画像，请上传历史交割单进行分析">
        <el-button type="primary" size="small">上传交割单</el-button>
      </el-empty>

      <div v-else>
        <!-- 分类概览 -->
        <el-row :gutter="12" class="category-summary">
          <el-col :span="6" v-for="cat in categoryStats" :key="cat.label">
            <div class="cat-card" :class="cat.severity" @click="toggleCategory(cat.label)">
              <div class="cat-label">{{ cat.label }}</div>
              <div class="cat-count">{{ cat.count }}</div>
            </div>
          </el-col>
        </el-row>

        <!-- 按分类聚合展示 -->
        <div v-for="cat in groupedItems" :key="cat.category" class="category-section">
          <!-- 分类头部 -->
          <div
            class="category-header"
            :class="cat.severity"
            @click="toggleCategory(cat.category)"
          >
            <div class="cat-header-left">
              <span class="cat-icon">{{ categoryIcon(cat.category) }}</span>
              <span class="cat-title">{{ cat.category }}</span>
              <el-tag :type="severityType(cat.severity)" size="small">{{ severityLabel(cat.severity) }}</el-tag>
            </div>
            <div class="cat-header-right">
              <span class="cat-summary">{{ cat.summary }}</span>
              <el-icon class="toggle-icon" :class="{ expanded: isCategoryOpen(cat.category) }">
                <ArrowRight />
              </el-icon>
            </div>
          </div>

          <!-- 分类内容（可折叠）-->
          <div v-if="isCategoryOpen(cat.category)" class="category-body">
            <!-- 综合证据 -->
            <div class="aggregated-evidence" v-if="cat.aggregated_data">
              <div class="evidence-row">
                <span class="evidence-icon">📊</span>
                <span class="evidence-text">{{ cat.aggregated_data }}</span>
              </div>
            </div>

            <!-- 涉及标的 -->
            <div class="affected-stocks">
              <span class="section-label">涉及标的</span>
              <div class="stock-tags">
                <el-tag
                  v-for="stock in cat.all_stocks"
                  :key="stock"
                  size="small"
                  type="info"
                  effect="plain"
                  class="stock-tag"
                >
                  {{ stock }}
                </el-tag>
              </div>
            </div>

            <!-- 具体弱点列表 -->
            <div class="weakness-list">
              <div
                v-for="item in cat.items"
                :key="item.id"
                class="weakness-item"
                :class="item.severity"
              >
                <div class="item-header">
                  <div class="item-header-left">
                    <code class="item-id">{{ item.id }}</code>
                    <strong class="item-name">{{ item.name }}</strong>
                  </div>
                  <div class="item-header-right">
                    <el-tag :type="severityType(item.severity)" size="small">
                      {{ severityLabel(item.severity) }}
                    </el-tag>
                    <el-tag :type="item.confirmed ? 'success' : 'warning'" size="small">
                      {{ item.confirmed ? '✅已确认' : '⏳待确认' }}
                    </el-tag>
                  </div>
                </div>

                <p class="item-desc">{{ item.description }}</p>

                <!-- 数据证据（精简版）-->
                <div class="item-evidence">
                  <div class="evidence-chip" v-for="(point, i) in splitDataPoints(item.data_points)" :key="i">
                    {{ point }}
                  </div>
                </div>

                <!-- 关联弱点 -->
                <div class="related-row" v-if="parsedRelated(item).length > 0">
                  <span class="related-label">关联：</span>
                  <el-tag
                    v-for="relId in parsedRelated(item)"
                    :key="relId"
                    size="small"
                    effect="plain"
                  >{{ relId }}</el-tag>
                </div>

                <div class="item-actions">
                  <el-button
                    v-if="!item.confirmed"
                    type="primary"
                    size="small"
                    @click="confirm(item.id, true)"
                  >确认</el-button>
                  <el-button
                    v-else
                    type="default"
                    size="small"
                    @click="confirm(item.id, false)"
                  >取消确认</el-button>
                  <el-button size="small" link @click="copyItem(item)">复制</el-button>
                </div>
              </div>
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
import { ArrowRight } from '@element-plus/icons-vue'
import type { WeaknessProfile, WeaknessItem } from '@/types'
import { weaknessApi } from '@/api'

const profile = ref<WeaknessProfile | null>(null)
const openCategories = ref<Set<string>>(new Set())

// 默认全部展开
function initOpenCategories() {
  if (profile.value) {
    const cats = [...new Set(profile.value.items.map(i => i.category))]
    cats.forEach(c => openCategories.value.add(c))
  }
}

function toggleCategory(cat: string) {
  if (openCategories.value.has(cat)) {
    openCategories.value.delete(cat)
  } else {
    openCategories.value.add(cat)
  }
}

function isCategoryOpen(cat: string) {
  return openCategories.value.has(cat)
}

const stats = computed(() => {
  if (!profile.value) return { total: 0, critical: 0, confirmed: 0 }
  return {
    total: profile.value.items.length,
    critical: profile.value.items.filter(i => i.severity === 'critical').length,
    confirmed: profile.value.items.filter(i => i.confirmed).length,
  }
})

const categoryStats = computed(() => {
  if (!profile.value) return []
  const cats: Record<string, { count: number; sev: string }> = {}
  for (const item of profile.value.items) {
    if (!cats[item.category]) cats[item.category] = { count: 0, sev: item.severity }
    cats[item.category].count++
    if (item.severity === 'critical') cats[item.category].sev = 'critical'
    else if (item.severity === 'major' && cats[item.category].sev !== 'critical') cats[item.category].sev = 'major'
    else if (item.severity === 'moderate' && !['critical', 'major'].includes(cats[item.category].sev)) {
      cats[item.category].sev = 'moderate'
    }
  }
  return Object.entries(cats).map(([label, v]) => ({
    label,
    count: v.count,
    severity: v.sev,
  }))
})

const groupedItems = computed(() => {
  if (!profile.value) return []
  const groups: Record<string, {
    category: string
    severity: string
    items: WeaknessItem[]
    all_stocks: string[]
    aggregated_data: string
    summary: string
  }> = {}

  for (const item of profile.value.items) {
    const cat = item.category
    if (!groups[cat]) {
      groups[cat] = {
        category: cat,
        severity: item.severity,
        items: [],
        all_stocks: [],
        aggregated_data: '',
        summary: '',
      }
    }
    groups[cat].items.push(item)
    // 收集不重复的标的
    const stocks = item.affected_stocks.split(/[、，,]/).map(s => s.trim()).filter(Boolean)
    stocks.forEach(s => {
      if (!groups[cat].all_stocks.includes(s)) groups[cat].all_stocks.push(s)
    })
    // 升级严重度
    if (item.severity === 'critical') groups[cat].severity = 'critical'
    else if (item.severity === 'major' && groups[cat].severity !== 'critical') groups[cat].severity = 'major'
  }

  // 生成综合摘要
  for (const g of Object.values(groups)) {
    const topSeverity = g.items.filter(i => i.severity === 'critical').length > 0 ? '严重' :
                         g.items.filter(i => i.severity === 'major').length > 0 ? '重要' : '中等'
    g.summary = `${g.items.length}个弱点 | ${topSeverity}`
  }

  return Object.values(groups).sort((a, b) => {
    const order = { critical: 0, major: 1, moderate: 2, minor: 3 }
    return (order[a.severity] ?? 9) - (order[b.severity] ?? 9)
  })
})

function categoryIcon(cat: string) {
  const icons: Record<string, string> = {
    '交易行为': '🎯',
    '仓位管理': '⚖️',
    '止损纪律': '🛑',
    '市场风险': '⚠️',
  }
  return icons[cat] || '📌'
}

function severityType(s: string) {
  return { critical: 'danger', major: 'warning', moderate: 'info', minor: 'success' }[s] || 'info'
}

function severityLabel(s: string) {
  return { critical: '严重', major: '重要', moderate: '中等', minor: '轻微' }[s] || s
}

function parsedRelated(item: WeaknessItem): string[] {
  try {
    return JSON.parse(item.related_weakness || '[]')
  } catch {
    return []
  }
}

function splitDataPoints(dataPoints: string): string[] {
  // 按 | 分割数据点，每段作为一个证据块
  return dataPoints.split('|').map(p => p.trim()).filter(Boolean)
}

async function loadProfile() {
  const res = await weaknessApi.get()
  profile.value = res.data
  initOpenCategories()
}

async function confirm(id: string, confirmed: boolean) {
  await weaknessApi.confirmItem(id, confirmed)
  await loadProfile()
  ElMessage.success(confirmed ? '已确认纳入弱点' : '已取消确认')
}

async function copyItem(item: WeaknessItem) {
  const text = `[${item.id}] ${item.name}\n${item.description}\n${item.data_points}`
  await navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}

onMounted(loadProfile)
</script>

<style scoped lang="scss">
.weakness-page { padding: 0; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  width: 100%;

  .header-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }
}

.category-summary {
  margin-bottom: 20px;

  .cat-card {
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 4px solid;
    cursor: pointer;
    transition: all 0.2s;

    &:hover { opacity: 0.85; }

    &.critical { border-color: #f56c6c; background: #fef0f0; }
    &.major { border-color: #e6a23c; background: #fdf6ec; }
    &.moderate { border-color: #909399; background: #f4f4f5; }
    &.minor { border-color: #67c23a; background: #f0f9eb; }

    .cat-label { font-size: 12px; color: #606266; margin-bottom: 4px; }
    .cat-count { font-size: 24px; font-weight: 700; }
  }
}

.category-section {
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

.category-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
  border-left-width: 4px;
  border-left-style: solid;

  &:hover { background: #f5f7fa; }

  &.critical { border-left-color: #f56c6c; }
  &.major { border-left-color: #e6a23c; }
  &.moderate { border-left-color: #909399; }
  &.minor { border-left-color: #67c23a; }

  .cat-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .cat-icon { font-size: 18px; }
  .cat-title { font-size: 15px; font-weight: 700; }

  .cat-header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .cat-summary { font-size: 12px; color: #909399; }

  .toggle-icon {
    transition: transform 0.2s;
    color: #909399;

    &.expanded { transform: rotate(90deg); }
  }
}

.category-body {
  padding: 12px 16px 16px;
  background: #fafafa;
  border-top: 1px solid #ebeef5;
}

.aggregated-evidence {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 12px;

  .evidence-row {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: 13px;
    line-height: 1.6;
  }

  .evidence-icon { font-size: 14px; flex-shrink: 0; }
  .evidence-text { color: #606266; }
}

.affected-stocks {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;

  .section-label {
    font-size: 12px;
    color: #909399;
    flex-shrink: 0;
    margin-top: 3px;
  }

  .stock-tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .stock-tag { font-size: 11px; }
}

.weakness-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.weakness-item {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 14px;
  border-left-width: 3px;
  border-left-style: solid;

  &.critical { border-left-color: #f56c6c; }
  &.major { border-left-color: #e6a23c; }
  &.moderate { border-left-color: #909399; }
  &.minor { border-left-color: #67c23a; }
}

.item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  flex-wrap: wrap;
  gap: 6px;

  .item-header-left { display: flex; align-items: center; gap: 8px; }
  .item-header-right { display: flex; gap: 4px; align-items: center; }
}

.item-id {
  font-size: 11px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  color: #909399;
}

.item-name {
  font-size: 14px;
  font-weight: 600;
}

.item-desc {
  font-size: 12px;
  color: #606266;
  margin: 0 0 8px;
  line-height: 1.5;
}

.item-evidence {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;

  .evidence-chip {
    font-size: 11px;
    background: #f0f2f5;
    color: #606266;
    padding: 3px 8px;
    border-radius: 4px;
    line-height: 1.4;
  }
}

.related-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;

  .related-label { font-size: 11px; color: #909399; }
}

.item-actions {
  display: flex;
  gap: 6px;
}
</style>
