"""應用配置 — 統一配置管理 + 啟動時驗證。

工程化改進：
- 分層配置：LLM / Backend / Agent / RateLimit / RAG / Monitoring
- 類型安全：所有字段有類型標註和默認值
- 啟動驗證：validate() 方法檢查生產環境必需配置
- 可選 mutable default：stage_providers 用 default_factory
- 配置導出：to_dict() 供 /health 端點展示（隱藏敏感字段）
"""

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

# 加載 agent/.env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, encoding="utf-8")

logger = logging.getLogger("agent.config")


class Settings(BaseSettings):
    """全局配置類 — 分層管理所有配置項。

    環境變量名與字段名的映射規則：大寫蛇形 → 小寫蛇形
    （如 DEVIN_API_KEY → devin_api_key）。
    """

    # ===== LLM 配置 =====
    devin_api_key: str = ""  # Devin API 密鑰
    qoder_personal_access_token: str = ""  # Qoder PAT
    deepseek_api_key: str = ""  # DeepSeek API key (V4-Pro/V4-Flash)
    glm_api_key: str = ""  # GLM/智譜 API key (GLM-5.2/GLM-4-Flash)
    qwen_api_key: str = ""  # Qwen/通義千問 API key

    # ===== Backend API =====
    backend_api_url: str = "http://localhost:8090/TradingWorkstation"
    backend_timeout: int = 600  # 後端調用超時（秒）
    backend_max_retries: int = 3  # 後端調用最大重試次數

    # ===== API 安全 =====
    api_key: str = ""  # API Key 認證（空則跳過認證，生產環境建議設置）

    # ===== Agent Service =====
    agent_port: int = 8100
    optimization_interval: int = 5  # 優化循環間隔（秒）
    max_iterations: int = 0  # 最大迭代次數，0=無限制
    model_check_interval: int = 300  # 模型檢查間隔（秒）
    max_stagnant_iterations: int = 0  # 連續無進展自動停止閾值，0=不限制（保持兼容）
    multi_window_backtest: bool = False  # 多窗口回測評分：用 3 個時間窗口加權平均

    # ===== 新聞自動同步 =====
    news_sync_enabled: bool = True  # 是否啟用新聞自動同步
    news_sync_interval: int = 360  # 同步間隔（秒，默認 6 分鐘）
    news_sync_catchup_days: int = 7  # 啟動時補抓天數
    news_sync_channels: str = "all"  # 同步頻道（all/a-stock/單頻道）
    news_sync_catchup_on_startup: bool = True  # 啟動時是否執行補抓

    # ===== 新聞過濾 =====
    news_filter_enabled: bool = True  # 是否啟用財經關鍵詞過濾
    news_filter_keywords: str = ""  # 自定義關鍵詞白名單（逗號分隔，空=用默認）
    news_filter_blacklist: str = ""  # 自定義黑名單（逗號分隔，追加到默認）

    # ===== Per-stage provider =====
    stage_providers: dict[str, str] = {}  # 每階段供應商偏好

    # ===== 速率限制 =====
    rate_limit_backtest: float = 0.033  # 回測: 每 30 秒 1 次
    rate_limit_screener: float = 0.2  # 選股: 每 5 秒 1 次
    rate_limit_read: float = 5.0  # 讀操作: 每秒 5 次

    # ===== RAG =====
    embedding_model: str = "BAAI/bge-small-zh-v1.5"  # 中文 embedding 模型
    rag_top_k: int = 3  # RAG 檢索返回數量
    rag_min_similarity: float = 0.3  # RAG 最低相似度閾值

    # ===== 監控 =====
    log_level: str = "INFO"  # 日誌級別
    enable_metrics: bool = True  # 是否啟用 Prometheus 指標

    # ===== 環境標識 =====
    environment: str = "development"  # development / staging / production

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """環境標識只允許特定值。"""
        allowed = {"development", "staging", "production"}
        v_lower = v.lower().strip()
        if v_lower not in allowed:
            raise ValueError(f"environment 必須是 {allowed} 之一，得到 {v}")
        return v_lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """日誌級別只允許特定值。"""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        v_upper = v.upper().strip()
        if v_upper not in allowed:
            raise ValueError(f"log_level 必須是 {allowed} 之一，得到 {v}")
        return v_upper

    @property
    def qoder_token(self) -> str:
        """Qoder PAT 的別名。"""
        return self.qoder_personal_access_token

    @property
    def is_production(self) -> bool:
        """是否為生產環境。"""
        return self.environment == "production"

    def validate_for_production(self) -> list[str]:
        """驗證生產環境必需配置，返回缺失項列表。

        Returns:
            list[str]: 缺失或無效的配置項描述（空列表=全部通過）
        """
        errors = []

        # 至少一個 LLM key
        if not self.devin_api_key and not self.qoder_personal_access_token:
            errors.append("生產環境需要至少一個 LLM API key（DEVIN_API_KEY 或 QODER_PERSONAL_ACCESS_TOKEN）")

        # 後端 URL 不應為 localhost（生產）
        if self.is_production and "localhost" in self.backend_api_url:
            errors.append(f"生產環境 backend_api_url 不應為 localhost: {self.backend_api_url}")

        # 優化間隔應為正數
        if self.optimization_interval <= 0:
            errors.append(f"optimization_interval 必須 > 0，當前 {self.optimization_interval}")

        # 端口範圍
        if not (1 <= self.agent_port <= 65535):
            errors.append(f"agent_port 必須在 1-65535，當前 {self.agent_port}")

        return errors

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """導出配置為字典（供 /health 端點展示）。

        Args:
            include_secrets: 是否包含敏感字段（API key 等）
        """
        d = {
            "environment": self.environment,
            "backend_api_url": self.backend_api_url,
            "agent_port": self.agent_port,
            "optimization_interval": self.optimization_interval,
            "max_iterations": self.max_iterations,
            "model_check_interval": self.model_check_interval,
            "max_stagnant_iterations": self.max_stagnant_iterations,
            "multi_window_backtest": self.multi_window_backtest,
            "backend_timeout": self.backend_timeout,
            "backend_max_retries": self.backend_max_retries,
            "rate_limits": {
                "backtest": self.rate_limit_backtest,
                "screener": self.rate_limit_screener,
                "read": self.rate_limit_read,
            },
            "rag": {
                "embedding_model": self.embedding_model,
                "top_k": self.rag_top_k,
                "min_similarity": self.rag_min_similarity,
            },
            "log_level": self.log_level,
            "enable_metrics": self.enable_metrics,
            "stage_providers": self.stage_providers,
        }
        if include_secrets:
            d["devin_api_key_set"] = bool(self.devin_api_key)
            d["qoder_token_set"] = bool(self.qoder_personal_access_token)
        else:
            d["devin_api_key_set"] = bool(self.devin_api_key)
            d["qoder_token_set"] = bool(self.qoder_personal_access_token)
        return d


# 全局配置單例
settings = Settings()

# 啟動時驗證（生產環境嚴格檢查）
_errors = settings.validate_for_production()
if _errors and settings.is_production:
    for e in _errors:
        logger.error(f"配置驗證失敗: {e}")
    # 生產環境不阻止啟動，但記錄錯誤
elif _errors:
    for e in _errors:
        logger.warning(f"配置警告: {e}")
