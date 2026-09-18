import type { AppSettings, ResultDetailData, ResultsPage, Scan, Stats } from './types'
import { hostedApi } from './hostedApi'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

const localApi = {
  stats: () => request<Stats>('/api/dashboard/stats'),
  results: (params: URLSearchParams) => request<ResultsPage>(`/api/results?${params}`),
  detail: (id: number) => request<ResultDetailData>(`/api/results/${id}`),
  startScan: (mode: 'live' | 'demo') =>
    request<Scan>('/api/scans', { method: 'POST', body: JSON.stringify({ mode }) }),
  scan: (id: number) => request<Scan>(`/api/scans/${id}`),
  settings: () => request<AppSettings>('/api/settings'),
  saveResearch: (value: AppSettings['research']) =>
    request('/api/settings/research', { method: 'PUT', body: JSON.stringify(value) }),
  saveAllegro: (value: Record<string, unknown>) =>
    request('/api/settings/allegro', { method: 'PUT', body: JSON.stringify(value) }),
  testAllegro: () => request<{ oauth: string; listing_access: string }>('/api/allegro/test', { method: 'POST' }),
  oauthUrl: () => request<{ url: string }>('/api/allegro/oauth/url'),
  toggleWatchlist: (productId: number) => request<{ watchlisted: boolean }>(`/api/products/${productId}/watchlist`, { method: 'POST' }),
  logs: () => request<Array<Record<string, unknown>>>('/api/logs'),
  verification: () => request<Array<Record<string, unknown>>>('/api/verification-queue'),
  addEvidence: (productId: number, value: Record<string, unknown>) => request(`/api/products/${productId}/evidence`, { method: 'POST', body: JSON.stringify(value) }),
}

const isHosted = !['localhost', '127.0.0.1'].includes(window.location.hostname)
export const api = isHosted ? hostedApi : localApi
