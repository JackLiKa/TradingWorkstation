"""市場形態自適應策略指引 — 根據牛/熊/震盪市調整策略取向。

核心思想：
- 牛市（trending_up / continuation_up）→ 進攻：多倉位、放寬止損、高動量選股、快調倉
- 熊市（trending_down / continuation_down）→ 防禦/空倉：減倉位、嚴止損、低波動/高紅利、慢調倉
- 震盪市（oscillation）→ 尋找強勢機會：中等倉位、均值回歸、大振幅選股、短調倉

本模組提供：
1. get_regime_strategy_guidance() — 返回結構化的策略指引文本（注入 strategy_generation prompt）
2. get_regime_config_adjustments() — 返回 config 參數調修建議（供 optimizer 動態調整 config）
3. get_regime_summary() — 返回形態摘要（供 market_analysis 傳遞）
"""

import logging
from typing import Any

logger = logging.getLogger("agent.regime_strategy")


# === 形態 → 策略取向映射 ===

REGIME_STRATEGY_MAP: dict[str, dict[str, Any]] = {
    "trending_up": {
        "label": "牛市上漲趨勢",
        "stance": "進攻",
        "description": "連續上漲，回撤小，趨勢明確。應積極進攻，捕捉強勢股，放寬止損讓利潤奔跑。",
        "criteria_guidance": {
            "minPctChange": "提高至 2-5（篩選強勢上漲股）",
            "minReturn20": "提高至 5-15（20日漲幅強勢）",
            "minTurn": "提高至 3-5（高換手=資金活躍）",
            "minVolumeRatio": "提高至 1.2-2.0（放量上漲）",
            "priceAboveMa5": "true（站上5日均線）",
            "priceAboveMa20": "true（站上20日均線）",
            "ma5AboveMa20": "true（均線多頭排列）",
            "macdCrossSignal": "golden_cross（MACD金叉）",
            "maxRsi14": "可放寬至 80（強勢股RSI偏高正常）",
            "maxAmplitude": "放寬至 8-12（允許大波動）",
            "industries": "聚焦景氣度≥65的強勢行業（最多3個）",
        },
        "config_adjustments": {
            "maxPositions": 8,        # 牛市多持倉
            "stopLossPct": 10,        # 放寬止損，讓利潤奔跑
            "takeProfitPct": None,    # 不設止盈，趨勢跟蹤
            "rebalanceInterval": 3,   # 快調倉，及時換強
            "holdingPeriod": 7,       # 短持有，快換股
        },
        "risk_rules": [
            "牛市核心：讓利潤奔跑，不要過早止盈",
            "止損放寬至 10%，避免被正常回調洗出",
            "倉位上限 8 個，分散捕捉多個強勢板塊",
            "優先選擇放量突破、均線多頭排列的強勢股",
            "3日調倉一次，及時換入新強勢股",
        ],
    },
    "continuation_up": {
        "label": "牛市上漲中繼",
        "stance": "偏進攻",
        "description": "上漲後小幅回調，可能繼續上漲。逢低加倉，把握回調後的再次上漲機會。",
        "criteria_guidance": {
            "minPctChange": "設為 0-1（回調中可選微跌股，等反彈）",
            "minReturn20": "提高至 3-10（中期趨勢仍強）",
            "minTurn": "設為 2-4（回調時換手適中）",
            "minVolumeRatio": "設為 0.8-1.5（回調縮量為佳）",
            "priceAboveMa20": "true（站上20日均線，趨勢未破）",
            "ma20AboveMa60": "true（中期趨勢向上）",
            "macdCrossSignal": "golden_cross（回調後金叉）",
            "maxRsi14": "設為 60-70（回調後RSI回落）",
            "maxAmplitude": "設為 6-10（允許回調波動）",
            "industries": "聚焦前期領漲行業（回調後可能繼續領漲）",
        },
        "config_adjustments": {
            "maxPositions": 6,
            "stopLossPct": 8,
            "takeProfitPct": None,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
        },
        "risk_rules": [
            "上漲中繼核心：逢低加倉，回調是買點",
            "止損 8%，保護上漲利潤",
            "倉位 6 個，適度分散",
            "優先選擇回調縮量、站上20日均線的強勢股",
            "5日調倉，等回調結束再加倉",
        ],
    },
    "oscillation": {
        "label": "震盪市",
        "stance": "靈活短線",
        "description": "漲跌交替頻繁，幅度有限，無明確方向。尋找強勢短線機會，嚴格止盈止損，快進快出。",
        "criteria_guidance": {
            "minPctChange": "設為 1-3（篩選當日強勢脈衝）",
            "minReturn20": "設為 -5~5（不要求中期趨勢）",
            "minTurn": "提高至 3-6（高換手=短線活躍）",
            "minVolumeRatio": "提高至 1.5-3.0（放量異動）",
            "minAmplitude": "提高至 4-8（大振幅才有短線空間）",
            "priceAboveMa5": "true（站上5日均線，短線強勢）",
            "macdCrossWithinDays": "設為 1-3（近期金叉）",
            "kdjCrossSignal": "golden_cross（KDJ金叉短線信號）",
            "maxRsi14": "設為 50-70（避免追高）",
            "industries": "選擇近期輪動熱點行業（最多2個）",
        },
        "config_adjustments": {
            "maxPositions": 4,        # 震盪市少持倉
            "stopLossPct": 7,        # 嚴格止損
            "takeProfitPct": 15,     # 設止盈，快進快出
            "rebalanceInterval": 3,  # 快調倉
            "holdingPeriod": 5,      # 短持有
        },
        "risk_rules": [
            "震盪市核心：快進快出，嚴格止盈止損",
            "止損 7%，止盈 15%，不貪不戀",
            "倉位 4 個，集中火力於最強短線機會",
            "優先選擇大振幅+高換手+放量的短線活躍股",
            "3日調倉，及時止盈或止損",
            "避免追高（maxRsi14 ≤ 70），尋找回調後的反彈機會",
        ],
    },
    "continuation_down": {
        "label": "熊市下跌中繼",
        "stance": "防禦",
        "description": "下跌後小幅反彈，可能繼續下跌。反彈是減倉機會，不宜追高，嚴格控制風險。",
        "criteria_guidance": {
            "minPctChange": "設為 -3~0（超跌反彈候選）",
            "minReturn20": "設為 -20~-5（超跌股）",
            "minTurn": "設為 1-3（換手適中）",
            "minVolumeRatio": "設為 0.5-1.2（縮量企穩）",
            "priceAboveMa60": "false（不要求站上60日均線）",
            "maxRsi14": "設為 30-50（超賣區域）",
            "minRsi14": "設為 20-30（RSI超賣反彈）",
            "maxAmplitude": "設為 5-8（反彈波動）",
            "industries": "選擇防禦性板塊（醫藥/消費/公用事業）或超跌反彈板塊",
        },
        "config_adjustments": {
            "maxPositions": 2,        # 熊市少持倉
            "stopLossPct": 5,        # 嚴格止損
            "takeProfitPct": 8,      # 快止盈
            "rebalanceInterval": 7,  # 慢調倉
            "holdingPeriod": 5,      # 短持有（反彈快進快出）
        },
        "risk_rules": [
            "下跌中繼核心：反彈是減倉機會，不是追漲機會",
            "止損 5%，止盈 8%，反彈快進快出",
            "倉位僅 2 個，大幅降低風險敞口",
            "優先選擇超跌企穩+縮量+RSI超賣的反彈候選",
            "7日調倉，等反彈結束及時退出",
            "避免追高，避免加倉，反彈後及時減倉",
        ],
    },
    "trending_down": {
        "label": "熊市下跌趨勢",
        "stance": "空倉防禦",
        "description": "連續下跌，反彈小，趨勢明確向下。最佳策略是空倉或極低倉位，避免接飛刀。",
        "criteria_guidance": {
            "minPctChange": "設為 -5~-1（深度超跌）",
            "minReturn20": "設為 -30~-10（嚴重超跌）",
            "minTurn": "設為 0.5-2（低換手=無人關注）",
            "minVolumeRatio": "設為 0.3-0.8（縮量見底信號）",
            "minRsi14": "設為 15-25（極度超賣）",
            "maxRsi14": "設為 35-45（遠離超買）",
            "priceAboveMa5": "false",
            "priceAboveMa20": "false",
            "priceAboveMa60": "false",
            "maxAmplitude": "設為 3-6（低波動防禦）",
            "industries": "僅選擇防禦性板塊（醫藥/消費/公用事業/黃金）",
        },
        "config_adjustments": {
            "maxPositions": 1,        # 熊市極低倉位（接近空倉）
            "stopLossPct": 4,        # 最嚴格止損
            "takeProfitPct": 6,      # 快止盈
            "rebalanceInterval": 10, # 慢調倉，少動
            "holdingPeriod": 3,      # 極短持有
        },
        "risk_rules": [
            "熊市核心：空倉是最好的策略，保留彈藥等底部",
            "若必須交易：止損 4%，止盈 6%，極短持有",
            "倉位僅 1 個，最小化風險敞口",
            "只選擇極度超跌+縮量+RSI<25 的潛在反彈候選",
            "10日調倉，減少交易頻率，避免頻繁虧損",
            "優先考慮防禦性板塊（醫藥/消費/公用事業/黃金）",
            "現金為王，等待趨勢反轉信號再進場",
        ],
    },
    "unknown": {
        "label": "數據不足",
        "stance": "謹慎",
        "description": "市場數據不足，無法判斷形態。採取謹慎策略，中等倉位，嚴格止損。",
        "criteria_guidance": {
            "minPctChange": "設為 0-2（中性偏強）",
            "minTurn": "設為 2-4（適度活躍）",
            "minVolumeRatio": "設為 1.0-1.5（正常放量）",
            "maxRsi14": "設為 60-70（避免追高）",
            "maxAmplitude": "設為 5-8（適度波動）",
        },
        "config_adjustments": {
            "maxPositions": 3,
            "stopLossPct": 7,
            "takeProfitPct": 12,
            "rebalanceInterval": 5,
            "holdingPeriod": 7,
        },
        "risk_rules": [
            "數據不足時採取謹慎策略",
            "中等倉位 3 個，嚴格止損 7%",
            "避免追高，避免過度集中",
        ],
    },
}


def get_regime_strategy_guidance(regime_type: str) -> str:
    """獲取市場形態策略指引文本（注入 strategy_generation prompt）。

    Args:
        regime_type: 市場形態類型（trending_up/trending_down/oscillation/continuation_up/continuation_down/unknown）

    Returns:
        結構化的策略指引文本
    """
    regime = REGIME_STRATEGY_MAP.get(regime_type, REGIME_STRATEGY_MAP["unknown"])

    lines = [
        f"## 市場形態策略指引（{regime['label']}）",
        f"形態類型: {regime_type}",
        f"策略取向: {regime['stance']}",
        f"形態描述: {regime['description']}",
        "",
        "### 選股條件調修建議",
    ]

    for param, guidance in regime["criteria_guidance"].items():
        lines.append(f"- {param}: {guidance}")

    lines.append("")
    lines.append("### 風險管理規則（必須遵循）")
    for rule in regime["risk_rules"]:
        lines.append(f"- {rule}")

    lines.append("")
    lines.append(
        f"⚠️ 當前市場為「{regime['label']}」，策略取向為「{regime['stance']}」。"
        "你必須根據上述指引調整選股條件，不可忽略市場形態。"
    )

    return "\n".join(lines)


def get_regime_config_adjustments(regime_type: str) -> dict[str, Any]:
    """獲取市場形態對應的 config 參數調修建議。

    供 optimizer 動態調整回測配置（maxPositions/stopLossPct/rebalanceInterval 等）。

    Args:
        regime_type: 市場形態類型

    Returns:
        dict: config 參數調整值
    """
    regime = REGIME_STRATEGY_MAP.get(regime_type, REGIME_STRATEGY_MAP["unknown"])
    return dict(regime["config_adjustments"])


def get_regime_summary(regime_type: str) -> dict[str, Any]:
    """獲取市場形態摘要（供 market_analysis 傳遞給 strategy_generation）。

    Args:
        regime_type: 市場形態類型

    Returns:
        dict: {regime_type, label, stance, description}
    """
    regime = REGIME_STRATEGY_MAP.get(regime_type, REGIME_STRATEGY_MAP["unknown"])
    return {
        "regime_type": regime_type,
        "label": regime["label"],
        "stance": regime["stance"],
        "description": regime["description"],
    }


def apply_regime_to_config(
    config: dict[str, Any],
    regime_type: str,
    user_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根據市場形態調整回測配置。

    用戶手動設置的字段優先保留，不被形態調整覆蓋。

    Args:
        config: 當前回測配置
        regime_type: 市場形態類型
        user_overrides: 用戶手動設置的字段（這些不被形態調整覆蓋）

    Returns:
        dict: 調整後的回測配置
    """
    adjustments = get_regime_config_adjustments(regime_type)
    user_overrides = user_overrides or {}

    # 1. 以原 config 為基礎
    new_config = dict(config)

    # 2. 應用用戶覆蓋值（用戶手動設置的優先）
    for key, value in user_overrides.items():
        if value is not None:
            new_config[key] = value

    # 3. 應用形態調整（跳過用戶已設置的字段）
    for key, value in adjustments.items():
        if key in user_overrides and user_overrides[key] is not None:
            continue
        new_config[key] = value

    logger.info(
        f"[regime_strategy] 根據形態「{regime_type}」調整 config: "
        f"maxPositions={new_config.get('maxPositions')}, "
        f"stopLossPct={new_config.get('stopLossPct')}, "
        f"rebalanceInterval={new_config.get('rebalanceInterval')}"
    )

    return new_config
