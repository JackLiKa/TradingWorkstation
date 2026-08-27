"""Prometheus 指標 — Agent 服務可觀測性。

暴露指標：
- agent_optimization_iterations_total: 優化迭代總數
- agent_optimization_score: 當前最佳評分（Gauge）
- agent_stage_duration_seconds: 各階段耗時（Histogram）
- agent_stage_judge_score: 各階段評委評分（Gauge）
- agent_llm_calls_total: LLM 調用總數（按 provider/model）
- agent_llm_duration_seconds: LLM 調用耗時（Histogram）
- agent_llm_fallback_total: LLM 降級次數
- agent_rag_operations_total: RAG 操作總數（store/search）
- agent_rag_search_duration_seconds: RAG 搜索耗時
- agent_backend_calls_total: 後端 API 調用總數
- agent_backend_errors_total: 後端 API 錯誤總數
- agent_backend_retry_total: 後端重試總數
- agent_json_failure_total: JSON 提取失敗總數（按 stage/recovered）

指標端點: GET /metrics（Prometheus 格式）
"""

import logging

logger = logging.getLogger("agent.metrics")

# 指標存儲（簡單實現，無外部依賴）
_counters: dict[str, float] = {}
_gauges: dict[str, float] = {}
_histograms: dict[str, list[float]] = {}

# Histogram 桶定義
DURATION_BUCKETS = [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]


def inc_counter(name: str, labels: dict[str, str] = None, value: float = 1.0):
    """遞增計數器。"""
    key = _metric_key(name, labels)
    _counters[key] = _counters.get(key, 0) + value


def set_gauge(name: str, value: float, labels: dict[str, str] = None):
    """設置 Gauge 值。"""
    key = _metric_key(name, labels)
    _gauges[key] = value


def observe_histogram(name: str, value: float, labels: dict[str, str] = None):
    """記錄 Histogram 觀測值。"""
    key = _metric_key(name, labels)
    if key not in _histograms:
        _histograms[key] = []
    _histograms[key].append(value)
    # 只保留最近 100 個觀測值（防止內存增長）
    if len(_histograms[key]) > 100:
        _histograms[key] = _histograms[key][-100:]


def _metric_key(name: str, labels: dict[str, str] = None) -> str:
    """生成指標鍵（含標籤）。"""
    if not labels:
        return name
    label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{label_str}}}"


def _parse_key(key: str) -> tuple[str, dict[str, str]]:
    """解析指標鍵為名稱和標籤。"""
    if "{" not in key:
        return key, {}
    name = key[: key.index("{")]
    label_str = key[key.index("{") + 1 : key.index("}")]
    labels = {}
    for pair in label_str.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            labels[k] = v
    return name, labels


def render_prometheus_metrics() -> str:
    """渲染 Prometheus 格式指標文本。"""
    lines = []

    # === Counters ===
    counter_names = set()
    for key in _counters:
        name, labels = _parse_key(key)
        counter_names.add(name)

    for name in sorted(counter_names):
        lines.append(f"# TYPE {name} counter")
        for key in sorted(_counters.keys()):
            n, labels = _parse_key(key)
            if n != name:
                continue
            label_str = ""
            if labels:
                label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"
            lines.append(f"{name}{label_str} {_counters[key]}")

    # === Gauges ===
    gauge_names = set()
    for key in _gauges:
        name, labels = _parse_key(key)
        gauge_names.add(name)

    for name in sorted(gauge_names):
        lines.append(f"# TYPE {name} gauge")
        for key in sorted(_gauges.keys()):
            n, labels = _parse_key(key)
            if n != name:
                continue
            label_str = ""
            if labels:
                label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"
            lines.append(f"{name}{label_str} {_gauges[key]}")

    # === Histograms ===
    hist_names = set()
    for key in _histograms:
        name, labels = _parse_key(key)
        hist_names.add(name)

    for name in sorted(hist_names):
        lines.append(f"# TYPE {name} histogram")
        for key in sorted(_histograms.keys()):
            n, labels = _parse_key(key)
            if n != name:
                continue
            values = _histograms[key]
            if not values:
                continue
            label_str = ""
            if labels:
                label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"

            # 構建桶標籤前綴（已有 label_str 時追加 le=，否則新建）
            if label_str:
                bucket_prefix = label_str[:-1] + ",le="  # 去掉末尾 }，加 ,
            else:
                bucket_prefix = "{le="

            # 計算桶累積
            for bucket in DURATION_BUCKETS:
                count = sum(1 for v in values if v <= bucket)
                lines.append(f'{name}_bucket{bucket_prefix}"{bucket}"}} {count}')
            count = sum(1 for v in values if v <= float("inf"))
            lines.append(f'{name}_bucket{bucket_prefix}"+Inf"}} {count}')
            lines.append(f"{name}_count{label_str} {len(values)}")
            lines.append(f"{name}_sum{label_str} {sum(values)}")

    return "\n".join(lines) + "\n"


# ===== 便捷函數 =====


def record_iteration_complete(iteration: int, score: float):
    """記錄一輪優化完成。"""
    inc_counter("agent_optimization_iterations_total")
    set_gauge("agent_optimization_score", score)
    set_gauge("agent_optimization_current_iteration", iteration)


def record_stage_duration(stage: str, duration_s: float, judge_score: float = 0):
    """記錄階段耗時和評委評分。"""
    observe_histogram("agent_stage_duration_seconds", duration_s, {"stage": stage})
    set_gauge("agent_stage_judge_score", judge_score, {"stage": stage})


def record_llm_call(provider: str, model: str, duration_s: float, fallback: bool = False):
    """記錄 LLM 調用。"""
    labels = {"provider": provider, "model": model}
    inc_counter("agent_llm_calls_total", labels)
    observe_histogram("agent_llm_duration_seconds", duration_s, labels)
    if fallback:
        inc_counter("agent_llm_fallback_total", {"provider": provider})


def record_llm_tokens(provider: str, prompt_tokens: int, completion_tokens: int):
    """記錄 LLM token 使用量（用於成本追蹤）。"""
    if prompt_tokens > 0:
        inc_counter("agent_llm_tokens_total", {"provider": provider, "type": "prompt"}, prompt_tokens)
    if completion_tokens > 0:
        inc_counter("agent_llm_tokens_total", {"provider": provider, "type": "completion"}, completion_tokens)


def record_llm_error(provider: str, error_type: str = "call"):
    """記錄 LLM 調用錯誤。"""
    inc_counter("agent_llm_errors_total", {"provider": provider, "type": error_type})


def record_rag_operation(op: str, duration_s: float = 0, success: bool = True):
    """記錄 RAG 操作。"""
    labels = {"operation": op, "status": "success" if success else "failed"}
    inc_counter("agent_rag_operations_total", labels)
    if op == "search" and duration_s > 0:
        observe_histogram("agent_rag_search_duration_seconds", duration_s)


def record_backend_call(endpoint: str, success: bool, retried: bool = False):
    """記錄後端 API 調用。"""
    inc_counter("agent_backend_calls_total", {"endpoint": endpoint})
    if not success:
        inc_counter("agent_backend_errors_total", {"endpoint": endpoint})
    if retried:
        inc_counter("agent_backend_retry_total", {"endpoint": endpoint})


def record_json_failure(stage: str = "strategy_generation", recovered: bool = False):
    """記錄 JSON 提取失敗（用於監控連續空轉問題 P4-7）。"""
    inc_counter("agent_json_failure_total", {"stage": stage, "recovered": str(recovered).lower()})
