"""監測 AI — 分析異常事件並給出建議。

職責:
1. 定期分析 NodeMonitor 收集的事件和告警
2. 用 LLM 分析異常根因
3. 給出具體的處理建議
4. 檢測後端/API 失敗、LLM 響應變慢等隱性問題

觸發條件:
- 有 CRITICAL 級別告警時立即分析
- 每輪迭代結束後定期分析
- 用戶主動請求分析
"""
import logging
from typing import Any

from app.core.llm_client import llm_client
from app.agents.monitor import node_monitor, AlertLevel

logger = logging.getLogger("agent.monitor_ai")

SYSTEM_PROMPT = """你是一個系統監控 AI，負責分析 AI 優化系統的運行狀態和異常事件。
你需要：
1. 分析異常事件的根因
2. 評估系統健康狀態
3. 給出具體的處理建議
4. 識別潛在的隱性問題（如 LLM 響應變慢、評委過嚴等）

請簡潔、專業地輸出分析結果。"""

ANALYSIS_PROMPT_TEMPLATE = """請分析以下系統監控數據，識別異常並給出建議。

## 運行概況
- run_id: {run_id}
- 總事件數: {total_events}
- 總告警數: {total_alerts}
- 活躍告警: {active_alerts}（嚴重 {critical}，警告 {warning}）

## 活躍告警列表
{alerts_text}

## 節點統計
{node_stats_text}

## 最近事件
{recent_events_text}

## 評分歷史
{score_history}

## 你的任務
1. 分析是否有嚴重問題需要立即處理
2. 識別性能瓶頸（哪個節點最慢）
3. 評估評委是否過嚴或過鬆
4. 給出 2-3 條具體建議

請按以下格式輸出（自然語言，不要 JSON）：

### 系統健康
（1句話總結系統狀態）

### 異常分析
（列出發現的問題及根因）

### 性能瓶頸
（最慢的節點及優化建議）

### 建議操作
（2-3 條具體建議）"""


class MonitorAI:
    """監測 AI — 分析異常並給出建議。"""

    async def analyze(self) -> dict[str, Any]:
        """分析當前監控狀態，返回分析結果。

        Returns:
            {
                "analysis": str,  # AI 分析文本
                "health": str,  # "healthy" | "warning" | "critical"
                "suggestions": list[str],  # 建議列表
            }
        """
        status = node_monitor.get_status()

        # 如果沒有事件，不需要分析
        if status["total_events"] == 0:
            return {
                "analysis": "系統尚未運行，無監控數據。",
                "health": "idle",
                "suggestions": [],
            }

        # 構建告警文本
        alerts_text = ""
        for a in status["active_alert_list"]:
            alerts_text += f"  [{a['level']}] {a['category']}: {a['message']}\n"
        if not alerts_text:
            alerts_text = "  無活躍告警"

        # 構建節點統計文本
        node_stats_text = ""
        for node_id, s in status["node_stats"].items():
            node_stats_text += (
                f"  {node_id}: 運行{s['total_runs']}次, "
                f"平均{s['avg_duration_ms']}ms, "
                f"最大{s['max_duration_ms']}ms, "
                f"失敗{s['failures']}次, "
                f"重試{s['retries']}次, "
                f"評委均分{s['avg_judge_score']}\n"
            )
        if not node_stats_text:
            node_stats_text = "  無統計數據"

        # 構建最近事件文本
        recent_events_text = ""
        for e in status["recent_events"][-10:]:
            recent_events_text += f"  [{e['timestamp'][:19]}] {e['node_id']}: {e['status']}"
            if e.get("duration_ms"):
                recent_events_text += f" ({e['duration_ms']}ms)"
            if e.get("error"):
                recent_events_text += f" ERROR: {e['error'][:50]}"
            recent_events_text += "\n"

        # 評分歷史
        score_history = str(status["score_history"]) if status["score_history"] else "無"

        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            run_id=status["run_id"] or "無",
            total_events=status["total_events"],
            total_alerts=status["total_alerts"],
            active_alerts=status["active_alerts"],
            critical=status["critical_alerts"],
            warning=status["warning_alerts"],
            alerts_text=alerts_text,
            node_stats_text=node_stats_text,
            recent_events_text=recent_events_text,
            score_history=score_history,
        )

        # 健康狀態
        if status["critical_alerts"] > 0:
            health = "critical"
        elif status["warning_alerts"] > 0:
            health = "warning"
        else:
            health = "healthy"

        try:
            response = await llm_client.analyze(prompt, SYSTEM_PROMPT)
            logger.info(f"[MonitorAI] 分析完成，健康狀態: {health}")
            return {
                "analysis": response,
                "health": health,
                "suggestions": self._extract_suggestions(response),
            }
        except Exception as e:
            logger.warning(f"[MonitorAI] LLM 分析失敗: {e}")
            return {
                "analysis": f"監測 AI 不可用: {e}\n\n基於規則的狀態: 健康={health}, 告警={status['active_alerts']}",
                "health": health,
                "suggestions": self._rule_based_suggestions(status),
            }

    def _extract_suggestions(self, analysis: str) -> list[str]:
        """從 AI 分析文本中提取建議。"""
        suggestions = []
        in_suggestions = False
        for line in analysis.split("\n"):
            line = line.strip()
            if "建議操作" in line or "建議" in line and "###" in line:
                in_suggestions = True
                continue
            if in_suggestions:
                if line.startswith("###"):
                    break
                if line and not line.startswith("###"):
                    # 去掉編號前綴
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean:
                        suggestions.append(clean)
        return suggestions[:5]  # 最多 5 條

    def _rule_based_suggestions(self, status: dict) -> list[str]:
        """基於規則的建議（LLM 不可用時的 fallback）。"""
        suggestions = []
        for alert in status["active_alert_list"]:
            if alert["suggestion"]:
                suggestions.append(f"{alert['category']}: {alert['suggestion']}")
        if not suggestions and status["active_alerts"] == 0:
            suggestions.append("系統運行正常，無需操作")
        return suggestions[:5]


# 全局監測 AI 實例
monitor_ai = MonitorAI()
