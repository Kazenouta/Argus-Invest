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
          </div>
        </div>
      </template>

      <!-- ── 上传面板 ─────────────────────────────────────── -->
      <div v-if="showUpload" class="upload-panel">
        <el-alert type="info" :closable="false" style="margin-bottom: 14px">
          <template #title>
            Excel 格式说明（直接上传，后端自动解析）：
          </template>
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
              <template #tip>
                <div style="font-size: 12px; color: #aaa; margin-top: 4px">
                  支持 .xlsx / .xls，不限列顺序，解析失败时会提示具体原因
                </div>
              </template>
            </el-upload>
          </el-form-item>

          <el-form-item v-if="fileList.length > 0">
            <el-button
              type="primary"
              :loading="uploading"
              :disabled="!uploadDate || uploading"
              @click="submitFile"
            >
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
        <el-table-column prop="ticker"     label="代码"       width="110" />
        <el-table-column prop="name"        label="名称"       width="130" />
        <el-table-column prop="quantity"    label="持股数"     width="100"  align="right" />
        <el-table-column prop="cost_price"  label="成本价"     width="100"  align="right">
          <template #default="{ row }">{{ fmtPrice(row.cost_price) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价"  width="100"  align="right">
          <template #default="{ row }">{{ fmtPrice(row.current_price) }}</template>
        </el-table-column>
        <el-table-column prop="market_value" label="市值"    width="120"  align="right">
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
        <el-table-column label="仓位%" width="80" align="right">
          <template #default="{ row }">{{ row.position_ratio?.toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="110" />
      </el-table>

      <el-empty v-else description="暂无持仓数据，请上传 Excel 文件" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'

const store = usePortfolioStore()

const showUpload = ref(false)
const uploading   = ref(false)
const uploadRef   = ref()
const fileList    = ref<{ name: string; raw?: File }[]>([])
const uploadDate  = ref(new Date().toISOString().split('T')[0])
const queryDate   = ref(new Date().toISOString().split('T')[0])

async function loadByDate() {
  await store.loadPortfolio(queryDate.value || undefined)
}

function onFileChange(file: { name: string; raw?: File }) {
  if (!file.raw) return
  fileList.value = [{ name: file.name, raw: file.raw }]
}

function onFileRemove() {
  fileList.value = []
}

async function submitFile() {
  if (!uploadDate.value) {
    ElMessage.error('请先选择持仓日期')
    return
  }
  const raw = fileList.value[0]?.raw
  if (!raw) {
    ElMessage.error('请先选择文件')
    return
  }

  const formData = new FormData()
  formData.append('file', raw)

  uploading.value = true
  try {
    const res = await axios.post(
      `/api/portfolio/upload-xlsx?date_str=${uploadDate.value}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    const d = res.data
    ElMessage.success(
      `上传成功：${d.count} 条持仓记录（${d.date}），将自动刷新列表`
    )
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

function fmtPrice(v?: number | null) {
  if (v == null) return '—'
  return v.toFixed(3)
}
function fmtMoney(v?: number | null) {
  if (v == null) return '—'
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 初始加载
store.loadPortfolio()
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
</style>
