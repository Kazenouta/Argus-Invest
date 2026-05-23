<template>
  <div class="kv-page">

    <!-- Header -->
    <div class="kv-header">
      <div class="kv-header__left">
        <span class="kv-icon">📖</span>
        <span class="kv-title">郭磊宏观</span>
        <el-tag size="small" type="info">大V观点</el-tag>
        <span class="kv-count" v-if="articles.length">
          共 {{ articles.length }} 篇 · {{ successfulCount }} 篇 AI 分析成功
        </span>
      </div>
      <div class="kv-header__right">
        <span class="kv-last-updated" v-if="lastRefreshed">
          更新于 {{ lastRefreshed }}
        </span>
        <el-button
          type="primary"
          size="small"
          :loading="refreshing"
          :disabled="refreshing"
          @click="refresh"
        >
          <el-icon><Refresh /></el-icon>
          {{ refreshing ? 'AI 提炼中...' : '刷新 + AI 提炼' }}
        </el-button>
      </div>
    </div>

    <!-- AI Processing Tip -->
    <el-alert
      v-if="refreshing"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        正在分析 PDF 并通过 AI 提炼关键信息，请耐心等待（每篇约 3-5 秒）…
      </template>
    </el-alert>

    <!-- Loading -->
    <div v-if="loading && !articles.length" class="kv-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载文章列表…</span>
    </div>

    <!-- Timeline Chart (only if we have data) -->
    <div v-if="!loading && chartSeries.length > 0" class="kv-chart-section">
      <div class="kv-section-title">
        📈 关键指标时间线
        <span class="kv-section-hint">（仅展示出现 ≥2 次的指标）</span>
      </div>
      <div ref="chartRef" class="kv-chart" />
    </div>

    <!-- Indicator Summary Table -->
    <div v-if="!loading && allIndicators.length > 0" class="kv-indicators-section">
      <div class="kv-section-title">📊 关键指标汇总</div>
      <el-table
        :data="allIndicators"
        size="small"
        stripe
        border
        class="kv-indicators-table"
        :default-sort="{ prop: 'date', order: 'descending' }"
      >
        <el-table-column prop="date" label="日期" width="100" sortable />
        <el-table-column prop="indicator" label="指标" width="200" />
        <el-table-column prop="value" label="数值" width="180">
          <template #default="{ row }">
            <span class="kv-indicators-value">{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="说明">
          <template #default="{ row }">
            <span class="kv-indicators-note">{{ row.note }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Empty -->
    <el-empty
      v-else-if="!articles.length && !refreshing"
      description="暂无文章，请点击「刷新 + AI 提炼」获取最新内容"
      :image-size="80"
    />

    <!-- Article List -->
    <div v-else class="kv-list">
      <div
        v-for="(article, idx) in articles"
        :key="idx"
        class="kv-card"
        :class="sentimentClass(article.ai_情绪倾向)"
      >
        <!-- Card Header -->
        <div class="kv-card__header" @click="toggleExpand(idx)">
          <div class="kv-card__meta">
            <span class="kv-card__date">{{ article.published_date || '日期未知' }}</span>
            <el-tag
              size="small"
              :type="sentimentTagType(article.ai_情绪倾向)"
            >
              {{ article.ai_情绪倾向 || '中性' }}
            </el-tag>
          </div>
          <div class="kv-card__title">
            <span v-if="isAiFailed(article)">
              <el-tag type="danger" size="small" style="margin-right:6px">⚠ AI 分析失败</el-tag>
            </span>
            {{ cleanTitle(article.title) }}
          </div>
          <div class="kv-card__expand">
            <el-icon>
              <component :is="expandedIdx === idx ? 'ArrowUp' : 'ArrowDown'" />
            </el-icon>
          </div>
        </div>

        <!-- AI Analysis Summary (always visible) -->
        <div v-if="!isAiFailed(article)" class="kv-card__summary">
          <div class="kv-summary__core">
            <span class="kv-summary__label">核心观点</span>
            <span class="kv-summary__value">{{ article.ai_核心观点 }}</span>
          </div>
          <div class="kv-summary__chips">
            <el-tag
              v-for="m in parseJsonField(article.ai_相关市场)"
              :key="m"
              size="small"
              type="info"
              style="margin-right: 4px"
            >
              🏦 {{ m }}
            </el-tag>
            <el-tag
              v-for="p in parseJsonField(article.ai_政策相关)"
              :key="p"
              size="small"
              type="warning"
              style="margin-right: 4px"
            >
              📋 {{ p }}
            </el-tag>
          </div>
        </div>

        <!-- AI Failed Notice -->
        <div v-else class="kv-card__summary kv-card__summary--failed">
          <span class="kv-failed-msg">
            AI 分析失败，请尝试重新刷新。
            <span v-if="article.body_text">正文已提取，可重新分析。</span>
          </span>
        </div>

        <!-- Expanded Detail -->
        <div v-if="expandedIdx === idx" class="kv-card__detail">

          <!-- AI Key Indicators -->
          <div v-if="!isAiFailed(article) && parsedIndicators(article).length > 0" class="kv-detail__section">
            <div class="kv-detail__label">📊 关键指标</div>
            <div class="kv-indicators-grid">
              <div
                v-for="ind in parsedIndicators(article)"
                :key="ind.name"
                class="kv-indicator-chip"
              >
                <span class="kv-indicator-chip__name">{{ ind.name }}</span>
                <span class="kv-indicator-chip__value">{{ ind.value }}</span>
                <span class="kv-indicator-chip__note">{{ ind.说明 }}</span>
              </div>
            </div>
          </div>

          <!-- Key Logic -->
          <div v-if="!isAiFailed(article) && article.ai_主要逻辑" class="kv-detail__section">
            <div class="kv-detail__label">🧠 主要逻辑</div>
            <div class="kv-detail__text">{{ article.ai_主要逻辑 }}</div>
          </div>

          <!-- Investment Insights -->
          <div v-if="!isAiFailed(article) && article.ai_投资启示" class="kv-detail__section">
            <div class="kv-detail__label">💡 投资启示</div>
            <div class="kv-detail__text kv-detail__text--insight">{{ article.ai_投资启示 }}</div>
          </div>

          <!-- Risk -->
          <div v-if="!isAiFailed(article) && article.ai_风险提示" class="kv-detail__section">
            <div class="kv-detail__label">⚠️ 风险提示</div>
            <div class="kv-detail__text kv-detail__text--risk">{{ article.ai_风险提示 }}</div>
          </div>

          <!-- Original Text -->
          <div v-if="article.body_text" class="kv-detail__section">
            <div class="kv-detail__label">📝 原文摘要</div>
            <div class="kv-detail__text kv-detail__text--body">
              <pre class="kv-body-pre">{{ extractAbstract(article.body_text) }}</pre>
            </div>
          </div>

          <!-- Footer -->
          <div class="kv-detail__footer">
            <span class="kv-detail__fetched">
              原文抓取于 {{ article.fetched_date }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { kvApi } from '@/api'
import * as echarts from 'echarts'

const ACCOUNT = 'guolei'

// ── State ─────────────────────────────────────────────────────────────────
const articles = ref<any[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastRefreshed = ref('')
const expandedIdx = ref<number | null>(null)
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

// ── Computed ───────────────────────────────────────────────────────────────
const successfulCount = computed(() =>
  articles.value.filter(a => !isAiFailed(a)).length
)

// Parse JSON fields (may be stored as JSON strings or arrays)
function parseJsonField(field: any): string[] {
  if (!field) return []
  if (Array.isArray(field)) return field
  if (typeof field === 'string') {
    try { return JSON.parse(field) } catch { return [] }
  }
  return []
}

// Parse ai_关键指标
function parsedIndicators(article: any): any[] {
  return parseJsonField(article.ai_关键指标)
}

// Check if AI analysis failed
function isAiFailed(article: any): boolean {
  const v = article.ai_核心观点 || ''
  return v.startsWith('（AI分析失败') || v.startsWith('(AI分析失败')
}

// Clean title (remove 【】 prefix and .pdf suffix)
function cleanTitle(title: string): string {
  return title
    .replace(/^【[^】]+】/, '')
    .replace(/\.pdf$/i, '')
    .trim()
}

// Extract abstract from body_text (first "摘要" section until "正文")
function extractAbstract(bodyText: string): string {
  if (!bodyText) return ''
  const abstractMatch = bodyText.match(/摘要\n([\s\S]*?)(?=正文|$)/)
  if (abstractMatch) {
    return abstractMatch[1].trim().substring(0, 600) + (abstractMatch[1].length > 600 ? '…' : '')
  }
  return bodyText.substring(0, 400) + (bodyText.length > 400 ? '…' : '')
}

// All indicators across all articles (flat table)
const allIndicators = computed(() => {
  const rows: any[] = []
  for (const article of articles.value) {
    if (isAiFailed(article)) continue
    const date = article.published_date || ''
    for (const ind of parsedIndicators(article)) {
      rows.push({ date, indicator: ind.name, value: ind.value, note: ind.说明 || '' })
    }
  }
  return rows
})

// Chart series: indicators that appear in ≥2 articles
const chartSeries = computed(() => {
  const indicatorMap: Record<string, { dates: string[], values: (number | string)[] }> = {}

  for (const article of articles.value) {
    if (isAiFailed(article)) continue
    const date = article.published_date
    if (!date) continue
    for (const ind of parsedIndicators(article)) {
      const name = ind.name
      if (!indicatorMap[name]) indicatorMap[name] = { dates: [], values: [] }
      // Try to extract numeric value (handle formats like "5.0%", "50.4（环比+1.4）", "14.7%" etc.)
      const numericMatch = String(ind.value).match(/[-+]?\d+\.?\d*/)
      const numericVal = numericMatch ? parseFloat(numericMatch[0]) : null
      indicatorMap[name].dates.push(date)
      indicatorMap[name].values.push(numericVal)
    }
  }

  // Filter: only include indicators appearing in ≥2 distinct dates
  const colorPalette = [
    '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8d0',
  ]
  const result: any[] = []
  let colorIdx = 0
  for (const [name, data] of Object.entries(indicatorMap)) {
    const uniqueDates = [...new Set(data.dates)]
    if (uniqueDates.length >= 2) {
      result.push({
        name,
        dates: uniqueDates.sort(),
        values: uniqueDates.map(d => {
          const idx = data.dates.indexOf(d)
          return data.values[idx]
        }),
        color: colorPalette[colorIdx % colorPalette.length],
      })
      colorIdx++
    }
  }
  return result
})

// ── ECharts Init ──────────────────────────────────────────────────────────
function initChart() {
  if (!chartRef.value || chartSeries.value.length === 0) return
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  chartInstance = echarts.init(chartRef.value)

  const allDates = [...new Set(chartSeries.value.flatMap(s => s.dates))].sort()
  const series = chartSeries.value.map(s => ({
    name: s.name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 8,
    data: allDates.map(d => {
      const idx = s.dates.indexOf(d)
      return idx >= 0 ? s.values[idx] : null
    }),
    lineStyle: { width: 2.5 },
    itemStyle: { color: s.color },
    connectNulls: false,
  }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = `<strong>${params[0].axisValue}</strong><br/>`
        for (const p of params) {
          if (p.value !== null && p.value !== undefined) {
            html += `${p.marker} ${p.seriesName}: <strong>${p.value}</strong><br/>`
          }
        }
        return html
      },
    },
    legend: {
      bottom: 0,
      type: 'scroll',
      textStyle: { fontSize: 11 },
    },
    grid: { left: 80, right: 30, top: 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: allDates,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 11 },
    },
    series,
  }

  chartInstance.setOption(option)
}

function resizeChart() {
  chartInstance?.resize()
}

// ── Load articles ──────────────────────────────────────────────────────────
async function loadArticles() {
  loading.value = true
  try {
    const res = await kvApi.articles(ACCOUNT)
    articles.value = (res.data?.articles || res.articles || []) as any[]
    if (articles.value.length) {
      lastRefreshed.value = new Date().toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    }
  } catch (e: any) {
    ElMessage.error('加载文章失败: ' + (e.message || e.detail || '未知错误'))
  } finally {
    loading.value = false
    await nextTick()
    initChart()
  }
}

// ── Refresh & AI Summarize ────────────────────────────────────────────────
async function refresh() {
  refreshing.value = true
  expandedIdx.value = null
  try {
    const res = await kvApi.refresh(ACCOUNT)
    const data = res.data as any ?? res as any
    if (data.success) {
      ElMessage.success(
        `刷新成功！本次新增 ${data.new_articles ?? 0} 篇新文章，已完成 AI 提炼`
      )
      await loadArticles()
    } else {
      ElMessage.warning(data.message || '刷新完成，无新文章')
    }
  } catch (e: any) {
    ElMessage.error('刷新失败: ' + (e.detail || e.message || '未知错误'))
  } finally {
    refreshing.value = false
  }
}

// ── Expand / Collapse ─────────────────────────────────────────────────────
function toggleExpand(idx: number) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

// ── Sentiment helpers ─────────────────────────────────────────────────────
function sentimentClass(signal: string) {
  if (!signal) return ''
  if (signal.includes('看多') || signal.includes('乐观') || signal.includes('积极')) return 'kv-card--bullish'
  if (signal.includes('看空') || signal.includes('偏空') || signal.includes('谨慎')) return 'kv-card--bearish'
  return 'kv-card--neutral'
}

function sentimentTagType(signal: string) {
  if (!signal) return 'info'
  if (signal.includes('看多') || signal.includes('乐观') || signal.includes('积极')) return 'danger'
  if (signal.includes('看空') || signal.includes('偏空') || signal.includes('谨慎')) return 'success'
  return 'info'
}

// ── Init ──────────────────────────────────────────────────────────────────
onMounted(() => {
  loadArticles()
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance?.dispose()
})
</script>

<style scoped lang="scss">
.kv-page {
  padding: 0;
}

// ── Header ────────────────────────────────────────────────────────────────
.kv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  &__left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.kv-icon { font-size: 22px; }

.kv-title {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.kv-count {
  font-size: 12px;
  color: #909399;
}

.kv-last-updated {
  font-size: 12px;
  color: #C0C4CC;
}

// ── Section Title ──────────────────────────────────────────────────────────
.kv-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.kv-section-hint {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

// ── Loading ───────────────────────────────────────────────────────────────
.kv-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 40px;
  color: #909399;
  font-size: 14px;
  justify-content: center;
}

// ── Timeline Chart ─────────────────────────────────────────────────────────
.kv-chart-section {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #F0F2F5;
  padding: 16px;
}

.kv-chart {
  width: 100%;
  height: 220px;
}

// ── Indicators Table ──────────────────────────────────────────────────────
.kv-indicators-section {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #F0F2F5;
  padding: 16px;
}

.kv-indicators-table {
  font-size: 13px;
}

.kv-indicators-value {
  font-weight: 600;
  color: #409EFF;
  font-size: 12px;
}

.kv-indicators-note {
  color: #606266;
  font-size: 12px;
}

// ── Article List ───────────────────────────────────────────────────────────
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kv-card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #F0F2F5;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  overflow: hidden;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }

  // Sentiment left border
  &--bullish { border-left: 3px solid #e53935; }
  &--bearish { border-left: 3px solid #43a047; }
  &--neutral { border-left: 3px solid #E6A23C; }

  &__header {
    padding: 14px 16px 10px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 6px;
    position: relative;
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__date {
    font-size: 12px;
    color: #909399;
  }

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
    line-height: 1.4;
    padding-right: 30px;
  }

  &__expand {
    position: absolute;
    right: 16px;
    top: 14px;
    color: #C0C4CC;
    font-size: 14px;
  }

  // Summary (always visible)
  &__summary {
    padding: 0 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;

    &--failed {
      padding: 10px 16px;
    }
  }
}

// ── Summary ────────────────────────────────────────────────────────────────
.kv-summary__core {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.kv-summary__label {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
  font-weight: 500;
}

.kv-summary__value {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  font-weight: 500;
}

.kv-summary__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

// AI Failed
.kv-failed-msg {
  font-size: 13px;
  color: #E6A23C;
}

// ── Key Indicators Grid ────────────────────────────────────────────────────
.kv-indicators-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-indicator-chip {
  display: grid;
  grid-template-columns: 180px 160px 1fr;
  gap: 8px;
  align-items: start;
  font-size: 12px;
  padding: 6px 8px;
  background: #f5f7fa;
  border-radius: 6px;

  &__name {
    font-weight: 600;
    color: #303133;
  }

  &__value {
    color: #409EFF;
    font-weight: 600;
  }

  &__note {
    color: #606266;
  }
}

// ── Expanded Detail ───────────────────────────────────────────────────────
.kv-card__detail {
  border-top: 1px solid #f0f0f0;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #fafafa;
}

.kv-detail__section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kv-detail__label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.kv-detail__text {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;

  &--body {
    font-size: 12px;
    color: #606266;
  }

  &--risk {
    color: #E6A23C;
  }

  &--insight {
    color: #303133;
    background: #fff8ec;
    padding: 8px 10px;
    border-radius: 6px;
    border-left: 3px solid #E6A23C;
  }
}

.kv-body-pre {
  font-family: inherit;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.6;
}

.kv-detail__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}

.kv-detail__fetched {
  font-size: 12px;
  color: #C0C4CC;
}
</style>
