# AI Agent 服務（Trading Workstation Agent）

> FastAPI + LangGraph 風格優化循環，端口 8100，API 前綴 `/api/agent`。
> 深入文檔：[`docs/AGENT_SERVICE.md`](../docs/AGENT_SERVICE.md)、API [`docs/api.md`](../docs/api.md)、開發規範 [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)。

## 技術棧

Python 3.10+（<3.15）/ FastAPI / Uvicorn / Pydantic Settings / HTTPX / Milvus Lite (RAG) / sentence-transformers / Prometheus 自定義指標 / LangGraph 風格 async 串聯循環

## 架構概覽

Agent 通過 6 個 AI 階段 + 1 個後端回測步驟構成閉環優化，每輪迭代自動改進選股策略：

```
market_news → industry_analysis → market_analysis → strategy_generation
                                                          ↓
              prompt_generation ← backtest_reflection ← 後端回測 + 評分
                      ↓
                下一輪迭代
```

- 每個 AI 階段輸出經 **JudgeAI** 把關（pass threshold = 60）
- 回測由 Java 後端執行（REST 調用），非 AI 步驟
- 評分超越歷史最佳時自動落庫（`backtest_strategy` 表）
- 未超越時下一輪回到歷史最優策略重新出發

## 六個 AI 階段

| 階段 | 代號 | 職責 |
|------|------|------|
| 行情新聞分析 | `market_news` | 抓取財經新聞，AI 摘要市場情緒與事件 |
| 行業分析 | `industry_analysis` | 基於新聞篩選利好行業 + 候選股票池 |
| 行情分析 | `market_analysis` | 結合後端市場概覽，AI 分析當前市場狀態 |
| 策略生成 | `strategy_generation` | 生成 JSON 選股條件（criteria），核心產出 |
| 回測反思 | `backtest_reflection` | 根據回測統計反思策略優劣，提出改進方向 |
| 提示詞生成 | `prompt_generation` | 生成下一輪策略生成的改進提示詞 |

## 七個 LLM 供應商

| Provider ID | 模型 | 特點 |
|-------------|------|------|
| `deepseek-pro` | deepseek-chat | 付費，能力強 |
| `deepseek-flash` | deepseek-chat（flash 模式） | 付費，速度快 |
| `glm-5.2` | glm-5.2 | 智譜免費額度 |
| `glm-flash` | glm-4-flash | 智譜免費，JSON 穩定（備用首選） |
| `qwen` | qwen-turbo | 阿里通義 |
| `qoder` | qoder | Qoder 平台 |
| `devin` | devin | Devin API |

**降級鏈**：優先免費/低成本供應商，失敗時按鏈降級。每個階段可獨立配置 `stage_providers`。

## 多窗口評分

啟用 `multi_window_backtest=true` 時，對 3 個時間窗口分別回測取加權平均：

| 窗口 | 權重 |
|------|------|
| 90 天 | 0.5 |
| 180 天 | 0.3 |
| 365 天 | 0.2 |

- 加權平均分用於迭代比較
- **365 天窗口的完整回測結果**用於反思和落庫（主窗口）
- 降低單一窗口隨機性，評分更穩定

**綜合評分公式**：return × 0.4 + drawdown × 0.3 + Sharpe × 0.3（`scoring.py:compute_composite_score`）

## 無進展終止

- 每輪 `Δscore = 本輪評分 - 歷史最佳`
- `Δscore < 1.0` 視為「無實質進展」，`stagnant_count += 1`
- `max_stagnant_iterations > 0` 且 `stagnant_count >= max_stagnant_iterations` 時自動停止
- `max_stagnant_iterations=0`（默認）= 不自動停止，持續運行直到用戶手動停止

## JSON 失敗保護

策略生成階段期望 JSON 輸出，解析失敗時分級處理（防止空轉燒 token）：

| 連續失敗次數 | 行為 |
|--------------|------|
| 1-2 | 復用當前 criteria 繼續循環 |
| ≥3 | 切換備用供應商重試一次（優先 glm-flash） |
| 備用也失敗 | 暫停 60 秒後繼續 |
| ≥5 | 停止優化循環 |

所有失敗記錄到 `error_store` 供監控。

## 目錄結構

```text
agent/
├── app/
│   ├── main.py                    # FastAPI 入口 + lifespan 初始化
│   ├── api/
│   │   └── routes.py              # 22 個 API 端點
│   ├── core/
│   │   ├── config.py              # Pydantic Settings（從 .env 讀取）
│   │   ├── llm_client.py          # LLM 客戶端（7 供應商 + 降級鏈）
│   │   ├── providers.py           # 供應商註冊與默認分配
│   │   ├── rate_limiter.py        # 令牌桶限流（backtest/screener/read）
│   │   ├── metrics.py             # Prometheus 自定義指標
│   │   └── logging.py             # 結構化日誌
│   ├── agents/
│   │   ├── optimizer.py           # 主優化循環（run_optimization_loop）
│   │   ├── judge.py               # JudgeAI（pass_threshold=60）
│   │   ├── scoring.py             # compute_composite_score
│   │   ├── safety.py              # JSON 安全檢查 + 輸出消毒
│   │   ├── state.py               # OptimizerState + checkpoint 恢復
│   │   ├── charter.py             # 系統人設/charter 文本
│   │   ├── few_shot.py            # few-shot 示例
│   │   ├── monitor.py             # 節點監控（run_id/耗時/評分）
│   │   └── stages/                # 6 個 AI 階段實現
│   │       ├── market_news.py
│   │       ├── industry_analysis.py
│   │       ├── market_analysis.py
│   │       ├── strategy_generation.py
│   │       ├── backtest_reflection.py
│   │       └── prompt_generation.py
│   ├── services/
│   │   ├── backend_client.py      # 調用 Java 後端 REST API
│   │   ├── market_data_client.py  # 市場數據客戶端
│   │   ├── vector_store.py        # Milvus Lite 向量庫（RAG）
│   │   ├── experience_store.py    # RAG 經驗存取
│   │   ├── error_store.py         # 錯誤記錄（供監控）
│   │   └── model_checker.py       # 模型可用性檢查
│   └── utils/
│       └── json_extractor.py      # JSON 提取工具
├── tests/                         # 197 個 pytest 測試
├── data/                          # checkpoint + Milvus 數據
├── requirements.txt
└── .env.example
```

## 構建與運行

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動（開發）
python -m uvicorn app.main:app --port 8100 --reload

# 或用啟動腳本
.\start.ps1    # Windows
```

驗證：

```bash
curl http://localhost:8100/api/agent/health     # → {"available":true,...}
curl http://localhost:8100/docs                  # Swagger UI
curl http://localhost:8100/api/agent/metrics     # Prometheus 指標
```

## 配置

`agent/.env`（從 `.env.example` 複製）：

| 配置組 | 關鍵項 | 默認 | 說明 |
|--------|--------|------|------|
| 後端 | `BACKEND_API_URL` | `http://localhost:8090/TradingWorkstation` | **必須帶 context-path** |
| 服務 | `AGENT_PORT` | 8100 | |
| LLM Keys | `DEEPSEEK_API_KEY`/`GLM_API_KEY`/`QWEN_API_KEY`/`QODER_PERSONAL_ACCESS_TOKEN`/`DEVIN_API_KEY` | — | 至少配一個 |
| 優化 | `OPTIMIZATION_INTERVAL` | 5 | 輪間隔秒數 |
| 優化 | `MAX_ITERATIONS` | 0 | 0=不限 |
| 優化 | `MAX_STAGNANT_ITERATIONS` | 0 | 0=不自動停 |
| 優化 | `MULTI_WINDOW_BACKTEST` | false | true=啟用多窗口評分 |
| 限流 | `RATE_LIMIT_BACKTEST_*`/`RATE_LIMIT_SCREENER_*`/`RATE_LIMIT_READ_*` | — | 令牌桶限流 |
| RAG | `RAG_ENABLED`/`EMBEDDING_MODEL` | true/BAAI/bge-small-zh | Milvus Lite + sentence-transformers |
| 監控 | `ENABLE_METRICS`/`LOG_LEVEL`/`ENVIRONMENT` | true/INFO/development | |

## API 端點

完整 22 端點見 [`docs/api.md`](../docs/api.md)，核心端點：

| 方法 | 路徑 | 說明 |
|------|------|------|
| `POST` | `/api/agent/start` | **啟動優化循環**（含可選 config 覆蓋） |
| `POST` | `/api/agent/stop` | 停止優化循環 |
| `GET` | `/api/agent/status` | 當前狀態（運行中/迭代數/最佳評分） |
| `GET` | `/api/agent/history` | 歷史迭代記錄 |
| `GET` | `/api/agent/criteria` | 當前選股條件 |
| `GET` | `/api/agent/config` | 當前回測配置 |
| `GET` | `/api/agent/metrics` | Prometheus 指標 |
| `GET` | `/api/agent/health` | 健康檢查（含模型可用性） |
| `GET` | `/api/agent/providers` | 供應商列表與狀態 |
| `GET` | `/api/agent/monitoring` | 監控數據（run_id/節點耗時/評分序列） |

> **⚠️ 端點名稱**：啟動優化的端點是 `POST /api/agent/start`（非 `/optimize`）。

## 狀態行為

- **啟動來源**：優先從後端 DB 讀取評分最高的已保存策略作為 `f0`；無歷史策略時用默認參數
- **崩潰恢復**：有 checkpoint 時恢復迭代數/最佳評分/reflection/next_prompt
- **用戶配置優先**：`/start` 時手動設置的 config 字段優先保留，不被 checkpoint/DB 覆蓋
- **內存控制**：最多保留 100 輪迭代記錄在內存（`MAX_IN_MEMORY_ITERATIONS`）
- **checkpoint**：每輪結束寫本地文件，崩潰後可恢復

## 測試

**197 個 pytest 測試**：

```bash
python -m pytest tests/           # 197 tests collected
python -m pytest tests/ --cov=app # 覆蓋率 ~18.6%（閾值 40%，當前未達標）
```

> 覆蓋率閾值 40% 是 `pyproject.toml` 中的 `--cov-fail-under` 配置；當前實際覆蓋率 ~18.6%，測試本身全部通過但命令因覆蓋率未達標而退出非零碼。這是既有狀態，非本次文檔變更引入。
