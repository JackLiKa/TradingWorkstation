/**
 * Agent 服務 API 客戶端 — 通過 next rewrites 反代到 agent 服務 (端口 8100)。
 * 統一走 next 反代避免瀏覽器直連 :8100 的 CORS 問題。
 */
import type {
  AgentState,
  AgentHistory,
  AgentIteration,
  AgentModelStatus,
  ModelCheckResult,
  MonitorStatus,
  MonitorAnalysis,
  AvailableProvider,
  SetStageProviderRequest,
  ProvidersResponse,
  NodeEvent,
  TimelineData,
} from './types';

/** 行業新聞項（來自 Agent 服務的東方財富搜索） */
export interface IndustryNewsItem {
  title: string;
  source: string;
  date: string;
  url: string;
}

/** 華爾街見聞新聞項 */
export interface WallstreetcnNewsItem {
  uri: string;
  title: string;
  summary: string;
  content?: string;
  source: string;
  author?: string;
  date: string;
  url: string;
  channel: string;
  image_url?: string;
  similarity?: number;
}

// 通過 next rewrites 反代：/TradingWorkstation/agent-api/* → agent:8100/api/agent/*
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/TradingWorkstation';
const AGENT_PROXY = `${API_BASE}/agent-api`;
const AGENT_API_KEY = process.env.NEXT_PUBLIC_AGENT_API_KEY || '';

/** 構建帶 API Key 的請求頭。 */
function agentHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (AGENT_API_KEY) headers['X-API-Key'] = AGENT_API_KEY;
  return headers;
}

async function agentFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${AGENT_PROXY}${path}`, {
    headers: agentHeaders(),
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

async function agentPost<T>(path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${AGENT_PROXY}${path}`, {
    method: 'POST',
    headers: agentHeaders(),
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

export const agentApi = {
  health: () => agentFetch<{ status: string; backend_available: boolean; model: AgentModelStatus; models: ModelCheckResult[] }>(`/health`),
  start: (criteria?: Record<string, unknown>, config?: Record<string, unknown>) =>
    agentPost<{ status: string; state: AgentState }>(`/start`, { criteria, config }),
  stop: () => agentPost<{ status: string; state: AgentState }>(`/stop`),
  status: () => agentFetch<AgentState>(`/status`),
  history: (limit = 20) => agentFetch<AgentHistory>(`/history?limit=${limit}`),
  iteration: (n: number) => agentFetch<AgentIteration>(`/history/${n}`),
  checkModel: () => agentPost<AgentModelStatus & { models: ModelCheckResult[] }>(`/model/check`),
  getCriteria: () => agentFetch<{ criteria: Record<string, unknown>; config: Record<string, unknown> }>(`/criteria`),
  updateCriteria: (criteria: Record<string, unknown>) =>
    agentPost<{ status: string; criteria: Record<string, unknown> }>(`/criteria`, { criteria }),
  // ===== 回測配置管理 =====
  updateConfig: (config: Record<string, unknown>) =>
    agentPost<{ status: string; config: Record<string, unknown> }>(`/config`, { config }),
  getDataRange: () => agentFetch<{ earliestTradeDate: string | null; latestTradeDate: string | null }>(`/data-range`),
  monitor: () => agentFetch<MonitorStatus>(`/monitor`),
  monitorEvents: (limit?: number) =>
    agentFetch<{ events: NodeEvent[]; total: number }>(`/monitor/events${limit ? `?limit=${limit}` : ''}`),
  monitorTimeline: () => agentFetch<TimelineData>(`/monitor/timeline`),
  monitorAnalyze: () => agentFetch<MonitorAnalysis>(`/monitor/analyze`),
  resolveAlert: (alertId: string) =>
    agentPost<{ status: string; alert_id: string }>(`/monitor/alerts/${alertId}/resolve`),
  // ===== 供應商管理 =====
  getProviders: () => agentFetch<ProvidersResponse>(`/providers`),
  setStageProvider: (req: SetStageProviderRequest) =>
    agentPost<{ status: string; stage_preferences: Record<string, string> }>(`/providers/stage`, req),
  resetStageProviders: () =>
    agentPost<{ status: string; stage_preferences: Record<string, string> }>(`/providers/stage/reset`),
  // ===== 行業新聞搜索 =====
  searchNews: (keyword: string, pageSize = 10) =>
    agentFetch<{ keyword: string; news: IndustryNewsItem[] }>(`/news/search?keyword=${encodeURIComponent(keyword)}&page_size=${pageSize}`),
  // ===== 華爾街見聞新聞 =====
  syncWallstreetcnNews: (channel = 'a-stock', limit = 20) =>
    agentPost<{ status: string; channel: string; fetched: number; stored: number; duplicated: number; failed: number }>(
      `/news/sync?channel=${channel}&limit=${limit}`, {}
    ),
  searchWallstreetcn: (keyword: string, limit = 10) =>
    agentFetch<{ keyword: string; news: WallstreetcnNewsItem[]; source: string }>(
      `/news/wallstreetcn/search?keyword=${encodeURIComponent(keyword)}&limit=${limit}`
    ),
  getWallstreetcnLatest: (channel = 'a-stock', limit = 20) =>
    agentFetch<{ channel: string; news: WallstreetcnNewsItem[]; source: string }>(
      `/news/wallstreetcn/latest?channel=${channel}&limit=${limit}`
    ),
  vectorSearchNews: (query: string, topK = 10, channel?: string, daysBack = 7) =>
    agentFetch<{ query: string; news: WallstreetcnNewsItem[]; count: number }>(
      `/news/vector/search?query=${encodeURIComponent(query)}&top_k=${topK}${channel ? `&channel=${channel}` : ''}&days_back=${daysBack}`
    ),
  getNewsVectorStatus: () =>
    agentFetch<{ available: boolean; collection: string; ttl_days: number; max_vectors: number; init_error: string }>(
      `/news/vector/status`
    ),
  cleanupExpiredNews: () =>
    agentPost<{ deleted: number; status: string }>(`/news/cleanup`, {}),
};
