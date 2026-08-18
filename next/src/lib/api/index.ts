/**
 * @file 後端 API 端點聚合 — 將所有 API 調用方法掛載到 `api` 對象上，
 * 按模塊分組（dashboard、stock、chart、screener、backtest、sync、system、preference）。
 */
import { apiFetch, apiPost, apiPut, apiDelete } from './client';
import type {
  DashboardSnapshotDto,
  SummaryMetricsDto,
  StockDailyDto,
  SearchResultDto,
  StockSuggestionDto,
  HotSymbolDto,
  CandlestickDto,
  ScreenerResultDto,
  ScreenerCriteriaDto,
  BacktestResultDto,
  BacktestRequestDto,
  SaveStrategyDto,
  SavedStrategySummaryDto,
  SavedStrategyDetailDto,
  SyncStatusDto,
  SyncRequestDto,
  SystemHealthDto,
  DatabaseConfigDto,
  DatabaseConfigUpdateDto,
  UserPreferenceDto,
} from './types';

/** 後端 API 調用集合，按功能模塊分組 */
export const api = {
  // ===== Dashboard 儀表盤（聚合端點，保留向後相容） =====
  dashboard: (params: URLSearchParams) =>
    apiFetch<DashboardSnapshotDto>(`/dashboard?${params.toString()}`),

  // ===== 獨立資源端點（前端漸進式加載用） =====
  summary: () => apiFetch<SummaryMetricsDto>(`/dashboard/summary`),
  movers: (limit = 8) => apiFetch<HotSymbolDto[]>(`/stock/movers?limit=${limit}`),

  // ===== Stock 股票搜索 =====
  search: (params: URLSearchParams) => apiFetch<SearchResultDto>(`/stock/search?${params.toString()}`),
  suggest: (q: string, limit = 10) => apiFetch<StockSuggestionDto[]>(`/stock/suggest?q=${encodeURIComponent(q)}&limit=${limit}`),

  // ===== Chart K線圖 =====
  candlestick: (params: URLSearchParams) => apiFetch<CandlestickDto>(`/chart/candlestick?${params.toString()}`),
  olderCandlestick: (params: URLSearchParams) => apiFetch<CandlestickDto>(`/chart/candlestick/older?${params.toString()}`),

  // ===== Screener 選股器 =====
  runScreener: (criteria: ScreenerCriteriaDto) => apiPost<ScreenerResultDto>(`/screener/run`, criteria, 120000),

  // ===== Backtest 回測 =====
  runBacktest: (request: BacktestRequestDto) => apiPost<BacktestResultDto>(`/backtest/run`, request, 180000),
  saveStrategy: (dto: SaveStrategyDto) => apiPost<SavedStrategyDetailDto>(`/backtest/strategies`, dto),
  listStrategies: () => apiFetch<SavedStrategySummaryDto[]>(`/backtest/strategies`),
  getStrategy: (id: number) => apiFetch<SavedStrategyDetailDto>(`/backtest/strategies/${id}`),
  deleteStrategy: (id: number) => apiDelete<void>(`/backtest/strategies/${id}`),

  // ===== Sync 數據同步 =====
  runSync: (request: SyncRequestDto) => apiPost<SyncStatusDto>(`/sync/run`, request),
  syncStatus: () => apiFetch<SyncStatusDto>(`/sync/status`),
  cancelSync: () => apiPost<SyncStatusDto>(`/sync/cancel`, {}),

  // ===== System 系統管理 =====
  health: () => apiFetch<SystemHealthDto>(`/system/health`),
  databaseConfig: () => apiFetch<DatabaseConfigDto>(`/system/database`),
  updateDatabaseConfig: (update: DatabaseConfigUpdateDto) => apiPut<DatabaseConfigDto>(`/system/database`, update),

  // ===== Preference 用戶偏好 =====
  preference: () => apiFetch<UserPreferenceDto>(`/preference`),
  savePreference: (pref: UserPreferenceDto) => apiPut<UserPreferenceDto>(`/preference`, pref),
};
