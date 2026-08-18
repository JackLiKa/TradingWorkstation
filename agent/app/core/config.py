"""應用配置 — 從 .env 讀取，不硬編碼密鑰。"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加載 agent/.env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    """全局配置類 — 通過 pydantic-settings 從環境變量/.env 自動加載配置。

    環境變量名與字段名的映射規則：大寫蛇形 → 小寫蛇形
    （如 DEVIN_API_KEY → devin_api_key）。
    """

    # LLM API keys（環境變量名自動映射：DEVIN_API_KEY -> devin_api_key）
    devin_api_key: str = ""  # Devin API 密鑰，用於免費 GLM-5.2 High 模型
    qoder_personal_access_token: str = ""  # Qoder PAT，用於免費 lite 模型

    # Backend API — 量化交易後端（Java Spring Boot）的基礎 URL
    backend_api_url: str = "http://localhost:8090/TradingWorkstation"

    # Agent service — 本服務的運行參數
    agent_port: int = 8100  # FastAPI 監聽端口
    optimization_interval: int = 5  # 優化循環每輪之間的等待間隔（秒）
    max_iterations: int = 0  # 最大迭代次數，0 表示無限制

    # Model check — 模型可用性定時檢查間隔（秒）
    model_check_interval: int = 300

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # 忽略 .env 中未定義的額外變量
    }

    @property
    def qoder_token(self) -> str:
        """Qoder PAT 的別名，方便外部統一引用。"""
        return self.qoder_personal_access_token


# 全局配置單例 — 整個應用共享同一份配置
settings = Settings()
