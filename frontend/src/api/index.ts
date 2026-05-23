/**
 * API client for Argus-Invest backend.
 * All requests go through Vite proxy to FastAPI.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ── Portfolio ───────────────────────────────────────────────────────────────

export const portfolioApi = {
  list: (asOfDate?: string) =>
    api.get('/portfolio/', { params: asOfDate ? { as_of_date: asOfDate } : {} }),

  upload: (records: unknown[]) =>
    api.post('/portfolio/', records),

  snapshot: (asOfDate?: string) =>
    api.get('/portfolio/snapshot', { params: asOfDate ? { as_of_date: asOfDate } : {} }),
}

// ── Trades ──────────────────────────────────────────────────────────────────

export const tradesApi = {
  list: (params?: { start_date?: string; end_date?: string; ticker?: string }) =>
    api.get('/trades/', { params }),

  add: (trade: unknown) =>
    api.post('/trades/', trade),

  update: (tradeId: number, trade: unknown) =>
    api.put(`/trades/${tradeId}`, trade),

  delete: (tradeId: number) =>
    api.delete(`/trades/${tradeId}`),

  analyze: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/trades/analyze', { params }),
}

// ── Weakness ────────────────────────────────────────────────────────────────

export const weaknessApi = {
  get: () => api.get('/weakness/'),

  save: (profile: unknown) =>
    api.post('/weakness/', profile),

  confirmItem: (itemId: string, confirmed: boolean = true) =>
    api.put(`/weakness/${itemId}/confirm`, null, { params: { confirmed } }),
}

// ── Rules ───────────────────────────────────────────────────────────────────

export const rulesApi = {
  get: () => api.get('/rules/'),

  save: (library: unknown) =>
    api.post('/rules/', library),

  update: (ruleId: string, patch: unknown) =>
    api.put(`/rules/${ruleId}`, patch),

  reset: () => api.post('/rules/reset'),
}

// ── Thinking ─────────────────────────────────────────────────────────────────

export const planApi = {
  list: (ticker?: string) =>
    api.get('/portfolio/plans/', { params: ticker ? { ticker } : {} }),
  latest: () =>
    api.get('/portfolio/plans/latest'),
  add: (plan: unknown) =>
    api.post('/portfolio/plans/', plan),
  delete: (planId: number) =>
    api.delete(`/portfolio/plans/${planId}`),
}

export const thinkingApi = {
  list: (params?: { start_date?: string; end_date?: string; ticker?: string }) =>
    api.get('/thinking/', { params }),

  add: (record: unknown) =>
    api.post('/thinking/', record),

  update: (thinkingId: number, record: unknown) =>
    api.put(`/thinking/${thinkingId}`, record),

  delete: (thinkingId: number) =>
    api.delete(`/thinking/${thinkingId}`),
}

// ── Persona ─────────────────────────────────────────────────────────────────

export const personaApi = {
  list: () => api.get('/persona/'),
  get: (skillId: string) => api.get(`/persona/${skillId}`),
  chat: (payload: { skill_id: string; messages: Array<{ role: string; content: string }> }) =>
    api.post('/persona/chat', payload),
}

// ── Health ───────────────────────────────────────────────────────────────────

export const healthApi = {
  check: () => api.get('/health'),
}

// ── Monitor ─────────────────────────────────────────────────────────────────

export const monitorApi = {
  status: () => api.get('/monitor/status'),
  rules: () => api.get('/monitor/rules'),
  check: () => api.post('/monitor/check'),
  events: () => api.get('/monitor/events'),
  lastResult: () => api.get('/monitor/last-result'),
}

// ── Market Overview ─────────────────────────────────────────────────────────

export const marketApi = {
  overview: () => api.get('/market/overview'),
  overviewCache: () => api.get('/market/overview/cache'),
  aiOverview: () => api.get('/market/ai-overview'),
  aiOverviewCache: () => api.get('/market/ai-overview/cache'),
}

// ── Watchlist ─────────────────────────────────────────────────────────────────

export const watchlistApi = {
  list: () => api.get('/watchlist/'),
  add: (record: unknown) => api.post('/watchlist/', record),
  update: (id: number, patch: unknown) => api.put(`/watchlist/${id}`, patch),
  delete: (id: number) => api.delete(`/watchlist/${id}`),
  checkSignals: () => api.post('/watchlist/check-signals'),
  getLastCheck: () => api.get('/watchlist/check-signals/last'),
}

// ── Quant ────────────────────────────────────────────────────────────────────

export const quantAPI = {
  getStrategies: () => api.get('/quant/strategies'),

  runBacktest: (params: Record<string, unknown>) =>
    api.post('/quant/backtest', params),

  getBacktest: (id: number) => api.get(`/quant/backtest/${id}`),

  getBacktestTrades: (id: number) => api.get(`/quant/backtest/${id}/trades`),

  deleteBacktest: (id: number) => api.delete(`/quant/backtest/${id}`),

  runOptimize: (params: Record<string, unknown>) =>
    api.post('/quant/optimize', params),

  optimizePortfolio: (params: Record<string, unknown>) =>
    api.post('/quant/portfolio/optimize', params),

  getSignals: (params?: { ticker?: string; strategy_name?: string }) =>
    api.get('/quant/signals', { params }),

  getFactors: (ticker: string, factorNames?: string[]) =>
    api.get('/quant/factors', { params: { ticker, factor_names: factorNames?.join(',') } }),
}

// ── KV / 大V观点 ─────────────────────────────────────────────────────────────

export const kvApi = {
  accounts: () => api.get('/kv/accounts'),
  articles: (account: string, limit = 20) =>
    api.get(`/kv/${account}/articles`, { params: { limit } }),
  refresh: (account: string, maxNew = 5) =>
    api.post(`/kv/${account}/refresh`, null, { params: { max_new: maxNew } }),
}

// ── Messages ───────────────────────────────────────────────────────────────────

export const messageApi = {
  list: (limit = 100) => api.get('/messages/', { params: { limit } }),
  unreadCount: () => api.get('/messages/unread-count'),
  markRead: (id: number) => api.put(`/messages/${id}/read`),
  markAllRead: () => api.put('/messages/read-all'),
}
