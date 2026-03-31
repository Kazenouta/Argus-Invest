<template>
  <div class="weakness-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>弱点画像</span>
          <el-tag type="info">{{ profile?.version || 'v1' }}</el-tag>
        </div>
      </template>

      <el-empty v-if="!profile || profile.items.length === 0" description="暂无弱点画像，请上传历史交割单进行分析">
        <el-button type="primary" size="small">上传交割单</el-button>
      </el-empty>

      <div v-else>
        <!-- 统计摘要 -->
        <el-row :gutter="16" class="summary-row">
          <el-col :span="6">
            <el-statistic title="弱点总数" :value="profile.total_count" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="严重弱点" :value="profile.critical_count">
              <template #suffix>
                <el-tag v-if="profile.critical_count > 0" type="danger" size="small" style="margin-left:4px">⚠</el-tag>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="12">
            <el-statistic title="最后更新" :value="profile.last_updated" />
          </el-col>
        </el-row>

        <!-- 弱点列表 -->
        <div v-for="item in profile.items" :key="item.id" class="weakness-card" :class="item.severity">
          <div class="card-header">
            <strong>{{ item.title }}</strong>
            <div class="header-right">
              <el-tag :type="severityType(item.severity)" size="small">{{ item.severity }}</el-tag>
              <el-tag :type="item.confirmed ? 'success' : 'warning'" size="small">
                {{ item.confirmed ? '✅已确认' : '⏳待确认' }}
              </el-tag>
            </div>
          </div>
          <p class="description">{{ item.description }}</p>
          <div class="stats">
            <span>出现 {{ item.occurrence_count }} 次</span>
            <span>平均亏损 {{ item.avg_loss_ratio.toFixed(1) }}%</span>
            <span>最大亏损 {{ item.max_loss_ratio.toFixed(1) }}%</span>
          </div>
          <div class="actions">
            <el-button v-if="!item.confirmed" type="primary" size="small" @click="confirm(item.id!, true)">
              确认纳入
            </el-button>
            <el-button v-else type="default" size="small" @click="confirm(item.id!, false)">
              取消确认
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { WeaknessProfile } from '@/types'

const profile = ref<WeaknessProfile | null>(null)

function severityType(s: string) {
  return { critical: 'danger', high: 'warning', medium: 'info', low: 'success' }[s] || 'info'
}

async function loadProfile() {
  const res = await import('@/api').then(m => m.weaknessApi.get())
  profile.value = res.data
}

async function confirm(id: number, confirmed: boolean) {
  await import('@/api').then(m => m.weaknessApi.confirmItem(id, confirmed))
  await loadProfile()
  ElMessage.success(confirmed ? '已确认' : '已取消')
}

onMounted(loadProfile)
</script>

<style scoped lang="scss">
.weakness-page { padding: 0; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  width: 100%;

  .header-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }
}

.summary-row {
  margin-bottom: 20px;
}

.weakness-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  border-left-width: 4px;

  &.critical { border-left-color: #f56c6c; }
  &.high { border-left-color: #e6a23c; }
  &.medium { border-left-color: #909399; }
  &.low { border-left-color: #67c23a; }

  .description {
    margin: 8px 0;
    font-size: 14px;
    color: #606266;
  }

  .stats {
    display: flex;
    gap: 20px;
    font-size: 13px;
    color: #909399;
    margin-bottom: 10px;
  }

  .actions {
    display: flex;
    gap: 8px;
  }
}
</style>
