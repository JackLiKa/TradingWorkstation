"""LLM 供應商註冊表 — 多模型路由架構核心。

定義所有支持的供應商、模型、API 端點、定價和能力標籤。
每個供應商通過 OpenAI-compatible API 調用（統一接口）。

供應商清單（2026 性價比優先）：
- deepseek-pro:    DeepSeek V4-Pro, 推理最強, $0.44/$0.87, 用於 AI2/AI3
- deepseek-flash:  DeepSeek V4-Flash, 性價比, $0.14/$0.28, 用於 AI1
- glm-5.2:         GLM-5.2, JSON最穩定, $0.55/$1.85, 用於 AI0.5
- glm-flash:       GLM-4-Flash, 免費, 用於 Judge/AI4/Monitor
- qwen:            Qwen3.6, 中文金融最佳, $0.33/$1.95, 用於 AI0
- qoder:           Qoder Lite, 免費 agent SDK, 備用
- devin:           Devin GLM-5.2-High, 免費 agent session, 備用（延遲高）
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelInfo:
    """單個模型的元數據。"""
    provider: str          # 供應商 ID（如 "deepseek-pro"）
    display_name: str      # 顯示名稱（如 "DeepSeek V4-Pro"）
    model_id: str          # API 模型 ID（如 "deepseek-chat"）
    base_url: str          # OpenAI-compatible API base URL
    api_key_env: str       # 環境變量名（API key）
    is_free: bool = False  # 是否免費
    input_price: float = 0.0   # 輸入價格 $/1M tokens
    output_price: float = 0.0  # 輸出價格 $/1M tokens
    supports_json_mode: bool = False  # 是否支持 response_format json
    tags: list[str] = field(default_factory=list)  # 能力標籤
    description: str = ""


# ===== 供應商註冊表 =====
PROVIDERS: dict[str, ModelInfo] = {
    # --- DeepSeek（推理最強 + 性價比）---
    "deepseek-pro": ModelInfo(
        provider="deepseek-pro",
        display_name="DeepSeek V4-Pro",
        model_id="deepseek-reasoner",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        is_free=False,
        input_price=0.44,
        output_price=0.87,
        supports_json_mode=True,
        tags=["reasoning", "json", "chinese", "cost-effective"],
        description="推理最強，適合策略生成和回測反思",
    ),
    "deepseek-flash": ModelInfo(
        provider="deepseek-flash",
        display_name="DeepSeek V4-Flash",
        model_id="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        is_free=False,
        input_price=0.14,
        output_price=0.28,
        supports_json_mode=True,
        tags=["fast", "json", "chinese", "cheap"],
        description="性價比最高，適合行情分析和輕量任務",
    ),

    # --- GLM/智譜（JSON 最穩定 + 免費 Flash）---
    "glm-5.2": ModelInfo(
        provider="glm-5.2",
        display_name="GLM-5.2",
        model_id="glm-5.2",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="GLM_API_KEY",
        is_free=False,
        input_price=0.55,
        output_price=1.85,
        supports_json_mode=True,
        tags=["json", "tool-calling", "chinese", "stable"],
        description="JSON 結構化輸出最穩定，適合行業分析",
    ),
    "glm-flash": ModelInfo(
        provider="glm-flash",
        display_name="GLM-4.5-Flash（免費）",
        model_id="glm-4.5-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="GLM_API_KEY",
        is_free=True,
        input_price=0.0,
        output_price=0.0,
        supports_json_mode=True,
        tags=["free", "json", "chinese", "fast"],
        description="免費 + JSON 穩定，適合 Judge/AI4/Monitor",
    ),

    # --- Qwen/通義千問（中文金融最佳）---
    "qwen": ModelInfo(
        provider="qwen",
        display_name="Qwen3.6",
        model_id="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="QWEN_API_KEY",
        is_free=False,
        input_price=0.33,
        output_price=1.95,
        supports_json_mode=True,
        tags=["chinese", "finance", "json"],
        description="中文金融文本質量最佳，適合行情新聞",
    ),

    # --- Qoder（免費 agent SDK，備用）---
    "qoder": ModelInfo(
        provider="qoder",
        display_name="Qoder Lite（免費）",
        model_id="qoder-lite",
        base_url="",  # Qoder 用 SDK，不走 OpenAI API
        api_key_env="QODER_PERSONAL_ACCESS_TOKEN",
        is_free=True,
        tags=["free", "agent-sdk"],
        description="免費 agent SDK，備用供應商",
    ),

    # --- Devin（免費 agent session，備用，延遲高）---
    "devin": ModelInfo(
        provider="devin",
        display_name="Devin GLM-5.2-High（免費）",
        model_id="glm-5.2-high",
        base_url="",  # Devin 用 session API，不走 OpenAI API
        api_key_env="DEVIN_API_KEY",
        is_free=True,
        tags=["free", "agent-session", "high-latency"],
        description="免費 agent session，延遲較高（~72s），備用",
    ),
}


# ===== 各階段默認模型路由（性價比優先）=====
# 用戶可通過 API/前端覆蓋每個階段的供應商
STAGE_DEFAULT_PROVIDERS: dict[str, str] = {
    "market_news":         "qwen",           # AI 0: 中文金融文本最佳
    "industry_analysis":   "glm-5.2",        # AI 0.5: JSON 最穩定
    "market_analysis":     "deepseek-flash", # AI 1: 性價比最高
    "strategy_generation": "deepseek-pro",   # AI 2: 推理最強（最關鍵）
    "backtest_reflection": "deepseek-pro",   # AI 3: 深度推理
    "prompt_generation":   "glm-flash",      # AI 4: 免費，短文本足夠
    "judge":               "glm-flash",      # Judge: 免費 + 快速 + 一致
    "monitor":             "glm-flash",      # Monitor: 免費
}


def get_provider_info(provider_id: str) -> Optional[ModelInfo]:
    """獲取供應商信息。"""
    return PROVIDERS.get(provider_id)


def get_all_provider_ids() -> list[str]:
    """獲取所有供應商 ID。"""
    return list(PROVIDERS.keys())


def get_default_provider_for_stage(stage: str) -> str:
    """獲取某階段的默認供應商。"""
    return STAGE_DEFAULT_PROVIDERS.get(stage, "")


def is_openai_compatible(provider_id: str) -> bool:
    """判斷供應商是否走 OpenAI-compatible API（vs agent SDK/session）。"""
    info = PROVIDERS.get(provider_id)
    if not info:
        return False
    return bool(info.base_url)


def get_api_key(provider_id: str) -> str:
    """從環境變量獲取供應商的 API key。"""
    import os
    info = PROVIDERS.get(provider_id)
    if not info:
        return ""
    return os.environ.get(info.api_key_env, "")
