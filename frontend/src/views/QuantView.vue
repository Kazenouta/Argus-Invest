<template>
  <div class="quant-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 策略管理 -->
      <el-tab-pane label="策略管理" name="strategies">
        <div class="tab-section">
          <div class="section-header">
            <span>预置策略</span>
            <el-button type="primary" size="small" @click="showStrategyEditor = true">
              <el-icon><Edit /></el-icon> 自定义策略
            </el-button>
          </div>

          <el-table :data="strategies" style="width: 100%; margin-top: 12px" max-height="400">
            <el-table-column prop="name" label="策略名称" width="180" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="threshold" label="阈值" width="80" />
            <el-table-column label="操作" width="280">
              <template #default="{ row }">
                <el-button size="small" @click="quickBacktest(row)">快速回测</el-button>
                <el-button size="small" type="success" @click="scanSignals(row)">扫描信号</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 策略编辑器 -->
          <el-dialog v-model="showStrategyEditor" title="自定义策略" width="700px">
            <el-form :model="customStrategy" label-width="100px">
              <el-form-item label="策略名称">
                <el-input v-model="customStrategy.name" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="customStrategy.description" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="条件表达式">
                <el-input v-model="customStrategy.condition_text" type="textarea" :rows="3"
                  placeholder="如: rsi_14 < 35 AND boll_position < 0.15" />
              </el-form-item>
              <el-form-item label="触发阈值">
                <el-input-number v-model="customStrategy.threshold" :min="0" :max="1" :step="0.05" />
              </el-form-item>
              <el-form-item label="操作类型">
                <el-select v-model="customStrategy.action">
                  <el-option label="买入" value="buy" />
                  <el-option label="卖出" value="sell" />
                  <el-option label="提醒" value="alert" />
                </el-select>
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showStrategyEditor = false">取消</el-button>
              <el-button type="primary" @click="applyCustomStrategy">保存并应用</el-button>
            </template>
          </el-dialog>
        </div>
      </el-tab-pane>

      <!-- 回测分析 -->
      <el-tab-pane label="回测分析" name="backtest">
        <div class="tab-section">
          <el-card shadow="never" style="margin-bottom: 16px">
            <template #header>回测参数</template>
            <el-form :model="btParams" inline label-width="80px" size="small">
              <el-form-item label="策略">
                <el-select v-model="btParams.strategy" style="width: 180px">
                  <el-option v-for="s in strategies" :key="s.name" :label="s.name" :value="s.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="股票代码">
                <el-input v-model="btParams.ticker" placeholder="SH600519" style="width: 140px" />
              </el-form-item>
              <el-form-item label="初始资金">
                <el-input-number v-model="btParams.initial_cash" :min="10000" :step="10000" />
              </el-form-item>
              <el-form-item label="开始日期">
                <el-date-picker v-model="btParams.start_date" type="date" value-format="YYYY-MM-DD" />
              </el-form-item>
              <el-form-item label="结束日期">
                <el-date-picker v-model="btParams.end_date" type="date" value-format="YYYY-MM-DD" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="backtesting" @click="runBacktest">
                  {{ backtesting ? '回测中...' : '开始回测' }}
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 回测结果 -->
          <div v-if="btResult">
            <el-card shadow="never" style="margin-bottom: 16px">
              <template #header>绩效指标</template>
              <el-row :gutter="16">
                <el-col :span="6" v-for="m in btMetrics" :key="m.key">
                  <div class="metric-card">
                    <div class="metric-label">{{ m.label }}</div>
                    <div class="metric-value" :class="m.valueClass">
                      {{ formatMetric(m.key, btResult[m.key]) }}
                    </div>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <el-card shadow="never">
              <template #header>权益曲线</template>
              <div ref="equityChart" style="width: 100%; height: 350px" />
            </el-card>
          </div>
        </div>
      </el-tab-pane>

      <!-- 组合优化 -->
      <el-tab-pane label="组合优化" name="portfolio">
        <div class="tab-section">
          <el-card shadow="never" style="margin-bottom: 16px">
            <template #header>优化参数</template>
            <el-form :model="pfParams" inline label-width="100px" size="small">
              <el-form-item label="股票代码">
                <el-input v-model="pfParams.tickers" placeholder="逗号分隔，如 SH600519,SZ000001" style="width: 320px" />
              </el-form-item>
              <el-form-item label="优化方法">
                <el-select v-model="pfParams.method" style="width: 140px">
                  <el-option label="最大夏普" value="max_sharpe" />
                  <el-option label="风险平价" value="risk_parity" />
                </el-select>
              </el-form-item>
              <el-form-item label="单票上限">
                <el-input-number v-model="pfParams.max_weight" :min="0.05" :max="1" :step="0.05" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="optimizing" @click="runOptimize">
                  {{ optimizing ? '优化中...' : '开始优化' }}
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <div v-if="pfResult">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-card shadow="never">
                  <template #header>最优权重</template>
                  <div ref="weightChart" style="width: 100%; height: 300px" />
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card shadow="never">
                  <template #header>有效前沿</template>
                  <div ref="frontierChart" style="width: 100%; height: 300px" />
                </el-card>
              </el-col>
            </el-row>
          </div>
        </div>
      </el-tab-pane>

      <!-- 实时信号 -->
      <el-tab-pane label="实时信号" name="signals">
        <div class="tab-section">
          <div class="section-header">
            <el-select v-model="signalStrategy" placeholder="选择策略" style="width: 180px" size="small">
              <el-option v-for="s in strategies" :key="s.name" :label="s.name" :value="s.name" />
            </el-select>
            <el-button type="primary" size="small" :loading="scanning" @click="fetchSignals">
              <el-icon><Refresh /></el-icon> 刷新信号
            </el-button>
          </div>

          <el-table :data="signals" style="width: 100%; margin-top: 12px" max-height="500">
            <el-table-column prop="ticker" label="代码" width="120" />
            <el-table-column prop="signal_name" label="策略" width="160" />
            <el-table-column prop="score" label="评分" width="80" sortable>
              <template #default="{ row }">
                <el-tag :type="row.score > 0.6 ? 'success' : row.score > 0.4 ? 'warning' : 'info'">
                  {{ row.score.toFixed(2) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="80" />
            <el-table-column prop="date" label="日期" width="120" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { quantAPI } from '@/api'
import * as echarts from 'echarts'

// ── State ──
const activeTab = ref('strategies')

const strategies = ref<any[]>([])
const showStrategyEditor = ref(false)
const customStrategy = reactive({
  name: '', description: '', condition_text: '',
  threshold: 0.5, action: 'buy',
})

// Backtest
const btParams = reactive({
  strategy: '', ticker: 'SH600519',
  initial_cash: 100_000, start_date: '', end_date: '',
})
const backtesting = ref(false)
const btResult = ref<any>(null)

// Portfolio
const pfParams = reactive({
  tickers: '', method: 'max_sharpe', max_weight: 0.2,
})
const optimizing = ref(false)
const pfResult = ref<any>(null)

// Signals
const signals = ref<any[]>([])
const signalStrategy = ref('')
const scanning = ref(false)

// Charts
const equityChart = ref<HTMLElement>()
const weightChart = ref<HTMLElement>()
const frontierChart = ref<HTMLElement>()

// ── Metrics display ──
const btMetrics = ref([
  { key: 'total_return', label: '累计收益(%)', valueClass: '' },
  { key: 'annual_return', label: '年化收益(%)', valueClass: '' },
  { key: 'sharpe_ratio', label: '夏普比率', valueClass: '' },
  { key: 'max_drawdown', label: '最大回撤(%)', valueClass: '' },
  { key: 'calmar_ratio', label: '卡玛比率', valueClass: '' },
  { key: 'win_rate', label: '胜率', valueClass: '' },
  { key: 'total_trades', label: '交易次数', valueClass: '' },
  { key: 'profit_loss_ratio', label: '盈亏比', valueClass: '' },
])

function formatMetric(key: string, value: any): string {
  if (value === undefined || value === null) return '-'
  if (key === 'win_rate') return (Number(value) * 100).toFixed(1) + '%'
  return Number(value).toFixed(2)
}

// ── API calls ──
async function loadStrategies() {
  try {
    const res = await quantAPI.getStrategies()
    strategies.value = res.strategies
  } catch (e: any) {
    console.error('Failed to load strategies:', e)
  }
}

function quickBacktest(strategy: any) {
  btParams.strategy = strategy.name
  activeTab.value = 'backtest'
}

async function scanSignals(strategy: any) {
  signalStrategy.value = strategy.name
  activeTab.value = 'signals'
  await fetchSignals()
}

async function runBacktest() {
  backtesting.value = true
  btResult.value = null
  try {
    const strategy = strategies.value.find((s: any) => s.name === btParams.strategy)
    const res = await quantAPI.runBacktest({
      strategy: strategy || {
        name: btParams.strategy,
        condition_text: 'rsi_14 < 30',
        threshold: 0.5,
        action: 'buy',
      },
      tickers: [btParams.ticker],
      start_date: btParams.start_date || undefined,
      end_date: btParams.end_date || undefined,
      initial_cash: btParams.initial_cash,
    })
    btResult.value = res
    await nextTick()
    renderEquityChart(res.equity_curve)
    ElMessage.success('回测完成')
  } catch (e: any) {
    ElMessage.error('回测失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    backtesting.value = false
  }
}

async function runOptimize() {
  optimizing.value = true
  pfResult.value = null
  try {
    const tickers = pfParams.tickers.split(',').map((t: string) => t.trim()).filter(Boolean)
    const res = await quantAPI.optimizePortfolio({
      tickers,
      method: pfParams.method,
      max_weight_per_asset: pfParams.max_weight,
    })
    pfResult.value = res
    await nextTick()
    renderWeightChart(res.weights)
    if (res.efficient_frontier?.length) renderFrontierChart(res.efficient_frontier)
    ElMessage.success('优化完成')
  } catch (e: any) {
    ElMessage.error('优化失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    optimizing.value = false
  }
}

async function fetchSignals() {
  scanning.value = true
  try {
    const res = await quantAPI.getSignals({ strategy_name: signalStrategy.value || undefined })
    signals.value = res.signals
  } catch (e: any) {
    ElMessage.error('获取信号失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    scanning.value = false
  }
}

function applyCustomStrategy() {
  strategies.value.push({ ...customStrategy })
  showStrategyEditor.value = false
  Object.assign(customStrategy, { name: '', description: '', condition_text: '', threshold: 0.5, action: 'buy' })
  ElMessage.success('策略已添加')
}

// ── Charts ──
function renderEquityChart(data: any[]) {
  if (!equityChart.value || !data?.length) return
  const chart = echarts.init(equityChart.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map((d: any) => d.date.slice(5)) },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + '万' } },
    series: [{
      name: '权益', type: 'line', data: data.map((d: any) => d.equity),
      smooth: true, areaStyle: { opacity: 0.1 },
    }],
  })
}

function renderWeightChart(weights: Record<string, number>) {
  if (!weightChart.value) return
  const chart = echarts.init(weightChart.value)
  const data = Object.entries(weights).filter(([, v]) => v > 0.001)
  chart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: data.map(([k, v]) => ({ name: k, value: Number((v * 100).toFixed(1)) })),
      label: { formatter: '{b}\n{d}%' },
    }],
  })
}

function renderFrontierChart(frontier: any[]) {
  if (!frontierChart.value) return
  const chart = echarts.init(frontierChart.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', name: '波动率(%)' },
    yAxis: { type: 'value', name: '收益率(%)' },
    series: [{
      type: 'scatter', name: '有效前沿',
      data: frontier.map((p: any) => [p.volatility, p.expected_return]),
    }],
  })
}

// ── Init ──
onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.quant-page {
  padding: 0;
}
.tab-section {
  padding: 16px 0;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.metric-card {
  text-align: center;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
</style>
