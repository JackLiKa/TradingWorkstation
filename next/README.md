# Next.js 前端（Trading Workstation Frontend）

> Next.js 15.1.9（App Router）+ React 19 + TypeScript。端口 3010，`basePath: /TradingWorkstation`。
> 深入文檔：架構 [`docs/architecture.md`](../docs/architecture.md)（含 context-path 契約鏈）、API [`docs/api.md`](../docs/api.md)、開發規範 [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)。

## 技術棧

Next.js 15.1.9 / React 19.0.1 / TypeScript 5.6 / Tailwind 3.4 / ECharts 5.5（echarts-for-react）/ SWR 2.2 / Zustand 5.0 / @tanstack/react-table 8.20 / lucide-react / date-fns / shadcn/ui

## 頁面結構（App Router 路由樹）

```
/TradingWorkstation/                    # 總覽儀表盤（指標卡+K線+波動榜+行情表）
├── /dashboard                          # （同根頁面，儀表盤）
├── /screener                           # 選股器 + 回測 + 策略管理（一頁三合一）
├── /backtest                           # （回測在 screener 頁內）
├── /industry                           # 行業分析（景氣度/輪動/Markov/預測/季節性/資金流，21 個組件）
├── /forecast                           # （預測在 industry 頁內）
├── /agent                              # AI 優化：啟停/工作流圖/監控/供應商選擇
├── /agent-dashboard                    # AI 可觀測性（評分趨勢、調用鏈，自繪 SVG 圖表）
├── /sync                               # 數據同步配置與進度
└── /settings                           # DB 健康檢查與連接配置
```

## 目錄結構

```text
src/
├── app/                          # App Router 路由頁
│   ├── layout.tsx                # 根佈局（暗色主題 + Sidebar + Topbar + LoadingOverlay）
│   ├── page.tsx                  # 總覽儀表盤
│   ├── industry/page.tsx         # 行業分析（21 個組件）
│   ├── screener/page.tsx         # 選股器 + 回測 + 策略管理
│   ├── agent/page.tsx            # AI 優化控制台
│   ├── agent-dashboard/page.tsx  # AI 可觀測性
│   ├── sync/page.tsx             # 數據同步
│   ├── settings/page.tsx         # DB 配置
│   └── globals.css               # 全局樣式（Tailwind + 暗色主題）
├── components/                   # 按頁面域分組
│   ├── agent/                    # 10 個（工作流圖/監控/供應商選擇…）
│   ├── backtest/                 # 5 個（淨值曲線/調倉明細/策略對比…）
│   ├── chart/                    # 2 個（K 線圖/技術指標）
│   ├── chat/                     # 4 個（FloatingChatCard/ChatMessageList/ChatInput/ConversationList）— AI 投研聊天懸浮卡片，SSE 流式 + thinking 動畫 + 工具調用實時展示
│   ├── dashboard/                # 7 個（指標卡/波動榜/行情表/MarketSnapshotPanel 行情預計算快照面板…）
│   ├── industry/                 # 21 個（景氣度/輪動/Markov/預測/資金流…）
│   ├── screener/                 # 4 個（條件面板/結果表…）
│   ├── layout/                   # 5 個（Sidebar/Topbar/DbStatusBanner/LoadingOverlay/AppProviders）
│   └── ui/                       # 9 個（shadcn/ui 通用組件）
├── hooks/
│   └── useEChartsOption.ts       # ECharts 共用封裝 hook
└── lib/
    ├── api/
    │   ├── client.ts             # fetch 封裝：API_BASE + 統一 ApiError
    │   ├── types.ts              # 63 個類型，手工鏡像後端 DTO（權威）
    │   ├── generated.ts          # OpenAPI 自動生成類型（npm run gen:api）
    │   ├── openapi.json          # 後端 spec 本地快照（fallback 用）
    │   ├── index.ts              # 45 個後端 API 函數
    │   ├── agent.ts              # 20 個 agent API 函數（直連 :8100）
    │   └── __tests__/api.test.ts # vitest 測試（24 個）
    ├── hooks/
    │   ├── useDbHealth.ts        # DB 健康狀態 hook
    │   └── useDelayedRender.ts   # 延遲渲染 hook
    └── store/
        └── loading.ts            # Zustand 全局加載態
```

## 構建

```bash
npm install --legacy-peer-deps   # 必須帶 flag（SWR peer dep 限制）
npm run dev                      # 開發模式 :3010
npm run build                    # 生產構建
npm run lint                     # ESLint
npm run typecheck                # tsc --noEmit 類型檢查
npm run test                     # vitest（24 個測試）
npm run test:watch               # vitest watch 模式
```

## API 客戶端

`src/lib/api/` 結構：

| 文件 | 職責 |
|------|------|
| `client.ts` | fetch 封裝：`apiFetch`/`apiPost`/`apiPut`/`apiDelete`，統一 `ApiError`（HTTP_*/後端 code/TIMEOUT） |
| `types.ts` | 63 個 TypeScript 類型，**與後端 DTO 字段逐一對應**（手工維護） |
| `index.ts` | 45 個後端 API 函數（按模塊分組：dashboard/stock/chart/screener/backtest/sync/system/preference） |
| `agent.ts` | 20 個 agent API 函數（通過 next rewrites 反代到 :8100） |

**請求鏈路**（重要）：

```
瀏覽器 → :3010/TradingWorkstation/api/*（basePath）
       → next.config.js rewrites → ${BACKEND_HOST}/TradingWorkstation/api/*
瀏覽器 → :3010/TradingWorkstation/agent-api/*（basePath）
       → next.config.js rewrites → ${AGENT_HOST}/api/agent/*
```

- `BACKEND_HOST` **不帶**前綴（默認 `http://localhost:8090`），前綴由 rewrite destination 補
- `AGENT_HOST` **不帶**前綴（默認 `http://localhost:8100`），rewrite destination 自動補 `/api/agent/`
- `proxyTimeout: 180s` — 為回測等慢請求設置
- agent API 走 next 反代統一入口，避免瀏覽器直連 :8100 的 CORS 問題

**開發約定**：新端點 → `types.ts` 加類型 → `index.ts`/`agent.ts` 加函數 → 頁面用 SWR 消費；勿在組件裡裸寫 fetch。

## ECharts 封裝

`src/hooks/useEChartsOption.ts` — 統一處理 ECharts 圖表的常見關切點：

- **主題色板**：`DARK_THEME` 常量（暗色主題，軸線/標籤/分割線/tooltip 配色）
- **tooltip 統一格式化**：`darkTooltipBase` / `darkLegendBase` 基礎配置（可被 builderFn 覆蓋）
- **空態處理**：無數據時返回「暫無數據」佔位 option（`EMPTY_OPTION`）
- **loading 狀態**：外部傳入，hook 透明傳遞

用法：

```tsx
const { option, loading, isEmpty } = useEChartsOption(rawData, (data) => ({
  xAxis: { type: 'category', data: data.map(d => d.date) },
  series: [{ type: 'line', data: data.map(d => d.value) }],
}));
```

## 狀態管理

`src/lib/store/loading.ts` — Zustand 全局加載態，管理全屏 LoadingOverlay 的顯示/隱藏：

```ts
const { start, stop } = useLoadingStore();
start('回測中...');  // 顯示全屏遮罩
stop();              // 隱藏
```

## 樣式

- **Tailwind CSS 3.4** — 暗色主題（`<html lang="zh-CN" className="dark">`）
- **shadcn/ui** — 通用 UI 組件在 `src/components/ui/`（9 個：Button/Card/Dialog/Input/Select/Table/Tabs/Tooltip/Badge）
- 全局樣式在 `src/app/globals.css`

## 類型同步

`src/lib/api/types.ts` 中的 63 個類型**手工鏡像後端 DTO**，改後端 DTO 必須同步此處。

### OpenAPI 自動生成管線（已啟用）

從後端 Swagger/OpenAPI spec 自動生成前端 TypeScript 類型，消滅手工同步的契約 drift：

```bash
# 方式 1：直接從後端 URL 生成（需後端啟動）
npm run gen:api          # openapi-typescript http://localhost:8090/TradingWorkstation/v3/api-docs -o src/lib/api/generated.ts

# 方式 2：從本地 openapi.json 生成（離線 fallback，後端未啟動時用）
npm run gen:api:local    # openapi-typescript src/lib/api/openapi.json -o src/lib/api/generated.ts

# 方式 3：智能模式（自動選擇 URL → 文件 fallback，並刷新 openapi.json）
npm run gen:api:smart    # tsx scripts/generate-api-types.ts
```

| 腳本 | 來源 | 輸出 | 後端要求 |
|------|------|------|----------|
| `gen:api` | 後端 `/v3/api-docs` URL | `src/lib/api/generated.ts` | 需啟動 |
| `gen:api:local` | 本地 `src/lib/api/openapi.json` | `src/lib/api/generated.ts` | 不需要 |
| `gen:api:smart` | 自動（URL 優先 → 文件 fallback） | `src/lib/api/generated.ts` + 刷新 `openapi.json` | 可選 |

- `generated.ts` 是自動生成的補充（`paths`/`components`/`operations` 命名空間），**不破壞** `types.ts` 手寫類型
- `types.ts` 仍為權威來源，`generated.ts` 可逐步替換手寫類型以消滅契約 drift
- `openapi.json` 是後端 spec 的本地快照（fallback 用），由 `gen:api:smart` 自動刷新
- 生成腳本：`scripts/generate-api-types.ts`（支持 `--url` / `--file` 顯式模式）

## 測試

**24 個 vitest 測試**（`src/lib/api/__tests__/api.test.ts`），覆蓋 lib/api 層：

```bash
npm run test    # Test Files 1 passed, Tests 24 passed
```
