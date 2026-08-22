/**
 * @file 與後端 DTO 一一對應的 TypeScript 類型定義
 * 所有接口均與 Java 後端的 DTO 類保持字段名稱和類型一致，
 * 用於前端 API 調用時的類型推斷與編譯時檢查。
 *
 * @see ./generated.d.ts — 由 `npm run gen:api` 從後端 OpenAPI 自動生成，
 *       可逐步替換本文件中的手寫類型以消滅契約 drift。
 */

/** 股票日線行情數據（對應 stock_daily 表） */
export interface StockDailyDto {
  code: string;
  tradeDate: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  preclose: number | null;
  volume: number | null;
  amount: number | null;
  adjustflag: number;
  turn: number | null;
  tradeStatus: number | null;
  pctChange: number | null;
  isSt: number | null;
}

/** 儀表盤匯總指標（總記錄數、股票數量、最新交易日等） */
export interface SummaryMetricsDto {
  totalRecords: number;
  totalSymbols: number;
  earliestTradeDate: string | null;
  latestTradeDate: string | null;
  averagePctChange: number | null;
  latestTurnover: number | null;
}

/** 行業日聚合數據（對應 industry_daily 表） */
export interface IndustryDailyDto {
  tradeDate: string;
  industry: string;
  stockCount: number;
  avgPctChg: number | null;
  totalAmount: number | null;
  totalVolume: number | null;
  avgTurn: number | null;
  risingCount: number | null;
  fallingCount: number | null;
  avgClose: number | null;
  maxClose: number | null;
  minClose: number | null;
}

/** 指數日線數據（對應 index_daily 表） */
export interface IndexDailyDto {
  code: string;
  tradeDate: string;
  closePrice: number | null;
  pctChange: number | null;
}

/** 行業景氣度指標（綜合評分） */
export interface IndustryProsperityDto {
  tradeDate: string;
  industry: string;
  avgPctChg: number | null;
  totalAmount: number | null;
  avgTurn: number | null;
  risingCount: number | null;
  fallingCount: number | null;
  momentumScore: number;
  capitalScore: number;
  activityScore: number;
  breadthScore: number;
  prosperityIndex: number;
  grade: string;
}

/** 行業輪動信號數據 */
export interface RotationSignalDto {
  days: number;
  industryRotation: {
    industry_l1: Record<string, number>;
    industry_l2: Record<string, number>;
  };
  styleRotation: Record<string, number>;
  leadingIndustries: { name: string; change: number }[];
  laggingIndustries: { name: string; change: number }[];
  rotationStrength: number | null;
  summary: string;
}

/** 行業輪動預測數據 */
export interface RotationPredictionDto {
  analysisDate: string;
  predictionWindow: string;
  predictedLeaders: {
    industry: string;
    score: number;
    momentumScore: number;
    capitalScore: number;
    trendScore: number;
    reason: string;
  }[];
  predictedLaggards: {
    industry: string;
    score: number;
    momentumScore: number;
    capitalScore: number;
    trendScore: number;
    reason: string;
  }[];
  predictionReasoning: string;
  confidence: number;
}

/** 輪動預測回測結果 */
export interface RotationBacktestDto {
  lookbackDays: number;
  forwardDays: number;
  totalPredictions: number;
  hitCount: number;
  hitRate: number;
  avgLeaderReturn: number;
  avgLaggardReturn: number;
  avgExcessReturn: number;
  summary: string;
  entries: {
    predictDate: string;
    topPredicted: string;
    actualTopIndustry: string;
    predictedReturn: number;
    marketAvgReturn: number;
    excessReturn: number;
    hit: boolean;
  }[];
}

/** 行業景氣度異常預警 */
export interface ProsperityAlertDto {
  analysisDate: string;
  alerts: {
    industry: string;
    alertType: 'surge' | 'plunge' | 'grade_up' | 'grade_down';
    alertTypeName: string;
    yesterdayProsperity: number;
    todayProsperity: number;
    change: number;
    yesterdayGrade: string;
    todayGrade: string;
    severity: 'high' | 'medium' | 'low';
    message: string;
  }[];
  summary: string;
}

/** 輪動預測 AutoML 結果 */
export interface RotationAutoMlDto {
  bestLookbackDays: number;
  bestForwardDays: number;
  bestHitRate: number;
  bestExcessReturn: number;
  bestCompositeScore: number;
  summary: string;
  combinations: {
    lookbackDays: number;
    forwardDays: number;
    hitRate: number;
    avgExcessReturn: number;
    avgLeaderReturn: number;
    totalPredictions: number;
    compositeScore: number;
    evalHitRate: number;
    evalExcessReturn: number;
  }[];
}

/** 行業景氣度週期性分析 */
export interface ProsperitySeasonalityDto {
  analysisPeriod: string;
  totalDataPoints: number;
  industries: Record<string, {
    industry: string;
    monthlyAvg: Record<number, number>;
    weekdayAvg: Record<number, number>;
    bestMonth: number;
    worstMonth: number;
    bestMonthAvg: number;
    worstMonthAvg: number;
    seasonalityStrength: number;
    overallAvg: number;
  }>;
  summary: string;
}

/** 行業景氣度 Markov 狀態轉移模型 */
export interface ProsperityMarkovDto {
  analysisDate: string;
  totalTransitions: number;
  industries: Record<string, {
    industry: string;
    transitionMatrix: number[][];
    currentState: number;
    currentStateName: string;
    nextProbabilities: Record<number, number>;
    steadyState: Record<number, number>;
    transitionCount: number;
    mostLikelyNext: string;
    mostLikelyNextProb: number;
  }>;
  summary: string;
}

/** 行業景氣度多模型預測 */
export interface ProsperityForecastDto {
  analysisDate: string;
  forecastDays: number;
  industries: Record<string, {
    industry: string;
    arimaForecast: number[];
    holtWintersForecast: number[];
    linearForecast: number[];
    ensembleForecast: number[];
    currentProsperity: number;
    arimaTrend: string;
    holtWintersTrend: string;
    linearTrend: string;
    consensusTrend: string;
    forecastDates: string[];
  }>;
  summary: string;
}

/** 景氣度預測回測結果 */
export interface ProsperityForecastBacktestDto {
  forecastDays: number;
  totalPredictions: number;
  mae: number;
  directionAccuracy: number;
  gradeHitRate: number;
  avgTopReturn: number;
  avgMarketReturn: number;
  avgExcessReturn: number;
  summary: string;
  entries: {
    predictDate: string;
    targetDate: string;
    topPredicted: string;
    topActual: string;
    predictedProsperity: number;
    actualProsperity: number;
    absError: number;
    directionCorrect: boolean;
    gradeCorrect: boolean;
  }[];
  arimaMae: number;
  hwMae: number;
  linearMae: number;
  optimalWeights: string;
}

/** 行業輪動 Markov 模型 */
export interface RotationMarkovDto {
  analysisDate: string;
  totalTransitions: number;
  industries: Record<string, {
    industry: string;
    transitionMatrix: number[][];
    currentState: number;
    currentStateName: string;
    nextProbabilities: Record<number, number>;
    steadyState: Record<number, number>;
    transitionCount: number;
    mostLikelyNext: string;
    mostLikelyNextProb: number;
    leaderProbability: number;
  }>;
  summary: string;
}

/** 漲跌幅最大的熱門股票（用於波動列表展示） */
export interface HotSymbolDto {
  code: string;
  closePrice: number | null;
  pctChange: number | null;
  volume: number | null;
}

/** 股票日線查詢參數（ code + 復權類型 + 日期範圍 + 分頁） */
export interface StockDailyQueryDto {
  code: string;
  adjustflag: number;
  startDate: string | null;
  endDate: string | null;
  limit: number;
  offset?: number;
}

/** 搜索結果（分頁結構，包含 items + offset + hasMore） */
export interface SearchResultDto {
  items: StockDailyDto[];
  offset: number;
  limit: number;
  hasMore: boolean;
}

/** 股票搜索建議項（用於自動補全下拉列表） */
export interface StockSuggestionDto {
  code: string;
  closePrice: number | null;
  pctChange: number | null;
}

/** 儀表盤單個指標卡片數據（標題 + 值 + 副標題） */
export interface DashboardMetricDto {
  title: string;
  value: string;
  subtitle: string;
}

/** 技術指標序列數據（MA、BOLL、MACD、KDJ、RSI 各週期的數值數組） */
export interface IndicatorSeriesDto {
  maSeries: Record<string, (number | null)[]>;
  bollUpper: (number | null)[];
  bollMiddle: (number | null)[];
  bollLower: (number | null)[];
  macdDif: (number | null)[];
  macdDea: (number | null)[];
  macdHist: (number | null)[];
  kdjK: (number | null)[];
  kdjD: (number | null)[];
  kdjJ: (number | null)[];
  rsi: (number | null)[];
}

/** K線圖數據（含日線記錄 + 技術指標 + 是否有更多歷史數據） */
export interface CandlestickDto {
  code: string;
  records: StockDailyDto[];
  hasMore: boolean;
  indicators: IndicatorSeriesDto | null;
}

/** 儀表盤快照（聚合端點返回的全部數據，含指標、K線、熱門股、日誌等） */
export interface DashboardSnapshotDto {
  metrics: DashboardMetricDto[];
  records: StockDailyDto[];
  chart: CandlestickDto;
  hotSymbols: HotSymbolDto[];
  selectedQuery: StockDailyQueryDto;
  connected: boolean;
  statusText: string;
  logLines: string[];
}

/** 選股篩選條件（價格區間、漲跌幅、換手率、技術指標、信號排列等全部可選條件） */
export interface ScreenerCriteriaDto {
  asOfDate: string;
  adjustflag: number;
  minClose?: number | null;
  maxClose?: number | null;
  minPctChange?: number | null;
  maxPctChange?: number | null;
  minTurn?: number | null;
  maxTurn?: number | null;
  minAmplitude?: number | null;
  maxAmplitude?: number | null;
  minVolume?: number | null;
  minAmount?: number | null;
  minVolumeRatio?: number | null;
  maxVolumeRatio?: number | null;
  minReturn20?: number | null;
  maxReturn20?: number | null;
  minReturn60?: number | null;
  maxReturn60?: number | null;
  minReturn120?: number | null;
  maxReturn120?: number | null;
  minRsi14?: number | null;
  maxRsi14?: number | null;
  minKValue?: number | null;
  maxKValue?: number | null;
  minDValue?: number | null;
  maxDValue?: number | null;
  minJValue?: number | null;
  maxJValue?: number | null;
  minMacdHist?: number | null;
  maxMacdHist?: number | null;
  minBollWidth?: number | null;
  maxBollWidth?: number | null;
  minBollPercentB?: number | null;
  maxBollPercentB?: number | null;
  priceAboveMa5?: boolean | null;
  priceAboveMa20?: boolean | null;
  priceAboveMa60?: boolean | null;
  ma5AboveMa20?: boolean | null;
  ma20AboveMa60?: boolean | null;
  macdCrossSignal?: string | null;
  macdCrossWithinDays?: number | null;
  kdjCrossSignal?: string | null;
  kdjCrossWithinDays?: number | null;
  bollPosition?: string | null;
  excludeSt?: boolean | null;
  maxResults?: number | null;
  sortBy?: string | null;
  industries?: string[] | null;
}

/** 選股結果中的單隻股票（含全部技術指標數值和綜合評分） */
export interface ScreenedStockDto {
  code: string;
  tradeDate: string;
  closePrice: number;
  pctChange: number;
  amplitude: number;
  turn: number;
  volume: number;
  amount: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  ma120: number | null;
  volumeRatio: number | null;
  return20: number | null;
  return60: number | null;
  return120: number | null;
  rsi14: number | null;
  kValue: number | null;
  dValue: number | null;
  jValue: number | null;
  kdjCrossSignal: string;
  kdjGoldenCrossDaysAgo: number | null;
  kdjDeathCrossDaysAgo: number | null;
  dif: number | null;
  dea: number | null;
  macdHist: number | null;
  macdCrossSignal: string;
  macdGoldenCrossDaysAgo: number | null;
  macdDeathCrossDaysAgo: number | null;
  bollUpper: number | null;
  bollMiddle: number | null;
  bollLower: number | null;
  bollWidth: number | null;
  bollPercentB: number | null;
  bollPosition: string;
  score: number;
  isSt: boolean;
}

/** 選股結果（篩選條件 + 掃描/命中數量 + 候選股票列表 + 日誌摘要） */
export interface ScreenerResultDto {
  criteria: ScreenerCriteriaDto;
  screenDate: string | null;
  scannedSymbols: number;
  matchedSymbols: number;
  candidates: ScreenedStockDto[];
  summaryLines: string[];
}

/** 回測配置（日期範圍、調倉間隔、持倉數、初始資金、手續費、止損止盈、無風險利率、滑點） */
export interface BacktestConfigDto {
  startDate: string;
  endDate: string;
  rebalanceInterval: number;
  holdingPeriod: number;
  maxPositions: number;
  initialCapital: number;
  commissionBps: number;
  stopLossPct?: number | null;
  takeProfitPct?: number | null;
  /** 無風險年化利率（默認 0.02），用於夏普比率計算 */
  riskFreeRate?: number | null;
  /** 滑點（基點，默認 0），買入價上浮、賣出價下浮 */
  slippageBps?: number | null;
}

/** 回測請求（選股條件 + 回測配置） */
export interface BacktestRequestDto {
  criteria: ScreenerCriteriaDto;
  config: BacktestConfigDto;
}

/** 淨值曲線上的單個數據點（日期 + 淨值） */
export interface EquityPoint {
  date: string;
  value: number;
}

/** 單次調倉事件（日期 + 買入/賣出/持有股票列表） */
export interface RebalanceEvent {
  date: string;
  bought: string[];
  sold: string[];
  held: string[];
}

/** 回測統計指標（總收益、年化、基準、超額、最大回撤、夏普等） */
export interface BacktestStatistics {
  totalReturn: number;
  annualReturn: number;
  benchmarkReturn: number;
  excessReturn: number;
  maxDrawdown: number;
  sharpe: number;
  rebalanceCount: number;
  totalTrades: number;
}

/** 回測結果（配置 + 策略/基準/超額淨值曲線 + 調倉記錄 + 統計 + 日誌） */
export interface BacktestResultDto {
  config: BacktestConfigDto;
  strategyCurve: EquityPoint[];
  benchmarkCurve: EquityPoint[];
  excessCurve: EquityPoint[];
  rebalances: RebalanceEvent[];
  statistics: BacktestStatistics;
  logLines: string[];
}

/** 數據同步請求（復權類型、日期範圍、股票代碼、同步模式、指數/行業開關） */
export interface SyncRequestDto {
  /** 復權類型列表，逗號分隔（如 "1,2,3"）；為空時默認 "3" */
  adjustflags?: string;
  /** 向後兼容：單個復權類型 */
  adjustflag?: number;
  startDate?: string;
  endDate?: string;
  codes?: string;
  /** 同步模式：incremental=增量更新，range=指定日期範圍 */
  mode?: string;
  /** 是否同時同步指數數據 */
  syncIndex?: boolean;
  /** 是否同時同步行業分類數據 */
  syncIndustry?: boolean;
}

/** 同步任務狀態（運行狀態、進度、消息、已寫入條數、時間戳） */
export interface SyncStatusDto {
  state: string;
  progress: number;
  message: string;
  written: number;
  startedAt: string | null;
  finishedAt: string | null;
  error: string | null;
}

/** 數據庫連接配置（主機、端口、庫名、用戶、字符集） */
export interface DatabaseConfigDto {
  host: string;
  port: number;
  name: string;
  user: string;
  charset: string;
}

/** 數據庫配置更新請求（所有字段可選，密碼留空表示不修改） */
export interface DatabaseConfigUpdateDto {
  host?: string | null;
  port?: number | null;
  name?: string | null;
  user?: string | null;
  password?: string | null;
  charset?: string | null;
}

/** 系統健康狀態（數據庫連接、表結構校驗、問題列表） */
export interface SystemHealthDto {
  connected: boolean;
  schemaValid: boolean;
  databaseName: string;
  host: string;
  port: number;
  message: string;
  schemaIssues: string[];
}

/** 用戶偏好設置（默認復權、查詢條數、觀察列表、選股預設、指標配置） */
export interface UserPreferenceDto {
  defaultAdjustflag: string;
  defaultLimit: number;
  defaultLookbackDays: number;
  watchlist: string[];
  screenerPresets: Record<string, { name: string; description: string; criteria: Record<string, unknown> }>;
  indicatorConfig: {
    showMa: boolean;
    maPeriods: number[];
    showBoll: boolean;
    showMacd: boolean;
    showKdj: boolean;
    bollPeriod: number;
    bollStd: number;
    macdFastPeriod: number;
    macdSlowPeriod: number;
    macdSignalPeriod: number;
    kdjPeriod: number;
    kdjKSmoothing: number;
    kdjDSmoothing: number;
  };
  defaultSortBy: string;
}

/** 保存策略的請求體（名稱 + 選股條件 + 回測配置 + 回測結果） */
export interface SaveStrategyDto {
  name: string;
  criteria: ScreenerCriteriaDto;
  config: BacktestConfigDto;
  result: BacktestResultDto | null;
}

/** 已保存策略的摘要信息（列表展示用，不含完整條件和結果） */
export interface SavedStrategySummaryDto {
  id: number;
  name: string;
  createdAt: string;
  updatedAt: string;
}

/** 已保存策略的完整詳情（含選股條件、回測配置和回測結果） */
export interface SavedStrategyDetailDto {
  id: number;
  name: string;
  criteria: ScreenerCriteriaDto;
  config: BacktestConfigDto;
  result: BacktestResultDto | null;
  createdAt: string;
  updatedAt: string;
}

// ===== Agent 相關類型 =====

/** Agent LLM 模型狀態（提供商、模型名、可用性、是否免費） */
export interface AgentModelStatus {
  provider: string;
  model_name: string;
  available: boolean;
  is_free: boolean;
  last_check: string;
  error?: string;
}

/** 單個供應商的模型檢查結果 */
export interface ModelCheckResult {
  provider: string;
  model_name: string;
  available: boolean;
  is_free: boolean;
  last_check: string;
  error: string;
}

/** Agent 運行時狀態（當前迭代、最佳評分、各階段結果、市場上下文等） */
export interface AgentState {
  running: boolean;
  current_iteration: number;
  total_iterations: number;
  best_score: number;
  best_iteration: number;
  best_strategy_id: number | null;
  current_criteria: Record<string, unknown>;
  current_config: Record<string, unknown>;
  current_market_context: string;
  current_reflection: string;
  /** 行情新聞分析結果 */
  current_market_news: string;
  /** 利好行業列表 */
  current_favorable_industries: string[];
  /** 行業篩選後的股票代碼 */
  current_filtered_codes: string[];
  /** 當前執行的 AI 節點名稱 */
  current_stage: string;
  /** 當前節點狀態: idle/running/judging/passed/failed/retrying */
  current_stage_status: string;
  /** 當前迭代的各階段結果（增量更新，用於實時可視化） */
  current_stage_results: StageResult[];
  status_message: string;
  started_at: string | null;
  stopped_at: string | null;
  model_status: AgentModelStatus;
  available_providers: AvailableProvider[];
}

/** 可用 LLM 供應商 */
export interface AvailableProvider {
  provider: string;
  display_name?: string;
  model: string;
  available: boolean;
  is_free?: boolean;
}

/** 單個 AI 節點的評委結果 */
export interface StageResult {
  stage_name: string;
  output: string;
  judge_score: number;
  judge_passed: boolean;
  judge_feedback: string;
  attempts: number;
  duration_ms: number;
  error: string | null;
}

/** 單次迭代的完整記錄（選股條件、回測統計、6 個 AI 階段輸出、評委結果） */
export interface AgentIteration {
  iteration: number;
  timestamp: string;
  criteria: Record<string, unknown>;
  config: Record<string, unknown>;
  screener_summary: string;
  backtest_statistics: Record<string, number>;
  composite_score: number;
  /** 6 個 AI 階段輸出 */
  market_news: string;
  favorable_industries: string[];
  filtered_codes: string[];
  market_analysis: string;
  strategy_generation: string;
  backtest_reflection: string;
  next_prompt: string;
  next_criteria: Record<string, unknown>;
  /** 各階段評委結果 */
  stage_results: StageResult[];
  error: string | null;
}

/** Agent 歷史記錄（總數 + 迭代列表） */
export interface AgentHistory {
  total: number;
  iterations: AgentIteration[];
}

// ===== 監控類型 =====

/** 單個節點事件（運行 ID、迭代輪次、節點 ID、狀態、耗時、評委評分等） */
export interface NodeEvent {
  run_id: string;
  iteration: number;
  node_id: string;
  node_type: string;
  status: string;
  timestamp: string;
  duration_ms: number;
  attempts: number;
  judge_score: number;
  judge_passed: boolean;
  error: string | null;
  metadata: Record<string, unknown>;
}

/** 監控告警（級別、分類、節點、消息、建議、是否已解決） */
export interface MonitorAlert {
  alert_id: string;
  level: 'info' | 'warning' | 'critical';
  category: string;
  node_id: string;
  iteration: number;
  message: string;
  suggestion: string;
  timestamp: string;
  resolved: boolean;
}

/** 單個節點的統計數據（運行次數、耗時、失敗率、重試次數、評委均分） */
export interface NodeStats {
  total_runs: number;
  total_duration_ms: number;
  avg_duration_ms: number;
  max_duration_ms: number;
  failures: number;
  retries: number;
  avg_judge_score: number;
  judge_scores: number[];
}

/** 監控狀態匯總（事件數、告警數、節點統計、評分歷史） */
export interface MonitorStatus {
  run_id: string;
  total_events: number;
  total_alerts: number;
  active_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  recent_events: NodeEvent[];
  active_alert_list: MonitorAlert[];
  node_stats: Record<string, NodeStats>;
  score_history: number[];
}

/** AI 診斷分析結果（分析文本、健康狀態、建議操作列表） */
export interface MonitorAnalysis {
  analysis: string;
  health: 'idle' | 'healthy' | 'warning' | 'critical';
  suggestions: string[];
}

// ===== 時間軸可視化類型 =====

/** 時間軸中的單個節點執行記錄 */
export interface TimelineNode {
  node_id: string;
  node_type: string;
  timestamp: string;
  duration_ms: number;
  status: string;
  judge_score: number;
  judge_passed: boolean;
  attempts: number;
  error: string | null;
}

/** 單次迭代的時間軸數據 */
export interface TimelineIteration {
  iteration: number;
  nodes: TimelineNode[];
}

/** 節點定義（元數據） */
export interface NodeDefinition {
  id: string;
  label: string;
  type: string;
  order: number;
}

/** 時間軸 API 返回數據 */
export interface TimelineData {
  iterations: TimelineIteration[];
  node_definitions: NodeDefinition[];
  total_iterations: number;
  run_id: string;
}

// ===== AI 調用日誌（Agent Dashboard）=====

/** AI 調用日誌記錄 — 對應後端 ai_call_log 表 */
export interface AiCallLog {
  id: number;
  iteration: number;
  stageName: string;
  stageDisplayName: string;
  provider: string;
  modelName: string;
  inputJson: string;
  outputText: string;
  outputJson: string;
  judgeScore: number | null;
  judgePassed: boolean | null;
  judgeFeedback: string;
  attempts: number;
  durationMs: number;
  error: string | null;
  createdAt: string;
}

/** 評分趨勢數據（用於前端圖表） */
export interface ScoreTrend {
  stageTrends: StageTrendPoint[];
  iterationTrends: IterationTrendPoint[];
  stages: string[];
  maxIteration: number | null;
}

export interface StageTrendPoint {
  iteration: number;
  stageName: string;
  avgScore: number;
  maxScore: number;
  minScore: number;
}

export interface IterationTrendPoint {
  iteration: number;
  avgScore: number;
  callCount: number;
}

/** 供應商偏好設置請求 */
export interface SetStageProviderRequest {
  stage_name: string;
  provider: string;
}

/** 供應商列表響應 */
export interface ProvidersResponse {
  providers: AvailableProvider[];
  stage_preferences: Record<string, string>;
  stage_defaults: Record<string, string>;
  provider_details: Record<string, {
    display_name: string;
    model_id: string;
    is_free: boolean;
    supports_json_mode: boolean;
    tags: string[];
    description: string;
  }>;
}
