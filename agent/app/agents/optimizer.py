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
from datetime import datetime
from typing import Any, Optional

from app.agents.state import (
    OptimizerState,
    IterationResult,
    StageResult,
    DEFAULT_CRITERIA,
    DEFAULT_BACKTEST_CONFIG,
)
from app.agents.scoring import compute_composite_score
from app.agents.judge import JudgeAI
from app.agents.monitor import node_monitor
from app.agents.monitor_ai import monitor_ai
from app.agents.stages.market_news import MarketNewsStage
from app.agents.stages.industry_analysis import IndustryAnalysisStage, parse_industry_output
from app.agents.stages.market_analysis import MarketAnalysisStage
from app.agents.stages.strategy_generation import StrategyGenerationStage, parse_strategy_output
from app.agents.stages.backtest_reflection import BacktestReflectionStage
from app.agents.stages.prompt_generation import PromptGenerationStage
from app.core.llm_client import llm_client
from app.services.backend_client import backend_client
from app.services.experience_store import (
    store_iteration_experience,
    retrieve_relevant_experiences,
    format_experiences_for_prompt,
    is_rag_available,
)
from app.core.metrics import (
    record_iteration_complete,
    record_stage_duration,
    record_rag_operation,
)

logger = logging.getLogger("agent.optimizer")

# 全局狀態
state = OptimizerState()
_stop_event = asyncio.Event()
_current_task: Optional[asyncio.Task] = None

# 初始化各 AI 節點和評委
_market_news_stage = MarketNewsStage()
_industry_stage = IndustryAnalysisStage()
_market_stage = MarketAnalysisStage()
_strategy_stage = StrategyGenerationStage()
_reflection_stage = BacktestReflectionStage()
_prompt_stage = PromptGenerationStage()
_judge = JudgeAI(pass_threshold=60.0)


async def _load_best_strategy_from_db() -> tuple[dict, dict, float, Optional[int]]:
    """從數據庫讀取評分最高的策略作為 f0。

    評分從策略的 result.statistics 計算（而非名稱解析），確保可靠性。
    """
    try:
        strategies = await backend_client.list_strategies()
        if not strategies:
            logger.info("數據庫無已保存策略，使用默認參數")
            return dict(DEFAULT_CRITERIA), dict(DEFAULT_BACKTEST_CONFIG), -999, None

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
            return dict(DEFAULT_CRITERIA), dict(DEFAULT_BACKTEST_CONFIG), -999, None

        logger.info(f"從數據庫載入最佳策略: id={best_id}, 評分={best_score}")
        return best_criteria, best_config, best_score, best_id
    except Exception as e:
        logger.warning(f"從數據庫讀取策略失敗: {e}，使用默認參數")
        return dict(DEFAULT_CRITERIA), dict(DEFAULT_BACKTEST_CONFIG), -999, None


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

    # 嘗試從 checkpoint 恢復狀態（崩潰恢復）
    restored = state.restore()
    if restored and state.best_score > -999:
        logger.info(f"從 checkpoint 恢復: iteration={state.current_iteration}, best_score={state.best_score}")

    criteria, config, db_best_score, db_strategy_id = await _load_best_strategy_from_db()
    if db_best_score > -999:
        # DB 有策略時，用 DB 的（權威來源），但保留 checkpoint 的 reflection/next_prompt
        state.current_criteria = criteria
        state.current_config = config
        state.best_score = db_best_score
        state.best_strategy_id = db_strategy_id
        # 同步保存最優策略的 criteria/config，供後續迭代回退使用
        state.best_criteria = dict(criteria)
        state.best_config = dict(config)
        logger.info(f"f0 = 數據庫最佳策略 (評分={db_best_score}, id={db_strategy_id})")
    else:
        state.current_criteria = dict(DEFAULT_CRITERIA)
        state.current_config = dict(DEFAULT_BACKTEST_CONFIG)
        state.best_criteria = dict(DEFAULT_CRITERIA)
        state.best_config = dict(DEFAULT_BACKTEST_CONFIG)
        logger.info("f0 = 默認策略（數據庫無歷史策略）")

    while not _stop_event.is_set():
        iteration = state.current_iteration + 1
        stage_results: list[dict] = []
        state.current_stage_results = []  # 重置當前迭代的階段結果
        node_monitor.set_iteration(iteration)  # 設置監控的當前迭代

        def _add_stage_result(sr: StageResult):
            """記錄階段結果到本地列表和全局狀態（用於實時可視化）。"""
            d = sr.to_dict()
            stage_results.append(d)
            state.current_stage_results = list(stage_results)  # 同步到狀態

        try:
            # === AI 0: 行情新聞分析（+ 評委） ===
            state.status_message = f"第 {iteration} 輪：AI 0 行情新聞分析中..."
            logger.info(f"第 {iteration} 輪：AI 0 行情新聞")
            news_result: StageResult = await _market_news_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                history=state.iterations,
            )
            _add_stage_result(news_result)
            market_news = news_result.output

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
            state.status_message = f"第 {iteration} 輪：AI 1 行情分析中..."
            logger.info(f"第 {iteration} 輪：AI 1 行情分析")
            market_data = await backend_client.get_market_overview()
            market_result: StageResult = await _market_stage.run(
                state=state,
                judge=_judge,
                max_attempts=2,
                market_data=market_data,
                history=state.iterations,
                prev_reflection=state.current_reflection,
            )
            _add_stage_result(market_result)
            market_context = market_result.output
            state.current_market_context = market_context

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
            )
            _add_stage_result(strategy_result)
            parsed = parse_strategy_output(strategy_result.output)
            strategy_reasoning = parsed.get("reasoning", "")
            new_criteria = parsed.get("criteria", state.current_criteria)

            # === 回測（非 AI） ===
            state.status_message = f"第 {iteration} 輪：運行回測中..."
            state.current_stage = "backtest"
            state.current_stage_status = "running"
            node_monitor.record_start("backtest", node_type="backtest")
            logger.info(f"第 {iteration} 輪：運行回測")
            backtest_start = time.time()
            backtest_result = await backend_client.run_backtest(
                new_criteria, state.current_config
            )
            backtest_duration_ms = int((time.time() - backtest_start) * 1000)
            stats = backtest_result.get("statistics", {})
            composite_score = compute_composite_score(stats)
            state.current_stage_status = "passed"
            node_monitor.record_end(
                "backtest", node_type="backtest", duration_ms=backtest_duration_ms,
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
            reflection = reflection_result.output
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
            next_prompt = prompt_result.output
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
            state.current_iteration = iteration
            state.current_stage = ""
            state.current_stage_status = ""
            state.status_message = f"第 {iteration} 輪完成，評分 {composite_score}，準備下一輪..."

            # 記錄評分到監控（用於無進展檢測）
            node_monitor.record_score(composite_score)

            logger.info(f"第 {iteration} 輪完成，評分: {composite_score}")

            # === 記錄 Prometheus 指標 ===
            record_iteration_complete(iteration, composite_score)

            # === 狀態 checkpoint（崩潰恢復用）===
            state.checkpoint()

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
            state.iterations.append(IterationResult(
                iteration=iteration,
                timestamp=datetime.now().isoformat(),
                criteria=dict(state.current_criteria),
                config=dict(state.current_config),
                screener_summary="",
                backtest_statistics={},
                composite_score=0,
                error=str(e),
            ))
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
