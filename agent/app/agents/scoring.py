"""評分計算 — 綜合評分和評委評分邏輯。"""

from typing import Any


def compute_composite_score(stats: dict[str, Any]) -> float:
    """計算綜合評分: 收益(35%) + 回撤控制(25%) + 夏普(20%) + 超額收益(10%) + 交易活躍度(10%)。

    收益: totalReturn（正數加權，負數懲罰）
    回撤: -maxDrawdown（回撤越小越好）
    夏普: sharpe（越大越好）
    超額收益: excessReturn（相對基準的 alpha，鼓勵主動管理貢獻）
    交易活躍度: totalTrades（0 筆交易懲罰，避免「假穩健」空倉策略被獎勵）

    Args:
        stats: 回測統計字典，需包含 totalReturn / maxDrawdown / sharpe 字段

    Returns:
        float: 綜合評分（0-100 區間，保留兩位小數）
    """
    total_return = stats.get("totalReturn", 0)
    max_drawdown = stats.get("maxDrawdown", 0)
    sharpe = stats.get("sharpe", 0)
    excess_return = stats.get("excessReturn", 0)
    total_trades = stats.get("totalTrades", 0)

    # 收益分數：正收益 0-100，負收益 -50-0
    return_score = min(max(total_return * 2, -50), 100)
    # 回撤分數：回撤 0% = 100分，回撤 50%+ = 0分
    drawdown_score = max(100 - max_drawdown * 2, 0)
    # 夏普分數：夏普 0 = 50分，夏普 2+ = 100分，夏普 < 0 = 0分
    sharpe_score = min(max(sharpe * 25 + 50, 0), 100)
    # 超額收益分數：正超額 0-100，負超額 -30-0（鼓勵主動管理 alpha）
    excess_score = min(max(excess_return * 3, -30), 100)
    # 交易活躍度分數：0 筆交易 = 0 分（懲罰空倉「假穩健」），≥10 筆 = 100 分
    # 避免策略通過不交易來規避回撤
    trade_score = min(total_trades * 10, 100)

    composite = (
        return_score * 0.35
        + drawdown_score * 0.25
        + sharpe_score * 0.20
        + excess_score * 0.10
        + trade_score * 0.10
    )
    return round(composite, 2)
