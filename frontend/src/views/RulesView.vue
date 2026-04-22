<template>
  <div class="rules-page">
    <!-- 页标题 -->
    <div class="page-header">
      <h2 class="page-title">指标规则库</h2>
      <p class="page-desc">
        基于《炒股的智慧》支撑线/阻力线理论，作用于持仓标的的买卖信号规则。
        当前共 <strong>{{ rules.length }}</strong> 条，全部自动启用。
      </p>
    </div>

    <!-- 规则列表 -->
    <div class="rules-grid">
      <div
        v-for="rule in rules"
        :key="rule.rule_id"
        class="rule-card"
        :class="rule.severity"
      >
        <!-- 卡片头部 -->
        <div class="rule-header">
          <div class="rule-header-left">
            <code class="rule-id">{{ rule.rule_id }}</code>
            <span class="rule-name">{{ rule.name }}</span>
          </div>
          <div class="rule-header-right">
            <el-tag :type="severityTagType(rule.severity)" size="small">
              {{ severityLabel(rule.severity) }}
            </el-tag>
            <el-tag :type="signalTagType(rule.signal)" size="small">
              {{ signalLabel(rule.signal) }}
            </el-tag>
          </div>
        </div>

        <!-- 信号说明 -->
        <p class="rule-desc">{{ rule.desc }}</p>

        <!-- 触发条件 -->
        <div class="rule-condition" v-if="rule.condition">
          <div class="condition-title">触发条件</div>
          <div class="condition-text">{{ rule.condition }}</div>
        </div>

        <!-- 操作建议 -->
        <div class="rule-action" v-if="rule.action">
          <div class="action-title">操作建议</div>
          <div class="action-text">{{ rule.action }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface IndicatorRule {
  rule_id: string
  name: string
  severity: 'critical' | 'major' | 'minor'
  signal: string
  desc: string
  condition?: string
  action?: string
}

const rules = ref<IndicatorRule[]>([
  {
    rule_id: 'SR-01',
    name: '支撑线保护（跌破警告）',
    severity: 'critical',
    signal: 'SELL / WATCH',
    desc: '现价接近支撑位（历史波段低点区域），若跌破支撑线则触发减仓/清仓信号。',
    condition: '现价 ≤ 支撑位 × 1.02 → 警告；现价 < 支撑位 → 触发卖出',
    action: '若跌破支撑位，建议减仓50%或清仓',
  },
  {
    rule_id: 'SR-02',
    name: '阻力线突破（关注买入机会）',
    severity: 'major',
    signal: 'WATCH',
    desc: '现价接近阻力位（历史波段高点区域），突破后有望开启升势。',
    condition: '现价在阻力位 ±3% 以内',
    action: '突破阻力位可少量买入，止损设在本支撑以下',
  },
  {
    rule_id: 'SR-03',
    name: '均线趋势保护',
    severity: 'major',
    signal: 'SELL_HALF / SAFE',
    desc: '收盘价与20日均线的位置关系判断短期趋势，跌破减仓，站稳持有。',
    condition: '跌破MA20 → 减仓50%；站稳MA20 → 安全持有',
    action: '跌破MA20建议减仓50%；若继续跌破MA60则清仓',
  },
  {
    rule_id: 'SR-04',
    name: '⚠️ 强制止损线（-8%）',
    severity: 'critical',
    signal: 'STOP_LOSS',
    desc: '持仓亏损达到8%时强制触发止损线，禁止加仓摊薄成本。',
    condition: '持仓涨幅 ≤ -8%（成本 × 0.92）',
    action: '立即减仓50%，禁止加仓摊薄成本！',
  },
  {
    rule_id: 'SR-05',
    name: '⚠️ 深度止损线（-15%）',
    severity: 'critical',
    signal: 'STOP_LOSS',
    desc: '持仓亏损达到15%时触发无条件清仓红线，不侥幸、不等待、不补仓。',
    condition: '持仓涨幅 ≤ -15%（成本 × 0.85）',
    action: '无条件立即清仓，不侥幸、不等待、不补仓！',
  },
  {
    rule_id: 'SR-06',
    name: '移动止盈触发（最高价回撤≥15%）',
    severity: 'critical',
    signal: 'SELL',
    desc: '从持仓期内最高价回撤15%触发移动止盈线，锁定利润。',
    condition: '最高价 × 0.85（回撤15%）→ 触发止盈；接近回撤10% → 预警',
    action: '触及止盈线立即卖出；预警时减仓50%',
  },
  {
    rule_id: 'SR-07',
    name: '利润保护触发（成本+5%守护线）',
    severity: 'critical',
    signal: 'SELL_HALF',
    desc: '持仓盈利≥20%后，移动止盈线移动至成本+5%，保护已有利润。',
    condition: '持仓涨幅 ≥ 20%，且现价跌破成本+5%',
    action: '减半仓；继续跌破成本价则全部清仓',
  },
  {
    rule_id: 'SR-08',
    name: '250日均线（长线牛熊分界）',
    severity: 'critical',
    signal: 'SELL / SAFE',
    desc: '250日均线是长线趋势的分界线，区分牛市和熊市。',
    condition: '跌破MA250 → 熊市信号（减仓）；站上MA250 → 长线安全',
    action: '跌破MA250建议减仓；重新站上后再考虑介入',
  },
])

function severityTagType(s: string) {
  return { critical: 'danger', major: 'warning', minor: 'success' }[s] || 'info'
}

function severityLabel(s: string) {
  return { critical: '严重', major: '重要', minor: '轻微' }[s] || s
}

function signalTagType(s: string) {
  if (s.includes('STOP_LOSS') || s.includes('SELL')) return 'danger'
  if (s.includes('WATCH') || s.includes('SELL_HALF')) return 'warning'
  return 'success'
}

function signalLabel(s: string) {
  const map: Record<string, string> = {
    'SELL': '卖出',
    'SELL / WATCH': '卖出/关注',
    'WATCH': '关注',
    'STOP_LOSS': '止损',
    'SELL_HALF': '建议减半',
    'SAFE': '安全',
    'SELL / SAFE': '卖出/安全',
  }
  return map[s] || s
}
</script>

<style scoped lang="scss">
.rules-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px;
}

.page-desc {
  font-size: 13px;
  color: #909399;
  margin: 0;
  line-height: 1.5;

  strong {
    color: #409eff;
  }
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 12px;
}

.rule-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 16px;
  border-left-width: 4px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  }

  // 左侧边条颜色
  &.critical { border-left-color: #f56c6c; }
  &.major    { border-left-color: #e6a23c; }
  &.minor    { border-left-color: #67c23a; }
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 6px;

  .rule-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rule-header-right {
    display: flex;
    gap: 4px;
  }
}

.rule-id {
  font-size: 11px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  color: #909399;
  font-family: monospace;
}

.rule-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.rule-desc {
  font-size: 12px;
  color: #606266;
  margin: 0 0 10px;
  line-height: 1.5;
}

.rule-condition,
.rule-action {
  background: #f9fafb;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;

  .condition-title,
  .action-title {
    font-size: 11px;
    color: #909399;
    margin-bottom: 4px;
  }

  .condition-text,
  .action-text {
    font-size: 12px;
    color: #409eff;
    font-weight: 500;
    line-height: 1.4;
  }
}
</style>
