"""評分計算 — 市場語境感知的綜合評分和評委評分邏輯。

評分設計原則（參考量化交易最佳實踐）：
1. 風險調整收益優先於絕對收益（Sharpe/Calmar/Sortino）
2. 基準相對表現是核心（alpha/excess return/information ratio）
3. 交易質量反映策略真實性（勝率/盈虧比/交易頻率）
4. 市場語境決定空倉價值（大跌時空倉=防禦，上漲時空倉=失效）
5. 樣本充分性避免小樣本過擬合（≥30 筆交易才統計顯著）
"""

from typing import Any


def compute_composite_score(stats: dict[str, Any]) -> float:
    """計算綜合評分 — 市場語境感知的靈活評分機制。

    評分維度（有交易策略）：
    1. 收益表現 (20%) — 絕對收益，正收益 0-100，負收益 -50-0
    2. 回撤控制 (15%) — 回撤 0%=100分，回撤 50%+=0分
    3. 夏普比率 (15%) — 夏普 0=50分，2+=100分，<0=0分
    4. Calmar 比率 (10%) — 年化收益/最大回撤，衡量每承受1%回撤的年化回報
    5. 超額收益 (15%) — 相對基準的 alpha，正超額 0-100，負超額 -30-0
    6. 交易質量 (15%) — 勝率(40%) + 盈虧比(30%) + 交易活躍度(30%)
    7. 樣本充分性 (7%) — 交易筆數 ≥30=100分，<30 線性衰減
    8. 信息比率 (3%) — 主動管理能力，IR 0=50分，1+=100分

    特殊處理（0 交易策略）：
    當 totalTrades=0 且 benchmarkReturn 存在時，啟用市場語境感知評分：
    - 市場大跌（基準 < -5%）+ 空倉 = 主動防禦 → 30-50 分
      （基準跌越多，空倉越有價值，但低於有交易的好策略）
    - 市場小跌（基準 -5%~0%）+ 空倉 = 尚可防禦 → 15-30 分
    - 市場震盪（基準 0%~5%）+ 空倉 = 無作為 → 5-10 分
    - 市場上漲（基準 > 5%）+ 空倉 = 被動失效 → 0-5 分

    向後兼容：當 benchmarkReturn 不存在時，0 交易策略走正常公式（不觸發特殊處理）。

    Args:
        stats: 回測統計字典，需包含 totalReturn / maxDrawdown / sharpe 等字段

    Returns:
        float: 綜合評分（0-100 區間，保留兩位小數）
    """
    total_return = stats.get("totalReturn", 0)
    max_drawdown = stats.get("maxDrawdown", 0)
    sharpe = stats.get("sharpe", 0)
    excess_return = stats.get("excessReturn", 0)
    total_trades = stats.get("totalTrades", 0)
    annual_return = stats.get("annualReturn", 0)
    benchmark_return = stats.get("benchmarkReturn")
    win_rate = stats.get("winRate", 0)
    profit_loss_ratio = stats.get("profitLossRatio", 0)
    information_ratio = stats.get("informationRatio", 0)

    # === 0 交易策略：市場語境感知評分 ===
    # 僅當 benchmarkReturn 存在時啟用（確保真實回測數據，測試 mock 不受影響）
    if total_trades == 0 and benchmark_return is not None:
        return _score_zero_trade_strategy(benchmark_return, excess_return)

    # === 有交易策略（或向後兼容的 0 交易無基準數據）：正常多維評分 ===
    return _score_active_strategy(
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        excess_return=excess_return,
        total_trades=total_trades,
        annual_return=annual_return,
        win_rate=win_rate,
        profit_loss_ratio=profit_loss_ratio,
        information_ratio=information_ratio,
    )


def _score_zero_trade_strategy(benchmark_return: float, excess_return: float) -> float:
    """0 交易策略的市場語境感知評分。

    空倉策略的價值完全取決於市場環境：
    - 市場大跌時空倉 = 主動防禦，避免損失 → 給予合理分數
    - 市場上漲時空倉 = 被動失效，錯過行情 → 給予極低分數

    分數區間設計原則：
    - 最高 ~50 分（基準跌 10%+ 時），低於有交易的好策略（通常 60+）
    - 最低 0 分（基準大漲時），明確懲罰被動失效
    - 分數與基準跌幅正相關，反映空倉的「避險價值」
    """
    if benchmark_return < -5:
        # 市場大跌：空倉是合理的防禦策略
        # 基礎分 30 + 避險獎勵（基準跌越多，空倉越值錢，每跌 1% 加 2 分，上限 20）
        defensive_bonus = min(abs(benchmark_return) * 2, 20)
        composite = 30 + defensive_bonus
    elif benchmark_return < 0:
        # 市場小跌：空倉尚可，但避險價值有限
        composite = 15 + abs(benchmark_return) * 3
    elif benchmark_return < 5:
        # 市場震盪/微漲：空倉無作為，既未避險也未獲利
        composite = max(5, 10 - benchmark_return * 1)
    else:
        # 市場大漲：空倉完全錯過行情，屬被動失效
        composite = max(0, 5 - (benchmark_return - 5) * 0.5)

    return round(min(max(composite, 0), 100), 2)


def _score_active_strategy(
    total_return: float,
    max_drawdown: float,
    sharpe: float,
    excess_return: float,
    total_trades: int,
    annual_return: float,
    win_rate: float,
    profit_loss_ratio: float,
    information_ratio: float,
) -> float:
    """有交易策略的多維評分（也用於向後兼容的無基準 0 交易情況）。"""
    # 收益分數：正收益 0-100，負收益 -50-0
    return_score = min(max(total_return * 1.25, -50), 100)

    # 回撤分數：回撤 0% = 100分，回撤 50%+ = 0分
    drawdown_score = max(100 - max_drawdown * 2, 0)

    # 夏普分數：夏普 0 = 50分，夏普 2+ = 100分，夏普 < 0 = 0分
    sharpe_score = min(max(sharpe * 25 + 50, 0), 100)

    # Calmar 分數：年化收益/最大回撤，Calmar 0 = 0分，Calmar 3+ = 100分
    calmar = annual_return / max_drawdown if max_drawdown > 0 else (100.0 if annual_return > 0 else 0)
    calmar_score = min(max(calmar * 33.3, 0), 100)

    # 超額收益分數：正超額 0-100，負超額 -30-0
    excess_score = min(max(excess_return * 3, -30), 100)

    # 交易質量分數：勝率(40%) + 盈虧比(30%) + 交易活躍度(30%)
    trade_quality_score = _compute_trade_quality_score(
        total_trades, win_rate, profit_loss_ratio
    )

    # 樣本量分數：交易筆數 <30 時懲罰（小樣本統計不顯著）
    # ≥30 筆 = 100 分，<30 筆線性衰減至 0
    sample_score = min(total_trades / 30 * 100, 100) if total_trades > 0 else 0

    # 信息比率分數：IR 0 = 50分，IR 1+ = 100分，IR < 0 = 0分
    # 信息比率衡量策略相對基準的主動管理能力
    ir_score = _compute_ir_score(information_ratio)

    composite = (
        return_score * 0.20
        + drawdown_score * 0.15
        + sharpe_score * 0.15
        + calmar_score * 0.10
        + excess_score * 0.15
        + trade_quality_score * 0.15
        + sample_score * 0.07
        + ir_score * 0.03
    )
    return round(composite, 2)


def _compute_trade_quality_score(
    total_trades: int, win_rate: float, profit_loss_ratio: float
) -> float:
    """計算交易質量分數 — 勝率(40%) + 盈虧比(30%) + 交易活躍度(30%)。

    勝率：衡量策略判斷正確的比例
    - 60%+ = 100分（優秀），50% = 50分（中等），<30% = 0分（差）
    盈虧比：衡量盈利交易平均賺的 vs 虧損交易平均虧的
    - 2.0+ = 100分（優秀），1.0 = 50分（中等），<0.5 = 0分（差）
    交易活躍度：衡量策略是否在運作
    - ≥10 筆 = 100分，0 筆 = 0分
    """
    # 勝率分數：30% 以下 = 0分，60%+ = 100分，線性插值
    if win_rate > 0:
        win_rate_score = min(max((win_rate - 30) * 2.5, 0), 100)
    else:
        win_rate_score = 50  # 無數據時給中等分

    # 盈虧比分數：0.5 以下 = 0分，2.0+ = 100分，線性插值
    if profit_loss_ratio > 0:
        pl_ratio_score = min(max((profit_loss_ratio - 0.5) * 50, 0), 100)
    else:
        pl_ratio_score = 50  # 無數據時給中等分

    # 交易活躍度分數：0 筆 = 0 分，≥10 筆 = 100 分
    trade_activity_score = min(total_trades * 10, 100)

    return win_rate_score * 0.40 + pl_ratio_score * 0.30 + trade_activity_score * 0.30


def _compute_ir_score(information_ratio: float) -> float:
    """計算信息比率分數 — 衡量策略的主動管理能力。

    信息比率 = alpha / tracking_error，衡量每承擔1單位追蹤誤差獲得的超額收益。
    - IR ≥ 1 = 100分（優秀的主動管理）
    - IR = 0 = 50分（中性）
    - IR ≤ -0.5 = 0分（嚴重跑輸基準）
    """
    if information_ratio == 0:
        return 50.0  # 無數據或恰好為 0 時給中等分
    return min(max(information_ratio * 50 + 50, 0), 100)
