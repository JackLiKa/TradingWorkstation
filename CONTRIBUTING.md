# 贡献指南 (Contributing)

感谢你对量化交易工作台项目的兴趣！本文档描述了参与贡献的流程和规范。

## 开发环境准备

### 前置依赖

- **JDK 21**（后端）
- **Node.js 18+** + npm（前端）
- **Python 3.10+**（Agent 服务 + 数据同步）
- **MySQL 8.0+**（数据库）
- **Maven 3.9+**（后端构建）

### 本地启动

```bash
# 1. 克隆仓库
git clone https://github.com/JackLiKa/TradingWorkstation.git
cd TradingWorkstation

# 2. 配置环境变量
cp .env.example .env              # 编辑填写 DB_PASSWORD
cp agent/.env.example agent/.env  # 编辑填写 LLM API Key（可选）
cp next/.env.example next/.env.local

# 3. 创建数据库并导入数据
mysql -e "CREATE DATABASE IF NOT EXISTS a_stock_baostock DEFAULT CHARACTER SET utf8mb4"
pip install -r ingestion/requirements.txt
python ingestion/baostock_ingest.py  # 选择选项 11

# 4. 按顺序启动服务
cd java && mvn spring-boot:run                              # 端口 8090
cd next && npm install --legacy-peer-deps && npm run dev    # 端口 3010
cd agent && pip install -r requirements.txt                 # 可选
python -m uvicorn app.main:app --port 8100
```

## 开发规范

### 代码风格

- **Java**：遵循 Google Java Style Guide，使用 Lombok 减少样板代码
- **TypeScript**：遵循 ESLint 配置，使用函数式组件 + Hooks
- **Python**：遵循 PEP 8，使用类型注解

### 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

<body>

<footer>
```

类型（type）：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（非新功能、非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖变更 |

示例：

```
feat(backtest): 添加止损止盈功能
fix(frontend): 修复数据库状态显示错误
docs(api): 更新 API 文档
perf(screener): 并行化指标计算
```

### 分支策略

- `main` — 主分支，保持可运行状态
- `feat/<name>` — 新功能分支
- `fix/<name>` — Bug 修复分支
- `docs/<name>` — 文档分支

### Pull Request 流程

1. Fork 仓库并创建功能分支
2. 安装 pre-commit hooks（首次贡献）：
   ```bash
   pip install pre-commit
   pre-commit install
   ```
3. 确保代码通过编译和测试：
   ```bash
   # 後端
   cd java && mvn -DskipTests compile
   # 前端
   cd next && npx tsc --noEmit && npx eslint src/
   # Agent
   cd agent && python -m pytest tests/ -v
   cd agent && ruff check app/ tests/ && ruff format --check app/ tests/
   ```
4. 提交前自动检查（pre-commit 会自动运行 ruff + gitleaks）
5. 提交 PR，描述变更内容和测试方式
6. 等待代码审查

### 模块修改指南

| 修改范围 | 影响文件 | 注意事项 |
|----------|----------|----------|
| 后端 API | `java/src/main/java/com/quantization/module/*` | 保持统一 ApiResponse 格式 |
| 前端页面 | `next/src/app/*/page.tsx` + `next/src/components/*` | 保持 SWR 缓存策略 |
| AI Agent | `agent/app/agents/*` | 保持六阶段流程不变 |
| 数据同步 | `ingestion/baostock_ingest.py` | 测试增量 + 全量模式 |
| 文档 | `docs/*` + `README.md` | 同步更新代码示例 |

## 报告 Bug

请使用 GitHub Issues 报告 Bug，包含以下信息：

- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息（OS、JDK 版本、Node 版本、Python 版本、MySQL 版本）
- 相关日志/截图

## 功能建议

欢迎在 Issues 中提出功能建议，请描述：

- 使用场景
- 期望的功能描述
- 是否有替代方案

## 行为准则

请保持友善和尊重，避免人身攻击和不当言论。
