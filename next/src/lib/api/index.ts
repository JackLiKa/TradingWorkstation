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
  IndustryDailyDto,
  IndexDailyDto,
  RotationSignalDto,
  IndustryProsperityDto,
  RotationPredictionDto,
  RotationBacktestDto,
  RotationAutoMlDto,
  ProsperityAlertDto,
  ProsperitySeasonalityDto,
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
  AiCallLog,
  ScoreTrend,
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

  // ===== 行業日聚合 =====
  industryDaily: (tradeDate?: string) =>
    apiFetch<IndustryDailyDto[]>(`/stock/industry-daily${tradeDate ? `?tradeDate=${tradeDate}` : ''}`),
  industryDailyRange: (industry: string, start: string, end: string) =>
    apiFetch<IndustryDailyDto[]>(`/stock/industry-daily/range?industry=${encodeURIComponent(industry)}&start=${start}&end=${end}`),

  allIndustryDailyRange: (start: string, end: string) =>
    apiFetch<IndustryDailyDto[]>(`/stock/industry-daily/all-range?start=${start}&end=${end}`),
  industriesList: () => apiFetch<string[]>(`/stock/industries/list`),

  // ===== 指數歷史 =====
  indexHistory: (code: string, days = 30) =>
    apiFetch<IndexDailyDto[]>(`/stock/index-history?code=${encodeURIComponent(code)}&days=${days}`),

  // ===== 行業輪動信號 =====
  rotation: (days = 5) => apiFetch<RotationSignalDto>(`/stock/rotation?days=${days}`),

  // ===== 行業輪動預測 =====
  rotationPrediction: (lookbackDays = 20) =>
    apiFetch<RotationPredictionDto>(`/stock/rotation-prediction?lookbackDays=${lookbackDays}`),

  // ===== 輪動預測回測 =====
  rotationPredictionBacktest: (lookbackDays = 20, forwardDays = 5, backtestDays = 90) =>
    apiFetch<RotationBacktestDto>(
      `/stock/rotation-prediction/backtest?lookbackDays=${lookbackDays}&forwardDays=${forwardDays}&backtestDays=${backtestDays}`
    ),

  // ===== 輪動預測 AutoML 自動調參 =====
  rotationAutoMl: (backtestDays = 90) =>
    apiFetch<RotationAutoMlDto>(`/stock/rotation-prediction/automl?backtestDays=${backtestDays}`),

  // ===== 行業景氣度異常預警 =====
  prosperityAlerts: (threshold = 10.0, notify = false) =>
    apiFetch<ProsperityAlertDto>(
      `/stock/industry-prosperity/alerts?threshold=${threshold}${notify ? '&notify=true' : ''}`
    ),

  // ===== 通知服務測試 =====
  testNotification: () => apiFetch<string>(`/system/notification/test`),

  // ===== 行業景氣度週期性分析 =====
  prosperitySeasonality: (months = 12) =>
    apiFetch<ProsperitySeasonalityDto>(`/stock/industry-prosperity/seasonality?months=${months}`),

  // ===== 行業景氣度指標 =====
  industryProsperity: (tradeDate?: string) =>
    apiFetch<IndustryProsperityDto[]>(`/stock/industry-prosperity${tradeDate ? `?tradeDate=${tradeDate}` : ''}`),

  industryProsperityRange: (start: string, end: string, topN = 15) =>
    apiFetch<IndustryProsperityDto[]>(`/stock/industry-prosperity/range?start=${start}&end=${end}&topN=${topN}`),

  // ===== Chart K線圖 =====
  candlestick: (params: URLSearchParams) => apiFetch<CandlestickDto>(`/chart/candlestick?${params.toString()}`),
  olderCandlestick: (params: URLSearchParams) => apiFetch<CandlestickDto>(`/chart/candlestick/older?${params.toString()}`),

  // ===== Screener 選股器 =====
  runScreener: (criteria: ScreenerCriteriaDto) => apiPost<ScreenerResultDto>(`/screener/run`, criteria, 120000),

  // ===== Backtest 回測 =====
  runBacktest: (request: BacktestRequestDto) => apiPost<BacktestResultDto>(`/backtest/run`, request, 180000),
  runBacktestAndSave: (request: BacktestRequestDto) => apiPost<BacktestResultDto>(`/backtest/run-and-save`, request, 180000),
  saveStrategy: (dto: SaveStrategyDto) => apiPost<SavedStrategyDetailDto>(`/backtest/strategies`, dto),
  listStrategies: (source?: string) =>
    apiFetch<SavedStrategySummaryDto[]>(`/backtest/strategies${source ? `?source=${source}` : ''}`),
  getStrategy: (id: number) => apiFetch<SavedStrategyDetailDto>(`/backtest/strategies/${id}`),
  deleteStrategy: (id: number) => apiDelete<void>(`/backtest/strategies/${id}`),

  // ===== AI 調用日誌（Agent Dashboard）=====
  aiCallLogs: (page = 0, size = 20) =>
    apiFetch<{ content: AiCallLog[]; totalElements: number; totalPages: number }>(`/aicalllog?page=${page}&size=${size}`),
  aiCallLogsByStage: (stageName: string, page = 0, size = 20) =>
    apiFetch<{ content: AiCallLog[]; totalElements: number; totalPages: number }>(`/aicalllog/stage/${stageName}?page=${page}&size=${size}`),
  aiCallLogsByIteration: (iteration: number) =>
    apiFetch<AiCallLog[]>(`/aicalllog/iteration/${iteration}`),
  recentAiCallLogs: (limit = 10) => apiFetch<AiCallLog[]>(`/aicalllog/recent?limit=${limit}`),
  scoreTrend: () => apiFetch<ScoreTrend>(`/aicalllog/score-trend`),

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
