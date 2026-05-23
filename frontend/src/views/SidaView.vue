<template>
  <div class="sida-section">
    <div class="section-title">
      <div class="section-title__left">
        <span class="sida-star">★</span>
        <span>斯大最新观点</span>
        <el-tag size="small" type="info" style="margin-left: 8px">斯托伯的天空</el-tag>
      </div>
      <div class="section-title__right">
        <span class="section-title__date">基于 {{ latestFileName }}</span>
        <el-button size="small" text type="primary" @click="showDetail = !showDetail">
          {{ showDetail ? '收起详情' : '展开详情' }}
        </el-button>
        <el-button size="small" type="primary" @click="refreshSida" :loading="refreshing">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button size="small" type="primary" @click="showUpload = true">
          <el-icon><Upload /></el-icon> 上传文件
        </el-button>
      </div>
    </div>

    <!-- 最新一句话核心观点 -->
    <div class="sida-banner" @click="showDetail = !showDetail">
      <div class="sida-banner__icon">💡</div>
      <div class="sida-banner__text">
        <div class="sida-banner__quote">"{{ latestView.coreThinking }}"</div>
        <div class="sida-banner__sub">—— 斯大 · 2026年4月24日</div>
      </div>
    </div>

    <!-- 大盘 + 各板块观点卡片 -->
    <div class="sida-cards">
      <div
        v-for="(item, key) in latestView.marketViews"
        :key="key"
        class="sida-card"
        :class="signalClass(item.signal)"
      >
        <div class="sida-card__header">
          <span class="sida-card__name">{{ assetName(key) }}</span>
          <el-tag size="small" :type="signalTagType(item.signal)">{{ item.signal }}</el-tag>
        </div>
        <div class="sida-card__view">{{ item.view }}</div>
        <div class="sida-card__detail" v-if="showDetail">{{ item.detail }}</div>
      </div>
    </div>

    <!-- 仓位概况 -->
    <div class="sida-position" v-if="showDetail">
      <div class="sida-position__title">📊 斯大当前仓位概况</div>
      <div class="sida-position__row">
        <span>整体仓位：<b>{{ latestView.positionSummary.整体仓位 }}</b></span>
        <span>主要持仓：<b>{{ latestView.positionSummary.主要持仓 }}</b></span>
      </div>
      <div class="sida-position__row">
        <span>态度：<b>{{ latestView.positionSummary.态度 }}</b></span>
        <span>已清仓：<b>{{ latestView.positionSummary.已清仓 }}</b></span>
      </div>
      <div class="sida-position__return">
        2025年年度收益：<b>142%</b>｜本年度收益：<b>21%</b>（截至2026-04-24）
      </div>
    </div>

    <!-- 历史观点时间线 -->
    <div class="sida-timeline" v-if="showDetail">
      <div class="sida-timeline__title">📅 近期观点演变</div>
      <div class="sida-timeline__items">
        <div
          v-for="item in latestView.recentHistory"
          :key="item.date"
          class="sida-timeline__item"
        >
          <span class="sida-timeline__date">{{ item.date.slice(5) }}</span>
          <span class="sida-timeline__title-text">{{ item.title }}</span>
          <el-tag size="small" type="info" class="sida-timeline__tag">{{ item.signal }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 核心投资观 -->
    <div class="sida-thoughts" v-if="showDetail">
      <div class="sida-thoughts__title">🧭 斯大投资思维框架</div>
      <div class="sida-thoughts__items">
        <div class="sida-thoughts__item">
          <div class="sida-thoughts__label">风险观</div>
          <div class="sida-thoughts__text">风险永远是第一位的。我们所有的收益都来自于风险本身。经历了一轮牛市后，市场出现很多偏离投资基本逻辑的观点，这种心态很危险。</div>
        </div>
        <div class="sida-thoughts__item">
          <div class="sida-thoughts__label">策略观</div>
          <div class="sida-thoughts__text">保持冷静和理性，密切观察和跟踪局势变化，做最有利于自己的判断和策略。现金比例保持充足，等待机会。</div>
        </div>
        <div class="sida-thoughts__item">
          <div class="sida-thoughts__label">战争判断</div>
          <div class="sida-thoughts__text">目前局势明朗：继续打，继续炸，突然撤兵概率很低。原油危机持续，能源安全是超长周期逻辑。</div>
        </div>
        <div class="sida-thoughts__item">
          <div class="sida-thoughts__label">技术分析</div>
          <div class="sida-thoughts__text">技术指标是深度投研的结果，而不是原因。见顶信号：换手率和成交量暴增（尤其是4-5倍），是综合判断结果。</div>
        </div>
      </div>
    </div>

    <div class="sida-footer">
      ⚠️ 以上为斯大个人观点摘录，仅供参考，不构成投资建议
    </div>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUpload"
      title="上传斯大周报文件"
      width="480px"
      :append-to-body="true"
    >
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #title>上传说明：将斯大的新一期周报 HTML 文件上传，系统自动解析并更新首页观点展示。</template>
      </el-alert>

      <el-form label-width="80px" size="default">
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".html,.htm"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :file-list="uploadFileList"
            style="width: 100%"
          >
            <el-button type="primary" plain>
              <el-icon><Upload /></el-icon>&nbsp;选择周报 HTML 文件
            </el-button>
            <template #tip>
              <div style="font-size: 12px; color: #aaa; margin-top: 4px">
                支持 .html 文件，系统会自动识别最新一期并解析
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item v-if="uploadFileList.length > 0">
          <el-button type="primary" :loading="uploading" :disabled="uploading" @click="submitUpload">
            确认上传并解析
          </el-button>
          <el-button @click="resetUpload">重置</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Refresh } from '@element-plus/icons-vue'

const showDetail = ref(false)
const showUpload = ref(false)
const uploadRef = ref()
const uploadFileList = ref<{ name: string; raw?: File }[]>([])
const uploading = ref(false)
const refreshing = ref(false)

const latestFileName = computed(() => {
  // 从文件列表中取最新日期的文件名
  return latestView.value._meta?.sourceFile || '2026-04-24 周报'
})

const latestView = ref({
  _meta: {
    sourceFile: '2026-04-24 周总结——局势并没有变得更好'
  },
  coreThinking: '能源为主，化工、黄金、铜铝均衡持仓，继续持有大比例现金。我认为目前的策略安排能够帮助我有效的度过市场的高度不确定性阶段，并在未来局势明朗后带来理想的结果。',
  marketViews: {
    '大盘': {
      view: '虹吸效应明显，亏钱效应突出',
      detail: '除"光"板块外其他板块走得并不好，创业板达3785高位，未来往下跌一点很多人今年收益将归零。量化主导让波动加大，经常砸黄金拉科技，跷跷板效应明显。',
      signal: '偏空',
      level: 3
    },
    '原油/能源': {
      view: '继续看多，但需警惕高位冲击',
      detail: '海峡封锁已接近2个月，原油供应缺口和价格中枢抬升明显。日韩原油短缺已影响民生，保鲜膜等日常用品已开始涨价。美军三艘航母齐聚中东，地面部队随时可能到来，局势明显恶化。',
      signal: '看多',
      level: 5
    },
    '黄金': {
      view: '原油高位压制，耐心等待',
      detail: '原油持续高位使美元坚韧，直接压制黄金。沃什若上台后进行缩表，就算降息也可能无法让黄金再次启动。需要等待实质性美元信用下降。耐心和认知都很重要。',
      signal: '中性/等待',
      level: 2
    },
    '铜': {
      view: '逻辑未变，耐心等待',
      detail: '铜铝观点没有变化，一季报充分验证了逻辑的强大。继续等待局势明朗。',
      signal: '中性',
      level: 3
    },
    '电解铝': {
      view: '继续看好，自主可控优势强大',
      detail: '从924以来因科技AI虹吸效应估值受打压，但市场是否会在未来进行纠偏值得期待。自主可控和难以被替代的资产，逻辑强大。',
      signal: '中性/乐观',
      level: 3
    },
    '化工': {
      view: '磷化工格局清晰，长期看好',
      detail: '虽然受能源危机冲击，但磷化工格局越来越清晰，几个大佬对市场的影响力和议价能力在提升，未来的空间在变大而不是缩小。等待能源危机明确走势。',
      signal: '中性/乐观',
      level: 3
    }
  },
  positionSummary: {
    '整体仓位': '不到6成',
    '主要持仓': '能源为主，化工、黄金、铜铝均衡持仓',
    '已清仓': '国电',
    '态度': '防守为主，等待局势明朗'
  },
  recentHistory: [
    { date: '2026-04-24', title: '局势并没有变得更好', signal: '能源/化工' },
    { date: '2026-04-17', title: '稳健策略遇上高风偏', signal: '能源/化工' },
    { date: '2026-04-03', title: '最值钱的就是风险本身', signal: '能源/防守' },
    { date: '2026-03-27', title: '全球聚焦这个周末', signal: '能源/谨慎' },
    { date: '2026-03-20', title: '第二次海湾战争？', signal: '能源/军工' },
    { date: '2026-03-13', title: '战争风险外溢', signal: '能源/谨慎' },
    { date: '2026-03-06', title: '战乱年代的净土', signal: '能源' },
    { date: '2026-02-27', title: '战略稳定期', signal: '铜铝/战略' }
  ]
})

function assetName(key: string) {
  return key
}

function signalClass(signal: string) {
  if (signal.includes('看多') || signal.includes('乐观')) return 'sida-card--bullish'
  if (signal.includes('偏空') || signal.includes('谨慎')) return 'sida-card--bearish'
  return 'sida-card--neutral'
}

function signalTagType(signal: string) {
  if (signal.includes('看多') || signal.includes('乐观')) return 'danger'
  if (signal.includes('偏空') || signal.includes('谨慎')) return 'warning'
  return 'info'
}

// ── 上传相关 ──────────────────────────────────────────────────
function onFileChange(file: { name: string; raw?: File }) {
  if (!file.raw) return
  uploadFileList.value = [{ name: file.name, raw: file.raw }]
}
function onFileRemove() {
  uploadFileList.value = []
}

async function submitUpload() {
  const raw = uploadFileList.value[0]?.raw
  if (!raw) { ElMessage.error('请先选择文件'); return }
  const formData = new FormData()
  formData.append('file', raw)
  formData.append('author', '斯托伯的天空')
  uploading.value = true
  try {
    const res = await fetch('/api/sida/upload', { method: 'POST', body: formData })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '上传失败')
    ElMessage.success(`上传成功：${data.filename}，已解析并更新观点`)
    uploadFileList.value = []
    uploadRef.value?.clearFiles()
    showUpload.value = false
    // 触发父组件刷新（如果有）
  } catch (err: unknown) {
    ElMessage.error((err as Error).message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function refreshSida() {
  refreshing.value = true
  try {
    const res = await fetch('/api/sida/refresh')
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '刷新失败')
    if (!data.hasNew) {
      ElMessage.info(data.message || '已是最新')
    } else {
      // 用后端返回的完整数据更新视图
      latestView.value = { ...data.parsed }
      ElMessage.success(data.message || '已刷新')
    }
  } catch (err: unknown) {
    ElMessage.error((err as Error).message || '刷新失败')
  } finally {
    refreshing.value = false
  }
}

function resetUpload() {
  uploadFileList.value = []
  uploadRef.value?.clearFiles()
}
</script>

<style scoped lang="scss">
.sida-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding: 0 2px;

  &__left {
    display: flex;
    align-items: center;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__date {
    font-size: 12px;
    font-weight: 400;
    color: #C0C4CC;
  }
}

.sida-star {
  color: #FFD700;
  font-size: 18px;
  margin-right: 4px;
  text-shadow: 0 0 2px rgba(255, 215, 0, 0.6);
  line-height: 1;
}

// Banner
.sida-banner {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  padding: 16px 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: opacity 0.2s;

  &:hover { opacity: 0.95; }

  &__icon {
    font-size: 22px;
    flex-shrink: 0;
    margin-top: 2px;
  }

  &__text {
    flex: 1;
  }

  &__quote {
    font-size: 14px;
    color: #fff;
    line-height: 1.6;
    font-style: italic;
  }

  &__sub {
    font-size: 12px;
    color: rgba(255,255,255,0.7);
    margin-top: 6px;
  }
}

// Cards grid
.sida-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.sida-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid #F0F2F5;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);

  &--bullish {
    border-left: 3px solid #e53935;
    .sida-card__view { color: #e53935; }
  }
  &--bearish {
    border-left: 3px solid #43a047;
    .sida-card__view { color: #43a047; }
  }
  &--neutral {
    border-left: 3px solid #E6A23C;
    .sida-card__view { color: #E6A23C; }
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  &__name {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
  }

  &__view {
    font-size: 13px;
    font-weight: 600;
    line-height: 1.4;
  }

  &__detail {
    font-size: 12px;
    color: #606266;
    margin-top: 6px;
    line-height: 1.5;
  }
}

// Position
.sida-position {
  background: #fafafa;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  font-size: 13px;

  &__title {
    font-weight: 600;
    color: #303133;
    margin-bottom: 8px;
  }

  &__row {
    display: flex;
    gap: 20px;
    margin-bottom: 4px;
    color: #606266;
    b { color: #303133; }
  }

  &__return {
    margin-top: 8px;
    color: #606266;
    border-top: 1px solid #eee;
    padding-top: 8px;
    b { color: #e53935; }
  }
}

// Timeline
.sida-timeline {
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  border: 1px solid #F0F2F5;

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 10px;
  }

  &__items {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  &__date {
    color: #909399;
    width: 50px;
    flex-shrink: 0;
  }

  &__title-text {
    color: #303133;
    flex: 1;
  }

  &__tag {
    flex-shrink: 0;
  }
}

// Thoughts
.sida-thoughts {
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  border: 1px solid #F0F2F5;

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 10px;
  }

  &__items {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  &__item {
    background: #f9f9f9;
    border-radius: 6px;
    padding: 10px 12px;
  }

  &__label {
    font-size: 12px;
    font-weight: 600;
    color: #409EFF;
    margin-bottom: 4px;
  }

  &__text {
    font-size: 12px;
    color: #606266;
    line-height: 1.5;
  }
}

.sida-footer {
  text-align: center;
  font-size: 11px;
  color: #C0C4CC;
  padding: 4px 0;
}
</style>
