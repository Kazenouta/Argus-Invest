<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAppStore } from '@/stores/app'
import { usePortfolioStore } from '@/stores/portfolio'

const appStore = useAppStore()
const portfolioStore = usePortfolioStore()

onMounted(async () => {
  await appStore.checkHealth()
  if (appStore.systemReady) {
    await portfolioStore.loadPortfolio()
  }
})
</script>

<template>
  <div class="home">
    <h1>Argus-Invest</h1>
    <p class="subtitle">私人投顾系统</p>

    <div class="status-card" :class="{ ok: appStore.systemReady, error: !appStore.systemReady }">
      <h3>系统状态</h3>
      <p v-if="appStore.systemReady">✅ 后端服务正常 · 数据目录就绪</p>
      <p v-else>❌ 后端服务未启动，请先运行 <code>cd backend && uvicorn app.main:app --reload</code></p>
    </div>

    <div v-if="appStore.systemReady && portfolioStore.snapshot" class="snapshot">
      <h3>今日持仓快照</h3>
      <div class="stat-grid">
        <div class="stat">
          <span class="label">总市值</span>
          <span class="value">¥ {{ portfolioStore.snapshot.total_market_value.toFixed(2) }}</span>
        </div>
        <div class="stat">
          <span class="label">浮盈/亏</span>
          <span class="value" :class="portfolioStore.snapshot.total_float_profit >= 0 ? 'profit' : 'loss'">
            {{ portfolioStore.snapshot.total_float_profit >= 0 ? '+' : '' }}{{ portfolioStore.snapshot.total_float_profit.toFixed(2) }}
          </span>
        </div>
        <div class="stat">
          <span class="label">浮盈比例</span>
          <span class="value" :class="portfolioStore.snapshot.float_profit_ratio >= 0 ? 'profit' : 'loss'">
            {{ portfolioStore.snapshot.float_profit_ratio >= 0 ? '+' : '' }}{{ portfolioStore.snapshot.float_profit_ratio.toFixed(2) }}%
          </span>
        </div>
        <div class="stat">
          <span class="label">持仓数量</span>
          <span class="value">{{ portfolioStore.snapshot.position_count }} 只</span>
        </div>
        <div class="stat">
          <span class="label">现金比例</span>
          <span class="value">{{ portfolioStore.snapshot.cash_ratio.toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <nav class="nav-grid">
      <router-link to="/portfolio" class="nav-card">📊 持仓管理</router-link>
      <router-link to="/trades" class="nav-card">📝 调仓记录</router-link>
      <router-link to="/thinking" class="nav-card">💭 盘中思考</router-link>
      <router-link to="/weakness" class="nav-card">⚠️ 弱点画像</router-link>
      <router-link to="/rules" class="nav-card">📋 规则库</router-link>
    </nav>
  </div>
</template>

<style scoped>
.home { padding: 2rem; max-width: 900px; margin: 0 auto; }
h1 { font-size: 2rem; margin-bottom: 0.25rem; }
.subtitle { color: #666; margin-bottom: 2rem; }
.status-card { padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 2rem; }
.status-card.ok { background: #f0f9f0; border: 1px solid #4caf50; }
.status-card.error { background: #fff3f3; border: 1px solid #f44336; }
.snapshot { background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
.snapshot h3 { margin-top: 0; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; }
.stat { background: white; padding: 1rem; border-radius: 6px; display: flex; flex-direction: column; gap: 0.25rem; }
.stat .label { font-size: 0.8rem; color: #888; }
.stat .value { font-size: 1.25rem; font-weight: 600; }
.profit { color: #e53935; }
.loss { color: #43a047; }
.nav-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem; }
.nav-card { background: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; padding: 1.5rem; text-align: center; text-decoration: none; color: #333; font-weight: 500; transition: all 0.2s; }
.nav-card:hover { background: #eef; border-color: #bcf; transform: translateY(-2px); }
code { background: #eee; padding: 0.1rem 0.3rem; border-radius: 3px; }
</style>
