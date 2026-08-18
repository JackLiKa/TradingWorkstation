"""優化器狀態數據類 — 負責狀態存儲和序列化。"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

from app.core.llm_client import llm_client

# 預設選股條件（初始值）
_now = datetime.now()
DEFAULT_CRITERIA: dict[str, Any] = {
    "asOfDate": f"{_now.year}-01-01",
    "adjustflag": 3,
    "excludeSt": True,
    "maxResults": 50,
    "sortBy": "score",
}

# 預設回測配置（初始值）
DEFAULT_BACKTEST_CONFIG: dict[str, Any] = {
    "startDate": f"{_now.year}-01-01",
    "endDate": _now.strftime("%Y-%m-%d"),
    "rebalanceInterval": 5,
    "holdingPeriod": 10,
    "maxPositions": 5,
    "initialCapital": 1_000_000,
    "commissionBps": 3,
    "stopLossPct": None,
    "takeProfitPct": None,
}


@dataclass
class StageResult:
    """單個 AI 節點的執行結果。"""
    stage_name: str  # 節點名稱（如 "market_news"）
    output: str  # AI 原始輸出文本
    judge_score: float = 0.0  # 評委給出的分數（0-100）
    judge_passed: bool = True  # 評委是否判定通過
    judge_feedback: str = ""  # 評委反饋意見
    attempts: int = 1  # 嘗試次數（含重試）
    duration_ms: int = 0  # 執行耗時（毫秒）
    error: Optional[str] = None  # 異常信息，無異常時為 None

    def to_dict(self) -> dict:
        """將結果序列化為字典，用於 API 返回和 JSON 存儲。"""
        return asdict(self)


@dataclass
class IterationResult:
    """單次迭代結果 — 包含各 AI 階段的輸出。

    記錄一輪完整優化循環（AI0→AI0.5→AI1→AI2→回測→AI3→AI4）的全部產出，
    用於歷史追溯和前端可視化。
    """
    iteration: int  # 迭代輪次（從 1 開始遞增）
    timestamp: str  # ISO 格式時間戳
    criteria: dict[str, Any]  # 本輪使用的選股條件
    config: dict[str, Any]  # 本輪使用的回測配置
    screener_summary: str  # 選股摘要（命中數、調倉次數等）
    backtest_statistics: dict[str, Any]  # 回測統計指標（收益、回撤、夏普等）
    composite_score: float  # 綜合評分
    # 各 AI 階段輸出
    market_news: str = ""  # AI 0 行情新聞分析結果
    favorable_industries: list = field(default_factory=list)  # AI 0.5 識別的利好行業
    filtered_codes: list = field(default_factory=list)  # AI 0.5 篩選後的股票代碼
    market_analysis: str = ""  # AI 1 行情分析結果
    strategy_generation: str = ""  # AI 2 策略生成理由
    backtest_reflection: str = ""  # AI 3 回測反思結論
    next_prompt: str = ""  # AI 4 下一輪提示詞指引
    next_criteria: dict[str, Any] = field(default_factory=dict)  # 下一輪建議的選股條件
    # 各階段評委結果
    stage_results: list[dict] = field(default_factory=list)  # 各階段的 StageResult 序列化列表
    error: Optional[str] = None  # 異常信息，正常完成時為 None

    def to_dict(self) -> dict:
        """將迭代結果序列化為字典，用於 API 返回和歷史存儲。"""
        return asdict(self)


@dataclass
class OptimizerState:
    """優化器運行狀態 — 全局單例，貫穿整個優化循環生命週期。

    既保存歷史迭代記錄，也保存當前進行中的中間狀態，
    供 API 層實時查詢和前端可視化。
    """
    running: bool = False  # 優化循環是否正在運行
    current_iteration: int = 0  # 當前迭代輪次
    iterations: list[IterationResult] = field(default_factory=list)  # 歷史迭代結果列表
    best_score: float = -999  # 歷史最高綜合評分
    best_iteration: int = 0  # 取得最高評分的迭代輪次
    best_strategy_id: Optional[int] = None  # 最高分策略在後端的 ID
    best_criteria: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CRITERIA))  # 歷史最優策略的選股條件
    best_config: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_BACKTEST_CONFIG))  # 歷史最優策略的回測配置
    current_criteria: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CRITERIA))  # 當前選股條件
    current_config: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_BACKTEST_CONFIG))  # 當前回測配置
    current_market_context: str = ""  # 當前市場環境分析結果
    current_reflection: str = ""  # 上一輪回測反思結論
    current_next_prompt: str = ""  # 下一輪提示詞指引
    # 新增：行情新聞和行業分析結果
    current_market_news: str = ""  # 當前行情新聞分析結果
    current_favorable_industries: list = field(default_factory=list)  # 當前利好行業列表
    current_filtered_codes: list = field(default_factory=list)  # 當前篩選後的股票代碼
    # 當前階段信息（可觀測性）
    current_stage: str = ""  # 當前正在執行的階段名稱
    current_stage_status: str = ""  # 當前階段狀態: idle/running/judging/passed/failed/retrying
    # 當前迭代的各階段結果（增量更新，用於實時可視化）
    current_stage_results: list[dict] = field(default_factory=list)
    status_message: str = "idle"  # 人類可讀的狀態描述
    started_at: Optional[str] = None  # 啟動時間（ISO 格式）
    stopped_at: Optional[str] = None  # 停止時間（ISO 格式）

    def to_dict(self) -> dict:
        """將運行狀態序列化為字典，供 /status 等 API 端點返回。

        Returns:
            dict: 包含運行狀態、當前參數、歷史摘要和模型狀態的字典
        """
        return {
            "running": self.running,
            "current_iteration": self.current_iteration,
            "total_iterations": len(self.iterations),
            "best_score": self.best_score,
            "best_iteration": self.best_iteration,
            "best_strategy_id": self.best_strategy_id,
            "current_criteria": self.current_criteria,
            "current_config": self.current_config,
            "current_market_context": self.current_market_context,
            "current_reflection": self.current_reflection,
            "current_market_news": self.current_market_news,
            "current_favorable_industries": self.current_favorable_industries,
            "current_filtered_codes": self.current_filtered_codes,
            "current_stage": self.current_stage,
            "current_stage_status": self.current_stage_status,
            "current_stage_results": self.current_stage_results,
            "status_message": self.status_message,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "model_status": {
                "provider": llm_client.model_status.provider,
                "model_name": llm_client.model_status.model_name,
                "available": llm_client.model_status.available,
                "is_free": llm_client.model_status.is_free,
            },
        }
