# AI Agent 服务 (Trading Workstation Agent)

> FastAPI + LangGraph 风格优化循环的 AI 策略优化服务，通过多模型 LLM 路由自动生成、回测、反思、改进量化交易策略。

## 技术栈

- **Python 3.10+**
- **FastAPI** + **Uvicorn** Web 服务
- **LangGraph 风格** 六阶段优化循环
- **多模型 LLM 路由**：支持 7 个供應商（DeepSeek V4-Pro/Flash、GLM-5.2/4-Flash、Qwen3.6、Qoder、Devin），按階段性價比自動路由 + 自動降級
- **RAG 經驗記憶**：Milvus Lite + BGE 中文 embedding，策略生成前檢索歷史經驗
- **Prometheus 指標**：`/metrics` 端點暴露優化/LLM/RAG/後端全鏈路指標
- **速率限制**：令牌桶算法，防止高頻迭代壓垮後端 API
- **HTTP 客户端** 调用后端 REST API（选股、回测、策略保存）

## 多模型 LLM 路由（2026 性價比最優配置）

每個 AI 節點按需求特點路由到最適合的模型：

| 節點 | 默認供應商 | 理由 | 價格($/1M) |
|------|-----------|------|-----------|
| AI 0 行情新聞 | Qwen3.6 | 中文金融文本最佳 | 0.33/1.95 |
| AI 0.5 行業分析 | GLM-5.2 | JSON 結構化最穩定 | 0.55/1.85 |
| AI 1 行情分析 | DeepSeek V4-Flash | 性價比最高 | 0.14/0.28 |
| AI 2 策略生成 ★ | DeepSeek V4-Pro | 推理最強 + JSON strict | 0.44/0.87 |
| AI 3 回測反思 | DeepSeek V4-Pro | 深度推理分析 | 0.44/0.87 |
| AI 4 提示詞 | GLM-4-Flash | 免費，短文本足夠 | 0/0 |
| Judge 評委 | GLM-4-Flash | 免費 + 快速 + 一致 | 0/0 |
| Monitor 監控 | GLM-4-Flash | 免費 | 0/0 |

用戶可通過前端或 API 為每個階段獨立選擇供應商，支持自動降級。

## 目录结构

```text
agent/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── core/
│   │   ├── config.py              # 統一配置管理（分層 + 驗證）
│   │   ├── providers.py           # LLM 供應商註冊表 + 階段路由
│   │   ├── llm_client.py          # LLM 客戶端（多模型路由 + 降級）
│   │   ├── metrics.py             # Prometheus 指標
│   │   ├── rate_limiter.py        # 令牌桶速率限制器
│   │   ├── logging.py             # 日誌配置（文件輪轉 + 敏感信息過濾）
│   │   └── model_checker.py       # 模型可用性检查
│   ├── agents/
│   │   ├── optimizer.py           # 优化循环主逻辑
│   │   ├── state.py               # 优化器状态（持久化 + 內存截斷）
│   │   ├── judge.py               # Judge AI 评分（多維度 rubric）
│   │   ├── monitor.py             # 系统监控
│   │   ├── monitor_ai.py          # AI 诊断监控
│   │   ├── charter.py             # Agent 憲章（共享身份/職責/約束）
│   │   ├── few_shot.py            # 少樣本提示示例
│   │   ├── scoring.py             # 综合评分计算
│   │   └── stages/                # 六阶段 AI 节点
│   │       ├── base.py            # 阶段基类（含供應商路由 + JSON mode）
│   │       ├── market_news.py     # 阶段 1：市场新闻分析
│   │       ├── industry_analysis.py  # 阶段 2：行业分析与选股
│   │       ├── market_analysis.py    # 阶段 3：市场分析
│   │       ├── strategy_generation.py  # 阶段 4：策略生成
│   │       ├── backtest_reflection.py  # 阶段 5：回测反思
│   │       └── prompt_generation.py    # 阶段 6：Prompt 生成
│   ├── api/
│   │   └── routes.py              # API 路由（含 /metrics + /providers）
│   └── services/
│       ├── backend_client.py      # 后端 REST API 客户端（連接池 + 重試 + 速率限制）
│       ├── experience_store.py    # RAG 經驗存儲/檢索
│       ├── vector_store.py        # Milvus Lite 向量數據庫
│       └── market_data_client.py  # 市场数据客户端
├── tests/                         # pytest 測試套件（114 個測試）
├── requirements.txt
├── requirements-dev.txt           # 測試依賴
├── pytest.ini
├── .env.example                   # 环境变量模板
└── start.ps1                      # Windows 启动脚本
```

## 优化循环流程

```
┌─────────────────────────────────────────────────────────┐
│                    AI 优化循环                            │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ 1.市场新闻 │→│ 2.行业分析 │→│ 3.市场分析 │            │
│  │   分析    │   │   选股    │   │          │            │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘            │
│       │Judge AI     │Judge AI     │Judge AI            │
│       ↓             ↓             ↓                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ 4.策略生成 │→│ 5.回测反思 │→│ 6.Prompt  │            │
│  │          │   │          │   │   生成   │            │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘            │
│       │Judge AI     │Judge AI     │Judge AI            │
│       ↓             ↓             ↓                    │
│  ┌──────────────────────────────────────┐              │
│  │  评分 > 历史最优？ → 更新 best_criteria │              │
│  │  保存策略到后端数据库                  │              │
│  └──────────────────────────────────────┘              │
│                       ↓                                 │
│              下一轮（基于历史最优）                       │
└─────────────────────────────────────────────────────────┘
```

**关键策略**：每轮迭代始终基于历史最优策略（`best_criteria` + `best_config`），而非上一轮的结果。只有当新一轮评分严格高于 `best_score` 时才更新基准。

## 环境变量

从 `agent/.env` 读取：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEVIN_API_KEY` | (空) | Devin (Cognition) API Key |
| `QODER_PERSONAL_ACCESS_TOKEN` | (空) | Qoder Personal Access Token |
| `BACKEND_API_URL` | http://localhost:8090/TradingWorkstation | 后端 API 地址 |
| `AGENT_PORT` | 8100 | Agent 服务端口 |
| `OPTIMIZATION_INTERVAL` | 5 | 迭代间隔（秒） |
| `MAX_ITERATIONS` | 0 | 最大迭代次数（0=无限制） |
| `MODEL_CHECK_INTERVAL` | 300 | 模型检查间隔（秒） |

> 至少配置一个 LLM API Key（`DEVIN_API_KEY` 或 `QODER_PERSONAL_ACCESS_TOKEN`），否则 AI 优化功能不可用。

## 安装与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写 API Key

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100

# 或用启动脚本（Windows）
.\start.ps1
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent/health` | GET | 模型可用性检查 |
| `/api/agent/status` | GET | 优化器当前状态 |
| `/api/agent/history` | GET | 优化历史记录 |
| `/api/agent/criteria` | GET | 当前选股条件 |
| `/api/agent/monitor` | GET | 系统监控数据 |
| `/api/agent/start` | POST | 启动优化循环 |
| `/api/agent/stop` | POST | 停止优化循环 |
| `/api/agent/check-model` | POST | 手动触发模型检查 |

Swagger 文档：`http://localhost:8100/docs`

## 评分机制

综合评分（`compute_composite_score`）基于回测统计指标：

- 总收益率（权重高）
- 夏普比率
- 最大回撤（负向）
- 超额收益

评分越高策略越优。历史最优策略从后端数据库加载，确保重启后不丢失。

## 注意事项

- Agent 依赖后端 REST API，必须先启动 Java 后端
- 至少需要一个可用的 LLM API Key
- 优化循环是长时间运行的任务，建议在后台运行
- 每轮迭代结果会自动保存到后端数据库的 `saved_strategies` 表
