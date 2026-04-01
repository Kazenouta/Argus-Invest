<template>
  <div class="trades-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>调仓记录</span>
          <div class="header-actions">
            <el-date-picker
              v-model="queryRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              size="small"
              style="width: 240px; margin-right: 8px"
              @change="loadTrades"
            />
            <el-select
              v-model="queryTicker"
              placeholder="全部股票"
              clearable
              filterable
              size="small"
              style="width: 130px; margin-right: 8px"
              @change="loadTrades"
            >
              <el-option
                v-for="t in tickerOptions"
                :key="t.ticker"
                :label="`${t.ticker} ${t.name}`"
                :value="t.ticker"
              />
            </el-select>
            <el-button type="primary" size="small" @click="showUpload = !showUpload">
              <el-icon><Upload /></el-icon>
              {{ showUpload ? '取消上传' : '上传调仓' }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- ── 上传面板 ─────────────────────────────────────── -->
      <div v-if="showUpload" class="upload-panel">
        <el-alert type="info" :closable="false" style="margin-bottom: 14px">
          <template #title>上传说明：从券商导出的「当日成交」Excel 文件，系统自动解析并批量追加调仓记录。</template>
          <ul style="margin: 6px 0 0 0; font-size: 12px; line-height: 1.9; color: #666">
            <li>支持同花顺/东方财富等券商导出的成交文件（表头含「流水号/证券代码/方向/成交数量/成交价格/成交时间」）</li>
            <li><b>证券买入</b> → 买入记录，<b>证券卖出/增强限价卖出</b> → 卖出记录</li>
            <li>撤单记录自动跳过（金额为 0 的成交不入库）</li>
            <li>上传后自动刷新列表，支持多次上传追加</li>
          </ul>
        </el-alert>

        <el-form label-width="80px" size="default">
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
                <el-icon><Upload /></el-icon>&nbsp;选择当日成交 Excel
              </el-button>
              <template #tip>
                <div style="font-size: 12px; color: #aaa; margin-top: 4px">
                  支持 .xlsx / .xls 文件，解析失败时会提示具体原因
                </div>
              </template>
            </el-upload>
          </el-form-item>

          <el-form-item v-if="fileList.length > 0">
            <el-button type="primary" :loading="uploading" :disabled="uploading" @click="submitUpload">
              确认上传
            </el-button>
            <el-button @click="resetUpload">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- ── 调仓记录列表 ────────────────────────────────── -->
      <el-table
        v-if="!tableLoading && trades.length > 0"
        :data="trades"
        stripe
        size="small"
        style="margin-top: 12px"
      >
        <el-table-column prop="date"    label="日期"   width="110" />
        <el-table-column prop="ticker" label="代码"   width="110" />
        <el-table-column prop="name"   label="名称"   width="120" />
        <el-table-column prop="action" label="方向"   width="75"  align="center">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="90"  align="right" />
        <el-table-column prop="price"    label="价格"  width="90"  align="right">
          <template #default="{ row }">{{ row.price?.toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="amount"  label="金额"  width="110" align="right">
          <template #default="{ row }">{{ fmtMoney(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="逻辑" min-width="220">
          <template #default="{ row }">
            <div class="reason-cell" @click="openEditDialog(row)">
              <span class="reason-text" :title="row.reason">
                {{ row.reason || '点击填写逻辑...' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" align="center">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="removeTrade(row.id!)">删</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="tableLoading" style="text-align:center;padding:40px;color:#999">
        <el-icon class="is-loading" style="font-size:20px"><Loading /></el-icon>
        <div style="margin-top:8px">加载中…</div>
      </div>

      <el-empty v-else-if="!tableLoading && trades.length === 0" description="暂无调仓记录，请上传成交文件" />
    </el-card>

    <!-- ── 逻辑编辑弹窗 ─────────────────────────────────── -->
    <el-dialog
      v-model="dialogVisible"
      :title="`填写逻辑 — ${dialogRow?.name || ''} (${dialogRow?.ticker || ''})`"
      width="520px"
      :append-to-body="true"
      class="reason-dialog"
    >
      <el-form label-width="0">
        <el-form-item>
          <el-input
            v-model="dialogReason"
            type="textarea"
            :rows="5"
            :autosize="{ minRows: 3, maxRows: 8 }"
            placeholder="描述本次操作的判断依据和逻辑，如：5日线上穿10日线，成交量放大至20日均量1.5倍，基本面业绩预增..."
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="dialogSaving" @click="confirmEdit">确定</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Loading } from '@element-plus/icons-vue'
import { tradesApi } from '@/api'
import type { TradeRecord } from '@/types'

const trades       = ref<TradeRecord[]>([])
const tableLoading = ref(false)
const showUpload   = ref(false)
const uploading    = ref(false)
const uploadRef    = ref()
const fileList     = ref<{ name: string; raw?: File }[]>([])
const queryRange   = ref<string[] | null>(null)
const queryTicker  = ref('')

// ── 弹窗状态 ─────────────────────────────────────────────
const dialogVisible = ref(false)
const dialogSaving  = ref(false)
const dialogRow     = ref<TradeRecord | null>(null)
const dialogReason  = ref('')

// ── 加载数据 ─────────────────────────────────────────────
async function loadTrades() {
  tableLoading.value = true
  try {
    const [start, end] = queryRange.value || []
    const res = await tradesApi.list({
      start_date: start || undefined,
      end_date:   end   || undefined,
      ticker:     queryTicker.value || undefined,
    })
    trades.value = res.data
  } catch {
    ElMessage.error('加载调仓记录失败')
  } finally {
    tableLoading.value = false
  }
}

// ── 弹窗相关 ─────────────────────────────────────────────
function openEditDialog(row: TradeRecord) {
  dialogRow.value    = row
  dialogReason.value = row.reason || ''
  dialogVisible.value = true
}

async function confirmEdit() {
  const row = dialogRow.value
  if (!row) return
  dialogSaving.value = true
  try {
    await tradesApi.update(row.id!, { ...row, reason: dialogReason.value.trim() })
    row.reason = dialogReason.value.trim()
    dialogVisible.value = false
    ElMessage.success('逻辑已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    dialogSaving.value = false
  }
}

// ── 上传相关 ─────────────────────────────────────────────
function onFileChange(file: { name: string; raw?: File }) {
  if (!file.raw) return
  fileList.value = [{ name: file.name, raw: file.raw }]
}
function onFileRemove() {
  fileList.value = []
}

async function submitUpload() {
  const raw = fileList.value[0]?.raw
  if (!raw) { ElMessage.error('请先选择文件'); return }
  const formData = new FormData()
  formData.append('file', raw)
  uploading.value = true
  try {
    const res = await fetch('/api/trades/upload-xlsx', { method: 'POST', body: formData })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '上传失败')
    ElMessage.success(`上传成功：${data.count} 条调仓记录`)
    resetUpload()
    showUpload.value = false
    await loadTrades()
  } catch (err: unknown) {
    ElMessage.error((err as Error).message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function resetUpload() {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

// ── 删除 ─────────────────────────────────────────────────
async function removeTrade(id: number) {
  try {
    await tradesApi.delete(id)
    trades.value = trades.value.filter(t => t.id !== id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 辅助 ─────────────────────────────────────────────────
function actionLabel(a?: string) {
  return { buy: '买入', sell: '卖出', adjust: '调仓' }[a || ''] || a || '—'
}
function actionTag(a?: string) {
  return { buy: 'danger', sell: 'success', adjust: 'warning' }[a || ''] || 'info'
}
function fmtMoney(v?: number | null) {
  if (v == null) return '—'
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const tickerOptions = computed(() => {
  const map = new Map<string, { ticker: string; name: string }>()
  for (const t of trades.value) {
    if (t.ticker && !map.has(t.ticker)) {
      map.set(t.ticker, { ticker: t.ticker, name: t.name || t.ticker })
    }
  }
  return Array.from(map.values())
})

onMounted(loadTrades)
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
.reason-cell {
  cursor: pointer;
  padding: 2px 0;
  .reason-text {
    font-size: 12px;
    color: #909399;
    font-style: italic;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: block;
    &:not([title=""]) { color: #606266; font-style: normal; }
  }
  &:hover .reason-text { color: #409eff; text-decoration: underline; }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
