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
      <span>市场概览</span>
      <div class="section-title__right">
        <span class="section-title__date" v-if="marketStore.updatedAt">
          更新于 {{ marketStore.updatedAt.replace('T', ' ').slice(0, 19) }}
        </span>
        <el-button size="small" :loading="marketStore.loading" @click="marketStore.loadOverview()">
          刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="home__market" v-loading="marketStore.loading">
      <!-- 成交额 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" style="background:#7C3AED"></span>
            <span>A股成交额</span>
          </div>
          <div class="metric-card__value">
            {{ marketStore.volume && marketStore.volume.amount > 0
                ? Number(marketStore.volume.amount).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
                : '—' }}
            <span class="metric-card__unit" v-if="marketStore.volume && marketStore.volume.amount > 0">亿</span>
          </div>
          <div class="metric-card__sub" v-if="marketStore.volume && marketStore.volume.change_pct !== 0"
               :class="marketStore.volume.change_pct >= 0 ? 'profit' : 'loss'">
            {{ marketStore.volume.change_pct >= 0 ? '↑' : '↓' }}
            {{ Math.abs(marketStore.volume.change_pct).toFixed(1) }}% 较昨日
          </div>
          <div class="metric-card__sub" v-else>—</div>
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
              {{ marketStore.ztDt ? marketStore.ztDt.zt_count : '—' }}
              <span class="zt-label">涨停</span>
            </span>
            <span class="dt-count">
              {{ marketStore.ztDt ? marketStore.ztDt.dt_count : '—' }}
              <span class="dt-label">跌停</span>
            </span>
          </div>
          <div class="metric-card__sub">上一交易日</div>
        </div>
      </el-col>

      <!-- 融资余额 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{ background: '#409EFF' }"></span>
            <span>融资余额</span>
          </div>
          <div class="metric-card__value">
            {{ marketStore.margin ? Number(marketStore.margin.balance).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '—' }}
            <span class="metric-card__unit" v-if="marketStore.margin">亿</span>
          </div>
          <div class="metric-card__sub" v-if="marketStore.margin"
               :class="marketStore.margin.change_pct >= 0 ? 'profit' : 'loss'">
            {{ marketStore.margin.change_pct >= 0 ? '↑' : '↓' }}
            {{ Math.abs(marketStore.margin.change_pct).toFixed(2) }}% 较前日
          </div>
          <div class="metric-card__sub" v-else>—</div>
        </div>
      </el-col>

      <!-- 散户情绪 -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-card__label">
            <span class="metric-card__dot" :style="{
              background: marketStore.breadth && marketStore.breadth.signal === '做多情绪' ? '#e53935'
                        : marketStore.breadth && marketStore.breadth.signal === '去杠杆偏空' ? '#43a047'
                        : '#909399'
            }"></span>
            <span>散户情绪</span>
          </div>
          <div class="metric-card__value">
            {{ marketStore.breadth ? marketStore.breadth.signal : '—' }}
          </div>
          <div class="metric-card__sub" v-if="marketStore.breadth">
            融资余额 {{ marketStore.breadth.rzye >= 0 ? '↑' : '↓' }}
            {{ Math.abs(marketStore.breadth.change_pct).toFixed(2) }}%（近5日）
          </div>
          <div class="metric-card__sub" v-else>—</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMarketStore } from '@/stores/market'
import { storeToRefs } from 'pinia'

const appStore = useAppStore()
const portfolioStore = usePortfolioStore()
const marketStore = useMarketStore()
const { snapshot } = storeToRefs(portfolioStore)

const floatProfit = computed(() => snapshot.value?.total_float_profit ?? 0)
const floatProfitRatio = computed(() => snapshot.value?.float_profit_ratio ?? 0)

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
