<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import type { PortfolioRecord } from '@/types'

const store = usePortfolioStore()
const uploadMode = ref(false)
const newRecords = ref<PortfolioRecord[]>([])

// simple add-row form
const newRow = ref<PortfolioRecord>({
  ticker: '', name: '', quantity: 0, cost_price: 0,
  current_price: 0, market_value: 0, float_profit: 0,
  float_profit_ratio: 0, position_ratio: 0, date: new Date().toISOString().split('T')[0],
})

onMounted(() => store.loadPortfolio())

function addRow() {
  newRecords.value.push({ ...newRow.value })
  newRow.value = { ...newRow.value, ticker: '', name: '', quantity: 0, cost_price: 0,
    current_price: 0, market_value: 0, float_profit: 0, float_profit_ratio: 0, position_ratio: 0 }
}

async function submitUpload() {
  await store.uploadPortfolio(newRecords.value)
  newRecords.value = []
  uploadMode.value = false
}

function calcRow(row: PortfolioRecord) {
  row.market_value = row.quantity * row.current_price
  row.float_profit = (row.current_price - row.cost_price) * row.quantity
  row.float_profit_ratio = row.cost_price > 0
    ? (row.current_price / row.cost_price - 1) * 100 : 0
}
</script>

<template>
  <div class="page">
    <h2>持仓管理</h2>

    <div class="toolbar">
      <button @click="uploadMode = !uploadMode">{{ uploadMode ? '取消' : '上传持仓' }}</button>
    </div>

    <!-- Upload form -->
    <div v-if="uploadMode" class="upload-form">
      <h3>新增持仓记录</h3>
      <div v-for="(row, i) in newRecords" :key="i" class="row-card">
        <span>{{ row.ticker }} {{ row.name }}</span>
        <span>{{ row.quantity }}股 @ {{ row.cost_price }}</span>
      </div>
      <div class="form-grid">
        <input v-model="newRow.ticker" placeholder="股票代码，如 SZ000001" />
        <input v-model="newRow.name" placeholder="股票名称" />
        <input v-model.number="newRow.quantity" type="number" placeholder="数量" />
        <input v-model.number="newRow.cost_price" type="number" step="0.01" placeholder="成本价" />
        <input v-model.number="newRow.current_price" type="number" step="0.01" placeholder="当前价" @input="calcRow(newRow)" />
        <input v-model.number="newRow.position_ratio" type="number" step="0.1" placeholder="仓位占比%" />
        <input v-model="newRow.date" type="date" />
      </div>
      <div class="form-actions">
        <button @click="addRow">添加一行</button>
        <button @click="submitUpload" :disabled="newRecords.length === 0">确认上传</button>
      </div>
    </div>

    <!-- List -->
    <div v-if="store.positions.length > 0" class="position-list">
      <table>
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>数量</th><th>成本</th><th>现价</th>
            <th>市值</th><th>浮盈</th><th>比例</th><th>占比</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in store.positions" :key="p.ticker">
            <td>{{ p.ticker }}</td><td>{{ p.name }}</td>
            <td>{{ p.quantity }}</td><td>{{ p.cost_price.toFixed(2) }}</td>
            <td>{{ p.current_price.toFixed(2) }}</td>
            <td>{{ p.market_value.toFixed(2) }}</td>
            <td :class="p.float_profit >= 0 ? 'profit' : 'loss'">
              {{ p.float_profit >= 0 ? '+' : '' }}{{ p.float_profit.toFixed(2) }}
            </td>
            <td :class="p.float_profit_ratio >= 0 ? 'profit' : 'loss'">
              {{ p.float_profit_ratio >= 0 ? '+' : '' }}{{ p.float_profit_ratio.toFixed(2) }}%
            </td>
            <td>{{ p.position_ratio.toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="empty">暂无持仓数据</div>
  </div>
</template>

<style scoped>
.page { padding: 1.5rem; }
.toolbar { margin-bottom: 1rem; }
button { padding: 0.5rem 1rem; cursor: pointer; }
.upload-form { background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.5rem; margin: 1rem 0; }
.form-grid input { padding: 0.4rem; border: 1px solid #ccc; border-radius: 4px; }
.form-actions { display: flex; gap: 0.5rem; }
.row-card { background: white; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.5rem; display: flex; justify-content: space-between; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { padding: 0.5rem; text-align: right; border-bottom: 1px solid #eee; }
th { background: #f5f5f5; text-align: right; }
td:first-child, td:nth-child(2), th:first-child, th:nth-child(2) { text-align: left; }
.profit { color: #e53935; }
.loss { color: #43a047; }
.empty { color: #888; padding: 2rem; text-align: center; }
</style>
