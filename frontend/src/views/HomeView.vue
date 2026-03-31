<template>
  <div class="home">
    <!-- 关键指标卡片 -->
    <el-row :gutter="16" class="home__cards">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Coincedent /></el-icon>
              <span>总市值</span>
            </div>
          </template>
          <div class="card-value">
            ¥ {{ snapshot ? snapshot.total_market_value.toFixed(2) : '0.00' }}
          </div>
          <div class="card-desc">持仓快照</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><TrendCharts /></el-icon>
              <span>浮盈/亏</span>
            </div>
          </template>
          <div class="card-value" :class="floatProfit >= 0 ? 'profit' : 'loss'">
            {{ floatProfit >= 0 ? '+' : '' }}{{ floatProfit.toFixed(2) }}
          </div>
          <div class="card-desc">
            <span :class="floatProfitRatio >= 0 ? 'profit' : 'loss'">
              {{ floatProfitRatio >= 0 ? '+' : '' }}{{ floatProfitRatio.toFixed(2) }}%
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Wallet /></el-icon>
              <span>现金比例</span>
            </div>
          </template>
          <div class="card-value">{{ snapshot ? snapshot.cash_ratio.toFixed(1) : '0.0' }}%</div>
          <div class="card-desc">
            <el-progress
              :percentage="snapshot ? (100 - snapshot.cash_ratio) : 0"
              :stroke-width="6"
              :show-text="false"
              color="#409EFF"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><SetUp /></el-icon>
              <span>持仓数量</span>
            </div>
          </template>
          <div class="card-value">{{ snapshot ? snapshot.position_count : 0 }} 只</div>
          <div class="card-desc">建议 5-8 只</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统状态 & 快速操作 -->
    <el-row :gutter="16" class="home__section">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Monitor /></el-icon>
              <span>系统状态</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="后端服务">
              <el-tag :type="appStore.systemReady ? 'success' : 'danger'" size="small">
                {{ appStore.systemReady ? '在线' : '离线' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据目录">
              <el-tag :type="appStore.dataDirOk ? 'success' : 'danger'" size="small">
                {{ appStore.dataDirOk ? '就绪' : '异常' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="规则库">
              <el-tag type="info" size="small">11 条默认规则</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据存储">
              <el-tag type="info" size="small">DuckDB + Parquet</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Lightning /></el-icon>
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/portfolio')">
              <el-icon><Coincedent /></el-icon>
              持仓管理
            </el-button>
            <el-button type="success" @click="$router.push('/trades')">
              <el-icon><Swap /></el-icon>
              调仓记录
            </el-button>
            <el-button type="warning" @click="$router.push('/thinking')">
              <el-icon><ChatDotRound /></el-icon>
              盘中思考
            </el-button>
            <el-button @click="$router.push('/rules')">
              <el-icon><SetUp /></el-icon>
              规则库
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 持仓列表预览 -->
    <el-card v-if="positions.length > 0" shadow="hover" class="home__positions">
      <template #header>
        <div class="card-header">
          <el-icon><Coincedent /></el-icon>
          <span>持仓预览</span>
          <el-button type="text" @click="$router.push('/portfolio')" style="margin-left: auto">
            查看全部 →
          </el-button>
        </div>
      </template>
      <el-table :data="positions.slice(0, 5)" stripe size="small">
        <el-table-column prop="ticker" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="quantity" label="数量" width="90" align="right" />
        <el-table-column prop="cost_price" label="成本" width="90" align="right">
          <template #default="{ row }">{{ row.cost_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="现价" width="90" align="right">
          <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="float_profit" label="浮盈" align="right">
          <template #default="{ row }">
            <span :class="row.float_profit >= 0 ? 'profit' : 'loss'">
              {{ row.float_profit >= 0 ? '+' : '' }}{{ row.float_profit.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="position_ratio" label="占比" width="100" align="right">
          <template #default="{ row }">{{ row.position_ratio.toFixed(1) }}%</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 无数据提示 -->
    <el-empty v-if="!positions.length && appStore.systemReady" description="暂无持仓数据，请先上传持仓">
      <el-button type="primary" @click="$router.push('/portfolio')">去上传</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { usePortfolioStore } from '@/stores/portfolio'
import { storeToRefs } from 'pinia'

const appStore = useAppStore()
const portfolioStore = usePortfolioStore()
const { snapshot, positions } = storeToRefs(portfolioStore)

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
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 12px 0 6px;
  font-variant-numeric: tabular-nums;

  &.profit { color: #e53935; }
  &.loss { color: #43a047; }
}

.card-desc {
  color: #909399;
  font-size: 13px;

  .profit { color: #e53935; }
  .loss { color: #43a047; }
}

.home__section {
  margin-bottom: 16px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 0;
}

.home__positions {
  margin-top: 16px;
}

.profit { color: #e53935; }
.loss { color: #43a047; }
</style>
