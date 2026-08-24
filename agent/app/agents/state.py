"""優化器狀態數據類 — 三層狀態管理（內存 + 文件 + DB）。

狀態分層：
1. 瞬時狀態（TransientState）— 僅內存，重啟丟失
   - 當前階段進度、當前迭代各階段結果、實時狀態消息
   - 用途：實時可視化、進度追蹤

2. 持久狀態（PersistentState）— 文件 checkpoint，重啟可恢復
   - best_score/criteria/config、current_criteria/config
   - current_reflection/next_prompt、最近 N 輪摘要
   - 用途：崩潰恢復、跨重啟延續優化

3. 數據庫狀態（DbState）— MySQL 持久化，跨進程/跨交易日
   - 回顧分析結果（每5輪一次）
   - 當日市場摘要（每日一次，同交易日內複用）
   - 用途：跨交易日狀態、前端查詢、AI 數據複用

工程化改進：
- iterations 列表自動截斷（保留最近 100 輪），防止內存洩漏
- checkpoint/restore 支持文件持久化
- DB 狀態通過 backend_client 持久化到 Java 後端
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.llm_client import llm_client

logger = logging.getLogger("agent.state")

# 內存中保留的最大迭代輪數（防止 OOM）
MAX_IN_MEMORY_ITERATIONS = 100

# 回顧分析觸發間隔（每 N 輪觸發一次）
RETROSPECTIVE_INTERVAL = 5

# 預設選股條件（初始值）
_now = datetime.now()
# 回測起始日期至少回溯 1 年，確保樣本量充足（≥120 個交易日）
# 若當前月份 < 8 月，起始日期回退到前一年，保證 ≥1 年回測區間
_backtest_start_year = _now.year - 1 if _now.month < 8 else _now.year
DEFAULT_CRITERIA: dict[str, Any] = {
    "asOfDate": f"{_now.year}-01-01",
    "adjustflag": 3,
    "excludeSt": True,
    "maxResults": 50,
    "sortBy": "score",
}

# 預設回測配置（初始值）
DEFAULT_BACKTEST_CONFIG: dict[str, Any] = {
    "startDate": f"{_backtest_start_year}-01-01",
    "endDate": _now.strftime("%Y-%m-%d"),
    "rebalanceInterval": 5,
    "holdingPeriod": 10,
    "maxPositions": 5,
    "initialCapital": 1_000_000,
    "commissionBps": 3,
    "slippageBps": 5,  # 強制最小滑點 5bp，避免零滑點回測幻覺
    "stopLossPct": None,
    "takeProfitPct": None,
}


def build_default_criteria(latest_trade_date: str | None = None) -> dict[str, Any]:
    """構建預設選股條件，基準日期校準到數據庫最新交易日。

    Args:
        latest_trade_date: 數據庫最新交易日（YYYY-MM-DD）。None 時用年初。

    Returns:
        dict: 預設選股條件
    """
    criteria = dict(DEFAULT_CRITERIA)
    if latest_trade_date:
        # asOfDate 用最新交易日所在年的 1/1
        year = latest_trade_date[:4]
        criteria["asOfDate"] = f"{year}-01-01"
    return criteria


def build_default_backtest_config(latest_trade_date: str | None = None) -> dict[str, Any]:
    """構建預設回測配置，日期校準到數據庫最新交易日。

    回測區間至少 1 年，確保統計顯著性（≥120 個交易日）。
    若最新交易日在 8 月之前，起始日期回退到前一年。

    Args:
        latest_trade_date: 數據庫最新交易日（YYYY-MM-DD）。None 時用今天。

    Returns:
        dict: 預設回測配置，startDate≥1年前, endDate=最新交易日
    """
    config = dict(DEFAULT_BACKTEST_CONFIG)
    if latest_trade_date:
        year = int(latest_trade_date[:4])
        month = int(latest_trade_date[5:7]) if len(latest_trade_date) >= 7 else 12
        # 若最新交易日在 8 月前，起始日期回退到前一年（確保 ≥1 年回測區間）
        start_year = year - 1 if month < 8 else year
        config["startDate"] = f"{start_year}-01-01"
        config["endDate"] = latest_trade_date
    return config


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
    error: str | None = None  # 異常信息，無異常時為 None
    citations: list[dict[str, Any]] = field(default_factory=list)  # 工具調用引用來源
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)  # 工具調用記錄

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
    error: str | None = None  # 異常信息，正常完成時為 None

    def to_dict(self) -> dict:
        """將迭代結果序列化為字典，用於 API 返回和歷史存儲。"""
        return asdict(self)


@dataclass
class RetrospectiveResult:
    """回顧分析結果 — 每5輪由回顧AI生成，注入下一輪優化。

    分析最近5輪各AI節點的輸入輸出，發現問題、提出優化總結和改善方案。
    持久化到DB（agent_state表），供前端展示和跨重啟恢復。
    """

    iteration_range: tuple[int, int]  # 分析的迭代範圍（如 (1, 5)）
    timestamp: str  # ISO 格式時間戳
    findings: str  # 發現的問題（自然語言）
    optimization_summary: str  # 優化總結
    improvement_plan: str  # 改善方案（具體可執行的建議）
    stage_issues: dict[str, str] = field(default_factory=dict)  # 各階段問題 {stage_name: issue_description}
    score_trend: str = ""  # 評分趨勢分析
    recommendations: list[str] = field(default_factory=list)  # 具體建議列表

    def to_dict(self) -> dict:
        d = asdict(self)
        # tuple 序列化為 list
        d["iteration_range"] = list(self.iteration_range)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RetrospectiveResult":
        """從字典構建（用於從 DB 恢復）。"""
        rng = data.get("iteration_range", [0, 0])
        if isinstance(rng, list):
            rng = (rng[0], rng[1])
        return cls(
            iteration_range=rng,
            timestamp=data.get("timestamp", ""),
            findings=data.get("findings", ""),
            optimization_summary=data.get("optimization_summary", ""),
            improvement_plan=data.get("improvement_plan", ""),
            stage_issues=data.get("stage_issues", {}),
            score_trend=data.get("score_trend", ""),
            recommendations=data.get("recommendations", []),
        )

    def to_prompt_text(self) -> str:
        """格式化為可注入 next_prompt 的文本。"""
        lines = [
            f"## 回顧分析（第 {self.iteration_range[0]}-{self.iteration_range[1]} 輪）",
            f"### 發現的問題",
            self.findings,
            f"### 優化總結",
            self.optimization_summary,
            f"### 改善方案（必須遵循）",
            self.improvement_plan,
        ]
        if self.recommendations:
            lines.append("### 具體建議")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
        return "\n".join(lines)


@dataclass
class DailyDigest:
    """當日市場摘要 — 每日生成一次，同交易日內所有AI節點複用。

    凝練濃縮當天的市場信息和新聞，標準化格式持久化到DB。
    減少工具調用、提高數據命中率、減小幻覺。
    """

    trade_date: str  # 交易日 YYYY-MM-DD
    timestamp: str  # 生成時間 ISO 格式
    market_overview: str  # 市場概覽（指數表現、漲跌家數、成交額）
    sector_highlights: str  # 板塊亮點（強勢/弱勢行業）
    news_digest: str  # 新聞摘要（已凝練的關鍵新聞）
    sentiment: str  # 市場情緒（偏多/中性/偏空 + 理由）
    key_events: list[str] = field(default_factory=list)  # 關鍵事件列表
    data_sources: list[str] = field(default_factory=list)  # 數據來源（DB/Tool/MCP）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DailyDigest":
        """從字典構建（用於從 DB 恢復）。

        兼容兩種 key 格式：
        - snake_case：內部 state 序列化 / DB agent_state 的 stateJson
        - camelCase：Java 後端 DailyDigestDto 返回的 API 響應
        """
        return cls(
            trade_date=data.get("trade_date") or data.get("tradeDate") or "",
            timestamp=data.get("timestamp") or data.get("generatedAt") or "",
            market_overview=data.get("market_overview") or data.get("marketOverview") or "",
            sector_highlights=data.get("sector_highlights") or data.get("sectorHighlights") or "",
            news_digest=data.get("news_digest") or data.get("newsDigest") or "",
            sentiment=data.get("sentiment") or "",
            key_events=data.get("key_events") or data.get("keyEvents") or [],
            data_sources=data.get("data_sources") or data.get("dataSources") or [],
        )

    def is_empty(self) -> bool:
        """判斷摘要是否為空（無實質內容）。

        用於區分「有效摘要」和「生成失敗的空殼」。
        trade_date 和 market_overview 是必要字段，任一為空則視為無效。
        """
        return not self.trade_date or not self.market_overview

    def to_prompt_text(self) -> str:
        """格式化為可注入 AI prompt 的標準化文本。"""
        lines = [
            f"## 當日市場摘要（{self.trade_date}，生成於 {self.timestamp[:19]}）",
            f"### 市場概覽",
            self.market_overview,
            f"### 板塊亮點",
            self.sector_highlights,
            f"### 新聞摘要",
            self.news_digest,
            f"### 市場情緒",
            self.sentiment,
        ]
        if self.key_events:
            lines.append("### 關鍵事件")
            for event in self.key_events:
                lines.append(f"- {event}")
        if self.data_sources:
            lines.append(f"（數據來源: {', '.join(self.data_sources)}）")
        return "\n".join(lines)


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
    best_strategy_id: int | None = None  # 最高分策略在後端的 ID
    best_criteria: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CRITERIA))  # 歷史最優策略的選股條件
    best_config: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_BACKTEST_CONFIG))  # 歷史最優策略的回測配置
    current_criteria: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CRITERIA))  # 當前選股條件
    current_config: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_BACKTEST_CONFIG))  # 當前回測配置
    current_market_context: str = ""  # 當前市場環境分析結果
    current_reflection: str = ""  # 上一輪回測反思結論
    current_next_prompt: str = ""  # 下一輪提示詞指引
    current_regime_type: str = "unknown"  # 當前市場形態類型（trending_up/trending_down/oscillation/...）
    # 新增：行情新聞和行業分析結果
    current_market_news: str = ""  # 當前行情新聞分析結果
    current_favorable_industries: list = field(default_factory=list)  # 當前利好行業列表
    current_filtered_codes: list = field(default_factory=list)  # 當前篩選後的股票代碼
    # 當前階段信息（可觀測性）— 瞬時狀態
    current_stage: str = ""  # 當前正在執行的階段名稱
    current_stage_status: str = ""  # 當前階段狀態: idle/running/judging/passed/failed/retrying
    # 當前迭代的各階段結果（增量更新，用於實時可視化）— 瞬時狀態
    current_stage_results: list[dict] = field(default_factory=list)
    status_message: str = "idle"  # 人類可讀的狀態描述
    started_at: str | None = None  # 啟動時間（ISO 格式）
    stopped_at: str | None = None  # 停止時間（ISO 格式）

    # ===== 新增：回顧分析結果（持久狀態，DB + 文件）=====
    # 每 RETROSPECTIVE_INTERVAL 輪由回顧AI生成，注入下一輪 next_prompt
    last_retrospective: RetrospectiveResult | None = None  # 最近一次回顧分析結果
    retrospective_count: int = 0  # 已執行的回顧分析次數

    # ===== 新增：當日市場摘要快取（持久狀態，DB）=====
    # 同交易日內所有AI節點複用，減少工具調用
    current_daily_digest: DailyDigest | None = None  # 當日市場摘要
    daily_digest_date: str = ""  # 當日摘要對應的交易日

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
            # 新增：回顧分析和當日摘要
            "last_retrospective": self.last_retrospective.to_dict() if self.last_retrospective else None,
            "retrospective_count": self.retrospective_count,
            "current_daily_digest": self.current_daily_digest.to_dict() if self.current_daily_digest else None,
            "daily_digest_date": self.daily_digest_date,
            "model_status": {
                "provider": llm_client.model_status.provider,
                "model_name": llm_client.model_status.model_name,
                "available": llm_client.model_status.available,
                "is_free": llm_client.model_status.is_free,
            },
            "available_providers": llm_client.get_available_providers(),
        }

    def add_iteration(self, result: IterationResult) -> None:
        """添加迭代結果並自動截斷舊記錄（防止內存洩漏）。

        保留最近 MAX_IN_MEMORY_ITERATIONS 輪的完整數據。
        """
        self.iterations.append(result)
        # 截斷：超過上限時移除最舊的記錄
        if len(self.iterations) > MAX_IN_MEMORY_ITERATIONS:
            removed = len(self.iterations) - MAX_IN_MEMORY_ITERATIONS
            self.iterations = self.iterations[removed:]
            logger.info(f"狀態截斷: 移除 {removed} 條舊迭代記錄，保留最近 {len(self.iterations)} 條")

    def checkpoint(self, path: str = None) -> str:
        """將關鍵狀態保存到磁盤（用於崩潰恢復）。

        保存內容：best_score, best_criteria, best_config, current_criteria,
        current_config, current_reflection, current_next_prompt, current_iteration。
        不保存完整 iterations（太大），只保存最近 5 輪摘要。

        Returns:
            str: checkpoint 文件路徑
        """
        if path is None:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            path = str(data_dir / "optimizer_checkpoint.json")

        try:
            # 確保目錄存在
            checkpoint_dir = os.path.dirname(path)
            if checkpoint_dir:
                os.makedirs(checkpoint_dir, exist_ok=True)

            checkpoint_data = {
                "saved_at": datetime.now().isoformat(),
                "current_iteration": self.current_iteration,
                "best_score": self.best_score,
                "best_iteration": self.best_iteration,
                "best_strategy_id": self.best_strategy_id,
                "best_criteria": self.best_criteria,
                "best_config": self.best_config,
                "current_criteria": self.current_criteria,
                "current_config": self.current_config,
                "current_reflection": self.current_reflection,
                "current_next_prompt": self.current_next_prompt,
                # 新增：回顧分析結果和當日摘要
                "last_retrospective": self.last_retrospective.to_dict() if self.last_retrospective else None,
                "retrospective_count": self.retrospective_count,
                "current_daily_digest": self.current_daily_digest.to_dict() if self.current_daily_digest else None,
                "daily_digest_date": self.daily_digest_date,
                # 只保存最近 5 輪摘要（完整數據太大）
                "recent_iterations": [
                    {
                        "iteration": it.iteration,
                        "composite_score": it.composite_score,
                        "criteria": it.criteria,
                        "backtest_statistics": it.backtest_statistics,
                    }
                    for it in self.iterations[-5:]
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            logger.info(f"狀態 checkpoint 已保存: {path}")
            return path
        except Exception as e:
            logger.warning(f"Checkpoint 保存失敗: {e}")
            return ""

    def restore(self, path: str = None) -> bool:
        """從磁盤恢復狀態（崩潰恢復）。

        Returns:
            bool: 是否成功恢復
        """
        if path is None:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            path = str(data_dir / "optimizer_checkpoint.json")

        if not os.path.exists(path):
            logger.info("無 checkpoint 文件，使用默認狀態")
            return False

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            self.current_iteration = data.get("current_iteration", 0)
            self.best_score = data.get("best_score", -999)
            self.best_iteration = data.get("best_iteration", 0)
            self.best_strategy_id = data.get("best_strategy_id")
            self.best_criteria = data.get("best_criteria", dict(DEFAULT_CRITERIA))
            self.best_config = data.get("best_config", dict(DEFAULT_BACKTEST_CONFIG))
            self.current_criteria = data.get("current_criteria", dict(DEFAULT_CRITERIA))
            self.current_config = data.get("current_config", dict(DEFAULT_BACKTEST_CONFIG))
            self.current_reflection = data.get("current_reflection", "")
            self.current_next_prompt = data.get("current_next_prompt", "")

            # 恢復回顧分析結果和當日摘要
            retro_data = data.get("last_retrospective")
            if retro_data:
                self.last_retrospective = RetrospectiveResult.from_dict(retro_data)
            self.retrospective_count = data.get("retrospective_count", 0)
            digest_data = data.get("current_daily_digest")
            if digest_data:
                self.current_daily_digest = DailyDigest.from_dict(digest_data)
            self.daily_digest_date = data.get("daily_digest_date", "")

            # 恢復最近迭代摘要（不完整恢復，只供歷史參考）
            recent = data.get("recent_iterations", [])
            for r in recent:
                self.iterations.append(
                    IterationResult(
                        iteration=r.get("iteration", 0),
                        timestamp="",
                        criteria=r.get("criteria", {}),
                        config={},
                        screener_summary="",
                        backtest_statistics=r.get("backtest_statistics", {}),
                        composite_score=r.get("composite_score", 0),
                    )
                )

            logger.info(
                f"狀態已從 checkpoint 恢復: iteration={self.current_iteration}, "
                f"best_score={self.best_score}, 歷史記錄={len(self.iterations)} 條"
            )
            return True
        except Exception as e:
            logger.warning(f"Checkpoint 恢復失敗: {e}")
            return False

    def to_db_json(self) -> str:
        """序列化完整狀態為 JSON 字符串，用於 DB 持久化。

        包含文件 checkpoint 的全部字段 + 回顧分析結果 + 當日摘要。
        不包含完整 iterations（太大），只保存最近 5 輪摘要。
        """
        try:
            db_data = {
                "saved_at": datetime.now().isoformat(),
                "current_iteration": self.current_iteration,
                "best_score": self.best_score,
                "best_iteration": self.best_iteration,
                "best_strategy_id": self.best_strategy_id,
                "best_criteria": self.best_criteria,
                "best_config": self.best_config,
                "current_criteria": self.current_criteria,
                "current_config": self.current_config,
                "current_reflection": self.current_reflection,
                "current_next_prompt": self.current_next_prompt,
                "last_retrospective": self.last_retrospective.to_dict() if self.last_retrospective else None,
                "retrospective_count": self.retrospective_count,
                "current_daily_digest": self.current_daily_digest.to_dict() if self.current_daily_digest else None,
                "daily_digest_date": self.daily_digest_date,
                "recent_iterations": [
                    {
                        "iteration": it.iteration,
                        "composite_score": it.composite_score,
                        "criteria": it.criteria,
                        "backtest_statistics": it.backtest_statistics,
                    }
                    for it in self.iterations[-5:]
                ],
            }
            return json.dumps(db_data, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"DB 狀態序列化失敗: {e}")
            return "{}"

    async def checkpoint_db(self) -> bool:
        """將狀態持久化到後端數據庫（DB 層 checkpoint）。

        與文件 checkpoint 互補：文件用於快速恢復，DB 用於跨進程/跨交易日。
        後端不可用時靜默失敗，不影響優化循環。

        Returns:
            bool: 是否成功持久化
        """
        try:
            from app.services.backend_client import backend_client

            state_json = self.to_db_json()
            await backend_client.save_agent_state(
                state_json=state_json,
                current_iteration=self.current_iteration,
                best_score=self.best_score,
                retrospective_count=self.retrospective_count,
            )
            logger.debug(f"DB 狀態已持久化: iteration={self.current_iteration}")
            return True
        except Exception as e:
            logger.warning(f"DB 狀態持久化失敗（不影響優化）: {e}")
            return False

    async def restore_db(self) -> bool:
        """從後端數據庫恢復狀態（DB 層 restore）。

        優先級：DB > 文件 checkpoint（DB 更新更及時）。
        後端不可用時降級為文件 checkpoint。

        Returns:
            bool: 是否成功恢復
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.load_agent_state()
            if not data:
                logger.info("DB 無 Agent 狀態記錄")
                return False

            state_json = data.get("stateJson", "{}")
            parsed = json.loads(state_json)

            self.current_iteration = parsed.get("current_iteration", 0)
            self.best_score = parsed.get("best_score", -999)
            self.best_iteration = parsed.get("best_iteration", 0)
            self.best_strategy_id = parsed.get("best_strategy_id")
            self.best_criteria = parsed.get("best_criteria", dict(DEFAULT_CRITERIA))
            self.best_config = parsed.get("best_config", dict(DEFAULT_BACKTEST_CONFIG))
            self.current_criteria = parsed.get("current_criteria", dict(DEFAULT_CRITERIA))
            self.current_config = parsed.get("current_config", dict(DEFAULT_BACKTEST_CONFIG))
            self.current_reflection = parsed.get("current_reflection", "")
            self.current_next_prompt = parsed.get("current_next_prompt", "")

            # 恢復回顧分析結果和當日摘要
            retro_data = parsed.get("last_retrospective")
            if retro_data:
                self.last_retrospective = RetrospectiveResult.from_dict(retro_data)
            self.retrospective_count = parsed.get("retrospective_count", 0)
            digest_data = parsed.get("current_daily_digest")
            if digest_data:
                self.current_daily_digest = DailyDigest.from_dict(digest_data)
            self.daily_digest_date = parsed.get("daily_digest_date", "")

            # 恢復最近迭代摘要
            recent = parsed.get("recent_iterations", [])
            for r in recent:
                self.iterations.append(
                    IterationResult(
                        iteration=r.get("iteration", 0),
                        timestamp="",
                        criteria=r.get("criteria", {}),
                        config={},
                        screener_summary="",
                        backtest_statistics=r.get("backtest_statistics", {}),
                        composite_score=r.get("composite_score", 0),
                    )
                )

            logger.info(
                f"狀態已從 DB 恢復: iteration={self.current_iteration}, "
                f"best_score={self.best_score}, 歷史記錄={len(self.iterations)} 條"
            )
            return True
        except Exception as e:
            logger.warning(f"DB 狀態恢復失敗: {e}")
            return False
