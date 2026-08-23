"""評分計算 — 綜合評分和評委評分邏輯。"""

from typing import Any


def compute_composite_score(stats: dict[str, Any]) -> float:
    """計算綜合評分: 收益(25%) + 回撤控制(20%) + 夏普(15%) + Calmar(15%) + 超額收益(10%) + 交易活躍度(10%) + 樣本量懲罰(5%)。

    改進點（vs 舊公式）：
    1. 收益權重從 35% 降至 25%，避免高收益策略掩蓋回撤風險
    2. 新增 Calmar 比率（年化收益/最大回撤）15% — 直接衡量風險調整後收益
    3. 回撤權重從 25% 降至 20%，但新增 Calmar 彌補
    4. 夏普權重從 20% 降至 15%
    5. 新增樣本量懲罰 5% — 回測交易筆數 <30 時懲罰，避免小樣本過擬合
    6. 收益封頂從 50% 改為 80%，避免中等收益策略和極端收益策略拿一樣的分數

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
    annual_return = stats.get("annualReturn", 0)

    # 收益分數：正收益 0-100（80%封頂），負收益 -50-0
    return_score = min(max(total_return * 1.25, -50), 100)

    # 回撤分數：回撤 0% = 100分，回撤 50%+ = 0分
    drawdown_score = max(100 - max_drawdown * 2, 0)

    # 夏普分數：夏普 0 = 50分，夏普 2+ = 100分，夏普 < 0 = 0分
    sharpe_score = min(max(sharpe * 25 + 50, 0), 100)

    # Calmar 分數：年化收益/最大回撤，Calmar 0 = 0分，Calmar 3+ = 100分
    # Calmar 直接衡量「每承受1%回撤能獲得多少年化收益」，比夏普更直觀
    calmar = annual_return / max_drawdown if max_drawdown > 0 else (100.0 if annual_return > 0 else 0)
    calmar_score = min(max(calmar * 33.3, 0), 100)

    # 超額收益分數：正超額 0-100，負超額 -30-0
    excess_score = min(max(excess_return * 3, -30), 100)

    # 交易活躍度分數：0 筆交易 = 0 分，≥10 筆 = 100 分
    trade_score = min(total_trades * 10, 100)

    # 樣本量懲罰分數：交易筆數 <30 時懲罰（小樣本統計不顯著）
    # ≥30 筆 = 100 分，<30 筆線性衰減至 0
    sample_score = min(total_trades / 30 * 100, 100) if total_trades > 0 else 0

    composite = (
        return_score * 0.25
        + drawdown_score * 0.20
        + sharpe_score * 0.15
        + calmar_score * 0.15
        + excess_score * 0.10
        + trade_score * 0.10
        + sample_score * 0.05
    )
    return round(composite, 2)
