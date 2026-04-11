<template>
  <div class="portfolio-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>持仓看板</span>
          <div class="header-actions">
            <el-date-picker
              v-model="queryDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择查询日期"
              size="small"
              style="width: 148px; margin-right: 8px"
              @change="loadByDate"
            />
            <el-button type="primary" size="small" @click="showUpload = !showUpload">
              <el-icon><Upload /></el-icon>
              {{ showUpload ? '取消上传' : '上传持仓' }}
            </el-button>
            <el-button type="warning" size="small" :loading="checking" @click="checkPositions">
              <el-icon><Monitor /></el-icon>
              {{ checking ? '检测中…' : '检查持仓' }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- ── 上传面板 ─────────────────────────────────────── -->
      <div v-if="showUpload" class="upload-panel">
        <el-alert type="info" :closable="false" style="margin-bottom: 14px">
          <template #title>Excel 格式说明（直接上传，后端自动解析）：</template>
          <ul style="margin: 6px 0 0 0; font-size: 12px; line-height: 1.9; color: #666">
            <li><b>股票代码</b>（必填，支持 <code>SZ000001</code> 或纯数字 <code>000001</code>）</li>
            <li><b>股票名称</b>（必填）</li>
            <li><b>持股数量</b>（必填，整数）</li>
            <li><b>成本价</b>（必填，精确到分）</li>
            <li><b>当前价</b>（必填，精确到分）</li>
            <li><b>仓位占比%</b>（必填，如 <code>22.0</code> 表示 22%）</li>
          </ul>
          <div style="margin-top: 6px; font-size: 12px; color: #888">
            表头行可使用中文或英文，只要列名包含上述关键词即可自动识别。
            <br>上传后会<strong>覆盖</strong>该日期的所有持仓数据。
          </div>
        </el-alert>

        <el-form label-width="90px" size="default">
          <el-form-item label="持仓日期">
            <el-date-picker
              v-model="uploadDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 180px"
            />
          </el-form-item>
          <el-form-item label="选择文件">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls"
              :on-change="onFileChange"
              :on-remove="onFileRemove"
              :file-list="fileList"
              style="width: 100%"
            >
              <el-button type="primary" plain>
                <el-icon><Upload /></el-icon>&nbsp;选择 Excel 文件
              </el-button>
            </el-upload>
          </el-form-item>
          <el-form-item v-if="fileList.length > 0">
            <el-button type="primary" :loading="uploading" :disabled="!uploadDate || uploading" @click="submitFile">
              确认上传
            </el-button>
            <el-button @click="resetUpload">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- ── 持仓列表 ──────────────────────────────────────── -->
      <div v-if="store.loading" style="text-align:center;padding:40px;color:#999">
        <el-icon class="is-loading" style="font-size:20px"><Loading /></el-icon>
        <div style="margin-top:8px">加载中…</div>
      </div>

      <el-table
        v-else-if="store.positions.length > 0"
        :data="store.positions"
        stripe
        size="small"
      >
        <el-table-column prop="ticker" label="代码" width="110" />
        <el-table-column prop="name"   label="名称" width="130" />

        <el-table-column prop="market_value" label="市值" width="120" align="right">
          <template #default="{ row }">{{ fmtMoney(row.market_value) }}</template>
        </el-table-column>
        <el-table-column label="浮盈金额" width="110" align="right">
          <template #default="{ row }">
            <span :class="row.float_profit >= 0 ? 'profit' : 'loss'">
              {{ row.float_profit >= 0 ? '+' : '' }}{{ fmtMoney(row.float_profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="浮盈%" width="90" align="right">
          <template #default="{ row }">
            <el-tag :type="row.float_profit_ratio >= 0 ? 'danger' : 'success'" size="small">
              {{ row.float_profit_ratio >= 0 ? '+' : '' }}{{ row.float_profit_ratio?.toFixed(2) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="仓位" width="90" align="center">
          <template #default="{ row }">
            <span
              class="position-badge"
              :class="getPositionClass(row.position_ratio)"
            >{{ row.position_ratio?.toFixed(1) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="个股计划" min-width="200">
          <template #default="{ row }">
            <div class="plan-cell" @click="openPlanDialog(row)">
              <span class="plan-preview">{{ latestPlanMap[row.ticker] || '— 点击添加计划 —' }}</span>
              <el-icon class="plan-arrow"><ArrowRight /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="110" />
      </el-table>

      <el-empty v-else description="暂无持仓数据，请上传 Excel 文件" />

      <!-- ── 指标检测结果 ────────────────────────────────────── -->
      <div v-if="checkResult" class="check-result">
        <el-divider content-position="left">
          <el-icon><Monitor /></el-icon>
          指标检测结果
          <span class="check-meta">
            {{ checkResult.totalPositions }} 只持仓 ·
            {{ checkResult.totalEvents }} 条预警 ·
            {{ checkResult.checkedAt }}
          </span>
        </el-divider>
        <el-alert
          v-if="monitorStore.events.length === 0"
          type="success"
          :closable="false"
          show-icon
        >
          所有持仓指标正常，无预警信号
        </el-alert>
        <el-table
          v-else
          :data="monitorStore.events"
          stripe
          size="small"
        >
          <el-table-column prop="ticker" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="110" />
          <el-table-column prop="indicator" label="指标" width="130">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.indicator }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="signal" label="信号" width="80" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.signal === '买入' ? 'success' : row.signal === '警告' ? 'danger' : 'warning'"
              >{{ row.signal }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="value" label="当前值" width="90" align="right">
            <template #default="{ row }">{{ row.value.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="threshold_desc" label="阈值条件" min-width="160">
            <template #default="{ row }">
              <span style="font-size:12px;color:#666">{{ row.threshold_desc }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="200">
            <template #default="{ row }">
              <span style="font-size:12px">{{ row.message }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>

  <!-- ── 计划弹窗 ─────────────────────────────────────────── -->
  <el-dialog
    v-model="planDialogVisible"
    :title="`个股计划 — ${dialogTickerName}`"
    width="640px"
    :close-on-click-modal="false"
  >
    <div class="dialog-toolbar">
      <el-button type="primary" size="small" @click="openAddDrawer">
        <el-icon><Plus /></el-icon> 新增计划
      </el-button>
    </div>

    <el-table
      v-if="planDialogRecords.length > 0"
      :data="planDialogRecords"
      stripe
      size="small"
      style="margin-top: 10px"
    >
      <el-table-column prop="plan_date" label="日期" width="120" />
      <el-table-column prop="plan" label="计划内容" min-width="300">
        <template #default="{ row }">
          <div class="plan-content-cell">{{ row.plan }}</div>
        </template>
      </el-table-column>
      <el-table-column label="" width="60" align="center">
        <template #default="{ row }">
          <el-button
            link
            type="danger"
            size="small"
            @click="deletePlan(row.id)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无计划记录" style="margin: 20px 0" />

    <template #footer>
      <el-button @click="planDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- ── 新增计划抽屉 ───────────────────────────────────── -->
  <el-drawer
    v-model="addDrawerVisible"
    title="新增交易计划"
    direction="rtl"
    size="420px"
  >
    <el-form :model="planForm" label-width="80px" size="default" style="padding: 0 16px">
      <el-form-item label="日期">
        <el-date-picker
          v-model="planForm.plan_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="个股">
        <el-input :model-value="`${planForm.ticker} ${planForm.ticker_name}`" disabled />
      </el-form-item>
      <el-form-item label="交易计划">
        <el-input
          v-model="planForm.plan"
          type="textarea"
          :rows="6"
          placeholder="记录对该持仓的交易计划，如：若跌破30日线减仓50%；若反弹至60日线以上加仓两手…"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="planSaving" @click="submitPlan">保存</el-button>
        <el-button @click="addDrawerVisible = false">取消</el-button>
      </el-form-item>
    </el-form>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Loading, Plus, ArrowRight, Monitor } from '@element-plus/icons-vue'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMonitorStore } from '@/stores/monitor'
import { planApi, monitorApi } from '@/api'

const store = usePortfolioStore()
const monitorStore = useMonitorStore()

const showUpload = ref(false)
const checking = ref(false)
const checkResult = ref<{ checkedAt: string; totalEvents: number; totalPositions: number } | null>(null)
const uploading   = ref(false)
const uploadRef   = ref()
const fileList    = ref<{ name: string; raw?: File }[]>([])
const uploadDate  = ref(new Date().toISOString().split('T')[0])
const queryDate   = ref(new Date().toISOString().split('T')[0])

// ── Latest plan map (ticker → latest plan text) ───────────────
const latestPlanMap = ref<Record<string, string>>({})

async function loadLatestPlans() {
  try {
    const res = await planApi.latest()
    const data = Array.isArray(res.data) ? res.data : (res.data?.data ?? [])
    latestPlanMap.value = {}
    for (const row of data) {
      latestPlanMap.value[row.ticker] = row.plan ?? ''
    }
  } catch {
    // non-critical, ignore
  }
}

// ── Plan dialog ───────────────────────────────────────────────
const planDialogVisible = ref(false)
const dialogTicker = ref('')
const dialogTickerName = ref('')
const planDialogRecords = ref<any[]>([])

async function openPlanDialog(row: any) {
  dialogTicker.value = row.ticker
  dialogTickerName.value = row.name || row.ticker
  try {
    const res = await planApi.list(row.ticker)
    planDialogRecords.value = Array.isArray(res.data) ? res.data : []
  } catch {
    planDialogRecords.value = []
  }
  planDialogVisible.value = true
}

// ── Add drawer ───────────────────────────────────────────────
const addDrawerVisible = ref(false)
const planSaving = ref(false)
const planForm = reactive({
  plan_date: new Date().toISOString().split('T')[0],
  ticker: '',
  ticker_name: '',
  plan: '',
})

function openAddDrawer() {
  planForm.plan_date = new Date().toISOString().split('T')[0]
  planForm.ticker = dialogTicker.value
  planForm.ticker_name = dialogTickerName.value
  planForm.plan = ''
  addDrawerVisible.value = true
}

async function submitPlan() {
  if (!planForm.plan.trim()) {
    ElMessage.warning('请填写交易计划内容')
    return
  }
  planSaving.value = true
  try {
    await planApi.add({
      ticker: planForm.ticker,
      ticker_name: planForm.ticker_name,
      plan_date: planForm.plan_date,
      plan: planForm.plan.trim(),
    })
    ElMessage.success('计划已保存')
    addDrawerVisible.value = false
    // Refresh dialog list
    await openPlanDialog({ ticker: dialogTicker.value, name: dialogTickerName.value })
    // Refresh latest map
    await loadLatestPlans()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    planSaving.value = false
  }
}

async function deletePlan(planId: number) {
  try {
    await planApi.delete(planId)
    ElMessage.success('已删除')
    planDialogRecords.value = planDialogRecords.value.filter(r => r.id !== planId)
    await loadLatestPlans()
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── Upload helpers ───────────────────────────────────────────
async function loadByDate() {
  await store.loadPortfolio(queryDate.value || undefined)
  await loadLatestPlans()
}

function onFileChange(file: { name: string; raw?: File }) {
  if (!file.raw) return
  fileList.value = [{ name: file.name, raw: file.raw }]
}

function onFileRemove() {
  fileList.value = []
}

async function submitFile() {
  if (!uploadDate.value) { ElMessage.error('请先选择持仓日期'); return }
  const raw = fileList.value[0]?.raw
  if (!raw) { ElMessage.error('请先选择文件'); return }
  const formData = new FormData()
  formData.append('file', raw)
  uploading.value = true
  try {
    const res = await axios.post(`/api/portfolio/upload-xlsx?date_str=${uploadDate.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    const d = res.data
    ElMessage.success(`上传成功：${d.count} 条持仓记录（${d.date}），将自动刷新列表`)
    resetUpload()
    showUpload.value = false
    queryDate.value = uploadDate.value
    await loadByDate()
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

function resetUpload() {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

async function checkPositions() {
  checking.value = true
  checkResult.value = null
  try {
    await monitorStore.runCheck()
    const events = monitorStore.events
    console.debug('[PortfolioView] checkPositions events:', events.length, events)
    checkResult.value = {
      checkedAt: new Date().toLocaleString('zh-CN'),
      totalEvents: events.length,
      totalPositions: store.positions.length,
    }
  } catch (err) {
    console.error('[PortfolioView] checkPositions error:', err)
    ElMessage.error('检查失败，请稍后重试')
  } finally {
    checking.value = false
  }
}

function fmtMoney(v?: number | null) {
  if (v == null) return '—'
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getPositionClass(ratio?: number | null): string {
  if (ratio == null) return ''
  if (ratio < 5) return 'pos-light'
  if (ratio < 10) return 'pos-mid'
  return 'pos-heavy'
}

// Init
onMounted(async () => {
  await store.loadPortfolio()
  await loadLatestPlans()
  // 加载上次保存的检查结果（不重新计算）
  const saved = await monitorStore.loadLastResult()
  console.debug('[PortfolioView] loadLastResult result:', saved)
  if (saved) {
    checkResult.value = {
      checkedAt: new Date(saved.checked_at).toLocaleString('zh-CN'),
      totalEvents: saved.total_events,
      totalPositions: saved.total_positions,
    }
    console.debug('[PortfolioView] checkResult set:', checkResult.value)
  } else {
    console.debug('[PortfolioView] no saved result found')
  }
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
  align-items: center;
}
.upload-panel {
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}
.profit { color: #e53935; }
.loss   { color: #43a047; }
code {
  background: #eee;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}

.plan-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #409eff;
  font-size: 13px;
  &:hover .plan-arrow { opacity: 1; }
  .plan-preview {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    color: #606266;
    font-size: 13px;
  }
  .plan-arrow {
    flex-shrink: 0;
    opacity: 0.4;
    transition: opacity 0.15s;
  }
}

.dialog-toolbar {
  display: flex;
  justify-content: flex-end;
  padding-bottom: 0;
}

.plan-content-cell {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: #3a3a4a;
}

.position-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  &.pos-light  { background: #e8f4e8; color: #43a047; }
  &.pos-mid    { background: #fff3e0; color: #e67e22; }
  &.pos-heavy  { background: #fde8e8; color: #e53935; }
}

.check-result {
  margin-top: 16px;
}

.check-meta {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
  margin-left: 8px;
}
</style>
