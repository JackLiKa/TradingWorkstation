"""AI 1: 行情分析 — 分析市場環境，輸出市場狀態描述（含形態識別）。

輸入: 市場數據（dashboard summary）、多日市場形態、歷史迭代記錄、上一輪反思
輸出: 市場趨勢分析文本（2-4 句話），含形態判斷和策略建議
範式: 自然語言，包含市場形態、趨勢、波動率、適合策略類型
"""

import json
import logging

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage
from app.agents.stages.market_news import _format_market_breadth, _format_rotation
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.market")

SYSTEM_PROMPT = """你是一個專業的 A 股市場分析師，擅長分析市場環境和趨勢，特別是識別市場形態。

【市場形態類型】
|- 震盪行情：漲跌交替頻繁，幅度有限，無明確方向 → 適合均值回歸策略
|- 上漲中繼：上漲後小幅回調，可能繼續上漲 → 適合趨勢跟蹤策略（逢低加倉）
|- 下跌中繼：下跌後小幅反彈，可能繼續下跌 → 適合防禦策略（減倉/空倉）
|- 上漲趨勢：連續上漲，回撤小 → 適合趨勢跟蹤策略
|- 下跌趨勢：連續下跌，反彈小 → 適合防禦策略

【關鍵原則】
|- 不要只看單日漲跌：連續多日交替漲跌可能是震盪，不是趨勢反轉
|- 形態決定策略：震盪行情用均值回歸，趨勢行情用趨勢跟蹤，下跌中繼要防禦
|- 形態會延續：除非有明確反轉信號，當前形態大概率會延續

【數據真實性鐵律】
|- 只能引用上方 prompt 中「市場數據」「多日市場形態」區塊提供的數據
|- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、市盈率等數值
|- 禁止引用訓練記憶中的 A 股歷史行情、個股數據、政策事件
|- 禁止編造新聞消息或政策動態
|- 所有引用的數值必須能在上方「市場數據」或「多日市場形態」中找到對應來源
|- 如果數據不足，標註「數據不足」而非用編造的數據填充"""

PROMPT_TEMPLATE = """請分析當前 A 股市場環境，識別市場形態並推薦策略。

## 市場數據
{market_data}

## 多日市場形態（最近{regime_days}日）
{regime_text}

## 市場廣度與輪動（最近10日）
{breadth_text}
{rotation_text}

## 歷史優化記錄
{history_text}

## 上一輪反思結論
{prev_reflection}

{few_shot}

## 你的任務
分析當前市場環境（2-3句話），必須包括：
1. **市場形態判斷**：基於上方「多日市場形態」區塊，判斷當前處於哪種形態（震盪/上漲中繼/下跌中繼/上漲趨勢/下跌趨勢），引用多日數據中的交替次數和累計漲跌幅
2. 市場整體趨勢（上漲/下跌/震盪），引用上方「市場數據」中的具體數據（如上漲股票佔比、指數漲跌幅），必須包含「趨勢」一詞
3. 波動率水平（高/中/低），引用上方「市場數據」或「多日市場形態」中的具體數值，必須包含「波動」一詞
4. 適合的策略類型（趨勢跟蹤/均值回歸/防禦等），基於形態判斷和上方數據說明理由，必須包含「策略」一詞

【數據引用要求】
|- 所有引用的數值必須來自上方「市場數據」或「多日市場形態」區塊
|- 禁止編造未在輸入中出現的數據
|- 禁止引用訓練記憶中的 A 股歷史行情
|- 如果某項數據缺失，不要假設它的值
|- 形態判斷必須基於多日數據，不能只看單日

直接輸出分析結果，不要 JSON 格式。控制在 100-200 字。"""


class MarketAnalysisStage(BaseStage):
    """AI 1: 行情分析節點（含市場形態識別）。"""

    def __init__(self):
        super().__init__(stage_name="market_analysis", display_name="AI 1 · 行情分析")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行情情分析。

        kwargs:
            market_data: dict — dashboard summary 數據
            history: list[IterationResult] — 歷史迭代記錄
            prev_reflection: str — 上一輪反思結論
        """
        market_data = kwargs.get("market_data", {})
        history = kwargs.get("history", [])
        prev_reflection = kwargs.get("prev_reflection", "")

        # 獲取多日市場形態
        regime = await market_data_client._compute_market_regime()
        regime_text = _format_regime(regime)
        regime_days = regime.get("metrics", {}).get("days_analyzed", 0)

        # 獲取市場廣度與輪動信號（market_news 已調用過，可復用緩存）
        market_breadth = await market_data_client._get_market_breadth(10)
        rotation = await market_data_client._get_rotation_signals(10)
        breadth_text = _format_market_breadth(market_breadth)
        rotation_text = _format_rotation(rotation)

        # 構建歷史摘要
        history_text = ""
        for h in history[-3:]:
            stats = h.backtest_statistics
            history_text += (
                f"  第{h.iteration}輪: 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"評分={h.composite_score}\n"
            )

        prompt = PROMPT_TEMPLATE.format(
            market_data=json.dumps(market_data, ensure_ascii=False, indent=2, default=str),
            regime_text=regime_text,
            regime_days=regime_days,
            breadth_text=breadth_text,
            rotation_text=rotation_text,
            history_text=history_text if history_text else "無（首輪）",
            prev_reflection=prev_reflection if prev_reflection else "無（首輪）",
            few_shot=get_few_shot("market_analysis"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI1 行情分析] {response[:100]}...")
        return response


def _format_regime(regime: dict) -> str:
    """格式化市場形態數據為 prompt 可讀文本。"""
    if not regime or regime.get("regime_type") == "unknown":
        return "數據不足，無法計算市場形態"

    lines = []
    regime_type = regime.get("regime_type", "unknown")
    description = regime.get("description", "")
    lines.append(f"形態類型: {regime_type}")
    lines.append(f"系統計算描述: {description}")
    lines.append("")

    metrics = regime.get("metrics", {})
    if metrics:
        lines.append("形態指標:")
        lines.append(f"  累計漲跌幅: {metrics.get('total_change', 0)}%")
        lines.append(f"  平均絕對漲跌幅: {metrics.get('avg_abs_change', 0)}%")
        lines.append(f"  波動率(標準差): {metrics.get('volatility', 0)}%")
        lines.append(f"  漲跌交替次數: {metrics.get('alternations', 0)}")
        lines.append(f"  交替率: {metrics.get('alternation_ratio', 0)}")
        lines.append(f"  分析天數: {metrics.get('days_analyzed', 0)}")
        lines.append("")

    multi_day = regime.get("multi_day_data", [])
    if multi_day:
        lines.append("每日明細:")
        for d in multi_day:
            date = d.get("date", "")
            close = d.get("close", 0)
            pct = d.get("pct_chg", 0)
            arrow = "↑" if pct > 0 else "↓" if pct < 0 else "→"
            lines.append(f"  {date}: 收盤{close} {arrow} {pct}%")

    return "\n".join(lines)
