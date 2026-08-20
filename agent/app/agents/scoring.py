"""評分計算 — 綜合評分和評委評分邏輯。"""

from typing import Any


def compute_composite_score(stats: dict[str, Any]) -> float:
    """計算綜合評分: 收益(40%) + 回撤控制(30%) + 夏普(30%)。

    收益: totalReturn（正數加權，負數懲罰）
    回撤: -maxDrawdown（回撤越小越好）
    夏普: sharpe（越大越好）

    Args:
        stats: 回測統計字典，需包含 totalReturn / maxDrawdown / sharpe 字段

    Returns:
        float: 綜合評分（0-100 區間，保留兩位小數）
    """
    total_return = stats.get("totalReturn", 0)
    max_drawdown = stats.get("maxDrawdown", 0)
    sharpe = stats.get("sharpe", 0)

    # 收益分數：正收益 0-100，負收益 -50-0
    return_score = min(max(total_return * 2, -50), 100)
    # 回撤分數：回撤 0% = 100分，回撤 50%+ = 0分
    drawdown_score = max(100 - max_drawdown * 2, 0)
    # 夏普分數：夏普 0 = 50分，夏普 2+ = 100分，夏普 < 0 = 0分
    sharpe_score = min(max(sharpe * 25 + 50, 0), 100)

    composite = return_score * 0.4 + drawdown_score * 0.3 + sharpe_score * 0.3
    return round(composite, 2)
