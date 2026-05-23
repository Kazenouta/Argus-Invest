<template>
  <div class="watchlist-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>观察池</span>
          <div class="header-actions">
            <el-button type="success" size="small" :loading="checkingSignals" @click="checkSignals">
              <el-icon><Monitor /></el-icon>
              {{ checkingSignals ? '检查中…' : '检查信号' }}
            </el-button>
            <el-button type="primary" size="small" @click="openAddDialog()">
              <el-icon><Plus /></el-icon>
              添加股票
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选工具栏 -->
      <div class="filter-bar">
        <el-select v-model="filterIndustry" placeholder="主营业务筛选" clearable size="small" style="width:140px;margin-right:8px">
          <el-option v-for="ind in industryOptions" :key="ind" :label="ind" :value="ind" />
        </el-select>
        <el-select v-model="filterAttention" placeholder="关注度" clearable size="small" style="width:110px">
          <el-option label="高" value="高" />
          <el-option label="中" value="中" />
          <el-option label="低" value="低" />
        </el-select>
        <span class="filter-hint" v-if="filterIndustry || filterAttention">
          共 {{ filteredRecords.length }} 条
        </span>
      </div>

      <!-- 表格 -->
      <el-table :data="filteredRecords" stripe size="small" v-loading="loading">
        <el-table-column prop="stock_code" label="代码" width="110" />
        <el-table-column prop="stock_name" label="名称" width="100" />
        <el-table-column prop="industry" label="主营业务" width="100" />
        <el-table-column label="关注度" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="attentionType(row.attention_level)">
              {{ row.attention_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标买入价" width="110" align="right">
          <template #default="{ row }">
            {{ row.target_buy_price ? '¥' + row.target_buy_price.toFixed(3) : '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="add_reason" label="加入理由" min-width="160" />
        <el-table-column prop="trade_plan" label="交易计划" min-width="200" />
        <el-table-column prop="focus_points" label="关注点" min-width="140" />
        <el-table-column prop="notes" label="备注" min-width="120" />
        <el-table-column label="加入时间" width="140">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && records.length === 0" description="观察池为空，点击右上角添加股票" />

      <!-- ── 信号检测结果（持续展示） ─────────────────────────────── -->
      <div v-if="lastCheckResult" class="check-result">
        <el-divider content-position="left">
          <el-icon><Monitor /></el-icon>
          信号检测结果
          <span class="check-meta">
            {{ lastCheckResult.total_watchlist }} 只观察股票 ·
            {{ lastCheckResult.signals.length }} 条预警 ·
            {{ formatTime(lastCheckResult.checked_at) }}
          </span>
        </el-divider>
        <el-alert
          v-if="lastCheckResult.signals.length === 0"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        >
          当前无触发信号
        </el-alert>
        <div v-else style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px">
          <div
            v-for="sig in lastCheckResult.signals"
            :key="sig.stock_code"
            class="signal-item"
          >
            <el-tag size="small" :type="tierTagType(sig.tier, sig.signal_type)" :disable-transitions="false">
              {{ sig.signal_label || sig.signal_type }}
            </el-tag>
            <b style="margin-left: 8px">{{ sig.stock_name }}</b>({{ sig.stock_code }})
            <span style="color: #666; margin-left: 8px; font-size: 13px">{{ sig.message }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'add' ? '添加观察股票' : '编辑观察股票'" width="580px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" size="default">
        <el-form-item label="股票代码" required>
          <el-input v-model="form.stock_code" placeholder="如 SH600096" style="width:200px" />
        </el-form-item>
        <el-form-item label="股票名称" required>
          <el-input v-model="form.stock_name" placeholder="如 中国联通" style="width:200px" />
        </el-form-item>
        <el-form-item label="加入时间">
          <el-date-picker
            v-model="form.created_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择日期时间"
            style="width:200px"
          />
        </el-form-item>
        <el-form-item label="主营业务">
          <el-input v-model="form.industry" placeholder="如 通信" style="width:200px" />
        </el-form-item>
        <el-form-item label="关注度">
          <el-radio-group v-model="form.attention_level">
            <el-radio value="高">高</el-radio>
            <el-radio value="中">中</el-radio>
            <el-radio value="低">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标买入价">
          <el-input-number v-model="form.target_buy_price" :precision="3" :step="0.1" placeholder="目标买入价" style="width:160px" />
        </el-form-item>
        <el-form-item label="加入理由">
          <el-input v-model="form.add_reason" type="textarea" :rows="2" placeholder="为什么加入观察池" />
        </el-form-item>
        <el-form-item label="交易计划">
          <el-input v-model="form.trade_plan" type="textarea" :rows="3" placeholder="买入条件、目标价位、仓位计划等" />
        </el-form-item>
        <el-form-item label="关注点">
          <el-input v-model="form.focus_points" type="textarea" :rows="2" placeholder="需要重点关注的事项" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="其他备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Monitor } from '@element-plus/icons-vue'
import { watchlistApi } from '@/api'

const loading = ref(false)
const saving = ref(false)
const checkingSignals = ref(false)
const records = ref<any[]>([])
const lastCheckResult = ref<any | null>(null)
const dialogVisible = ref(false)
const dialogMode = ref<'add' | 'edit'>('add')
const currentEditId = ref<number | null>(null)

const form = ref({
  stock_code: '',
  stock_name: '',
  created_at: '',
  industry: '',
  attention_level: '中',
  target_buy_price: null as number | null,
  add_reason: '',
  trade_plan: '',
  focus_points: '',
  notes: '',
})

// Filters
const filterIndustry = ref('')
const filterAttention = ref('')

const industryOptions = computed(() => {
  const set = new Set(records.value.map(r => r.industry).filter(Boolean))
  return Array.from(set).sort()
})

const filteredRecords = computed(() => {
  return records.value.filter(r => {
    if (filterIndustry.value && r.industry !== filterIndustry.value) return false
    if (filterAttention.value && r.attention_level !== filterAttention.value) return false
    return true
  })
})

function attentionType(level: string): string {
  return level === '高' ? 'danger' : level === '中' ? 'warning' : 'info'
}

// tier: 1=最高(红色) / 2=次高(橙色) / 3=一般(蓝色)
// 防御：如果 tier 无效，退而根据 signal_type 推断
function tierTagType(tier: number | undefined, signalType?: string): string {
  if (tier === 1) return 'danger'
  if (tier === 2) return 'warning'
  if (tier === 3) return 'primary'
  // 兜底：根据旧数据 signal_type 推断 tier
  if (signalType === 'buy_signal') return 'danger'
  if (signalType === 'near_target') return 'primary'
  return 'warning'
}

function formatDate(ts: string | null): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(ts)
  }
}

function formatTime(ts: string | null): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(ts)
  }
}

async function loadLastCheckResult() {
  try {
    const res = await watchlistApi.getLastCheck()
    if (res.data?.has_result) {
      lastCheckResult.value = res.data
    }
  } catch { /* silent */ }
}

function openAddDialog() {
  dialogMode.value = 'add'
  currentEditId.value = null
  form.value = {
    stock_code: '', stock_name: '',
    created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    industry: '',
    attention_level: '中',
    target_buy_price: null,
    add_reason: '', trade_plan: '', focus_points: '', notes: '',
  }
  dialogVisible.value = true
}

function openEditDialog(row: any) {
  dialogMode.value = 'edit'
  currentEditId.value = row.id
  form.value = {
    stock_code: row.stock_code ?? '',
    stock_name: row.stock_name ?? '',
    created_at: row.created_at ?? '',
    industry: row.industry ?? '',
    attention_level: row.attention_level ?? '中',
    target_buy_price: row.target_buy_price ?? null,
    add_reason: row.add_reason ?? '',
    trade_plan: row.trade_plan ?? '',
    focus_points: row.focus_points ?? '',
    notes: row.notes ?? '',
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.stock_code.trim()) { ElMessage.warning('请填写股票代码'); return }
  if (!form.value.stock_name.trim()) { ElMessage.warning('请填写股票名称'); return }
  saving.value = true
  try {
    if (dialogMode.value === 'add') {
      await watchlistApi.add({ ...form.value })
      ElMessage.success('添加成功')
    } else {
      if (currentEditId.value === null) return
      await watchlistApi.update(currentEditId.value, { ...form.value })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await loadRecords()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该观察股票？', '删除确认', { type: 'warning' })
    await watchlistApi.delete(id)
    ElMessage.success('已删除')
    await loadRecords()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function checkSignals() {
  checkingSignals.value = true
  try {
    const res = await watchlistApi.checkSignals()
    const signals = res.data?.signals ?? []
    lastCheckResult.value = {
      checked_at: res.data?.checked_at,
      total_watchlist: res.data?.total_watchlist ?? 0,
      signals,
      messages_created: res.data?.messages_created ?? 0,
    }
    if (signals.length === 0) {
      ElMessage.info('当前无触发信号')
    } else {
      ElMessage.warning(`检测到 ${signals.length} 个信号，已写入消息中心`)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检查失败')
  } finally {
    checkingSignals.value = false
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const res = await watchlistApi.list()
    records.value = Array.isArray(res.data) ? res.data : []
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRecords()
  loadLastCheckResult()
})
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}
.check-meta {
  margin-left: 12px;
  font-size: 12px;
  color: #999;
}
.filter-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #999;
}
.check-result {
  margin-top: 12px;
}
.signal-item {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}
</style>
