<template>
  <div class="thinking-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2>盘中思考</h2>
      <div class="header-actions">
        <el-radio-group v-model="sourceFilter" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="manual">手动录入</el-radio-button>
          <el-radio-button value="diary">日记导入</el-radio-button>
        </el-radio-group>
        <el-button type="primary" size="small" @click="showForm = !showForm">
          <el-icon><Plus /></el-icon>
          {{ showForm ? '取消' : '记录思考' }}
        </el-button>
      </div>
    </div>

    <!-- Entry Form -->
    <transition name="slide-fade">
      <div v-if="showForm" class="form-card">
        <el-form :model="form" label-width="90px" size="small">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="思考时间">
                <el-date-picker v-model="form.thinking_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="关联股票">
                <el-input v-model="form.ticker" placeholder="代码（可选）" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="股票名称">
                <el-input v-model="form.ticker_name" placeholder="名称（可选）" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="思考内容">
            <el-input v-model="form.content" type="textarea" :rows="4" placeholder="判断依据、大盘观察、大佬观点、操作计划..." />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="submit">保存</el-button>
          </el-form-item>
        </el-form>
      </div>
    </transition>

    <!-- Thinking Cards -->
    <div v-if="filteredRecords.length > 0" class="cards-container">
      <div
        v-for="r in filteredRecords"
        :key="r.id"
        class="thinking-card"
        :class="{ 'is-diary': r.source === 'diary' }"
      >
        <!-- Card Header: Date + Stocks + Actions -->
        <div class="card-head">
          <div class="card-date">
            <el-icon class="date-icon"><Calendar /></el-icon>
            <span class="date-text">{{ formatDateOnly(r.thinking_time) }}</span>
            <span v-if="getDisplayStocks(r).length > 0" class="stocks-list">
              <span v-for="(stock, i) in getDisplayStocks(r)" :key="stock">
                <span class="stock-name">{{ stock }}</span>
                <span v-if="i < getDisplayStocks(r).length - 1" class="stock-sep">|</span>
              </span>
            </span>
          </div>
          <div class="head-actions">
            <el-button link type="primary" size="small" @click="startEdit(r)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(Number(r.id))">删除</el-button>
          </div>
        </div>

        <!-- Card Body (view mode) -->
        <div v-show="editingId !== Number(r.id)" class="card-body">
          <p class="thinking-text">{{ getThinkingText(r) }}</p>
          <div v-if="getAiComment(r)" class="ai-block">
            <div class="ai-label">
              <el-icon><MagicStick /></el-icon>
              AI 点评
            </div>
            <p class="ai-text">{{ getAiComment(r) }}</p>
          </div>
        </div>

        <!-- Card Body (edit mode) -->
        <div v-show="editingId === Number(r.id)" class="card-body edit-body">
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="5"
            placeholder="编辑思考内容..."
          />
          <div class="edit-actions">
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <el-button type="primary" size="small" @click="saveEdit(Number(r.id))">保存</el-button>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-else description="暂无思考记录" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, MagicStick, Plus } from '@element-plus/icons-vue'
import type { ThinkingRecord } from '@/types'

const showForm = ref(false)
const sourceFilter = ref('all')
const records = ref<ThinkingRecord[]>([])
// Map of recordId → the text being edited (only one card editable at a time)
const editingId = ref<number | null>(null)
const editContent = ref('')

const now = new Date()
const pad = (n: number) => n.toString().padStart(2, '0')
const fmtDatetime = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

const form = ref<Partial<ThinkingRecord>>({
  thinking_time: fmtDatetime,
  ticker: '',
  ticker_name: '',
  content: '',
  source: 'manual',
})

// Filter by source
const filteredRecords = computed(() => {
  if (sourceFilter.value === 'all') return records.value
  if (sourceFilter.value === 'diary') return records.value.filter(r => r.source === 'diary')
  return records.value.filter(r => r.source === 'manual')
})

// Date only: YYYY-MM-DD
function formatDateOnly(dt: string | Date): string {
  const d = new Date(dt)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// Get displayed stock names: prefer stock_names (pipe-sep), fallback to ticker_name
function getDisplayStocks(r: ThinkingRecord): string[] {
  if (r.stock_names) return r.stock_names.split('|').filter(Boolean)
  if (r.ticker_name) return [r.ticker_name]
  return []
}

// Get thinking text (strip AI markers if still embedded)
// Paragraphs: remove blank lines, indent each with 4 spaces
function getThinkingText(r: ThinkingRecord): string {
  const raw = r.content.search(/【涉及股票】/) !== -1
    ? r.content.slice(0, r.content.search(/【涉及股票】/)).trim()
    : r.content
  return raw
    .split(/\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean)
    .map(p => '    ' + p)
    .join('\n')
}

// Get AI comment: prefer dedicated field, fallback to parsing from content
function getAiComment(r: ThinkingRecord): string {
  if (r.ai_comment) return r.ai_comment
  const idx = r.content.search(/【涉及股票】/)
  if (idx === -1) return ''
  return r.content.slice(idx).replace(/【涉及股票】[^【]+/, '').trim()
}

async function load() {
  const res = await import('@/api').then(m => m.thinkingApi.list())
  records.value = res.data
}

function startEdit(r: ThinkingRecord) {
  editingId.value = Number(r.id)
  editContent.value = getThinkingText(r)
}

async function saveEdit(id: number) {
  if (!editContent.value.trim()) {
    ElMessage.warning('思考内容不能为空')
    return
  }
  const original = records.value.find(r => Number(r.id) === id)
  if (!original) {
    ElMessage.error('记录未找到')
    return
  }
  const payload: ThinkingRecord = {
    id: id,
    thinking_time: original.thinking_time,
    ticker: original.ticker,
    ticker_name: original.ticker_name,
    content: editContent.value.trim(),
    ai_comment: original.ai_comment ?? undefined,
    action: original.action ?? undefined,
    source: original.source,
    trade_id: original.trade_id ?? undefined,
    created_at: original.created_at ?? undefined,
  }
  await import('@/api').then(m => m.thinkingApi.update(id, payload))
  editingId.value = null
  await load()
  ElMessage.success('已更新')
}

function cancelEdit() {
  editingId.value = null
  editContent.value = ''
}

// Remove the entire card
async function remove(id: number) {
  await import('@/api').then(m => m.thinkingApi.delete(id))
  records.value = records.value.filter(r => Number(r.id) !== id)
  ElMessage.success('已删除')
}

async function submit() {
  if (!form.value.content) {
    ElMessage.warning('请填写思考内容')
    return
  }
  await import('@/api').then(m => m.thinkingApi.add(form.value as ThinkingRecord))
  showForm.value = false
  form.value = { thinking_time: fmtDatetime, ticker: '', ticker_name: '', content: '', source: 'manual' }
  await load()
  ElMessage.success('思考已保存')
}

onMounted(load)
</script>

<style scoped lang="scss">
.thinking-page {
  padding: 20px 24px;
  min-height: 100vh;
  background: #f5f7fa;
}

// ── Page Header ──────────────────────────────────────────────────
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: #1a1a2e;
  }

  .header-actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }
}

// ── Form Card ────────────────────────────────────────────────────
.form-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #e8eaf0;
}

.slide-fade-enter-active { transition: all 0.25s ease-out; }
.slide-fade-leave-active { transition: all 0.2s ease-in; }
.slide-fade-enter-from, .slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

// ── Cards Container ───────────────────────────────────────────────
.cards-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

// ── Thinking Card ─────────────────────────────────────────────────
.thinking-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e8eaf0;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;

  &:hover {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    transform: translateY(-1px);
  }

  &.is-diary {
    border-left: 3px solid #f5a623;
  }
}

// ── Card Head ─────────────────────────────────────────────────────
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #fafbfc;
  border-bottom: 1px solid #f0f2f5;
  gap: 12px;
  flex-wrap: wrap;

  .card-date {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: #1a1a2e;

    .date-icon { color: #409eff; }
    .date-text { font-variant-numeric: tabular-nums; }
  }

  .card-stocks {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .stock-tag {
    font-size: 12px;
    border-radius: 4px;
  }

  .stocks-list {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 4px;
    font-size: 13px;
    font-weight: 400;
    color: #606266;

    .stock-name {
      color: #409eff;
    }

    .stock-sep {
      color: #d0d0d0;
      margin: 0 2px;
    }
  }

  .head-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }
}

// ── Card Body ─────────────────────────────────────────────────────
.card-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.thinking-text {
  font-size: 14px;
  line-height: 1.8;
  color: #3a3a4a;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;

  p { margin: 0; }
}

.ai-block {
  background: #f0f7ff;
  border-radius: 8px;
  padding: 12px 14px;
  border-left: 3px solid #409eff;
  display: flex;
  flex-direction: column;
  gap: 6px;

  .ai-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #409eff;
  }

  .ai-text {
    font-size: 13px;
    line-height: 1.7;
    color: #2c5aa0;
    margin: 0;
    white-space: pre-wrap;
  }
}

// ── Sections ──────────────────────────────────────────────────────
.section {
  .section-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8c8c8c;
    margin-bottom: 8px;
  }

  .section-content {
    font-size: 14px;
    line-height: 1.8;
    color: #3a3a4a;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }
}

// ── AI Section ────────────────────────────────────────────────────
.ai-section {
  background: #f0f7ff;
  border-radius: 8px;
  padding: 12px 14px;
  border-left: 3px solid #409eff;

  .ai-label {
    color: #409eff;
  }

  .ai-content {
    color: #2c5aa0;
    font-size: 13px;
  }
}

// ── Edit Body ─────────────────────────────────────────────────────
.edit-body {
  .el-textarea {
    margin-bottom: 12px;
  }

  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
}
</style>
