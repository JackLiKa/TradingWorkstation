/**
 * 自動生成 — 請勿手工編輯。
 * 由 `npm run gen:api:smart`（scripts/generate-api-types.ts）
 * 從後端 OpenAPI spec 生成。
 * 來源：http://localhost:8090/TradingWorkstation/v3/api-docs
 * 生成時間：2026-08-22T14:56:55.671Z
 */

export type paths = {
    readonly "/api/system/database": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 当前数据库配置（不含密码） */
        readonly get: operations["currentConfig"];
        /** 更新数据库配置（写入 .env，重启后生效） */
        readonly put: operations["updateConfig"];
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/preference": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 读取用户偏好 */
        readonly get: operations["load"];
        /** 保存用户偏好 */
        readonly put: operations["save"];
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/sync/run": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 启动同步任务 */
        readonly post: operations["run"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/sync/cancel": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 取消同步任务 */
        readonly post: operations["cancel"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/index-history/batch": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 批量指數最近N日歷史 */
        readonly post: operations["indexHistoryBatch"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/screener/run": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 运行选股 */
        readonly post: operations["run_1"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/indicator/compute": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 计算指标全序列（图表叠加用） */
        readonly post: operations["compute"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/backtest/strategies": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 策略列表 */
        readonly get: operations["listStrategies"];
        readonly put?: never;
        /** 保存策略 */
        readonly post: operations["saveStrategy"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/backtest/run": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 运行回测 */
        readonly post: operations["run_2"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/backtest/run-and-save": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 运行回测并自动保存 */
        readonly post: operations["runAndSave"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog/log": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** 記錄 AI 調用日誌 */
        readonly post: operations["log"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/system/notification/test": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 測試通知服務（郵件/Webhook 配置驗證） */
        readonly get: operations["testNotification"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/system/health": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 数据库健康检查（连接 + 表结构校验） */
        readonly get: operations["health"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/sync/status": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 查询同步状态 */
        readonly get: operations["status"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/summary": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /**
         * 汇总指标（已弃用，请用 /api/dashboard/summary）
         * @deprecated
         */
        readonly get: operations["summary"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/suggest": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 搜索建議（自動補全） */
        readonly get: operations["suggest"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/sector-performance": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 多日板塊表現（10日行情分析） */
        readonly get: operations["sectorPerformance"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/search": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 日线表格查询（分页） */
        readonly get: operations["search"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/rotation": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 輪動信號分析（行業與風格輪動） */
        readonly get: operations["rotationSignals"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/rotation-prediction": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業輪動預測（歷史規律預測下一輪領漲） */
        readonly get: operations["rotationPrediction"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/rotation-prediction/backtest": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 輪動預測回測（歷史預測準確率驗證） */
        readonly get: operations["rotationPredictionBacktest"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/rotation-prediction/automl": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 輪動預測 AutoML 自動調參 */
        readonly get: operations["rotationPredictionAutoMl"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/rotation-markov": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業輪動 Markov 模型（領漲行業轉換概率） */
        readonly get: operations["rotationMarkov"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/movers": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 最新波动 */
        readonly get: operations["movers"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/market-breadth": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 市場廣度分析（多維指數） */
        readonly get: operations["marketBreadth"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度指標（綜合評分） */
        readonly get: operations["industryProsperity"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/seasonality": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度週期性分析（季節性模式） */
        readonly get: operations["prosperitySeasonality"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/range": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度歷史趨勢（多日對比） */
        readonly get: operations["industryProsperityRange"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/markov": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度 Markov 狀態轉移模型 */
        readonly get: operations["prosperityMarkov"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/forecast": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度多模型預測（ARIMA + Holt-Winters + 線性回歸） */
        readonly get: operations["prosperityForecast"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/forecast/backtest": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 景氣度預測回測（歷史預測準確率驗證） */
        readonly get: operations["prosperityForecastBacktest"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-prosperity/alerts": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業景氣度異常預警（突變與等級躍遷） */
        readonly get: operations["prosperityAlerts"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-daily": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業日聚合數據 */
        readonly get: operations["industryDaily"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-daily/range": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 行業日聚合區間數據 */
        readonly get: operations["industryDailyRange"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industry-daily/all-range": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 全部行業日聚合區間數據（相關性矩陣用） */
        readonly get: operations["allIndustryDailyRange"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industries": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 查詢所有行業分類 */
        readonly get: operations["industries"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/industries/list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 查詢所有不同行業列表 */
        readonly get: operations["industryList"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/index-list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 指數元數據列表（10 大類別） */
        readonly get: operations["indexList"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/stock/index-history": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 指數最近N日歷史（市場形態識別） */
        readonly get: operations["indexHistory"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/dashboard": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 加载总览（指标+表格+K线+波动+日志） */
        readonly get: operations["dashboard"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/dashboard/summary": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 汇总指标（缓存） */
        readonly get: operations["summary_1"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/chart/candlestick": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** K线初始批次（含指标序列） */
        readonly get: operations["candlestick"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/chart/candlestick/older": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 更早历史批次 */
        readonly get: operations["older"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/backtest/strategies/{id}": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 策略详情 */
        readonly get: operations["getStrategy"];
        readonly put?: never;
        readonly post?: never;
        /** 删除策略 */
        readonly delete: operations["deleteStrategy"];
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/backtest/recent": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 最近回测记录 */
        readonly get: operations["listRecentRuns"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 分頁查詢 AI 調用日誌 */
        readonly get: operations["findAll"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog/stage/{stageName}": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 按階段查詢 AI 調用日誌 */
        readonly get: operations["findByStage"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog/score-trend": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 評分趨勢數據 */
        readonly get: operations["scoreTrend"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog/recent": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 查詢最近日誌 */
        readonly get: operations["findRecent"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/aicalllog/iteration/{iteration}": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** 查詢某次迭代的調用鏈 */
        readonly get: operations["findByIteration"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
};
export type webhooks = Record<string, never>;
export type components = {
    schemas: {
        readonly DatabaseConfigUpdateDto: {
            readonly host?: string;
            /** Format: int32 */
            readonly port?: number;
            readonly name?: string;
            readonly user?: string;
            readonly password?: string;
            readonly charset?: string;
        };
        readonly ApiResponseDatabaseConfigDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["DatabaseConfigDto"];
        };
        readonly DatabaseConfigDto: {
            readonly host?: string;
            /** Format: int32 */
            readonly port?: number;
            readonly name?: string;
            readonly user?: string;
            readonly charset?: string;
        };
        readonly IndicatorConfigPreferenceDto: {
            readonly showMa?: boolean;
            readonly maPeriods?: readonly number[];
            readonly showBoll?: boolean;
            readonly showMacd?: boolean;
            readonly showKdj?: boolean;
            /** Format: int32 */
            readonly bollPeriod?: number;
            /** Format: double */
            readonly bollStd?: number;
            /** Format: int32 */
            readonly macdFastPeriod?: number;
            /** Format: int32 */
            readonly macdSlowPeriod?: number;
            /** Format: int32 */
            readonly macdSignalPeriod?: number;
            /** Format: int32 */
            readonly kdjPeriod?: number;
            /** Format: int32 */
            readonly kdjKSmoothing?: number;
            /** Format: int32 */
            readonly kdjDSmoothing?: number;
        };
        readonly ScreenerPresetDto: {
            readonly name?: string;
            readonly description?: string;
            readonly criteria?: {
                readonly [key: string]: Record<string, never>;
            };
        };
        readonly UserPreferenceDto: {
            readonly defaultAdjustflag?: string;
            /** Format: int32 */
            readonly defaultLimit?: number;
            /** Format: int32 */
            readonly defaultLookbackDays?: number;
            readonly watchlist?: readonly string[];
            readonly screenerPresets?: {
                readonly [key: string]: components["schemas"]["ScreenerPresetDto"];
            };
            readonly indicatorConfig?: components["schemas"]["IndicatorConfigPreferenceDto"];
            readonly defaultSortBy?: string;
        };
        readonly ApiResponseUserPreferenceDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["UserPreferenceDto"];
        };
        readonly SyncRequestDto: {
            readonly adjustflags?: string;
            /** Format: date */
            readonly startDate?: string;
            /** Format: date */
            readonly endDate?: string;
            readonly codes?: string;
            readonly mode?: string;
            readonly syncIndex?: boolean;
            readonly syncIndustry?: boolean;
        };
        readonly ApiResponseSyncStatusDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["SyncStatusDto"];
        };
        readonly SyncStatusDto: {
            readonly state?: string;
            /** Format: int32 */
            readonly progress?: number;
            readonly message?: string;
            /** Format: int32 */
            readonly written?: number;
            readonly startedAt?: string;
            readonly finishedAt?: string;
            readonly error?: string;
        };
        readonly IndexHistoryBatchRequestDto: {
            readonly codes?: readonly string[];
            /** Format: int32 */
            readonly days?: number;
        };
        readonly ApiResponseMapStringListIndexDailyDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: {
                readonly [key: string]: readonly components["schemas"]["IndexDailyDto"][];
            };
        };
        readonly IndexDailyDto: {
            readonly code?: string;
            /** Format: date */
            readonly tradeDate?: string;
            /** Format: double */
            readonly closePrice?: number;
            /** Format: double */
            readonly pctChange?: number;
        };
        readonly ScreenerCriteriaDto: {
            /** Format: date */
            readonly asOfDate?: string;
            /** Format: int32 */
            readonly adjustflag?: number;
            /** Format: double */
            readonly minClose?: number;
            /** Format: double */
            readonly maxClose?: number;
            /** Format: double */
            readonly minPctChange?: number;
            /** Format: double */
            readonly maxPctChange?: number;
            /** Format: double */
            readonly minTurn?: number;
            /** Format: double */
            readonly maxTurn?: number;
            /** Format: double */
            readonly minAmplitude?: number;
            /** Format: double */
            readonly maxAmplitude?: number;
            /** Format: int64 */
            readonly minVolume?: number;
            /** Format: double */
            readonly minAmount?: number;
            /** Format: double */
            readonly minVolumeRatio?: number;
            /** Format: double */
            readonly maxVolumeRatio?: number;
            /** Format: double */
            readonly minReturn20?: number;
            /** Format: double */
            readonly maxReturn20?: number;
            /** Format: double */
            readonly minReturn60?: number;
            /** Format: double */
            readonly maxReturn60?: number;
            /** Format: double */
            readonly minReturn120?: number;
            /** Format: double */
            readonly maxReturn120?: number;
            /** Format: double */
            readonly minRsi14?: number;
            /** Format: double */
            readonly maxRsi14?: number;
            /** Format: double */
            readonly minKValue?: number;
            /** Format: double */
            readonly maxKValue?: number;
            /** Format: double */
            readonly minDValue?: number;
            /** Format: double */
            readonly maxDValue?: number;
            /** Format: double */
            readonly minJValue?: number;
            /** Format: double */
            readonly maxJValue?: number;
            /** Format: double */
            readonly minMacdHist?: number;
            /** Format: double */
            readonly maxMacdHist?: number;
            /** Format: double */
            readonly minBollWidth?: number;
            /** Format: double */
            readonly maxBollWidth?: number;
            /** Format: double */
            readonly minBollPercentB?: number;
            /** Format: double */
            readonly maxBollPercentB?: number;
            readonly priceAboveMa5?: boolean;
            readonly priceAboveMa20?: boolean;
            readonly priceAboveMa60?: boolean;
            readonly ma5AboveMa20?: boolean;
            readonly ma20AboveMa60?: boolean;
            readonly macdCrossSignal?: string;
            /** Format: int32 */
            readonly macdCrossWithinDays?: number;
            readonly kdjCrossSignal?: string;
            /** Format: int32 */
            readonly kdjCrossWithinDays?: number;
            readonly bollPosition?: string;
            readonly excludeSt?: boolean;
            /** Format: int32 */
            readonly maxResults?: number;
            readonly sortBy?: string;
            readonly industries?: readonly string[];
        };
        readonly ApiResponseScreenerResultDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ScreenerResultDto"];
        };
        readonly ScreenedStockDto: {
            readonly code?: string;
            /** Format: date */
            readonly tradeDate?: string;
            /** Format: double */
            readonly closePrice?: number;
            /** Format: double */
            readonly pctChange?: number;
            /** Format: double */
            readonly amplitude?: number;
            /** Format: double */
            readonly turn?: number;
            /** Format: int64 */
            readonly volume?: number;
            /** Format: double */
            readonly amount?: number;
            /** Format: double */
            readonly ma5?: number;
            /** Format: double */
            readonly ma10?: number;
            /** Format: double */
            readonly ma20?: number;
            /** Format: double */
            readonly ma60?: number;
            /** Format: double */
            readonly ma120?: number;
            /** Format: double */
            readonly volumeRatio?: number;
            /** Format: double */
            readonly return20?: number;
            /** Format: double */
            readonly return60?: number;
            /** Format: double */
            readonly return120?: number;
            /** Format: double */
            readonly rsi14?: number;
            /** Format: double */
            readonly kValue?: number;
            /** Format: double */
            readonly dValue?: number;
            /** Format: double */
            readonly jValue?: number;
            readonly kdjCrossSignal?: string;
            /** Format: int32 */
            readonly kdjGoldenCrossDaysAgo?: number;
            /** Format: int32 */
            readonly kdjDeathCrossDaysAgo?: number;
            /** Format: double */
            readonly dif?: number;
            /** Format: double */
            readonly dea?: number;
            /** Format: double */
            readonly macdHist?: number;
            readonly macdCrossSignal?: string;
            /** Format: int32 */
            readonly macdGoldenCrossDaysAgo?: number;
            /** Format: int32 */
            readonly macdDeathCrossDaysAgo?: number;
            /** Format: double */
            readonly bollUpper?: number;
            /** Format: double */
            readonly bollMiddle?: number;
            /** Format: double */
            readonly bollLower?: number;
            /** Format: double */
            readonly bollWidth?: number;
            /** Format: double */
            readonly bollPercentB?: number;
            readonly bollPosition?: string;
            /** Format: double */
            readonly score?: number;
            readonly isSt?: boolean;
        };
        readonly ScreenerResultDto: {
            readonly criteria?: components["schemas"]["ScreenerCriteriaDto"];
            /** Format: date */
            readonly screenDate?: string;
            /** Format: int32 */
            readonly scannedSymbols?: number;
            /** Format: int32 */
            readonly matchedSymbols?: number;
            readonly candidates?: readonly components["schemas"]["ScreenedStockDto"][];
            readonly summaryLines?: readonly string[];
        };
        readonly IndicatorComputeRequest: {
            readonly records?: readonly components["schemas"]["StockDaily"][];
            readonly config?: components["schemas"]["IndicatorConfigDto"];
        };
        readonly IndicatorConfigDto: {
            readonly showMa?: boolean;
            readonly maPeriods?: readonly number[];
            readonly showBoll?: boolean;
            readonly showMacd?: boolean;
            readonly showKdj?: boolean;
            /** Format: int32 */
            readonly bollPeriod?: number;
            /** Format: double */
            readonly bollStd?: number;
            /** Format: int32 */
            readonly macdFastPeriod?: number;
            /** Format: int32 */
            readonly macdSlowPeriod?: number;
            /** Format: int32 */
            readonly macdSignalPeriod?: number;
            /** Format: int32 */
            readonly kdjPeriod?: number;
            /** Format: int32 */
            readonly kdjKSmoothing?: number;
            /** Format: int32 */
            readonly kdjDSmoothing?: number;
        };
        readonly StockDaily: {
            readonly code?: string;
            /** Format: date */
            readonly tradeDate?: string;
            /** Format: double */
            readonly openPrice?: number;
            /** Format: double */
            readonly highPrice?: number;
            /** Format: double */
            readonly lowPrice?: number;
            /** Format: double */
            readonly closePrice?: number;
            /** Format: double */
            readonly preclosePrice?: number;
            /** Format: int64 */
            readonly volume?: number;
            /** Format: double */
            readonly amount?: number;
            /** Format: int32 */
            readonly adjustflag?: number;
            /** Format: double */
            readonly turn?: number;
            /** Format: int32 */
            readonly tradeStatus?: number;
            /** Format: double */
            readonly pctChange?: number;
            /** Format: int32 */
            readonly isSt?: number;
            readonly stStock?: boolean;
        };
        readonly ApiResponseIndicatorSeriesDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["IndicatorSeriesDto"];
        };
        readonly IndicatorSeriesDto: {
            readonly maSeries?: {
                readonly [key: string]: readonly number[];
            };
            readonly bollUpper?: readonly number[];
            readonly bollMiddle?: readonly number[];
            readonly bollLower?: readonly number[];
            readonly macdDif?: readonly number[];
            readonly macdDea?: readonly number[];
            readonly macdHist?: readonly number[];
            readonly kdjK?: readonly number[];
            readonly kdjD?: readonly number[];
            readonly kdjJ?: readonly number[];
            readonly rsi?: readonly number[];
        };
        readonly BacktestConfigDto: {
            /** Format: date */
            readonly startDate?: string;
            /** Format: date */
            readonly endDate?: string;
            /** Format: int32 */
            readonly rebalanceInterval?: number;
            /** Format: int32 */
            readonly holdingPeriod?: number;
            /** Format: int32 */
            readonly maxPositions?: number;
            /** Format: double */
            readonly initialCapital?: number;
            /** Format: double */
            readonly commissionBps?: number;
            /** Format: double */
            readonly stopLossPct?: number;
            /** Format: double */
            readonly takeProfitPct?: number;
            /** Format: double */
            readonly riskFreeRate?: number;
            /** Format: int32 */
            readonly slippageBps?: number;
        };
        readonly BacktestResultDto: {
            readonly config?: components["schemas"]["BacktestConfigDto"];
            readonly strategyCurve?: readonly components["schemas"]["EquityPoint"][];
            readonly benchmarkCurve?: readonly components["schemas"]["EquityPoint"][];
            readonly excessCurve?: readonly components["schemas"]["EquityPoint"][];
            readonly rebalances?: readonly components["schemas"]["RebalanceEvent"][];
            readonly statistics?: components["schemas"]["BacktestStatistics"];
            readonly logLines?: readonly string[];
        };
        readonly BacktestStatistics: {
            /** Format: double */
            readonly totalReturn?: number;
            /** Format: double */
            readonly annualReturn?: number;
            /** Format: double */
            readonly benchmarkReturn?: number;
            /** Format: double */
            readonly excessReturn?: number;
            /** Format: double */
            readonly maxDrawdown?: number;
            /** Format: double */
            readonly sharpe?: number;
            /** Format: int32 */
            readonly rebalanceCount?: number;
            /** Format: int32 */
            readonly totalTrades?: number;
        };
        readonly EquityPoint: {
            /** Format: date */
            readonly date?: string;
            /** Format: double */
            readonly value?: number;
        };
        readonly RebalanceEvent: {
            /** Format: date */
            readonly date?: string;
            readonly bought?: readonly string[];
            readonly sold?: readonly string[];
            readonly held?: readonly string[];
        };
        readonly SaveStrategyDto: {
            readonly name?: string;
            readonly criteria?: components["schemas"]["ScreenerCriteriaDto"];
            readonly config?: components["schemas"]["BacktestConfigDto"];
            readonly result?: components["schemas"]["BacktestResultDto"];
            readonly source?: string;
        };
        readonly ApiResponseSavedStrategyDetailDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["SavedStrategyDetailDto"];
        };
        readonly SavedStrategyDetailDto: {
            /** Format: int64 */
            readonly id?: number;
            readonly name?: string;
            readonly criteria?: components["schemas"]["ScreenerCriteriaDto"];
            readonly config?: components["schemas"]["BacktestConfigDto"];
            readonly result?: components["schemas"]["BacktestResultDto"];
            /** Format: date-time */
            readonly createdAt?: string;
            /** Format: date-time */
            readonly updatedAt?: string;
        };
        readonly BacktestRequestDto: {
            readonly criteria?: components["schemas"]["ScreenerCriteriaDto"];
            readonly config?: components["schemas"]["BacktestConfigDto"];
        };
        readonly ApiResponseBacktestResultDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["BacktestResultDto"];
        };
        readonly AiCallLogRequest: {
            /** Format: int32 */
            readonly iteration?: number;
            readonly stageName: string;
            readonly stageDisplayName?: string;
            readonly provider: string;
            readonly modelName?: string;
            readonly inputJson?: string;
            readonly outputText?: string;
            readonly outputJson?: string;
            /** Format: double */
            readonly judgeScore?: number;
            readonly judgePassed?: boolean;
            readonly judgeFeedback?: string;
            /** Format: int32 */
            readonly attempts?: number;
            /** Format: int32 */
            readonly durationMs?: number;
            readonly error?: string;
        };
        readonly AiCallLogDto: {
            /** Format: int64 */
            readonly id?: number;
            /** Format: int32 */
            readonly iteration?: number;
            readonly stageName?: string;
            readonly stageDisplayName?: string;
            readonly provider?: string;
            readonly modelName?: string;
            readonly inputJson?: string;
            readonly outputText?: string;
            readonly outputJson?: string;
            /** Format: double */
            readonly judgeScore?: number;
            readonly judgePassed?: boolean;
            readonly judgeFeedback?: string;
            /** Format: int32 */
            readonly attempts?: number;
            /** Format: int32 */
            readonly durationMs?: number;
            readonly error?: string;
            /** Format: date-time */
            readonly createdAt?: string;
        };
        readonly ApiResponseAiCallLogDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["AiCallLogDto"];
        };
        readonly ApiResponseString: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: string;
        };
        readonly ApiResponseSystemHealthDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["SystemHealthDto"];
        };
        readonly SystemHealthDto: {
            readonly connected?: boolean;
            readonly schemaValid?: boolean;
            readonly databaseName?: string;
            readonly host?: string;
            /** Format: int32 */
            readonly port?: number;
            readonly message?: string;
            readonly schemaIssues?: readonly string[];
        };
        readonly ApiResponseSummaryMetricsDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["SummaryMetricsDto"];
        };
        readonly SummaryMetricsDto: {
            /** Format: int64 */
            readonly totalRecords?: number;
            /** Format: int64 */
            readonly totalSymbols?: number;
            /** Format: date */
            readonly earliestTradeDate?: string;
            /** Format: date */
            readonly latestTradeDate?: string;
            /** Format: double */
            readonly averagePctChange?: number;
            /** Format: double */
            readonly latestTurnover?: number;
        };
        readonly ApiResponseListStockSuggestionDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["StockSuggestionDto"][];
        };
        readonly StockSuggestionDto: {
            readonly code?: string;
            /** Format: double */
            readonly closePrice?: number;
            /** Format: double */
            readonly pctChange?: number;
        };
        readonly ApiResponseListSectorPerformanceDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["SectorPerformanceDto"][];
        };
        readonly SectorPerformanceDto: {
            /** Format: date */
            readonly date?: string;
            readonly industry?: string;
            /** Format: double */
            readonly avgPctChange?: number;
            readonly topCode?: string;
            readonly topCodeName?: string;
            /** Format: double */
            readonly topPctChange?: number;
        };
        readonly ApiResponseSearchResultDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["SearchResultDto"];
        };
        readonly SearchResultDto: {
            readonly items?: readonly components["schemas"]["StockDailyDto"][];
            /** Format: int32 */
            readonly offset?: number;
            /** Format: int32 */
            readonly limit?: number;
            readonly hasMore?: boolean;
        };
        readonly StockDailyDto: {
            readonly code?: string;
            /** Format: date */
            readonly tradeDate?: string;
            /** Format: double */
            readonly open?: number;
            /** Format: double */
            readonly high?: number;
            /** Format: double */
            readonly low?: number;
            /** Format: double */
            readonly close?: number;
            /** Format: double */
            readonly preclose?: number;
            /** Format: int64 */
            readonly volume?: number;
            /** Format: double */
            readonly amount?: number;
            /** Format: int32 */
            readonly adjustflag?: number;
            /** Format: double */
            readonly turn?: number;
            /** Format: int32 */
            readonly tradeStatus?: number;
            /** Format: double */
            readonly pctChange?: number;
            /** Format: int32 */
            readonly isSt?: number;
        };
        readonly ApiResponseRotationSignalDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["RotationSignalDto"];
        };
        readonly RankEntryDto: {
            readonly name?: string;
            /** Format: double */
            readonly change?: number;
        };
        readonly RotationSignalDto: {
            /** Format: int32 */
            readonly days?: number;
            readonly industryRotation?: {
                readonly [key: string]: {
                    readonly [key: string]: number;
                };
            };
            readonly styleRotation?: {
                readonly [key: string]: number;
            };
            readonly leadingIndustries?: readonly components["schemas"]["RankEntryDto"][];
            readonly laggingIndustries?: readonly components["schemas"]["RankEntryDto"][];
            /** Format: double */
            readonly rotationStrength?: number;
            readonly summary?: string;
        };
        readonly ApiResponseRotationPredictionDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["RotationPredictionDto"];
        };
        readonly PredictedIndustry: {
            readonly industry?: string;
            /** Format: double */
            readonly score?: number;
            /** Format: double */
            readonly momentumScore?: number;
            /** Format: double */
            readonly capitalScore?: number;
            /** Format: double */
            readonly trendScore?: number;
            readonly reason?: string;
        };
        readonly RotationPredictionDto: {
            readonly analysisDate?: string;
            readonly predictionWindow?: string;
            readonly predictedLeaders?: readonly components["schemas"]["PredictedIndustry"][];
            readonly predictedLaggards?: readonly components["schemas"]["PredictedIndustry"][];
            readonly predictionReasoning?: string;
            /** Format: double */
            readonly confidence?: number;
        };
        readonly ApiResponseRotationBacktestDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["RotationBacktestDto"];
        };
        readonly BacktestEntry: {
            readonly predictDate?: string;
            readonly topPredicted?: string;
            readonly actualTopIndustry?: string;
            /** Format: double */
            readonly predictedReturn?: number;
            /** Format: double */
            readonly marketAvgReturn?: number;
            /** Format: double */
            readonly excessReturn?: number;
            readonly hit?: boolean;
        };
        readonly RotationBacktestDto: {
            /** Format: int32 */
            readonly lookbackDays?: number;
            /** Format: int32 */
            readonly forwardDays?: number;
            /** Format: int32 */
            readonly totalPredictions?: number;
            /** Format: int32 */
            readonly hitCount?: number;
            /** Format: double */
            readonly hitRate?: number;
            /** Format: double */
            readonly avgLeaderReturn?: number;
            /** Format: double */
            readonly avgLaggardReturn?: number;
            /** Format: double */
            readonly avgExcessReturn?: number;
            readonly summary?: string;
            readonly entries?: readonly components["schemas"]["BacktestEntry"][];
        };
        readonly ApiResponseRotationAutoMlDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["RotationAutoMlDto"];
        };
        readonly ParamCombination: {
            /** Format: int32 */
            readonly lookbackDays?: number;
            /** Format: int32 */
            readonly forwardDays?: number;
            /** Format: double */
            readonly hitRate?: number;
            /** Format: double */
            readonly avgExcessReturn?: number;
            /** Format: double */
            readonly avgLeaderReturn?: number;
            /** Format: int32 */
            readonly totalPredictions?: number;
            /** Format: double */
            readonly compositeScore?: number;
            /** Format: double */
            readonly evalHitRate?: number;
            /** Format: double */
            readonly evalExcessReturn?: number;
        };
        readonly RotationAutoMlDto: {
            /** Format: int32 */
            readonly bestLookbackDays?: number;
            /** Format: int32 */
            readonly bestForwardDays?: number;
            /** Format: double */
            readonly bestHitRate?: number;
            /** Format: double */
            readonly bestExcessReturn?: number;
            /** Format: double */
            readonly bestCompositeScore?: number;
            readonly summary?: string;
            readonly combinations?: readonly components["schemas"]["ParamCombination"][];
        };
        readonly ApiResponseRotationMarkovDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["RotationMarkovDto"];
        };
        readonly IndustryRotationMarkov: {
            readonly industry?: string;
            readonly transitionMatrix?: readonly (readonly number[])[];
            /** Format: int32 */
            readonly currentState?: number;
            readonly currentStateName?: string;
            readonly nextProbabilities?: {
                readonly [key: string]: number;
            };
            readonly steadyState?: {
                readonly [key: string]: number;
            };
            /** Format: int32 */
            readonly transitionCount?: number;
            readonly mostLikelyNext?: string;
            /** Format: double */
            readonly mostLikelyNextProb?: number;
            /** Format: double */
            readonly leaderProbability?: number;
        };
        readonly RotationMarkovDto: {
            readonly analysisDate?: string;
            /** Format: int32 */
            readonly totalTransitions?: number;
            readonly industries?: {
                readonly [key: string]: components["schemas"]["IndustryRotationMarkov"];
            };
            readonly summary?: string;
        };
        readonly ApiResponseListHotSymbolDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["HotSymbolDto"][];
        };
        readonly HotSymbolDto: {
            readonly code?: string;
            /** Format: double */
            readonly closePrice?: number;
            /** Format: double */
            readonly pctChange?: number;
            /** Format: int64 */
            readonly volume?: number;
        };
        readonly ApiResponseMarketBreadthDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["MarketBreadthDto"];
        };
        readonly MarketBreadthDto: {
            /** Format: int32 */
            readonly days?: number;
            readonly compositeBreadth?: {
                readonly [key: string]: number;
            };
            readonly scaleBreadth?: {
                readonly [key: string]: number;
            };
            readonly styleBreadth?: {
                readonly [key: string]: number;
            };
            readonly leadingCategories?: {
                readonly [key: string]: number;
            };
            readonly laggingCategories?: {
                readonly [key: string]: number;
            };
            readonly summary?: string;
        };
        readonly ApiResponseListIndustryProsperityDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["IndustryProsperityDto"][];
        };
        readonly IndustryProsperityDto: {
            /** Format: date */
            readonly tradeDate?: string;
            readonly industry?: string;
            /** Format: double */
            readonly avgPctChg?: number;
            /** Format: double */
            readonly totalAmount?: number;
            /** Format: double */
            readonly avgTurn?: number;
            /** Format: int32 */
            readonly risingCount?: number;
            /** Format: int32 */
            readonly fallingCount?: number;
            /** Format: double */
            readonly momentumScore?: number;
            /** Format: double */
            readonly capitalScore?: number;
            /** Format: double */
            readonly activityScore?: number;
            /** Format: double */
            readonly breadthScore?: number;
            /** Format: double */
            readonly prosperityIndex?: number;
            readonly grade?: string;
        };
        readonly ApiResponseProsperitySeasonalityDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ProsperitySeasonalityDto"];
        };
        readonly MonthlyPattern: {
            readonly industry?: string;
            readonly monthlyAvg?: {
                readonly [key: string]: number;
            };
            readonly weekdayAvg?: {
                readonly [key: string]: number;
            };
            /** Format: int32 */
            readonly bestMonth?: number;
            /** Format: int32 */
            readonly worstMonth?: number;
            /** Format: double */
            readonly bestMonthAvg?: number;
            /** Format: double */
            readonly worstMonthAvg?: number;
            /** Format: double */
            readonly seasonalityStrength?: number;
            /** Format: double */
            readonly overallAvg?: number;
        };
        readonly ProsperitySeasonalityDto: {
            readonly analysisPeriod?: string;
            /** Format: int32 */
            readonly totalDataPoints?: number;
            readonly industries?: {
                readonly [key: string]: components["schemas"]["MonthlyPattern"];
            };
            readonly summary?: string;
        };
        readonly ApiResponseProsperityMarkovDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ProsperityMarkovDto"];
        };
        readonly IndustryMarkov: {
            readonly industry?: string;
            readonly transitionMatrix?: readonly (readonly number[])[];
            /** Format: int32 */
            readonly currentState?: number;
            readonly currentStateName?: string;
            readonly nextProbabilities?: {
                readonly [key: string]: number;
            };
            readonly steadyState?: {
                readonly [key: string]: number;
            };
            /** Format: int32 */
            readonly transitionCount?: number;
            readonly mostLikelyNext?: string;
            /** Format: double */
            readonly mostLikelyNextProb?: number;
        };
        readonly ProsperityMarkovDto: {
            readonly analysisDate?: string;
            /** Format: int32 */
            readonly totalTransitions?: number;
            readonly industries?: {
                readonly [key: string]: components["schemas"]["IndustryMarkov"];
            };
            readonly summary?: string;
        };
        readonly ApiResponseProsperityForecastDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ProsperityForecastDto"];
        };
        readonly IndustryForecast: {
            readonly industry?: string;
            readonly arimaForecast?: readonly number[];
            readonly holtWintersForecast?: readonly number[];
            readonly linearForecast?: readonly number[];
            readonly ensembleForecast?: readonly number[];
            /** Format: double */
            readonly currentProsperity?: number;
            readonly arimaTrend?: string;
            readonly holtWintersTrend?: string;
            readonly linearTrend?: string;
            readonly consensusTrend?: string;
            readonly forecastDates?: readonly string[];
        };
        readonly ProsperityForecastDto: {
            readonly analysisDate?: string;
            /** Format: int32 */
            readonly forecastDays?: number;
            readonly industries?: {
                readonly [key: string]: components["schemas"]["IndustryForecast"];
            };
            readonly summary?: string;
        };
        readonly ApiResponseProsperityForecastBacktestDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ProsperityForecastBacktestDto"];
        };
        readonly ProsperityForecastBacktestDto: {
            /** Format: int32 */
            readonly forecastDays?: number;
            /** Format: int32 */
            readonly totalPredictions?: number;
            /** Format: double */
            readonly mae?: number;
            /** Format: double */
            readonly directionAccuracy?: number;
            /** Format: double */
            readonly gradeHitRate?: number;
            /** Format: double */
            readonly avgTopReturn?: number;
            /** Format: double */
            readonly avgMarketReturn?: number;
            /** Format: double */
            readonly avgExcessReturn?: number;
            readonly summary?: string;
            readonly entries?: readonly components["schemas"]["BacktestEntry"][];
            /** Format: double */
            readonly arimaMae?: number;
            /** Format: double */
            readonly hwMae?: number;
            /** Format: double */
            readonly linearMae?: number;
            readonly optimalWeights?: string;
        };
        readonly AlertEntry: {
            readonly industry?: string;
            readonly alertType?: string;
            readonly alertTypeName?: string;
            /** Format: double */
            readonly yesterdayProsperity?: number;
            /** Format: double */
            readonly todayProsperity?: number;
            /** Format: double */
            readonly change?: number;
            readonly yesterdayGrade?: string;
            readonly todayGrade?: string;
            readonly severity?: string;
            readonly message?: string;
        };
        readonly ApiResponseProsperityAlertDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["ProsperityAlertDto"];
        };
        readonly ProsperityAlertDto: {
            readonly analysisDate?: string;
            readonly alerts?: readonly components["schemas"]["AlertEntry"][];
            readonly summary?: string;
        };
        readonly ApiResponseListIndustryDailyDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["IndustryDailyDto"][];
        };
        readonly IndustryDailyDto: {
            /** Format: date */
            readonly tradeDate?: string;
            readonly industry?: string;
            /** Format: int32 */
            readonly stockCount?: number;
            /** Format: double */
            readonly avgPctChg?: number;
            /** Format: double */
            readonly totalAmount?: number;
            /** Format: int64 */
            readonly totalVolume?: number;
            /** Format: double */
            readonly avgTurn?: number;
            /** Format: int32 */
            readonly risingCount?: number;
            /** Format: int32 */
            readonly fallingCount?: number;
            /** Format: double */
            readonly avgClose?: number;
            /** Format: double */
            readonly maxClose?: number;
            /** Format: double */
            readonly minClose?: number;
        };
        readonly ApiResponseListStockIndustryDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["StockIndustryDto"][];
        };
        readonly StockIndustryDto: {
            /** Format: int64 */
            readonly id?: number;
            readonly code?: string;
            /** Format: date */
            readonly updateDate?: string;
            readonly codeName?: string;
            readonly industry?: string;
            readonly industryClassification?: string;
        };
        readonly ApiResponseListString: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly string[];
        };
        readonly ApiResponseListIndexMetadataDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["IndexMetadataDto"][];
        };
        readonly IndexMetadataDto: {
            readonly code?: string;
            readonly name?: string;
            readonly category?: string;
            readonly categoryCode?: string;
        };
        readonly ApiResponseListIndexDailyDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["IndexDailyDto"][];
        };
        readonly ApiResponseDashboardSnapshotDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["DashboardSnapshotDto"];
        };
        readonly CandlestickDto: {
            readonly code?: string;
            readonly records?: readonly components["schemas"]["StockDailyDto"][];
            readonly hasMore?: boolean;
            readonly indicators?: components["schemas"]["IndicatorSeriesDto"];
        };
        readonly DashboardMetricDto: {
            readonly title?: string;
            readonly value?: string;
            readonly subtitle?: string;
        };
        readonly DashboardSnapshotDto: {
            readonly metrics?: readonly components["schemas"]["DashboardMetricDto"][];
            readonly records?: readonly components["schemas"]["StockDailyDto"][];
            readonly chart?: components["schemas"]["CandlestickDto"];
            readonly hotSymbols?: readonly components["schemas"]["HotSymbolDto"][];
            readonly selectedQuery?: components["schemas"]["StockDailyQueryDto"];
            readonly connected?: boolean;
            readonly statusText?: string;
            readonly logLines?: readonly string[];
        };
        readonly StockDailyQueryDto: {
            readonly code?: string;
            /** Format: int32 */
            readonly adjustflag?: number;
            /** Format: date */
            readonly startDate?: string;
            /** Format: date */
            readonly endDate?: string;
            /** Format: int32 */
            readonly limit?: number;
            /** Format: int32 */
            readonly offset?: number;
        };
        readonly ApiResponseCandlestickDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["CandlestickDto"];
        };
        readonly ApiResponseListSavedStrategySummaryDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["SavedStrategySummaryDto"][];
        };
        readonly SavedStrategySummaryDto: {
            /** Format: int64 */
            readonly id?: number;
            readonly name?: string;
            /** Format: date-time */
            readonly createdAt?: string;
            /** Format: date-time */
            readonly updatedAt?: string;
        };
        readonly ApiResponsePageAiCallLogDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: components["schemas"]["PageAiCallLogDto"];
        };
        readonly PageAiCallLogDto: {
            /** Format: int64 */
            readonly totalElements?: number;
            /** Format: int32 */
            readonly totalPages?: number;
            readonly first?: boolean;
            readonly last?: boolean;
            /** Format: int32 */
            readonly numberOfElements?: number;
            /** Format: int32 */
            readonly size?: number;
            readonly content?: readonly components["schemas"]["AiCallLogDto"][];
            /** Format: int32 */
            readonly number?: number;
            readonly sort?: readonly components["schemas"]["SortObject"][];
            readonly pageable?: components["schemas"]["PageableObject"];
            readonly empty?: boolean;
        };
        readonly PageableObject: {
            /** Format: int64 */
            readonly offset?: number;
            readonly sort?: readonly components["schemas"]["SortObject"][];
            /** Format: int32 */
            readonly pageNumber?: number;
            /** Format: int32 */
            readonly pageSize?: number;
            readonly paged?: boolean;
            readonly unpaged?: boolean;
        };
        readonly SortObject: {
            readonly direction?: string;
            readonly nullHandling?: string;
            readonly ascending?: boolean;
            readonly property?: string;
            readonly ignoreCase?: boolean;
        };
        readonly ApiResponseMapStringObject: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: {
                readonly [key: string]: Record<string, never>;
            };
        };
        readonly ApiResponseListAiCallLogDto: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: readonly components["schemas"]["AiCallLogDto"][];
        };
        readonly ApiResponseVoid: {
            readonly success?: boolean;
            readonly code?: string;
            readonly message?: string;
            readonly data?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
    readonly currentConfig: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseDatabaseConfigDto"];
                };
            };
        };
    };
    readonly updateConfig: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["DatabaseConfigUpdateDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseDatabaseConfigDto"];
                };
            };
        };
    };
    readonly load: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseUserPreferenceDto"];
                };
            };
        };
    };
    readonly save: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["UserPreferenceDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseUserPreferenceDto"];
                };
            };
        };
    };
    readonly run: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["SyncRequestDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSyncStatusDto"];
                };
            };
        };
    };
    readonly cancel: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSyncStatusDto"];
                };
            };
        };
    };
    readonly indexHistoryBatch: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["IndexHistoryBatchRequestDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseMapStringListIndexDailyDto"];
                };
            };
        };
    };
    readonly run_1: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["ScreenerCriteriaDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseScreenerResultDto"];
                };
            };
        };
    };
    readonly compute: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["IndicatorComputeRequest"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseIndicatorSeriesDto"];
                };
            };
        };
    };
    readonly listStrategies: {
        readonly parameters: {
            readonly query?: {
                readonly source?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListSavedStrategySummaryDto"];
                };
            };
        };
    };
    readonly saveStrategy: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["SaveStrategyDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSavedStrategyDetailDto"];
                };
            };
        };
    };
    readonly run_2: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BacktestRequestDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseBacktestResultDto"];
                };
            };
        };
    };
    readonly runAndSave: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BacktestRequestDto"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseBacktestResultDto"];
                };
            };
        };
    };
    readonly log: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["AiCallLogRequest"];
            };
        };
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseAiCallLogDto"];
                };
            };
        };
    };
    readonly testNotification: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseString"];
                };
            };
        };
    };
    readonly health: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSystemHealthDto"];
                };
            };
        };
    };
    readonly status: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSyncStatusDto"];
                };
            };
        };
    };
    readonly summary: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSummaryMetricsDto"];
                };
            };
        };
    };
    readonly suggest: {
        readonly parameters: {
            readonly query: {
                readonly q: string;
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListStockSuggestionDto"];
                };
            };
        };
    };
    readonly sectorPerformance: {
        readonly parameters: {
            readonly query?: {
                readonly days?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListSectorPerformanceDto"];
                };
            };
        };
    };
    readonly search: {
        readonly parameters: {
            readonly query?: {
                readonly code?: string;
                readonly adjustflag?: number;
                readonly startDate?: string;
                readonly endDate?: string;
                readonly limit?: number;
                readonly offset?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSearchResultDto"];
                };
            };
        };
    };
    readonly rotationSignals: {
        readonly parameters: {
            readonly query?: {
                readonly days?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseRotationSignalDto"];
                };
            };
        };
    };
    readonly rotationPrediction: {
        readonly parameters: {
            readonly query?: {
                readonly lookbackDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseRotationPredictionDto"];
                };
            };
        };
    };
    readonly rotationPredictionBacktest: {
        readonly parameters: {
            readonly query?: {
                readonly lookbackDays?: number;
                readonly forwardDays?: number;
                readonly backtestDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseRotationBacktestDto"];
                };
            };
        };
    };
    readonly rotationPredictionAutoMl: {
        readonly parameters: {
            readonly query?: {
                readonly backtestDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseRotationAutoMlDto"];
                };
            };
        };
    };
    readonly rotationMarkov: {
        readonly parameters: {
            readonly query?: {
                readonly lookbackDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseRotationMarkovDto"];
                };
            };
        };
    };
    readonly movers: {
        readonly parameters: {
            readonly query?: {
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListHotSymbolDto"];
                };
            };
        };
    };
    readonly marketBreadth: {
        readonly parameters: {
            readonly query?: {
                readonly days?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseMarketBreadthDto"];
                };
            };
        };
    };
    readonly industryProsperity: {
        readonly parameters: {
            readonly query?: {
                readonly tradeDate?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndustryProsperityDto"];
                };
            };
        };
    };
    readonly prosperitySeasonality: {
        readonly parameters: {
            readonly query?: {
                readonly months?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseProsperitySeasonalityDto"];
                };
            };
        };
    };
    readonly industryProsperityRange: {
        readonly parameters: {
            readonly query: {
                readonly start: string;
                readonly end: string;
                readonly topN?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndustryProsperityDto"];
                };
            };
        };
    };
    readonly prosperityMarkov: {
        readonly parameters: {
            readonly query?: {
                readonly months?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseProsperityMarkovDto"];
                };
            };
        };
    };
    readonly prosperityForecast: {
        readonly parameters: {
            readonly query?: {
                readonly months?: number;
                readonly forecastDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseProsperityForecastDto"];
                };
            };
        };
    };
    readonly prosperityForecastBacktest: {
        readonly parameters: {
            readonly query?: {
                readonly months?: number;
                readonly forecastDays?: number;
                readonly backtestDays?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseProsperityForecastBacktestDto"];
                };
            };
        };
    };
    readonly prosperityAlerts: {
        readonly parameters: {
            readonly query?: {
                readonly threshold?: number;
                readonly notify?: boolean;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseProsperityAlertDto"];
                };
            };
        };
    };
    readonly industryDaily: {
        readonly parameters: {
            readonly query?: {
                readonly tradeDate?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndustryDailyDto"];
                };
            };
        };
    };
    readonly industryDailyRange: {
        readonly parameters: {
            readonly query: {
                readonly industry: string;
                readonly start: string;
                readonly end: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndustryDailyDto"];
                };
            };
        };
    };
    readonly allIndustryDailyRange: {
        readonly parameters: {
            readonly query: {
                readonly start: string;
                readonly end: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndustryDailyDto"];
                };
            };
        };
    };
    readonly industries: {
        readonly parameters: {
            readonly query?: {
                readonly code?: string;
                readonly industry?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListStockIndustryDto"];
                };
            };
        };
    };
    readonly industryList: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListString"];
                };
            };
        };
    };
    readonly indexList: {
        readonly parameters: {
            readonly query?: {
                readonly categoryCode?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndexMetadataDto"];
                };
            };
        };
    };
    readonly indexHistory: {
        readonly parameters: {
            readonly query: {
                readonly code: string;
                readonly days?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListIndexDailyDto"];
                };
            };
        };
    };
    readonly dashboard: {
        readonly parameters: {
            readonly query?: {
                readonly code?: string;
                readonly adjustflag?: number;
                readonly startDate?: string;
                readonly endDate?: string;
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseDashboardSnapshotDto"];
                };
            };
        };
    };
    readonly summary_1: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSummaryMetricsDto"];
                };
            };
        };
    };
    readonly candlestick: {
        readonly parameters: {
            readonly query: {
                readonly code: string;
                readonly adjustflag?: number;
                readonly startDate?: string;
                readonly endDate?: string;
                readonly config: components["schemas"]["IndicatorConfigDto"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseCandlestickDto"];
                };
            };
        };
    };
    readonly older: {
        readonly parameters: {
            readonly query: {
                readonly code: string;
                readonly adjustflag?: number;
                readonly beforeDate: string;
                readonly startDate?: string;
                readonly endDate?: string;
                readonly config: components["schemas"]["IndicatorConfigDto"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseCandlestickDto"];
                };
            };
        };
    };
    readonly getStrategy: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path: {
                readonly id: number;
            };
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseSavedStrategyDetailDto"];
                };
            };
        };
    };
    readonly deleteStrategy: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path: {
                readonly id: number;
            };
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseVoid"];
                };
            };
        };
    };
    readonly listRecentRuns: {
        readonly parameters: {
            readonly query?: {
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListSavedStrategySummaryDto"];
                };
            };
        };
    };
    readonly findAll: {
        readonly parameters: {
            readonly query?: {
                readonly page?: number;
                readonly size?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponsePageAiCallLogDto"];
                };
            };
        };
    };
    readonly findByStage: {
        readonly parameters: {
            readonly query?: {
                readonly page?: number;
                readonly size?: number;
            };
            readonly header?: never;
            readonly path: {
                readonly stageName: string;
            };
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponsePageAiCallLogDto"];
                };
            };
        };
    };
    readonly scoreTrend: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseMapStringObject"];
                };
            };
        };
    };
    readonly findRecent: {
        readonly parameters: {
            readonly query?: {
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListAiCallLogDto"];
                };
            };
        };
    };
    readonly findByIteration: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path: {
                readonly iteration: number;
            };
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description OK */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "*/*": components["schemas"]["ApiResponseListAiCallLogDto"];
                };
            };
        };
    };
}
