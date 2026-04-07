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
}

// ── Weakness ────────────────────────────────────────────────────────────────

export const weaknessApi = {
  get: () => api.get('/weakness/'),

  save: (profile: unknown) =>
    api.post('/weakness/', profile),

  confirmItem: (itemId: number, confirmed: boolean = true) =>
    api.put(`/weakness/${itemId}/confirm`, null, { params: { confirmed } }),
}

// ── Rules ───────────────────────────────────────────────────────────────────

export const rulesApi = {
  get: () => api.get('/rules/'),

  save: (library: unknown) =>
    api.post('/rules/', library),

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
}

// ── Market Overview ─────────────────────────────────────────────────────────

export const marketApi = {
  overview: () => api.get('/market/overview'),
  aiOverview: () => api.get('/market/ai-overview'),
}
