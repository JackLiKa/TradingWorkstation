# Next.js 前端 (Trading Workstation Frontend)

> Next.js 15 (App Router) + React 19 + TypeScript 量化交易前端，提供总览面板、选股回测、AI 优化、数据同步等界面。

## 技术栈

- **Next.js 15.1.9** (App Router, 混合渲染 SSR/CSR)
- **React 19** + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** 组件风格
- **ECharts** K 线图与净值曲线
- **SWR** 数据请求缓存与轮询
- **lucide-react** 图标库

## 目录结构

```text
next/
├── src/
│   ├── app/                           # App Router 页面
│   │   ├── layout.tsx                 # 根布局（Sidebar + Topbar + DbStatusBanner）
│   │   ├── page.tsx                   # 总览面板（Dashboard）
│   │   ├── screener/page.tsx          # 选股器与回测
│   │   ├── agent/page.tsx             # AI 策略优化
│   │   ├── sync/page.tsx              # 数据同步
│   │   └── settings/page.tsx          # 系统设置
│   ├── components/
│   │   ├── layout/                    # Sidebar、Topbar、DbStatusBanner、LoadingOverlay
│   │   ├── dashboard/                 # Toolbar、MetricCard、MoversList、StockTable、LogPanel
│   │   ├── screener/                  # ScreenerFilterPanel、ScreenerResultTable、CandidateDetail
│   │   ├── backtest/                  # BacktestConfigPanel、BacktestStatisticsPanel、StrategyManager
│   │   ├── agent/                     # AgentModelCard、AgentIterationCard、AgentWorkflowGraph
│   │   ├── chart/                     # CandlestickChart、BacktestCurveChart
│   │   └── ui/                        # Button、Card、Badge、Skeleton、ErrorState、ProgressIndicator
│   ├── lib/
│   │   ├── api/                       # API 客户端（apiFetch、apiPost）+ 类型定义
│   │   ├── hooks/                     # useDbHealth 等自定义 Hook
│   │   └── utils.ts                   # 工具函数
│   └── styles/
├── public/
├── next.config.js                     # basePath + rewrites + proxyTimeout
├── .env.local                         # NEXT_PUBLIC_API_BASE（不入库）
├── package.json
└── start.ps1                          # Windows 启动脚本
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_BASE` | /TradingWorkstation | 客户端 API 请求前缀（与 basePath 一致） |
| `BACKEND_HOST` | http://localhost:8090 | next.config.js rewrites 代理目标 |

`.env.local` 示例：

```
NEXT_PUBLIC_API_BASE=/TradingWorkstation
```

> **注意**：`NEXT_PUBLIC_API_BASE` 必须是 `/TradingWorkstation`（不是 `http://localhost:8090`），否则客户端 fetch 会绕过 rewrites 代理直接请求后端，导致 404。

## 安装与运行

```bash
# 安装依赖（必须用 --legacy-peer-deps，因 SWR peer dep 限制）
npm install --legacy-peer-deps

# 开发模式
npm run dev

# 生产构建
npm run build && npm start
```

默认端口 3010，访问地址：`http://localhost:3010/TradingWorkstation`

## 关键配置

### basePath + rewrites

```javascript
// next.config.js
{
  basePath: '/TradingWorkstation',
  experimental: { proxyTimeout: 180000 },  // 回测等慢操作需要长超时
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8090/TradingWorkstation/api/:path*' },
    ];
  },
}
```

- `basePath` 使所有页面带 `/TradingWorkstation` 前缀
- `rewrites` 将 `/TradingWorkstation/api/*` 代理到后端
- `proxyTimeout` 解决回测等慢操作超时问题（默认 30 秒不够）

### 数据库状态可视化

- **Topbar**：实时显示数据库连接状态徽章（连接中/已连接/未连接/后端不可达）
- **DbStatusBanner**：全局状态横幅，未连接时醒目显示 + 重试按钮
- **useDbHealth Hook**：共享 SWR 缓存，15 秒轮询 `/api/system/health`

## 页面说明

| 页面 | 路由 | 功能 |
|------|------|------|
| 总览面板 | `/` | 指标卡片、K 线图、波动列表、搜索结果 |
| 选股回测 | `/screener` | 选股筛选、回测、策略管理 |
| AI 优化 | `/agent` | AI 策略优化循环、工作流图谱、历史记录 |
| 数据同步 | `/sync` | Baostock 数据拉取进度 |
| 系统设置 | `/settings` | 数据库配置、用户偏好 |

## 注意事项

- 安装依赖必须用 `--legacy-peer-deps`
- 修改 `next.config.js` 后需重启 dev server
- 修改 `.env.local` 后需重启 dev server（`NEXT_PUBLIC_*` 是编译时注入）
- 如果遇到 webpack chunk 404，删除 `.next` 目录后重启
