"""節點生命周期監控 + 異常檢測（AOP 可觀測性核心）。

職責:
1. 記錄每個節點的生命周期事件（start/end/duration/status）
2. 檢測異常：超時、失敗、重試循環、中斷
3. 維護運行歷史（可查詢、可追溯）
4. 暴露狀態給 API 和前端

AOP 設計:
- NodeEvent: 數據類，記錄單個節點事件
- NodeMonitor: 單例，收集所有節點事件，檢測異常
- 通過 BaseStage 的 pre/post 鉤子自動記錄，不侵入業務邏輯

異常檢測規則:
- 節點執行時間超過閾值 → TIMEOUT_WARNING / TIMEOUT_CRITICAL
- 節點失敗 → NODE_FAILED
- 評委連續拒絕 ≥ 2 次 → JUDGE_REJECTION_LOOP
- 優化循環長時間無進展 → STALL_DETECTED
- 異步任務被取消 → TASK_CANCELLED
"""

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("agent.monitor")


class NodeStatus(str, Enum):
    """節點狀態。"""

    PENDING = "pending"
    RUNNING = "running"
    JUDGING = "judging"
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AlertLevel(str, Enum):
    """告警級別。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class NodeEvent:
    """單個節點的生命周期事件。"""

    run_id: str  # 優化運行 ID（每次 start_optimization 生成一個）
    iteration: int  # 迭代輪次
    node_id: str  # 節點 ID（如 "market_news"）
    node_type: str  # "ai" | "backtest" | "judge"
    status: str  # NodeStatus 值
    timestamp: str  # ISO 格式時間戳
    duration_ms: int = 0  # 耗時
    attempts: int = 1  # 嘗試次數
    judge_score: float = 0.0  # 評委分數
    judge_passed: bool = True  # 評委是否通過
    error: str | None = None  # 錯誤信息
    metadata: dict[str, Any] = field(default_factory=dict)  # 額外元數據

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Alert:
    """異常告警。"""

    alert_id: str  # 唯一 ID
    level: str  # AlertLevel 值
    category: str  # 異常類別（如 "timeout", "failure", "stall"）
    node_id: str  # 相關節點 ID
    iteration: int  # 相關迭代
    message: str  # 告警信息
    suggestion: str = ""  # 建議處理方式
    timestamp: str = ""
    resolved: bool = False  # 是否已解決

    def to_dict(self) -> dict:
        return asdict(self)


class NodeMonitor:
    """節點監控器 — 單例，收集所有節點事件並檢測異常。

    AOP 紀錄點:
    - record_start(): 節點開始執行
    - record_judge(): 評委開始評分
    - record_end(): 節點執行結束
    - record_cancel(): 節點被取消
    - detect_anomalies(): 檢測異常並生成告警
    """

    # 節點超時閾值（毫秒）
    TIMEOUT_WARNING_MS = 120_000  # 2 分鐘 → warning
    TIMEOUT_CRITICAL_MS = 300_000  # 5 分鐘 → critical

    # 評委連續拒絕閾值
    JUDGE_REJECTION_THRESHOLD = 2

    # 無進展檢測：連續 N 輪評分未提升
    STALL_ITERATIONS = 5

    def __init__(self):
        self._events: list[NodeEvent] = []
        self._alerts: list[Alert] = []
        self._run_id: str = ""
        self._current_iteration: int = 0
        # 節點開始時間（用於計算耗時）
        self._node_start_times: dict[str, float] = {}
        # 評委連續拒絕計數
        self._judge_rejections: dict[str, int] = {}
        # 歷史評分（用於無進展檢測）
        self._score_history: list[float] = []
        self._alert_counter = 0

    @property
    def run_id(self) -> str:
        return self._run_id

    def start_run(self) -> str:
        """開始新的優化運行，生成 run_id。"""
        self._run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._events.clear()
        self._alerts.clear()
        self._current_iteration = 0
        self._node_start_times.clear()
        self._judge_rejections.clear()
        self._score_history.clear()
        logger.info(f"[Monitor] 新運行開始: run_id={self._run_id}")
        return self._run_id

    def end_run(self):
        """結束當前運行。"""
        logger.info(
            f"[Monitor] 運行結束: run_id={self._run_id}, 事件數={len(self._events)}, 告警數={len(self._alerts)}"
        )
        self._run_id = ""

    def set_iteration(self, iteration: int):
        """設置當前迭代輪次。"""
        self._current_iteration = iteration

    # === AOP 記錄點 ===

    def record_start(self, node_id: str, node_type: str = "ai"):
        """記錄節點開始執行。"""
        event_key = f"{self._current_iteration}_{node_id}"
        self._node_start_times[event_key] = time.time()
        event = NodeEvent(
            run_id=self._run_id,
            iteration=self._current_iteration,
            node_id=node_id,
            node_type=node_type,
            status=NodeStatus.RUNNING.value,
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)
        logger.debug(f"[Monitor] 節點開始: {node_id} (iter={self._current_iteration})")

    def record_judge(self, node_id: str):
        """記錄評委開始評分。"""
        event = NodeEvent(
            run_id=self._run_id,
            iteration=self._current_iteration,
            node_id=node_id,
            node_type="judge",
            status=NodeStatus.JUDGING.value,
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)

    def record_end(
        self,
        node_id: str,
        node_type: str = "ai",
        duration_ms: int = 0,
        attempts: int = 1,
        judge_score: float = 0.0,
        judge_passed: bool = True,
        error: str | None = None,
    ):
        """記錄節點執行結束。"""
        status = (
            NodeStatus.FAILED.value
            if error
            else (NodeStatus.PASSED.value if judge_passed else NodeStatus.RETRYING.value)
        )
        event = NodeEvent(
            run_id=self._run_id,
            iteration=self._current_iteration,
            node_id=node_id,
            node_type=node_type,
            status=status,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            attempts=attempts,
            judge_score=judge_score,
            judge_passed=judge_passed,
            error=error,
        )
        self._events.append(event)

        # 更新評委拒絕計數
        if not judge_passed and node_type == "ai":
            self._judge_rejections[node_id] = self._judge_rejections.get(node_id, 0) + 1
        elif judge_passed:
            self._judge_rejections.pop(node_id, None)

        # 異常檢測
        self._detect_timeout(node_id, duration_ms)
        self._detect_failure(node_id, error)
        self._detect_judge_loop(node_id)

        logger.debug(
            f"[Monitor] 節點結束: {node_id} (status={status}, duration={duration_ms}ms, "
            f"score={judge_score}, attempts={attempts})"
        )

    def record_cancel(self, node_id: str):
        """記錄節點被取消。"""
        event = NodeEvent(
            run_id=self._run_id,
            iteration=self._current_iteration,
            node_id=node_id,
            node_type="ai",
            status=NodeStatus.CANCELLED.value,
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)
        self._add_alert(
            level=AlertLevel.WARNING,
            category="cancelled",
            node_id=node_id,
            message=f"節點 {node_id} 在第 {self._current_iteration} 輪被取消",
            suggestion="檢查是否用戶主動停止，或任務超時",
        )

    def record_score(self, score: float):
        """記錄迭代評分（用於無進展檢測）。"""
        self._score_history.append(score)
        self._detect_stall()

    # === 異常檢測 ===

    def _detect_timeout(self, node_id: str, duration_ms: int):
        """檢測節點超時。"""
        if duration_ms >= self.TIMEOUT_CRITICAL_MS:
            self._add_alert(
                level=AlertLevel.CRITICAL,
                category="timeout",
                node_id=node_id,
                message=f"節點 {node_id} 執行時間 {duration_ms / 1000:.1f}s 超過臨界閾值 {self.TIMEOUT_CRITICAL_MS / 1000:.0f}s",
                suggestion="檢查 LLM 響應時間、網絡連接、或考慮降低 prompt 長度",
            )
        elif duration_ms >= self.TIMEOUT_WARNING_MS:
            self._add_alert(
                level=AlertLevel.WARNING,
                category="timeout",
                node_id=node_id,
                message=f"節點 {node_id} 執行時間 {duration_ms / 1000:.1f}s 超過警告閾值 {self.TIMEOUT_WARNING_MS / 1000:.0f}s",
                suggestion="監控是否持續變慢，可能需要優化 prompt",
            )

    def _detect_failure(self, node_id: str, error: str | None):
        """檢測節點失敗。"""
        if error:
            self._add_alert(
                level=AlertLevel.CRITICAL,
                category="failure",
                node_id=node_id,
                message=f"節點 {node_id} 執行失敗: {error[:200]}",
                suggestion="查看錯誤堆棧，檢查 LLM 連接、後端 API 可用性",
            )

    def _detect_judge_loop(self, node_id: str):
        """檢測評委連續拒絕循環。"""
        rejections = self._judge_rejections.get(node_id, 0)
        if rejections >= self.JUDGE_REJECTION_THRESHOLD:
            self._add_alert(
                level=AlertLevel.WARNING,
                category="judge_loop",
                node_id=node_id,
                message=f"節點 {node_id} 評委連續拒絕 {rejections} 次，可能存在 prompt 質量問題",
                suggestion="檢查 prompt 是否清晰，或放寬評委閾值",
            )

    def _detect_stall(self):
        """檢測優化無進展。"""
        if len(self._score_history) < self.STALL_ITERATIONS:
            return
        recent = self._score_history[-self.STALL_ITERATIONS :]
        if max(recent) - min(recent) < 1.0:  # 5 輪內評分變化 < 1 分
            self._add_alert(
                level=AlertLevel.WARNING,
                category="stall",
                node_id="optimizer",
                message=f"優化已連續 {self.STALL_ITERATIONS} 輪無顯著進展（評分變化 < 1.0）",
                suggestion="考慮調整探索策略、擴大參數搜索範圍，或停止優化",
            )

    def _add_alert(
        self,
        level: AlertLevel,
        category: str,
        node_id: str,
        message: str,
        suggestion: str = "",
    ):
        """添加告警。"""
        self._alert_counter += 1
        alert = Alert(
            alert_id=f"alert_{self._alert_counter:04d}",
            level=level.value,
            category=category,
            node_id=node_id,
            iteration=self._current_iteration,
            message=message,
            suggestion=suggestion,
            timestamp=datetime.now().isoformat(),
        )
        self._alerts.append(alert)
        log_msg = f"[Monitor] 告警 [{level.value}] {category}: {message}"
        if level == AlertLevel.CRITICAL:
            logger.error(log_msg)
        elif level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def resolve_alert(self, alert_id: str):
        """標記告警為已解決。"""
        for a in self._alerts:
            if a.alert_id == alert_id:
                a.resolved = True
                break

    # === 查詢接口 ===

    def get_status(self) -> dict[str, Any]:
        """獲取監控狀態摘要。"""
        active_alerts = [a for a in self._alerts if not a.resolved]
        critical_count = sum(1 for a in active_alerts if a.level == AlertLevel.CRITICAL.value)
        warning_count = sum(1 for a in active_alerts if a.level == AlertLevel.WARNING.value)

        # 最近事件（最後 20 個）
        recent_events = [e.to_dict() for e in self._events[-20:]]

        # 節點統計
        node_stats = self._compute_node_stats()

        return {
            "run_id": self._run_id,
            "total_events": len(self._events),
            "total_alerts": len(self._alerts),
            "active_alerts": len(active_alerts),
            "critical_alerts": critical_count,
            "warning_alerts": warning_count,
            "recent_events": recent_events,
            "active_alert_list": [a.to_dict() for a in active_alerts[-10:]],
            "node_stats": node_stats,
            "score_history": self._score_history[-20:],
        }

    def get_all_events(self, limit: int = 500) -> list[dict[str, Any]]:
        """獲取全部節點事件（用於時間軸可視化）。

        Args:
            limit: 最多返回的事件數（從最新開始倒序）
        """
        return [e.to_dict() for e in self._events[-limit:]]

    def get_timeline(self) -> dict[str, Any]:
        """獲取結構化時間軸數據（按迭代分組，用於 Gantt 圖）。

        返回格式:
        {
            "iterations": [
                {
                    "iteration": 1,
                    "nodes": [
                        {
                            "node_id": "market_news",
                            "node_type": "ai",
                            "start_time": "2026-08-20T10:00:00",
                            "end_time": "2026-08-20T10:00:05",
                            "duration_ms": 5000,
                            "status": "passed",
                            "judge_score": 75.0,
                            "attempts": 1,
                        },
                        ...
                    ]
                },
                ...
            ],
            "node_definitions": [...],  # 節點元數據
        }
        """
        # 按迭代分組
        iterations_map: dict[int, list[dict[str, Any]]] = {}
        for event in self._events:
            if event.status in (
                NodeStatus.PASSED.value,
                NodeStatus.FAILED.value,
                NodeStatus.RETRYING.value,
                NodeStatus.TIMEOUT.value,
                NodeStatus.CANCELLED.value,
            ):
                it = event.iteration
                if it not in iterations_map:
                    iterations_map[it] = []
                iterations_map[it].append(
                    {
                        "node_id": event.node_id,
                        "node_type": event.node_type,
                        "timestamp": event.timestamp,
                        "duration_ms": event.duration_ms,
                        "status": event.status,
                        "judge_score": event.judge_score,
                        "judge_passed": event.judge_passed,
                        "attempts": event.attempts,
                        "error": event.error,
                    }
                )

        iterations = [{"iteration": it, "nodes": nodes} for it, nodes in sorted(iterations_map.items())]

        # 節點定義（順序固定）
        node_defs = [
            {"id": "market_news", "label": "行情新聞", "type": "ai", "order": 0},
            {"id": "industry_analysis", "label": "行業篩選", "type": "ai", "order": 1},
            {"id": "market_analysis", "label": "行情分析", "type": "ai", "order": 2},
            {"id": "strategy_generation", "label": "策略生成", "type": "ai", "order": 3},
            {"id": "backtest", "label": "回測運行", "type": "backtest", "order": 4},
            {"id": "backtest_reflection", "label": "回測反思", "type": "ai", "order": 5},
            {"id": "prompt_generation", "label": "提示詞生成", "type": "ai", "order": 6},
        ]

        return {
            "iterations": iterations,
            "node_definitions": node_defs,
            "total_iterations": len(iterations),
            "run_id": self._run_id,
        }

    def _compute_node_stats(self) -> dict[str, dict]:
        """計算各節點的統計信息。"""
        stats: dict[str, dict] = {}
        for event in self._events:
            if event.status in (NodeStatus.PASSED.value, NodeStatus.FAILED.value, NodeStatus.RETRYING.value):
                if event.node_id not in stats:
                    stats[event.node_id] = {
                        "total_runs": 0,
                        "total_duration_ms": 0,
                        "avg_duration_ms": 0,
                        "max_duration_ms": 0,
                        "failures": 0,
                        "retries": 0,
                        "avg_judge_score": 0,
                        "judge_scores": [],
                    }
                s = stats[event.node_id]
                s["total_runs"] += 1
                s["total_duration_ms"] += event.duration_ms
                s["max_duration_ms"] = max(s["max_duration_ms"], event.duration_ms)
                if event.status == NodeStatus.FAILED.value:
                    s["failures"] += 1
                if event.status == NodeStatus.RETRYING.value or event.attempts > 1:
                    s["retries"] += 1
                if event.judge_score > 0:
                    s["judge_scores"].append(event.judge_score)

        # 計算平均值
        for s in stats.values():
            if s["total_runs"] > 0:
                s["avg_duration_ms"] = s["total_duration_ms"] // s["total_runs"]
            if s["judge_scores"]:
                s["avg_judge_score"] = round(sum(s["judge_scores"]) / len(s["judge_scores"]), 1)

        return stats


# 全局監控器單例
node_monitor = NodeMonitor()
