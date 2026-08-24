"""回測策略自動優化 Agent — 主優化循環（編排層）。

多 AI 窗口架構（6 個 AI 串聯 + 評委把關）:
0. 行情新聞 AI (stages/market_news.py) — 抓取實時金融數據 + 行業情緒 → 評委
0.5. 行業分析 AI (stages/industry_analysis.py) — 行業篩選 → 評委
1. 行情分析 AI (stages/market_analysis.py) → 評委
2. 策略生成 AI (stages/strategy_generation.py) → 評委
3. 回測（後端 API，非 AI）
4. 回測反思 AI (stages/backtest_reflection.py) → 評委
5. 提示詞生成 AI (stages/prompt_generation.py) → 評委

數據流: f0(初始/最高分策略) → AI0(新聞) → AI0.5(行業) → AI1 → AI2 → 回測 → AI3 → AI4 → f1 → ...

每次更優策略寫入數據庫，f0 從 DB 最高分策略開始。
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from app.agents.judge import JudgeAI
from app.agents.monitor import node_monitor
from app.agents.safety import check_json_output, sanitize_output
from app.agents.scoring import compute_composite_score
from app.agents.stages.backtest_reflection import BacktestReflectionStage
from app.agents.stages.industry_analysis import IndustryAnalysisStage, parse_industry_output
from app.agents.stages.market_analysis import MarketAnalysisStage
from app.agents.stages.market_news import MarketNewsStage
from app.agents.stages.prompt_generation import PromptGenerationStage
from app.agents.stages.strategy_generation import StrategyGenerationStage, parse_strategy_output
from app.agents.stages.retrospective import run_retrospective
from app.agents.state import (
    DEFAULT_BACKTEST_CONFIG,
    DEFAULT_CRITERIA,
    IterationResult,
    OptimizerState,
    StageResult,
    build_default_backtest_config,
    build_default_criteria,
    RETROSPECTIVE_INTERVAL,
)
from app.core.llm_client import llm_client
from app.core.metrics import (
    record_iteration_complete,
    record_json_failure,
    record_rag_operation,
)
from app.services.backend_client import backend_client
from app.services.market_data_client import market_data_client
from app.services.experience_store import (
    format_experiences_for_prompt,
    is_rag_available,
    retrieve_relevant_experiences,
    store_iteration_experience,
)

logger = logging.getLogger("agent.optimizer")

# 全局狀態
state = OptimizerState()
_stop_event = asyncio.Event()
_current_task: asyncio.Task | None = None

# 初始化各 AI 節點和評委
_market_news_stage = MarketNewsStage()
_industry_stage = IndustryAnalysisStage()
_market_stage = MarketAnalysisStage()
_strategy_stage = StrategyGenerationStage()
_reflection_stage = BacktestReflectionStage()
_prompt_stage = PromptGenerationStage()
_judge = JudgeAI(pass_threshold=60.0)

# 行業相關性快取（避免每輪重複計算）
_industry_corr_cache: dict[str, Any] = {"data": None, "ts": 0.0}
_INDUSTRY_CORR_TTL = 600.0  # 10 分鐘快取


async def _get_industry_correlation_cached() -> dict[str, Any]:
    """獲取行業相關性分析（帶快取，避免每輪重複計算）。"""
    import time as _time

    now = _time.time()
    if _industry_corr_cache["data"] and (now - _industry_corr_cache["ts"]) < _INDUSTRY_CORR_TTL:
        return _industry_corr_cache["data"]
    try:
        data = await market_data_client.get_industry_correlation(days=30)
        _industry_corr_cache["data"] = data
        _industry_corr_cache["ts"] = now
        return data
    except Exception as e:
        logger.warning(f"行業相關性快取獲取失敗: {e}")
        return {"high_corr_pairs": [], "industry_groups": [], "text": ""}


async def _dedup_high_corr_industries(criteria: dict[str, Any]) -> dict[str, Any]:
    """後處理：若 criteria.industries 中包含高相關行業對，保留較強的一個。

    策略：
    1. 獲取行業相關性分析（帶快取）
    2. 若 industries 中存在高相關對（相關係數 >= 0.7），保留第一個（通常是 AI 優先選擇的）
    3. 在 reasoning 中不額外修改（由 AI 自行解釋）
    4. 降級：相關性數據不可用時直接返回原 criteria
    """
    industries = criteria.get("industries")
    if not industries or not isinstance(industries, list) or len(industries) <= 1:
        return criteria

    corr_data = await _get_industry_correlation_cached()
    high_corr_pairs = corr_data.get("high_corr_pairs", [])
    if not high_corr_pairs:
        return criteria

    # 構建高相關映射
    corr_map: dict[str, set[str]] = {}
    for pair in high_corr_pairs:
        a, b = pair.get("a", ""), pair.get("b", "")
        if a and b:
            corr_map.setdefault(a, set()).add(b)
            corr_map.setdefault(b, set()).add(a)

    # 貪心去重：遍歷 industries，若與已保留的行業高相關則移除
    kept: list[str] = []
    removed: list[str] = []
    for ind in industries:
        is_high_corr = any(ind in corr_map.get(k, set()) for k in kept)
        if is_high_corr:
            removed.append(ind)
        else:
            kept.append(ind)

    if removed:
        logger.info(f"行業相關性後處理: 移除高相關行業 {removed}，保留 {kept}")
        new_criteria = dict(criteria)
        new_criteria["industries"] = kept
        return new_criteria

    return criteria


# ===== 多窗口回測評分 =====
# 啟用 multi_window_backtest 時，用 3 個不同時間窗口回測取加權均值，
# 降低單一窗口的隨機性，使評分更穩定。
MULTI_WINDOW_DAYS: list[int] = [90, 180, 365]  # 短/中/長窗口（天）
MULTI_WINDOW_WEIGHTS: list[float] = [0.5, 0.3, 0.2]  # 權重（短窗權重最高）
# 無進展自動停止的 Δscore 閾值（低於此值視為「無實質進展」）
STAGNANT_SCORE_DELTA_THRESHOLD = 1.0


def _weighted_average_score(scores: list[float], weights: list[float]) -> float:
    """計算加權平均評分。

    Args:
        scores: 各窗口的評分列表
        weights: 對應權重列表（長度需與 scores 一致）

    Returns:
        float: 加權平均評分（保留兩位小數）
    """
    if not scores or not weights or len(scores) != len(weights):
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0
    weighted = sum(s * w for s, w in zip(scores, weights))
    return round(weighted / total_weight, 2)


def _build_window_config(base_config: dict[str, Any], days: int) -> dict[str, Any]:
    """基於基準回測配置構建指定天數窗口的配置副本。

    以 base_config.endDate 為基準，將 startDate 回推 `days` 天。
    保留其餘配置字段（調倉、持倉、手續費等）不變。

    Args:
        base_config: 基準回測配置（含 endDate）
        days: 窗口天數

    Returns:
        dict: 新配置（深拷貝，不修改原配置）
    """
    cfg = dict(base_config)
    end_date_str = cfg.get("endDate")
    if end_date_str:
        try:
            end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d")
            start_date = end_date - timedelta(days=days)
            cfg["startDate"] = start_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            # endDate 無法解析時保留原樣（由後端處理）
            pass
    return cfg


def _validate_backtest_config(config: dict[str, Any]) -> dict[str, Any]:
    """回測參數安全校驗 — 防止 AI 設置不合理的參數導致回測結果失真。

    校驗規則（站在專業量化投資者角度）：
    1. slippageBps ≥ 5：零滑點回測結果不可信，A 股真實交易至少 5bp 滑點
    2. maxPositions ≥ 3：單倉位集中度風險極高，回撤不可控
    3. commissionBps ≥ 2：低於 2bp 不現實（A 股最低佣金約 2.5bp）
    4. stopLossPct ≤ 20：過寬止損等於不止損
    5. 回測區間 ≥ 120 個交易日（約 6 個月）：樣本量不足時統計不顯著
    """
    cfg = dict(config)
    warnings = []

    # 1. 滑點下限
    slip = cfg.get("slippageBps")
    if slip is None or slip < 5:
        old = slip
        cfg["slippageBps"] = 5
        warnings.append(f"slippageBps: {old} → 5（零滑點回測不可信）")

    # 2. 持倉數下限
    max_pos = cfg.get("maxPositions")
    if max_pos is not None and max_pos < 3:
        cfg["maxPositions"] = 3
        warnings.append(f"maxPositions: {max_pos} → 3（單倉位集中度風險）")

    # 3. 手續費下限
    comm = cfg.get("commissionBps")
    if comm is not None and comm < 2:
        cfg["commissionBps"] = 2
        warnings.append(f"commissionBps: {comm} → 2（低於真實佣金）")

    # 4. 止損上限
    sl = cfg.get("stopLossPct")
    if sl is not None and sl > 20:
        cfg["stopLossPct"] = 20
        warnings.append(f"stopLossPct: {sl} → 20（過寬止損等於不止損）")

    # 4b. 止損/止盈對稱性校驗：止盈/止損比應在 1.5-4 之間
    # 比例 <1.5 = 頻繁止盈但一次止損吃掉多次盈利；>4 = 止損過寬
    tp = cfg.get("takeProfitPct")
    if sl is not None and tp is not None and sl > 0 and tp > 0:
        ratio = tp / sl
        if ratio < 1.5:
            new_tp = round(sl * 2, 1)
            cfg["takeProfitPct"] = new_tp
            warnings.append(f"takeProfitPct: {tp} → {new_tp}（止盈/止損比 {ratio:.1f} 過低，應 ≥1.5）")
        elif ratio > 4:
            new_tp = round(sl * 3, 1)
            cfg["takeProfitPct"] = new_tp
            warnings.append(f"takeProfitPct: {tp} → {new_tp}（止盈/止損比 {ratio:.1f} 過高，止損過寬）")

    # 5. 回測區間長度（日曆天數）
    start = cfg.get("startDate", "")
    end = cfg.get("endDate", "")
    if start and end:
        try:
            from datetime import datetime
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            days = (e - s).days
            if days < 120:
                warnings.append(f"回測區間僅 {days} 天（<120天），統計不顯著，結果僅供參考")
        except (ValueError, TypeError):
            pass

    if warnings:
        logger.warning(f"[config校驗] 修正不合理參數: {'; '.join(warnings)}")

    return cfg


async def _run_multi_window_backtest(
    criteria: dict[str, Any],
    base_config: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """運行多窗口回測，返回加權平均評分和主窗口（最長窗口）回測結果。

    對 3 個時間窗口（90/180/365 天）分別回測，按權重 0.5/0.3/0.2 加權平均評分。
    主窗口（365 天）的完整回測結果用於後續反思/存庫。

    Args:
        criteria: 選股條件
        base_config: 基準回測配置

    Returns:
        tuple[float, dict]: (加權平均評分, 主窗口回測結果)
    """
    scores: list[float] = []
    primary_result: dict[str, Any] = {}
    for idx, days in enumerate(MULTI_WINDOW_DAYS):
        window_config = _build_window_config(base_config, days)
        result = await backend_client.run_backtest(criteria, window_config)
        window_stats = result.get("statistics", {})
        window_score = compute_composite_score(window_stats)
        scores.append(window_score)
        # 最長窗口為主窗口（用於反思和存庫）
        if idx == len(MULTI_WINDOW_DAYS) - 1:
            primary_result = result
    composite_score = _weighted_average_score(scores, MULTI_WINDOW_WEIGHTS)
    return composite_score, primary_result


async def _load_best_strategy_from_db(latest_trade_date: str | None = None) -> tuple[dict, dict, float, int | None]:
    """從數據庫讀取評分最高的策略作為 f0。

    評分從策略的 result.statistics 計算（而非名稱解析），確保可靠性。
    無歷史策略時返回的默認配置會校準到 latest_trade_date。
    """
    default_criteria = build_default_criteria(latest_trade_date)
    default_config = build_default_backtest_config(latest_trade_date)
    try:
        strategies = await backend_client.list_strategies()
        if not strategies:
            logger.info("數據庫無已保存策略，使用默認參數")
            return default_criteria, default_config, -999, None

        best_score = -999
        best_id = None
        best_criteria = None
        best_config = None

        for s in strategies:
            sid = s.get("id")
            if sid is None:
                continue
            try:
                detail = await backend_client.get_strategy(sid)
                result = detail.get("result")
                if not result:
                    # 無回測結果，嘗試用名稱解析評分作為 fallback
                    name = s.get("name", "")
                    if "評分" in name:
                        try:
                            score = float(name.split("評分")[-1].strip())
                            if score > best_score:
                                best_score = score
                                best_id = sid
                                best_criteria = detail.get("criteria", dict(DEFAULT_CRITERIA))
                                best_config = detail.get("config", dict(DEFAULT_BACKTEST_CONFIG))
                        except (ValueError, IndexError):
                            pass
                    continue

                stats = result.get("statistics", {})
                if not stats:
                    continue

                score = compute_composite_score(stats)
                logger.info(f"策略 id={sid} name={s.get('name', '')}: 計算評分={score}")

                if score > best_score:
                    best_score = score
                    best_id = sid
                    best_criteria = detail.get("criteria", dict(DEFAULT_CRITERIA))
                    best_config = detail.get("config", dict(DEFAULT_BACKTEST_CONFIG))
            except Exception as e:
                logger.warning(f"獲取策略 id={sid} 詳情失敗: {e}")
                continue

        if best_id is None or best_criteria is None:
            logger.info("無法找到有評分的策略，使用默認參數")
            return default_criteria, default_config, -999, None

        logger.info(f"從數據庫載入最佳策略: id={best_id}, 評分={best_score}")
        return best_criteria, best_config, best_score, best_id
    except Exception as e:
        logger.warning(f"從數據庫讀取策略失敗: {e}，使用默認參數")
        return default_criteria, default_config, -999, None


def _pick_backup_provider() -> str:
    """選擇一個與當前策略生成階段供應商不同的備用供應商（P4-7）。

    優先選擇 JSON 穩定的免費供應商（glm-flash），其次按降級鏈順序。
    返回空字符串表示無可用備用供應商。
    """
    from app.core.config import settings
    from app.core.providers import get_default_provider_for_stage

    current = settings.stage_providers.get("strategy_generation", "") or get_default_provider_for_stage(
        "strategy_generation"
    )
    chain = llm_client.get_fallback_chain()
    for pid in chain:
        if pid != current:
            return pid
    return ""


async def run_optimization_loop():
    """主優化循環 — 4 個 AI 串聯 + 評委把關，持續運行直到用戶停止。"""
    from app.core.config import settings

    state.running = True
    state.started_at = datetime.now().isoformat()
    state.status_message = "啟動中..."
    _stop_event.clear()

    # 啟動監控
    node_monitor.start_run()

    logger.info("優化循環啟動（多 AI 窗口架構 + 評委把關 + 監控）")

    # 啟動前檢查模型
    if not llm_client.model_status.available:
        await llm_client.check_models()
    if not llm_client.model_status.available:
        state.running = False
        state.status_message = "所有免費模型不可用，AI 優化功能已關閉"
        logger.warning("免費模型不可用，優化循環不啟動")
        return

    # 從數據庫讀取最高分策略作為 f0
    state.status_message = "從數據庫載入最佳策略..."

    # 保存用戶在 /start 時手動設置的回測配置（用戶值優先，不被 checkpoint/DB 策略覆蓋）
    # 必須在 restore() 之前捕獲，因為 restore() 會覆蓋 state.current_config
    user_config_overrides = dict(state.current_config)

    # 嘗試從 DB 恢復狀態（優先級高於文件 checkpoint，DB 更新更及時）
    db_restored = await state.restore_db()
    if not db_restored:
        # DB 不可用時降級為文件 checkpoint
        restored = state.restore()
        if restored and state.best_score > -999:
            logger.info(f"從文件 checkpoint 恢復: iteration={state.current_iteration}, best_score={state.best_score}")
    elif state.best_score > -999:
        logger.info(f"從 DB 恢復: iteration={state.current_iteration}, best_score={state.best_score}")

    # === 校準基準日期到數據庫最新交易日 ===
    latest_trade_date = await backend_client.get_latest_trade_date()
    if latest_trade_date:
        logger.info(f"數據庫最新交易日: {latest_trade_date}，基準日期已校準")
    else:
        logger.warning("無法獲取最新交易日，使用默認日期（今天）")

    criteria, config, db_best_score, db_strategy_id = await _load_best_strategy_from_db(latest_trade_date)
    if db_best_score > -999:
        # DB 有策略時，用 DB 的（權威來源），但保留 checkpoint 的 reflection/next_prompt
        state.current_criteria = criteria
        # 用戶手動設置的配置字段優先保留，其餘從 DB 最佳策略繼承
        state.current_config = {**config, **user_config_overrides}
        state.best_score = db_best_score
        state.best_strategy_id = db_strategy_id
        # 同步保存最優策略的 criteria/config，供後續迭代回退使用
        # best_config 也必須包含用戶配置，否則回退時會丟失用戶手動設置
        state.best_criteria = dict(criteria)
        state.best_config = dict(state.current_config)
        logger.info(f"f0 = 數據庫最佳策略 (評分={db_best_score}, id={db_strategy_id})")
        if user_config_overrides:
            logger.info(f"用戶手動配置已保留: {list(user_config_overrides.keys())}")
    else:
        # 無歷史策略時用默認配置，日期校準到最新交易日
        state.current_criteria = build_default_criteria(latest_trade_date)
        default_config = build_default_backtest_config(latest_trade_date)
        # 用戶手動設置的配置字段優先保留，其餘從默認配置繼承
        state.current_config = {**default_config, **user_config_overrides}
        state.best_criteria = dict(state.current_criteria)
        state.best_config = dict(state.current_config)
        logger.info(f"f0 = 默認策略（數據庫無歷史策略，日期校準到 {latest_trade_date or '今天'}）")
        if user_config_overrides:
            logger.info(f"用戶手動配置已保留: {list(user_config_overrides.keys())}")

    # 連續 JSON 提取失敗計數器（P4-7：防止空轉燒 token）
    consecutive_json_failures = 0
    _JSON_FAILURE_WARN_THRESHOLD = 3  # 達到此閾值時切換備用供應商重試
    _JSON_FAILURE_PAUSE_SECONDS = 60  # 備用供應商也失敗時暫停秒數
    _JSON_FAILURE_STOP_THRESHOLD = 5  # 達到此閾值時停止優化循環

    # 連續無進展計數器（max_stagnant_iterations：連續 N 輪 Δscore < 1 自動停止）
    stagnant_count = 0

    # === 冷啟動預熱輪（warmup）===
    # 前幾輪 state.iterations 為空，AI 易輸出「上下文不足，無法生成策略」。
    # 預熱輪跑 AI0→AI0.5→AI1→AI2 生成初始策略，替代 DEFAULT_CRITERIA 作為 f0。
    # 預熱輪不評分、不存入 iterations；失敗時降級為 DEFAULT_CRITERIA（保持兼容）。
    if state.current_iteration == 0 and db_best_score <= -999:
        logger.info("冷啟動預熱輪：生成初始策略以替代默認參數")
        state.status_message = "預熱輪：生成初始策略中..."
        state.current_stage_results = []
        warmup_results: list[dict] = []

        def _add_warmup_result(sr: StageResult, _results: list[dict] = warmup_results):
            """記錄預熱輪階段結果（標記 phase=warmup，用於前端區分）。"""
            d = sr.to_dict()
            d["phase"] = "warmup"
            _results.append(d)
            state.current_stage_results = list(_results)

        try:
            # AI 0: 行情新聞（共享 market_data 給 AI 1）
            shared_market_data = await backend_client.get_market_overview()
            news_result = await _market_news_stage.run(
                state=state, judge=_judge, max_attempts=2, history=state.iterations,
                market_data=shared_market_data,
            )
            _add_warmup_result(news_result)
            market_news = sanitize_output(news_result.output)

            # AI 0.5: 行業分析
            industry_result = await _industry_stage.run(
                state=state, judge=_judge, max_attempts=2, market_news=market_news,
            )
            _add_warmup_result(industry_result)

            # AI 1: 行情分析（復用 market_data + 接收 AI 0 分析結果）
            market_result = await _market_stage.run(
                state=state, judge=_judge, max_attempts=2,
                market_data=shared_market_data, history=state.iterations,
                prev_reflection=state.current_reflection,
                market_news=market_news,
            )
            _add_warmup_result(market_result)
            market_context = sanitize_output(market_result.output)

            # AI 2: 策略生成
            strategy_result = await _strategy_stage.run(
                state=state, judge=_judge, max_attempts=2,
                market_context=market_context,
                current_criteria=state.current_criteria,
                config=state.current_config,
                history=state.iterations,
                prev_reflection=state.current_reflection,
                next_prompt=state.current_next_prompt,
                rag_experiences="",
            )
            _add_warmup_result(strategy_result)

            # 解析策略 → 作為 f0 初始策略
            try:
                parsed = parse_strategy_output(strategy_result.output)
                new_criteria = parsed.get("criteria", state.current_criteria)
                # 行業相關性後處理
                new_criteria = await _dedup_high_corr_industries(new_criteria)
                state.current_criteria = new_criteria
                state.best_criteria = dict(new_criteria)
                logger.info("預熱輪成功：已生成初始策略替代默認參數")
                state.status_message = "預熱輪完成，進入正式迭代"
            except ValueError as e:
                logger.warning(f"預熱輪策略解析失敗，降級為默認參數: {e}")
                state.status_message = "預熱輪失敗，使用默認參數進入正式迭代"
        except Exception as e:
            logger.warning(f"預熱輪異常，降級為默認參數: {e}")
            state.status_message = "預熱輪異常，使用默認參數進入正式迭代"
        finally:
            state.current_stage = ""
            state.current_stage_status = ""

        # 預熱輪中被用戶停止
        if _stop_event.is_set():
            state.running = False
            state.stopped_at = datetime.now().isoformat()
            state.status_message = "已停止（預熱輪中斷）"
            node_monitor.end_run()
            logger.info("優化循環在預熱輪被停止")
            return

    while not _stop_event.is_set():
        iteration = state.current_iteration + 1
        stage_results: list[dict] = []
        state.current_stage_results = []  # 重置當前迭代的階段結果
        node_monitor.set_iteration(iteration)  # 設置監控的當前迭代

        def _add_stage_result(sr: StageResult, _results: list[dict] = stage_results):
            """記錄階段結果到本地列表和全局狀態（用於實時可視化）。"""
            d = sr.to_dict()
            _results.append(d)
            state.current_stage_results = list(_results)  # 同步到狀態

        try:
            # === 當日市場摘要複用（減少工具調用）===
            # 若當日已有摘要，注入到 market_data 供 AI0 優先使用
            if not state.current_daily_digest or state.daily_digest_date != latest_trade_date:
                try:
                    from app.services.daily_digest import generate_digest
                    digest = await generate_digest()
                    if digest:
                        logger.info(f"當日摘要已生成/複用（交易日={digest.trade_date}）")
                except Exception as e:
                    logger.warning(f"當日摘要生成失敗（不影響優化）: {e}")

            # === AI 0: 行情新聞分析（+ 評委） ===
            # 優化：提前獲取 market_data，AI 0 和 AI 1 共享，避免重複調用後端 API
            state.status_message = f"第 {iteration} 輪：AI 0 行情新聞分析中..."
            logger.info(f"第 {iteration} 輪：AI 0 行情新聞")
            shared_market_data = await backend_client.get_market_overview()
            # 若有當日摘要，注入到 market_data 供 AI0 參考
            if state.current_daily_digest:
                shared_market_data["daily_digest"] = state.current_daily_digest.to_prompt_text()
            news_result: StageResult = await _market_news_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                history=state.iterations,
                market_data=shared_market_data,  # ← 共享市場數據（含當日摘要）
            )
            _add_stage_result(news_result)
            market_news = sanitize_output(news_result.output)

            # === AI 0.5: 行業分析（+ 評委） ===
            state.status_message = f"第 {iteration} 輪：AI 0.5 行業篩選中..."
            logger.info(f"第 {iteration} 輪：AI 0.5 行業分析")
            industry_result: StageResult = await _industry_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                market_news=market_news,
            )
            _add_stage_result(industry_result)
            try:
                industry_parsed = parse_industry_output(industry_result.output)
                favorable_industries = industry_parsed.get("favorable_industries", [])
                filtered_codes = industry_parsed.get("filtered_codes", [])
                logger.info(f"行業分析: 利好行業={favorable_industries}, 篩選股票={len(filtered_codes)}隻")
            except Exception as e:
                logger.warning(f"行業分析解析失敗: {e}")
                favorable_industries = []
                filtered_codes = []

            # === AI 1: 行情分析（+ 評委） ===
            # 優化：AI 1 接收 AI 0 的分析結果，避免重複分析市場形態
            # 優化：復用 AI 0 已獲取的 market_data，避免重複調用後端 API
            state.status_message = f"第 {iteration} 輪：AI 1 行情分析中..."
            logger.info(f"第 {iteration} 輪：AI 1 行情分析")
            market_result: StageResult = await _market_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                market_data=shared_market_data,  # ← 復用 AI 0 的市場數據
                history=state.iterations,
                prev_reflection=state.current_reflection,
                market_news=market_news,  # ← 傳遞 AI 0 的分析結果
            )
            _add_stage_result(market_result)
            market_context = sanitize_output(market_result.output)
            state.current_market_context = market_context

            # === 市場形態自適應：根據 regime 調整回測配置 ===
            # 牛市→多倉位放寬止損，熊市→減倉位嚴止損，震盪市→中等倉位嚴止盈
            try:
                from app.services.market_data_client import market_data_client
                from app.services.regime_strategy import apply_regime_to_config

                regime = await market_data_client._compute_market_regime()
                regime_type = regime.get("regime_type", "unknown")
                state.current_regime_type = regime_type

                # 根據形態調整 config（用戶手動設置的字段不被覆蓋）
                state.current_config = apply_regime_to_config(
                    config=state.current_config,
                    regime_type=regime_type,
                    user_overrides=user_config_overrides,
                )
                logger.info(
                    f"第 {iteration} 輪: 市場形態={regime_type}, "
                    f"config 已調整: maxPositions={state.current_config.get('maxPositions')}, "
                    f"stopLossPct={state.current_config.get('stopLossPct')}, "
                    f"rebalanceInterval={state.current_config.get('rebalanceInterval')}"
                )
            except Exception as e:
                logger.warning(f"市場形態 config 調整失敗（不影響優化）: {e}")
                state.current_regime_type = "unknown"

            # === AI 2: 策略生成（+ 評委 + RAG 歷史經驗） ===
            state.status_message = f"第 {iteration} 輪：AI 2 策略生成中..."
            logger.info(f"第 {iteration} 輪：AI 2 策略生成")

            # RAG: 檢索與當前市場環境相似的歷史優化經驗
            rag_experiences_text = ""
            if is_rag_available():
                try:
                    rag_start = time.time()
                    experiences = retrieve_relevant_experiences(
                        market_context=market_context,
                        current_criteria=state.current_criteria,
                        top_k=3,
                    )
                    rag_duration = time.time() - rag_start
                    rag_experiences_text = format_experiences_for_prompt(experiences)
                    record_rag_operation("search", rag_duration, success=True)
                    if experiences:
                        logger.info(f"RAG: 注入 {len(experiences)} 條歷史經驗到策略生成 prompt")
                except Exception as e:
                    record_rag_operation("search", 0, success=False)
                    logger.warning(f"RAG 檢索失敗（不影響優化）: {e}")

            strategy_result: StageResult = await _strategy_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                market_context=market_context,
                current_criteria=state.current_criteria,
                config=state.current_config,
                history=state.iterations,
                prev_reflection=state.current_reflection,
                next_prompt=state.current_next_prompt,
                rag_experiences=rag_experiences_text,
                regime_type=getattr(state, "current_regime_type", "unknown"),
            )
            _add_stage_result(strategy_result)
            # JSON 輸出做安全檢查（不替換文本，由 Judge 判定）
            check_json_output(strategy_result.output)
            try:
                parsed = parse_strategy_output(strategy_result.output)
                # JSON 提取成功，重置連續失敗計數器
                consecutive_json_failures = 0
                strategy_reasoning = sanitize_output(parsed.get("reasoning", ""))
                new_criteria = parsed.get("criteria", state.current_criteria)
            except ValueError as e:
                # JSON 提取失敗兜底：使用當前條件繼續（不中斷優化循環）
                # P4-7: 連續失敗計數器，防止 LLM 持續返回無效 JSON 時空轉燒 token
                consecutive_json_failures += 1
                record_json_failure(stage="strategy_generation", recovered=False)
                logger.warning(
                    f"第 {iteration} 輪: 策略 JSON 提取失敗（連續第 {consecutive_json_failures} 次），"
                    f"使用當前條件兜底: {e}"
                )
                from app.services import error_store

                error_store.record_error(
                    stage_name="strategy_generation",
                    error_type="json_extraction",
                    error_message=str(e),
                    raw_output_preview=strategy_result.output[:500],
                    iteration=iteration,
                    run_id=node_monitor.run_id,
                    attempts=strategy_result.attempts,
                    provider=strategy_result.output[:50] if strategy_result.output else "",
                    recovered=True,
                    recovery_method="default",
                )

                # 達到停止閾值：記錄 ERROR 並停止優化循環
                if consecutive_json_failures >= _JSON_FAILURE_STOP_THRESHOLD:
                    logger.error(
                        f"第 {iteration} 輪: JSON 提取連續失敗達 {consecutive_json_failures} 次，"
                        f"停止優化循環以避免空轉燒 token"
                    )
                    state.status_message = (
                        f"JSON 提取連續失敗 {_JSON_FAILURE_STOP_THRESHOLD} 次，優化循環已停止"
                    )
                    break

                # 達到警告閾值：切換備用供應商重試一次
                if consecutive_json_failures >= _JSON_FAILURE_WARN_THRESHOLD:
                    logger.warning(
                        f"第 {iteration} 輪: JSON 提取連續失敗 {consecutive_json_failures} 次，"
                        f"切換備用供應商重試策略生成"
                    )
                    backup_provider = _pick_backup_provider()
                    if backup_provider:
                        # 臨時覆蓋階段供應商設置，重試策略生成
                        from app.core.config import settings as _settings

                        _orig_provider = _settings.stage_providers.get("strategy_generation", "")
                        _settings.stage_providers["strategy_generation"] = backup_provider
                        try:
                            logger.info(f"備用供應商重試: {backup_provider}")
                            retry_result: StageResult = await _strategy_stage.run(
                                state=state,
                                judge=_judge,
                                max_attempts=2,
                                market_context=market_context,
                                current_criteria=state.current_criteria,
                                config=state.current_config,
                                history=state.iterations,
                                prev_reflection=state.current_reflection,
                                next_prompt=state.current_next_prompt,
                                rag_experiences=rag_experiences_text,
                                regime_type=getattr(state, "current_regime_type", "unknown"),
                            )
                            _add_stage_result(retry_result)
                            check_json_output(retry_result.output)
                            try:
                                retry_parsed = parse_strategy_output(retry_result.output)
                                # 備用供應商成功，重置計數器
                                consecutive_json_failures = 0
                                record_json_failure(stage="strategy_generation", recovered=True)
                                strategy_reasoning = sanitize_output(
                                    retry_parsed.get("reasoning", "")
                                )
                                new_criteria = retry_parsed.get("criteria", state.current_criteria)
                                logger.info(f"第 {iteration} 輪: 備用供應商 {backup_provider} JSON 提取成功")
                            except ValueError as retry_e:
                                logger.warning(
                                    f"第 {iteration} 輪: 備用供應商 {backup_provider} JSON 提取也失敗: {retry_e}"
                                )
                                record_json_failure(stage="strategy_generation", recovered=False)
                                strategy_reasoning = "JSON 提取失敗（備用供應商也失敗），使用上一輪條件繼續"
                                new_criteria = state.current_criteria
                        except Exception as retry_e:
                            logger.warning(f"第 {iteration} 輪: 備用供應商重試異常: {retry_e}")
                            strategy_reasoning = "JSON 提取失敗（備用供應商異常），使用上一輪條件繼續"
                            new_criteria = state.current_criteria
                        finally:
                            _settings.stage_providers["strategy_generation"] = _orig_provider
                    else:
                        logger.warning("無可用備用供應商，跳過重試")

                    # 備用供應商也失敗時暫停 60 秒（而非立即繼續空轉）
                    if consecutive_json_failures >= _JSON_FAILURE_WARN_THRESHOLD:
                        logger.warning(
                            f"第 {iteration} 輪: JSON 提取仍失敗，暫停 {_JSON_FAILURE_PAUSE_SECONDS} 秒"
                        )
                        state.status_message = (
                            f"第 {iteration} 輪: JSON 提取連續失敗，暫停 {_JSON_FAILURE_PAUSE_SECONDS} 秒"
                        )
                        try:
                            await asyncio.wait_for(
                                _stop_event.wait(), timeout=_JSON_FAILURE_PAUSE_SECONDS
                            )
                        except asyncio.TimeoutError:
                            pass  # 暫停結束後繼續下一輪
                else:
                    parsed = {}
                    strategy_reasoning = "JSON 提取失敗，使用上一輪條件繼續"
                    new_criteria = state.current_criteria

            # === 行業相關性後處理：避免高相關行業過度集中 ===
            new_criteria = await _dedup_high_corr_industries(new_criteria)

            # === Config 安全校驗（防止 AI 設置不合理的回測參數）===
            state.current_config = _validate_backtest_config(state.current_config)

            # === 回測（非 AI） ===
            state.status_message = f"第 {iteration} 輪：運行回測中..."
            state.current_stage = "backtest"
            state.current_stage_status = "running"
            node_monitor.record_start("backtest", node_type="backtest")
            logger.info(f"第 {iteration} 輪：運行回測")
            backtest_start = time.time()
            if settings.multi_window_backtest:
                # 多窗口回測：3 個時間窗口加權平均評分
                logger.info(f"第 {iteration} 輪：多窗口回測（窗口={MULTI_WINDOW_DAYS}，權重={MULTI_WINDOW_WEIGHTS}）")
                composite_score, backtest_result = await _run_multi_window_backtest(
                    new_criteria, state.current_config
                )
            else:
                # 單一窗口回測（保持兼容）
                backtest_result = await backend_client.run_backtest(new_criteria, state.current_config)
                composite_score = compute_composite_score(backtest_result.get("statistics", {}))
            backtest_duration_ms = int((time.time() - backtest_start) * 1000)
            stats = backtest_result.get("statistics", {})
            state.current_stage_status = "passed"
            node_monitor.record_end(
                "backtest",
                node_type="backtest",
                duration_ms=backtest_duration_ms,
                judge_passed=True,
            )

            # 選股摘要
            log_lines = backtest_result.get("logLines", [])
            screener_summary = ""
            for line in log_lines:
                if "命中" in line or "候选" in line or "选股" in line:
                    screener_summary = line
                    break
            if not screener_summary:
                screener_summary = f"調倉 {stats.get('rebalanceCount', 0)} 次，交易 {stats.get('totalTrades', 0)} 筆"

            logger.info(
                f"回測結果: 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"評分={composite_score}"
            )

            # === AI 3: 回測反思（+ 評委） ===
            state.status_message = f"第 {iteration} 輪：AI 3 回測反思中..."
            logger.info(f"第 {iteration} 輪：AI 3 回測反思")
            reflection_result: StageResult = await _reflection_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                stats=stats,
                composite_score=composite_score,
                criteria=new_criteria,
                market_context=market_context,
                history=state.iterations,
            )
            _add_stage_result(reflection_result)
            reflection = sanitize_output(reflection_result.output)
            state.current_reflection = reflection

            # === AI 4: 提示詞生成（+ 評委） ===
            state.status_message = f"第 {iteration} 輪：AI 4 提示詞生成中..."
            logger.info(f"第 {iteration} 輪：AI 4 提示詞生成")
            prompt_result: StageResult = await _prompt_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                reflection=reflection,
                stats=stats,
                composite_score=composite_score,
                history=state.iterations,
            )
            _add_stage_result(prompt_result)
            next_prompt = sanitize_output(prompt_result.output)
            state.current_next_prompt = next_prompt

            # === 記錄迭代結果 ===
            result = IterationResult(
                iteration=iteration,
                timestamp=datetime.now().isoformat(),
                criteria=dict(new_criteria),
                config=dict(state.current_config),
                screener_summary=screener_summary,
                backtest_statistics=stats,
                composite_score=composite_score,
                market_news=market_news,
                favorable_industries=favorable_industries,
                filtered_codes=filtered_codes,
                market_analysis=market_context,
                strategy_generation=strategy_reasoning,
                backtest_reflection=reflection,
                next_prompt=next_prompt,
                next_criteria=dict(new_criteria),
                stage_results=stage_results,
            )
            state.iterations.append(result)
            # 截斷舊記錄防止內存洩漏（保留最近 100 輪）
            from app.agents.state import MAX_IN_MEMORY_ITERATIONS

            if len(state.iterations) > MAX_IN_MEMORY_ITERATIONS:
                removed = len(state.iterations) - MAX_IN_MEMORY_ITERATIONS
                state.iterations = state.iterations[removed:]
                logger.info(f"狀態截斷: 移除 {removed} 條舊記錄")

            # === RAG: 存儲本輪經驗到向量數據庫 ===
            if is_rag_available():
                try:
                    store_iteration_experience(
                        iteration=iteration,
                        market_context=market_context,
                        criteria=new_criteria,
                        stats=stats,
                        reflection=reflection,
                        composite_score=composite_score,
                        timestamp=result.timestamp,
                    )
                    record_rag_operation("store", success=True)
                except Exception as e:
                    record_rag_operation("store", success=False)
                    logger.warning(f"RAG 存儲經驗失敗（不影響優化）: {e}")

            # === 無進展檢測（max_stagnant_iterations） ===
            # Δscore = 本輪評分相對歷史最佳的提升；低於閾值視為「無實質進展」
            # 注意：delta 需在 best_score 更新前計算
            delta_score = composite_score - state.best_score
            if delta_score < STAGNANT_SCORE_DELTA_THRESHOLD:
                stagnant_count += 1
            else:
                stagnant_count = 0

            # === 更新最佳記錄並寫入 DB ===
            if composite_score > state.best_score:
                state.best_score = composite_score
                state.best_iteration = iteration
                # 保存最優策略的 criteria/config，供後續迭代回退使用
                state.best_criteria = dict(new_criteria)
                state.best_config = dict(state.current_config)
                try:
                    saved = await backend_client.save_strategy(
                        name=f"AI優化-第{iteration}輪-評分{composite_score}",
                        criteria=new_criteria,
                        config=state.current_config,
                        result=backtest_result,
                    )
                    state.best_strategy_id = saved.get("id")
                    logger.info(f"新最佳策略已保存: 評分 {composite_score}, id={state.best_strategy_id}")
                except Exception as e:
                    logger.warning(f"策略保存失敗: {e}")

            # === 應用新參數，準備下一輪 ===
            # 始終基於歷史最優策略迭代：若本輪未超越 best，下一輪回到 best_criteria 重新出發
            if composite_score >= state.best_score:
                # 本輪就是新最佳，從本輪結果出發
                state.current_criteria = new_criteria
                logger.info(f"第 {iteration} 輪為新最佳，下一輪從本輪結果出發")
            else:
                # 本輪未超越 best，回到歷史最優策略重新迭代
                state.current_criteria = dict(state.best_criteria)
                state.current_config = dict(state.best_config)
                logger.info(
                    f"第 {iteration} 輪評分 {composite_score} < 最佳 {state.best_score}，"
                    f"下一輪回到歷史最優策略 (第 {state.best_iteration} 輪) 重新迭代"
                )

                # === 防死循環：檢測連續重複回退 ===
                # 若連續多輪都回退到 best_criteria 且生成的策略相同，注入強變異 next_prompt
                new_criteria_sig = json.dumps(new_criteria, ensure_ascii=False, sort_keys=True)
                best_criteria_sig = json.dumps(state.best_criteria, ensure_ascii=False, sort_keys=True)
                if new_criteria_sig == best_criteria_sig:
                    state.repetition_counter = getattr(state, "repetition_counter", 0) + 1
                else:
                    state.repetition_counter = 0

                if state.repetition_counter >= 2:
                    logger.warning(
                        f"檢測到連續 {state.repetition_counter} 輪生成與 best 相同的策略，注入強變異 next_prompt"
                    )
                    state.current_next_prompt = (
                        f"⚠️ 緊急：連續 {state.repetition_counter} 輪生成與歷史最優完全相同的策略，"
                        f"這是死循環！本輪必須採取強變異措施：\n"
                        f"1. 若 industries 只有 1 個行業，立即擴展至 2-3 個景氣度 ≥ 65 的強勢行業\n"
                        f"2. 若 stopLossPct 為 null，立即設置 stopLossPct=8\n"
                        f"3. 若 rebalanceInterval ≤ 5，立即改為 10 或 15\n"
                        f"4. 調整 minTurn（當前值 ±2.0）或 minVolumeRatio（當前值 ±0.3）\n"
                        f"5. 移除或放寬最嚴格的過濾條件\n"
                        f"目標：打破重複，探索新的策略空間，即使可能暫時降低評分也要嘗試。\n\n"
                        f"---\n⚠️ 免責聲明：本系統輸出僅供研究參考，不構成任何投資建議。"
                    )
                elif stagnant_count >= 3:
                    # 策略不完全相同但連續 3+ 輪無實質進展（Δscore < 1）
                    # 說明 AI 在做無效微調，需要更大方向的探索
                    logger.warning(
                        f"連續 {stagnant_count} 輪無實質進展（策略略有不同但評分停滯），注入探索性 next_prompt"
                    )
                    state.current_next_prompt = (
                        f"⚠️ 注意：連續 {stagnant_count} 輪評分停滯在 {state.best_score} 附近，"
                        f"微調已無效果。本輪需要嘗試**不同方向**的策略變革：\n"
                        f"1. 嘗試完全不同的選股邏輯（如從趨勢跟蹤轉為均值回歸，或反之）\n"
                        f"2. 大幅調整參數範圍（如 minClose 從 10-100 改為 5-50 或 20-200）\n"
                        f"3. 嘗試不同的技術指標組合（如加入 KDJ 金叉或 MACD 信號）\n"
                        f"4. 調整回測窗口或調倉頻率（如 rebalanceInterval 從 5 改為 3 或 10）\n"
                        f"5. 擴展或替換行業（當前行業：{state.best_criteria.get('industries', [])}）\n"
                        f"目標：跳出局部最優，探索全局更優的策略空間。\n\n"
                        f"---\n⚠️ 免責聲明：本系統輸出僅供研究參考，不構成任何投資建議。"
                    )
            state.current_iteration = iteration
            state.current_stage = ""
            state.current_stage_status = ""
            state.status_message = f"第 {iteration} 輪完成，評分 {composite_score}，準備下一輪..."

            # === 無進展終止檢查（在迭代狀態記錄後，確保 current_iteration 反映本輪） ===
            if settings.max_stagnant_iterations > 0 and stagnant_count >= settings.max_stagnant_iterations:
                logger.info(
                    f"連續 {stagnant_count} 輪無實質進展（Δscore < {STAGNANT_SCORE_DELTA_THRESHOLD}），"
                    f"達到 max_stagnant_iterations={settings.max_stagnant_iterations}，停止優化循環"
                )
                state.status_message = (
                    f"連續 {stagnant_count} 輪無進展，優化循環已自動停止"
                )
                break

            # 記錄評分到監控（用於無進展檢測）
            node_monitor.record_score(composite_score)

            logger.info(f"第 {iteration} 輪完成，評分: {composite_score}")

            # === 記錄 Prometheus 指標 ===
            record_iteration_complete(iteration, composite_score)

            # === 狀態 checkpoint（崩潰恢復用）===
            state.checkpoint()
            # DB 層 checkpoint（跨進程/跨交易日恢復）
            await state.checkpoint_db()

            # === 回顧分析（每 RETROSPECTIVE_INTERVAL 輪觸發）===
            if state.current_iteration > 0 and state.current_iteration % RETROSPECTIVE_INTERVAL == 0:
                logger.info(f"第 {state.current_iteration} 輪：觸發回顧分析（每{RETROSPECTIVE_INTERVAL}輪）")
                state.status_message = f"第 {state.current_iteration} 輪：回顧分析中..."
                try:
                    retro_result = await run_retrospective(state, window_size=RETROSPECTIVE_INTERVAL)
                    if retro_result:
                        logger.info(f"回顧分析完成，結論已注入下一輪 next_prompt")
                        state.status_message = f"第 {state.current_iteration} 輪完成+回顧分析完成，評分 {composite_score}"
                        # 回顧分析後再次 checkpoint（含回顧結果）
                        state.checkpoint()
                        await state.checkpoint_db()
                    else:
                        logger.warning("回顧分析未產出結果")
                except Exception as retro_e:
                    logger.error(f"回顧分析異常（不影響優化）: {retro_e}", exc_info=True)

            # 等待間隔
            await asyncio.wait_for(_stop_event.wait(), timeout=settings.optimization_interval)

        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            logger.info("優化循環被取消")
            node_monitor.record_cancel(state.current_stage or "optimizer")
            break
        except Exception as e:
            logger.error(f"第 {iteration} 輪異常: {e}", exc_info=True)
            state.status_message = f"第 {iteration} 輪錯誤: {e}"
            state.iterations.append(
                IterationResult(
                    iteration=iteration,
                    timestamp=datetime.now().isoformat(),
                    criteria=dict(state.current_criteria),
                    config=dict(state.current_config),
                    screener_summary="",
                    backtest_statistics={},
                    composite_score=0,
                    error=str(e),
                )
            )
            state.current_iteration = iteration
            try:
                await asyncio.wait_for(_stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                continue

    state.running = False
    state.stopped_at = datetime.now().isoformat()
    state.status_message = "已停止"
    state.current_stage = ""
    state.current_stage_status = ""
    node_monitor.end_run()
    logger.info("優化循環已停止")


def start_optimization():
    """啟動優化循環（在後台 task 中運行）。"""
    global _current_task
    if state.running:
        return
    _stop_event.clear()
    _current_task = asyncio.create_task(run_optimization_loop())


def stop_optimization():
    """停止優化循環 — 設置停止事件並取消當前 task。"""
    global _current_task
    _stop_event.set()
    state.status_message = "正在停止..."
    if _current_task and not _current_task.done():
        _current_task.cancel()
        logger.info("已發送 cancel 信號到優化循環 task")
    _current_task = None
