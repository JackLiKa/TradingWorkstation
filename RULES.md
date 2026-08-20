# RULES.md — 工程規範

> 所有貢獻者必須遵守的硬性規則。違反 Must Never 條目的 PR 將被拒絕。

## Must Always

- **計劃先行**：複雜功能（跨模組、新 API、架構變更）先規劃再實作
- **測試驅動**：新功能先寫測試（RED → GREEN → IMPROVE），覆蓋率目標 ≥ 80%
- **校驗輸入**：所有外部輸入（API 請求、用戶表單、LLM 輸出）在系統邊界校驗
- **不可變優先**：優先創建新對象而非修改共享狀態
- **遵循既有模式**：新增代碼遵循倉庫已有的架構模式，不發明新模式
- **統一響應格式**：所有 Java API 返回 `ApiResponse<T>` = `{success, code, message, data}`
- **DTO 對齊**：`next/src/lib/api/types.ts` 與 `java/.../module/*/dto` 字段一一對應
- **配置外部化**：密鑰、連接串、可調參數放 `.env` / `application.yml`，不硬編碼
- **增量更新冪等**：數據同步使用 `ON DUPLICATE KEY UPDATE`，重複運行安全
- **Agent 數據校驗**：回測日期區間必須在數據庫覆蓋範圍內，AI 操作基於真實數據
- **Conventional Commits**：提交格式 `<type>(<scope>): <description>`
- **PR 附測試計劃**：每個 PR 必須包含 Test plan checklist

## Must Never

- **永不硬編碼密鑰**：API Key、密碼、Token、連接串不寫入代碼、日誌、提交信息
- **永不提交 `.env`**：`.env`、`agent/.env`、`next/.env.local` 不入庫（已在 `.gitignore`）
- **永不提交運行時數據**：`agent/data/`（Milvus Lite DB、checkpoint）、`*.db`、`*.sqlite` 不入庫
- **永不提交臨時腳本**：`analyze_db.py`、`check_dups.py` 等臨時分析腳本不入庫
- **永不提交二進制文件**：`*.png`、`*.jar`、`*.parquet`、`*.arrow` 不入庫（除非在 `assets/` 下）
- **永不繞過安全檢查**：不跳過輸入校驗、不關閉 CSRF、不放寬 CORS 到 `*`（生產環境）
- **永不靜默吞掉錯誤**：`except: pass` 或 `catch (Exception) {}` 必須至少記錄日誌
- **永不重複實作已有功能**：新增代碼前先搜索倉庫是否已有類似實現
- **永不跳過測試提交**：PR 必須通過 CI 全部檢查
- **永不直接修改 `main` 分支**：功能開發使用 `feat/` 或 `fix/` 分支
- **永不在前端重複計算指標**：指標計算在 Java `IndicatorEngine`，前端只渲染
- **永不讓 AI 使用想像數據**：Agent prompt 必須基於真實數據庫數據，禁止編造價格/日期/行業

---

## 提交前安全 Checklist

> 每次 `git commit` 前逐項檢查。CI 會自動執行 gitleaks 掃描，但人工檢查不可省略。

### 密鑰與敏感信息

- [ ] 代碼中無硬編碼 API Key、密碼、Token
- [ ] 日誌中不記錄敏感信息（密鑰、密碼、完整連接串）
- [ ] 錯誤消息不洩露內部實現細節（如 SQL 語句、堆棧路徑）
- [ ] `.env` / `agent/.env` 不在 `git diff` 中
- [ ] `.env.example` 中的密鑰值為空或佔位符（如 `your-api-key-here`）

### 輸入校驗

- [ ] 所有 API 端點校驗請求體（`@Valid` + DTO 注解 / Pydantic 模型）
- [ ] 數值參數有範圍限制（如 `maxPositions` 1-20，`adjustflag` 1-3）
- [ ] 日期參數校驗格式和範圍（`startDate <= endDate`，在數據庫覆蓋範圍內）
- [ ] 字符串參數防注入（JPA 參數化查詢 / Pydantic 類型校驗）

### 數據安全

- [ ] SQL 使用參數化查詢（Spring Data JPA 已內建，禁止拼接 SQL）
- [ ] 前端渲染用戶/AI 內容時防 XSS（React 預設轉義，`dangerouslySetInnerHTML` 需審查）
- [ ] 文件上傳（如有）校驗類型和大小
- [ ] 數據庫遷移（如有）不破壞已有數據

### 依賴安全

- [ ] 新增依賴發布 ≥ 7 天（避免供應鏈攻擊）
- [ ] 不使用 `latest` / `*` 浮動版本範圍
- [ ] `requirements.txt` / `pom.xml` / `package.json` 版本固定或範圍合理

### 運行時數據

- [ ] `agent/data/` 不在暫存區
- [ ] 無臨時腳本（`analyze_*.py`、`check_*.py`、`test_*.py` 在根目錄）被提交
- [ ] 無 `*.db`、`*.sqlite`、`*.parquet` 二進制文件被提交

---

## 代碼質量 Checklist

### 結構

- [ ] 函數體 < 50 行
- [ ] 單文件 < 800 行
- [ ] 嵌套不超過 4 層
- [ ] 無死代碼（未使用的函數、變量、import）

### 命名

- [ ] 命名清晰可讀，無無意義縮寫
- [ ] Java 遵循 camelCase，Python 遵循 snake_case，TypeScript 遵循 camelCase
- [ ] 常量全大寫 + 下劃線（`MAX_RETRIES`）

### 錯誤處理

- [ ] 每一層都有錯誤處理
- [ ] UI 層顯示用戶友好消息
- [ ] 服務端記錄詳細上下文日誌
- [ ] 無 `except: pass` 或空 `catch` 塊

### 測試

- [ ] 新功能有對應測試
- [ ] Bug 修復有回歸測試
- [ ] 測試隔離良好（無共享可變狀態）
- [ ] Mock 使用合理（不 mock 被測對象本身）

---

## AI Agent 專用規則

> 適用於 `agent/` 目錄下的 AI 優化服務。

### Prompt 工程

- **Must**：所有 AI 操作基於 prompt 中明確提供的真實數據
- **Must**：prompt 中明確禁止編造價格、日期、股票代碼、行業、政策
- **Must**：Judge AI 必須拒絕無證據支撐的事實性聲明
- **Must**：few-shot 示例不得暗示不存在的新闻或市场事件
- **Must Not**：使用記憶中的歷史 A 股數據作為當前證據
- **Must Not**：在證據缺失時編造數據填補空白

### LLM 路由

- **Must**：每個階段可獨立配置供應商，支持自動降級
- **Must**：LLM 調用使用速率限制器防止壓垮後端
- **Must**：LLM 失敗時靜默降級，不影響優化循環
- **Must Not**：在代碼中硬編碼供應商 API Key

### RAG 向量庫

- **Must**：RAG 不可用時靜默降級，不影響優化循環
- **Must**：向量庫文件（`agent/data/`）不入庫
- **Must**：初始化失敗允許重試（不永久放棄）
- **Must Not**：在 RAG 經驗中存儲敏感信息
