/**
 * Shared TypeScript types mirroring backend models.
 */

export interface PortfolioRecord {
  id?: number
  ticker: string
  name: string
  quantity: number
  cost_price: number
  current_price: number
  market_value: number
  float_profit: number
  float_profit_ratio: number
  position_ratio: number
  date: string
}

export interface PortfolioSnapshot {
  date: string
  total_market_value: number
  total_cost: number
  total_float_profit: number
  float_profit_ratio: number
  cash_ratio: number
  position_ratio: number
  position_count: number
  positions: PortfolioRecord[]
}

export interface TradeRecord {
  id?: number
  date: string
  ticker: string
  name: string
  action: 'buy' | 'sell' | 'adjust'
  quantity: number
  price: number
  amount: number
  reason: string
  thinking_id?: number
  created_at?: string
  updated_at?: string
}

export interface ThinkingRecord {
  id?: number
  thinking_time: string
  ticker?: string
  ticker_name?: string
  stock_names?: string
  content: string
  ai_comment?: string
  action?: string
  source: 'manual' | 'voice'
  trade_id?: number
  created_at?: string
}

export interface WeaknessItem {
  id?: number
  weakness_type: string
  title: string
  description: string
  occurrence_count: number
  avg_loss_ratio: number
  max_loss_ratio: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  enabled: boolean
  confirmed: boolean
  created_at?: string
  updated_at?: string
}

export interface WeaknessProfile {
  version: string
  last_updated: string
  items: WeaknessItem[]
  total_count: number
  critical_count: number
}

export interface RuleBase {
  rule_id: string
  category: string
  title: string
  description: string
  params: Record<string, unknown>
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  enabled: boolean
  created_at?: string
}

export interface RuleLibrary {
  version: string
  last_updated: string
  rules: RuleBase[]
}
