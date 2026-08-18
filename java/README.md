# Java 后端 (Trading Workstation Backend)

> Java 21 + Spring Boot 3.3.4 量化交易后端服务，提供 REST API 供前端和 Agent 服务调用。

## 技术栈

- **Java 21** + **Spring Boot 3.3.4**
- **Spring Data JPA** (Hibernate 6.5) + **HikariCP** 连接池
- **Caffeine** 内存缓存（仪表盘数据）
- **springdoc-openapi** Swagger API 文档
- **Lombok** 减少样板代码
- **MySQL 8.0+** 数据库

## 目录结构

```text
java/
├── src/main/java/com/quantization/
│   ├── QuantizationApplication.java    # 入口
│   ├── common/                         # 跨切面：ApiResponse、异常处理、配置
│   └── module/
│       ├── stock/                      # 股票行情：entity/repository/dto/service/controller
│       ├── indicator/                  # 技术指标引擎（MA/BOLL/MACD/KDJ/RSI 等）
│       ├── dashboard/                  # 仪表盘汇总
│       ├── screener/                   # 选股器
│       ├── backtest/                   # 回测引擎
│       ├── chart/                      # K 线图数据
│       ├── sync/                       # Baostock 数据同步编排
│       ├── system/                     # 系统健康检查、数据库配置
│       └── preference/                 # 用户偏好持久化
├── src/main/resources/
│   └── application.yml                 # 配置（从 .env 读取）
├── pom.xml
└── start.ps1                           # Windows 启动脚本
```

## 模块职责

| 模块 | 职责 | 关键端点 |
|------|------|----------|
| `stock` | 股票日线 CRUD、搜索、波动列表 | `/api/stock/search`、`/api/stock/movers` |
| `indicator` | 技术指标计算引擎 | 内部调用，无独立端点 |
| `dashboard` | 仪表盘汇总指标 | `/api/dashboard/summary` |
| `screener` | 选股筛选 | `/api/screener/run` |
| `backtest` | 回测引擎 | `/api/backtest/run`、`/api/backtest/strategies` |
| `chart` | K 线图数据 | `/api/chart/candlestick` |
| `sync` | Baostock 数据同步 | `/api/sync/run`、`/api/sync/status` |
| `system` | 系统健康、数据库配置 | `/api/system/health`、`/api/system/database` |
| `preference` | 用户偏好 | `/api/preference` |

## 环境变量

从根目录 `.env` 读取，关键配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_HOST` | localhost | MySQL 主机 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_NAME` | a_stock_baostock | 数据库名 |
| `DB_USER` | root | 数据库用户 |
| `DB_PASSWORD` | (无) | 数据库密码 |
| `SERVER_PORT` | 8090 | 后端端口 |
| `SERVER_CONTEXT_PATH` | /TradingWorkstation | API 前缀 |
| `CORS_ALLOWED_ORIGINS` | http://localhost:3010 | CORS 白名单 |
| `CACHE_SUMMARY_TTL_SECONDS` | 60 | 仪表盘汇总缓存 TTL |
| `CACHE_METRICS_TTL_SECONDS` | 30 | 仪表盘指标缓存 TTL |

## 构建与运行

```bash
# 编译
mvn -DskipTests compile

# 运行（开发模式）
mvn spring-boot:run

# 打包并运行（生产模式）
mvn -DskipTests package
java -Xmx4g -jar target/trading-workstation-backend-1.0.0.jar
```

## API 文档

启动后访问 Swagger：`http://localhost:8090/TradingWorkstation/swagger-ui.html`

所有 API 统一响应格式：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": { ... }
}
```

## 性能优化

- **Caffeine 缓存**：仪表盘数据缓存 30-60 秒，减少数据库压力
- **并行指标计算**：选股器使用 `parallelStream` 并行计算技术指标
- **价格查找优化**：回测引擎用 `Map<code, Map<date, price>>` O(1) 查找
- **数据裁剪**：选股只取最近 150 天数据计算指标（指标最多需 120 天）

## 注意事项

- 需要 JDK 21，低版本会编译失败
- MySQL 必须提前创建数据库 `a_stock_baostock`
- 数据同步需要本机安装 Python + baostock 包
- 回测大日期范围（>1 年）可能需要 1-2 分钟，前端已配置 180 秒超时
