<template>
  <div class="home">
    <!-- 持仓关键指标 -->
    <el-row :gutter="16" class="home__cards">
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#409EFF"></span>
            <span>总市值</span>
          </div>
          <div class="metric-card__value">
            {{ snapshot ? Number(snapshot.total_market_value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—' }}
          </div>
          <div class="metric-card__sub">持仓快照</div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{ background: floatProfit >= 0 ? '#e53935' : '#43a047' }"></span>
            <span>浮盈/亏</span>
          </div>
          <div class="metric-card__value" :class="floatProfit >= 0 ? 'profit' : 'loss'">
            {{ floatProfit >= 0 ? '+' : '' }}{{ Number(floatProfit).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
          </div>
          <div class="metric-card__sub" :class="floatProfitRatio >= 0 ? 'profit' : 'loss'">
            {{ floatProfitRatio >= 0 ? '+' : '' }}{{ floatProfitRatio.toFixed(2) }}%
          </div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#67C23A"></span>
            <span>持仓占比</span>
          </div>
          <div class="metric-card__value">
            {{ snapshot ? (100 - snapshot.cash_ratio).toFixed(1) : '0.0' }}%
          </div>
          <div class="metric-card__sub">现金 {{ snapshot ? snapshot.cash_ratio.toFixed(1) : '0.0' }}%</div>
        </div>
      </el-col>

      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#E6A23C"></span>
            <span>持仓数量</span>
          </div>
          <div class="metric-card__value">
            {{ snapshot ? snapshot.position_count : 0 }}
            <span class="metric-card__unit">只</span>
          </div>
          <div class="metric-card__sub">建议 5-8 只</div>
        </div>
      </el-col>
    </el-row>

    <!-- 市场概览 -->
    <div class="section-title">
      <div class="section-title__left">
        <span>📊 市场概览</span>
        <el-tag v-if="marketStore.aiOverview" size="small" type="success" style="margin-left:8px">AI 搜索</el-tag>
      </div>
      <div class="section-title__right">
        <span class="section-title__date" v-if="marketStore.updatedAt">
          更新于 {{ marketStore.updatedAt.slice(0, 16) }}
        </span>
        <el-button size="small" :loading="marketStore.loading" @click="marketStore.loadOverview()">
          刷新
        </el-button>
      </div>
    </div>

    <!-- AI 数据加载失败时显示友好提示 -->
    <div v-if="marketStore.loading && !marketStore.aiOverview" class="ai-loading-tip">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在搜索最新市场数据…</span>
    </div>

    <div v-if="marketStore.aiOverview?.error && !marketStore.aiOverview?.成交额" class="ai-error-tip">
      <el-icon><Warning /></el-icon>
      <span>{{ marketStore.aiOverview.error }}，数据暂不可用</span>
    </div>

    <!-- 第一行：成交额 + 涨跌停 + 融资余额 + 散户情绪 -->
    <el-row :gutter="16" class="home__market" v-if="marketStore.aiOverview">

      <!-- 成交额 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#7C3AED"></span>
            <span>A股成交额</span>
          </div>
          <div class="metric-card__value">
            {{ marketStore.aiOverview.成交额?.value || '—' }}
          </div>
          <div class="metric-card__sub" :class="signalClass(marketStore.aiOverview.成交额?.信号)">
            <span v-if="marketStore.aiOverview.成交额?.趋势描述">{{ marketStore.aiOverview.成交额.趋势描述 }}</span>
            <span v-if="marketStore.aiOverview.成交额?.历史分位">｜历史分位：{{ marketStore.aiOverview.成交额.历史分位 }}</span>
          </div>
        </div>
      </el-col>

      <!-- 涨跌停 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#E6A23C"></span>
            <span>涨跌停家数</span>
          </div>
          <div class="metric-card__value">
            <span class="zt-count">
              {{ ztCount }}
              <span class="zt-label">涨停</span>
            </span>
            <span class="dt-count">
              {{ dtCount }}
              <span class="dt-label">跌停</span>
            </span>
          </div>
          <div class="metric-card__sub">
            <span v-if="marketStore.aiOverview.涨跌停?.变化描述">{{ marketStore.aiOverview.涨跌停.变化描述 }}</span>
          </div>
        </div>
      </el-col>

      <!-- 融资余额 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{ background: '#409EFF' }"></span>
            <span>融资余额</span>
          </div>
          <div class="metric-card__value" style="font-size:22px">
            {{ marketStore.aiOverview.融资余额?.value || '—' }}
          </div>
          <div class="metric-card__sub" v-if="marketStore.aiOverview.融资余额?.变化描述">
            {{ marketStore.aiOverview.融资余额.变化描述 }}
          </div>
        </div>
      </el-col>

      <!-- 散户情绪 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{
              background: signalColor(marketStore.aiOverview.散户情绪?.信号)
            }"></span>
            <span>散户情绪</span>
          </div>
          <div class="metric-card__value" :style="{ fontSize: '18px', color: signalColor(marketStore.aiOverview.散户情绪?.信号) }">
            {{ marketStore.aiOverview.散户情绪?.信号 || '—' }}
          </div>
          <div class="metric-card__sub" v-if="marketStore.aiOverview.散户情绪?.描述">
            {{ marketStore.aiOverview.散户情绪.描述 }}
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 第二行：资金流入 Top3 + 资金流出 Top3 + 综合信号 -->
    <el-row :gutter="16" class="home__market home__market--row2" v-if="marketStore.aiOverview">

      <!-- 资金流入行业 Top3 -->
      <el-col :span="8">
        <div class="metric-card metric-card--industry">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#e53935"></span>
            <span>近期资金流入行业 Top3</span>
          </div>
          <div class="industry-list">
            <div v-for="(item, i) in marketStore.aiOverview.资金流入行业" :key="i" class="industry-item industry-item--in">
              <span class="industry-rank">{{ i + 1 }}</span>
              <span class="industry-name">{{ item }}</span>
              <span class="industry-arrow">↑</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 资金流出行业 Top3 -->
      <el-col :span="8">
        <div class="metric-card metric-card--industry">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#43a047"></span>
            <span>近期资金流出行业 Top3</span>
          </div>
          <div class="industry-list">
            <div v-for="(item, i) in marketStore.aiOverview.资金流出行业" :key="i" class="industry-item industry-item--out">
              <span class="industry-rank">{{ i + 1 }}</span>
              <span class="industry-name">{{ item }}</span>
              <span class="industry-arrow">↓</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 综合信号 -->
      <el-col :span="8">
        <div class="metric-card metric-card--signal">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{ background: signalColor(marketStore.aiOverview.综合信号) }"></span>
            <span>综合信号</span>
          </div>
          <div class="signal-value" :style="{ color: signalColor(marketStore.aiOverview.综合信号) }">
            {{ marketStore.aiOverview.综合信号 || '—' }}
          </div>
          <div class="signal-desc">基于量价/杠杆/资金流综合判断</div>
        </div>
      </el-col>
    </el-row>

    <!-- 斯大最新观点 -->
    <SidaView />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMarketStore } from '@/stores/market'
import { storeToRefs } from 'pinia'
import { Loading, Warning } from '@element-plus/icons-vue'
import SidaView from './SidaView.vue'

const appStore = useAppStore()
const portfolioStore = usePortfolioStore()
const marketStore = useMarketStore()
const { snapshot } = storeToRefs(portfolioStore)

const floatProfit = computed(() => snapshot.value?.total_float_profit ?? 0)
const floatProfitRatio = computed(() => snapshot.value?.float_profit_ratio ?? 0)

// 辅助：涨跌停数字解析
const ztCount = computed(() => {
  const v = marketStore.aiOverview?.涨跌停?.value || ''
  const match = v.match(/(\d+)/)
  return match ? match[1] : '—'
})
const dtCount = computed(() => {
  const v = marketStore.aiOverview?.涨跌停?.value || ''
  const parts = v.split('/')
  const match = parts[1] ? parts[1].match(/(\d+)/) : null
  return match ? match[1] : '—'
})

// 辅助：信号颜色
function signalColor(signal?: string) {
  if (!signal) return '#909399'
  if (signal.includes('看多') || signal.includes('做多')) return '#e53935'
  if (signal.includes('看空') || signal.includes('去杠杆') || signal.includes('偏空')) return '#43a047'
  return '#E6A23C'
}
function signalClass(signal?: string) {
  if (!signal) return ''
  if (signal.includes('放量')) return 'volume-up'
  if (signal.includes('缩量')) return 'volume-down'
  return ''
}

onMounted(async () => {
  await appStore.checkHealth()
  if (appStore.systemReady) {
    await portfolioStore.loadPortfolio()
  }
})
</script>

<style scoped lang="scss">
.home {
  padding: 0;
}

.home__cards {
  margin-bottom: 20px;
}

.home__market {
  margin-bottom: 16px;
}

.home__market--row2 {
  margin-bottom: 20px;
}

// ── AI Loading / Error ──────────────────────────────────────────
.ai-loading-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #606266;
}

.ai-error-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fef0f0;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #f56c6c;
}

// ── Industry cards ─────────────────────────────────────────────
.industry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.industry-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;

  &--in .industry-arrow { color: #e53935; }
  &--out .industry-arrow { color: #43a047; }
}

.industry-rank {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #F0F2F5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #606266;
  flex-shrink: 0;
}

.industry-name {
  flex: 1;
  color: #303133;
}

.industry-arrow {
  font-size: 14px;
  font-weight: 700;
}

// ── Signal card ────────────────────────────────────────────────
.signal-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  margin: 8px 0 4px;
}

.signal-desc {
  font-size: 12px;
  color: #909399;
}

// ── Volume signal ──────────────────────────────────────────────
.volume-up { color: #e53935; }
.volume-down { color: #43a047; }

// ── Section Title ──────────────────────────────────────────────
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding: 0 2px;

  &__left {
    display: flex;
    align-items: center;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__date {
    font-size: 12px;
    font-weight: 400;
    color: #C0C4CC;
  }
}

// ── Metric Card ───────────────────────────────────────────────
.metric-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border: 1px solid #F0F2F5;
  transition: box-shadow 0.2s, transform 0.2s;
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 120px;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transform: translateY(-1px);
  }

  &__label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 500;
    color: #606266;
    margin-bottom: 12px;
  }

  &__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  &__value {
    font-size: 26px;
    font-weight: 700;
    color: #1D2129;
    line-height: 1.1;
    margin-bottom: 6px;
    font-variant-numeric: tabular-nums;
    display: flex;
    align-items: baseline;
    gap: 2px;
  }

  &__unit {
    font-size: 14px;
    font-weight: 400;
    color: #909399;
    margin-left: 2px;
  }

  &__sub {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

// ── ZT/DT counts ───────────────────────────────────────────────
.zt-count, .dt-count {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.zt-label, .dt-label {
  font-size: 11px;
  font-weight: 500;
  margin-left: 4px;
}

.zt-label { color: #e53935; }
.dt-label { color: #43a047; }
.dt-count { margin-left: 12px; }

.profit { color: #e53935; }
.loss   { color: #43a047; }
</style>
