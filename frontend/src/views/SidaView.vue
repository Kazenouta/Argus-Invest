<template>
  <div class="sida-section">
    <div class="section-title">
      <div class="section-title__left">
        <span>🧠 斯大最新观点</span>
        <el-tag size="small" type="info" style="margin-left: 8px">斯托伯的天空</el-tag>
      </div>
      <div class="section-title__right">
        <span class="section-title__date">基于 2026-04-03 周报</span>
        <el-button size="small" text type="primary" @click="showDetail = !showDetail">
          {{ showDetail ? '收起详情' : '展开详情' }}
        </el-button>
      </div>
    </div>

    <!-- 最新一句话核心观点 -->
    <div class="sida-banner" @click="showDetail = !showDetail">
      <div class="sida-banner__icon">💡</div>
      <div class="sida-banner__text">
        <div class="sida-banner__quote">"{{ latestView.coreThinking }}"</div>
        <div class="sida-banner__sub">—— 斯大 · 2026年4月3日</div>
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
        2025年年度收益：<b>142%</b>｜本年度收益：<b>21%</b>（截至2026-04-03）
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const showDetail = ref(false)

const latestView = {
  coreThinking: '风险才是投资里最重要最值钱的东西。长期做交易的投资者逐渐会明白，我们所有的收益都来自于风险本身。',
  marketViews: {
    '大盘': {
      view: '偏熊市趋势，风险大于机会',
      detail: '周五成交额跌至1.6万亿，融资余额仍高达2.6万亿。若外部形势无好转，可能回调至3700甚至3600。科技板块泡沫依旧坚硬，整体风险未充分释放。',
      signal: '偏空',
      level: 3
    },
    '原油/能源': {
      view: '最高确信度，持续看多',
      detail: '霍尔木兹再也不会回到战前状态。特朗普讲话后果断加仓旧能源（嗨油、中妹、煤炭ETF）。双方都没有意愿让油价大幅下跌，能源是当前最硬的板块之一。',
      signal: '强烈看多',
      level: 5
    },
    '黄金': {
      view: '等待，不着急布局',
      detail: '加息概率增加（原油涨价推动通胀）。黄金上涨逻辑依旧在（货币信用下降），但短期受加息预期压制，需等中美会谈和战争走势明朗。',
      signal: '中性/等待',
      level: 2
    },
    '铜': {
      view: '谨慎，等待局势明朗',
      detail: '受战争负面影响比铝大，担忧流动性和衰退，走势远不如铝。等局势明朗再做打算。',
      signal: '谨慎',
      level: 2
    },
    '电解铝': {
      view: '长逻辑不变，谨慎持有',
      detail: '中国电解铝优势非常强大，安全边际自信。等局势明朗再做调整。',
      signal: '中性',
      level: 3
    },
    '化工': {
      view: '长期逻辑不变，耐心持有',
      detail: '保供操作对龙头企业中长期有利无害。目前有时间做投研，看年报季报和产业面信息，正好避开高风险阶段。',
      signal: '中性/乐观',
      level: 3
    }
  },
  positionSummary: {
    '整体仓位': '不到6成',
    '主要持仓': '旧能源（嗨油、中妹煤炭ETF）',
    '已清仓': '国电',
    '态度': '防守为主，等待机会'
  },
  recentHistory: [
    { date: '2026-04-03', title: '最值钱的就是风险本身', signal: '能源/防守' },
    { date: '2026-03-27', title: '全球聚焦这个周末', signal: '能源/谨慎' },
    { date: '2026-03-20', title: '第二次海湾战争？', signal: '能源/军工' },
    { date: '2026-03-13', title: '战争风险外溢', signal: '能源/谨慎' },
    { date: '2026-03-06', title: '战乱年代的净土', signal: '能源' },
    { date: '2026-02-27', title: '战略稳定期', signal: '铜铝/战略' },
    { date: '2026-02-13', title: '新年快乐', signal: '铜铝/化工' },
    { date: '2026-01-30', title: '长期主义', signal: '价值投资/防守' }
  ]
}

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
