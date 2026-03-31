<template>
  <div class="trades-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>调仓记录</span>
          <el-button type="primary" size="small" @click="showForm = !showForm">
            <el-icon><Plus /></el-icon>
            {{ showForm ? '取消' : '新增调仓' }}
          </el-button>
        </div>
      </template>

      <!-- 新增表单 -->
      <div v-if="showForm" class="form-card">
        <el-form :model="form" label-width="90px" size="small">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="交易日期">
                <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
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
              <el-form-item label="操作类型">
                <el-select v-model="form.action" style="width:100%">
                  <el-option label="买入" value="buy" />
                  <el-option label="卖出" value="sell" />
                  <el-option label="调仓" value="adjust" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="成交数量">
                <el-input-number v-model="form.quantity" :min="0" style="width:100%" @change="calcAmount" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="成交价格">
                <el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%" @change="calcAmount" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="调仓逻辑">
            <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="必填：描述操作理由和判断依据" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="submit">保存</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 列表 -->
      <el-table :data="trades" stripe size="small">
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="ticker" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="action" label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="90" align="right" />
        <el-table-column prop="price" label="价格" width="90" align="right">
          <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="110" align="right">
          <template #default="{ row }">{{ row.amount.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="逻辑" min-width="200">
          <template #default="{ row }">
            <span class="reason-text">{{ row.reason || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="removeTrade(row.id!)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="trades.length === 0" description="暂无调仓记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePortfolioStore } from '@/stores/portfolio'
import type { TradeRecord } from '@/types'

const store = usePortfolioStore()
const showForm = ref(false)
const today = new Date().toISOString().split('T')[0]

const form = ref<TradeRecord>({
  date: today, ticker: '', name: '', action: 'buy',
  quantity: 0, price: 0, amount: 0, reason: '',
})

const trades = ref<TradeRecord[]>([])

function calcAmount() {
  form.value.amount = form.value.quantity * form.value.price
}

function actionLabel(a: string) {
  return { buy: '买入', sell: '卖出', adjust: '调仓' }[a] || a
}

function actionTagType(a: string) {
  return { buy: 'danger', sell: 'success', adjust: 'warning' }[a] || 'info'
}

async function submit() {
  if (!form.value.ticker || !form.value.reason) {
    ElMessage.warning('请填写股票代码和调仓逻辑')
    return
  }
  calcAmount()
  await store.addTrade({ ...form.value })
  showForm.value = false
  form.value = { date: today, ticker: '', name: '', action: 'buy', quantity: 0, price: 0, amount: 0, reason: '' }
  await load()
  ElMessage.success('调仓记录已保存')
}

async function removeTrade(id: number) {
  await store.trades.splice(0, 0) // trigger store
  const res = await import('@/api').then(m => m.tradesApi.delete(id))
  if (res.status === 200 || res.status === 204) {
    trades.value = trades.value.filter(t => t.id !== id)
    ElMessage.success('已删除')
  }
}

async function load() {
  const res = await import('@/api').then(m => m.tradesApi.list())
  trades.value = res.data
}

onMounted(load)
</script>

<style scoped lang="scss">
.trades-page { padding: 0; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.form-card {
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.reason-text {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 300px;
}
</style>
