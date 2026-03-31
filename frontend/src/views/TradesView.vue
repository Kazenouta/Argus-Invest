<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import type { TradeRecord } from '@/types'

const store = usePortfolioStore()
const showForm = ref(false)
const newTrade = ref<TradeRecord>({
  date: new Date().toISOString().split('T')[0],
  ticker: '', name: '', action: 'buy', quantity: 0,
  price: 0, amount: 0, reason: '',
})

onMounted(() => store.loadTrades())

function calcAmount() {
  newTrade.value.amount = newTrade.value.quantity * newTrade.value.price
}

async function submit() {
  await store.addTrade(newTrade.value)
  showForm.value = false
  newTrade.value = { date: new Date().toISOString().split('T')[0], ticker: '', name: '',
    action: 'buy', quantity: 0, price: 0, amount: 0, reason: '' }
}
</script>

<template>
  <div class="page">
    <h2>调仓记录</h2>

    <div class="toolbar">
      <button @click="showForm = !showForm">{{ showForm ? '取消' : '新增调仓' }}</button>
    </div>

    <div v-if="showForm" class="form-card">
      <div class="form-grid">
        <input v-model="newTrade.date" type="date" />
        <input v-model="newTrade.ticker" placeholder="股票代码" />
        <input v-model="newTrade.name" placeholder="股票名称" />
        <select v-model="newTrade.action">
          <option value="buy">买入</option><option value="sell">卖出</option>
          <option value="adjust">调仓</option>
        </select>
        <input v-model.number="newTrade.quantity" type="number" placeholder="数量" @input="calcAmount" />
        <input v-model.number="newTrade.price" type="number" step="0.01" placeholder="价格" @input="calcAmount" />
        <input :value="newTrade.amount.toFixed(2)" readonly placeholder="金额" />
      </div>
      <textarea v-model="newTrade.reason" placeholder="调仓逻辑（必填）" rows="3" />
      <button @click="submit" style="margin-top:0.5rem">保存</button>
    </div>

    <div class="trade-list">
      <table>
        <thead>
          <tr><th>日期</th><th>代码</th><th>名称</th><th>操作</th>
            <th>数量</th><th>价格</th><th>金额</th><th>逻辑</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in store.trades" :key="t.id">
            <td>{{ t.date }}</td><td>{{ t.ticker }}</td><td>{{ t.name }}</td>
            <td><span class="tag" :class="t.action">{{ t.action }}</span></td>
            <td>{{ t.quantity }}</td><td>{{ t.price.toFixed(2) }}</td>
            <td>{{ t.amount.toFixed(2) }}</td>
            <td class="reason">{{ t.reason }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="store.trades.length === 0" class="empty">暂无调仓记录</div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 1.5rem; }
.toolbar { margin-bottom: 1rem; }
button { padding: 0.5rem 1rem; cursor: pointer; }
.form-card { background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.5rem; margin-bottom: 0.5rem; }
.form-grid input, .form-grid select, textarea { padding: 0.4rem; border: 1px solid #ccc; border-radius: 4px; }
textarea { width: 100%; box-sizing: border-box; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { padding: 0.5rem; border-bottom: 1px solid #eee; text-align: right; }
th { background: #f5f5f5; }
td:first-child, td:nth-child(2), td:nth-child(3), th:first-child, th:nth-child(2), th:nth-child(3) { text-align: left; }
.tag { padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
.tag.buy { background: #e8f5e9; color: #2e7d32; }
.tag.sell { background: #ffebee; color: #c62828; }
.tag.adjust { background: #fff3e0; color: #e65100; }
.reason { max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.8rem; color: #555; }
.empty { color: #888; text-align: center; padding: 2rem; }
</style>
