/**
 * Agent 服務 API 客戶端 — 連接到 agent 服務 (端口 8100)。
 * 與主後端 (8090) 分離，使用獨立的 fetch 包裝。
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

const AGENT_BASE = process.env.NEXT_PUBLIC_AGENT_API_BASE || 'http://localhost:8100';

async function agentFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${AGENT_BASE}/api/agent${path}`, {
    headers: { 'Content-Type': 'application/json' },
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
  const res = await fetch(`${AGENT_BASE}/api/agent${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
};
