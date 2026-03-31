<template>
  <div class="thinking-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>盘中思考</span>
          <el-button type="primary" size="small" @click="showForm = !showForm">
            <el-icon><Plus /></el-icon>
            {{ showForm ? '取消' : '记录思考' }}
          </el-button>
        </div>
      </template>

      <!-- 录入表单 -->
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

      <!-- 思考列表 -->
      <div v-if="records.length > 0">
        <div v-for="r in records" :key="r.id" class="thinking-card">
          <div class="card-meta">
            <el-tag size="small">{{ r.thinking_time }}</el-tag>
            <el-tag v-if="r.ticker" size="small" type="primary">{{ r.ticker }} {{ r.ticker_name }}</el-tag>
            <el-tag size="small" type="info">{{ r.source }}</el-tag>
          </div>
          <p class="content">{{ r.content }}</p>
          <div class="card-footer">
            <el-button link type="danger" size="small" @click="remove(r.id!)">删除</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else description="暂无思考记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { ThinkingRecord } from '@/types'

const showForm = ref(false)
const records = ref<ThinkingRecord[]>([])

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

async function load() {
  const res = await import('@/api').then(m => m.thinkingApi.list())
  records.value = res.data
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

async function remove(id: number) {
  await import('@/api').then(m => m.thinkingApi.delete(id))
  records.value = records.value.filter(r => r.id !== id)
  ElMessage.success('已删除')
}

onMounted(load)
</script>

<style scoped lang="scss">
.thinking-page { padding: 0; }

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

.thinking-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fff;

  .card-meta {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
  }

  .content {
    white-space: pre-wrap;
    font-size: 14px;
    line-height: 1.7;
    color: #303133;
    margin: 0 0 10px;
  }

  .card-footer {
    display: flex;
    justify-content: flex-end;
  }
}
</style>
