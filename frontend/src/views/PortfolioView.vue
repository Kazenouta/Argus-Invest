<template>
  <div class="portfolio-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>持仓看板</span>
          <el-button type="primary" size="small" @click="showUpload = !showUpload">
            <el-icon><Upload /></el-icon>
            {{ showUpload ? '取消' : '上传持仓' }}
          </el-button>
        </div>
      </template>

      <!-- 上传表单 -->
      <div v-if="showUpload" class="upload-form">
        <el-form :model="form" label-width="80px" size="small">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="股票代码">
                <el-input v-model="form.ticker" placeholder="如 SZ000001" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="股票名称">
                <el-input v-model="form.name" placeholder="如 平安银行" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="持仓日期">
                <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="持股数量">
                <el-input-number v-model="form.quantity" :min="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="成本价">
                <el-input-number v-model="form.cost_price" :min="0" :precision="2" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="当前价">
                <el-input-number v-model="form.current_price" :min="0" :precision="2" style="width:100%" @change="recalc" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="仓位占比%">
                <el-input-number v-model="form.position_ratio" :min="0" :max="100" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item>
            <el-button type="primary" @click="addRow">添加</el-button>
            <el-button @click="submitUpload" :disabled="rows.length === 0">确认上传</el-button>
          </el-form-item>
        </el-form>

        <el-table v-if="rows.length > 0" :data="rows" size="small" stripe style="margin-top:12px">
          <el-table-column prop="ticker" label="代码" width="110" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="quantity" label="数量" width="100" align="right" />
          <el-table-column prop="cost_price" label="成本" width="100" align="right">
            <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="current_price" label="现价" width="100" align="right">
            <template #default="{ row }">{{ row.current_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="market_value" label="市值" width="110" align="right">
            <template #default="{ row }">{{ row.market_value?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="浮盈" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.float_profit >= 0 ? 'profit' : 'loss'">
                {{ row.float_profit >= 0 ? '+' : '' }}{{ row.float_profit?.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60">
            <template #default="{ row, $index }">
              <el-button link type="danger" size="small" @click="rows.splice($index, 1)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 持仓列表 -->
      <el-table v-if="positions.length > 0" :data="positions" stripe size="small">
        <el-table-column prop="ticker" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="quantity" label="持股数" width="100" align="right" />
        <el-table-column prop="cost_price" label="成本价" width="100" align="right">
          <template #default="{ row }">{{ row.cost_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价" width="100" align="right">
          <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="market_value" label="市值" width="120" align="right">
          <template #default="{ row }">{{ row.market_value.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="float_profit" label="浮盈金额" width="110" align="right">
          <template #default="{ row }">
            <span :class="row.float_profit >= 0 ? 'profit' : 'loss'">
              {{ row.float_profit >= 0 ? '+' : '' }}{{ row.float_profit.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="float_profit_ratio" label="浮盈%" width="90" align="right">
          <template #default="{ row }">
            <el-tag :type="row.float_profit_ratio >= 0 ? 'danger' : 'success'" size="small">
              {{ row.float_profit_ratio >= 0 ? '+' : '' }}{{ row.float_profit_ratio.toFixed(2) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="position_ratio" label="占比%" width="90" align="right">
          <template #default="{ row }">{{ row.position_ratio.toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="110" />
      </el-table>

      <el-empty v-else description="暂无持仓数据" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePortfolioStore } from '@/stores/portfolio'
import { storeToRefs } from 'pinia'
import type { PortfolioRecord } from '@/types'

const store = usePortfolioStore()
const { positions } = storeToRefs(store)
const showUpload = ref(false)

const today = new Date().toISOString().split('T')[0]
const form = ref<Partial<PortfolioRecord>>({
  date: today,
  ticker: '',
  name: '',
  quantity: 0,
  cost_price: 0,
  current_price: 0,
  position_ratio: 0,
})
const rows = ref<Partial<PortfolioRecord>[]>([])

function recalc() {
  const f = form.value
  if (f.quantity && f.cost_price && f.current_price) {
    f.market_value = f.quantity * f.current_price
    f.float_profit = (f.current_price - f.cost_price) * f.quantity
    f.float_profit_ratio = f.cost_price > 0
      ? (f.current_price / f.cost_price - 1) * 100 : 0
  }
}

function addRow() {
  if (!form.value.ticker) {
    ElMessage.warning('请填写股票代码')
    return
  }
  recalc()
  rows.value.push({ ...form.value })
  form.value = { date: today, ticker: '', name: '', quantity: 0, cost_price: 0, current_price: 0, position_ratio: 0 }
}

async function submitUpload() {
  const records = rows.value.map(r => ({
    ...r,
    date: r.date || today,
    market_value: (r.quantity || 0) * (r.current_price || 0),
    float_profit: ((r.current_price || 0) - (r.cost_price || 0)) * (r.quantity || 0),
    float_profit_ratio: r.cost_price
      ? ((r.current_price || 0) / r.cost_price - 1) * 100 : 0,
  })) as PortfolioRecord[]

  await store.uploadPortfolio(records)
  rows.value = []
  showUpload.value = false
  ElMessage.success('持仓上传成功')
}

onMounted(() => store.loadPortfolio())
</script>

<style scoped lang="scss">
.portfolio-page { padding: 0; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.upload-form {
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.profit { color: #e53935; }
.loss { color: #43a047; }
</style>
