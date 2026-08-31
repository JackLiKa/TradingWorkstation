/**
 * @file 日誌 API 客戶端 — 封裝日誌頁面所需的 API 調用。
 *
 * 數據來源：
 * - Java 後端 /api/logs/* — 系統請求日誌 + Java 應用日誌 + AI 調用日誌
 * - Agent 服務 /agent-api/logs/* — Agent 服務日誌
 *
 * 實時機制：
 * - SSE 推送新日誌（Java /api/logs/stream + Agent /agent-api/logs/stream）
 * - SWR 輪詢歷史日誌（首次加載）
 */

/** 統一日誌條目類型 */
export interface LogEntry {
  id: string;
  source: 'system' | 'java' | 'agent' | 'ai';
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | string;
  message: string;
  timestamp: string;
  details?: Record<string, unknown>;
  // Agent 日誌特有
  logger?: string;
  raw?: string;
}

/** 日誌分類統計 */
export interface LogStats {
  memoryBufferSize: number;
  bySource: Record<string, number>;
  requestLogTotal: number;
  aiCallLogTotal: number;
}

/** 日誌來源分類標籤 */
export const LOG_SOURCES = [
  { value: 'system', label: '系統請求', color: 'text-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  { value: 'java', label: 'Java 後端', color: 'text-green-400', badge: 'bg-green-500/10 text-green-400 border-green-500/30' },
  { value: 'agent', label: 'Agent 服務', color: 'text-purple-400', badge: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  { value: 'ai', label: 'AI 優化', color: 'text-orange-400', badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30' },
] as const;

/** 日誌級別標籤 */
export const LOG_LEVELS = [
  { value: 'ERROR', label: 'ERROR', color: 'text-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/30' },
  { value: 'WARN', label: 'WARN', color: 'text-yellow-400', badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' },
  { value: 'INFO', label: 'INFO', color: 'text-slate-400', badge: 'bg-slate-500/10 text-slate-400 border-slate-500/30' },
  { value: 'DEBUG', label: 'DEBUG', color: 'text-cyan-400', badge: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' },
] as const;

/** 獲取來源標籤配置 */
export function getSourceMeta(source: string) {
  return LOG_SOURCES.find((s) => s.value === source) ?? LOG_SOURCES[2];
}

/** 獲取級別標籤配置 */
export function getLevelMeta(level: string) {
  return LOG_LEVELS.find((l) => l.value === level.toUpperCase()) ?? LOG_LEVELS[2];
}

/** 噪聲過濾規則 — 過濾掉日誌頁面自身的請求和 wget 等噪聲 */
export function isNoiseLog(entry: LogEntry): boolean {
  // 過濾 /logs 端點自身的請求（避免自引用）
  if (entry.source === 'system') {
    const msg = entry.message || '';
    if (msg.includes('/api/logs') || msg.includes('/agent-api/logs')) return true;
    // 過濾 wget 噪聲
    if (msg.includes('wget') || msg.includes('Wget')) return true;
    // 過濾健康檢查
    if (msg.includes('/actuator/health')) return true;
    // 過濾 favicon
    if (msg.includes('/favicon')) return true;
  }
  // Agent 日誌中過濾 wget
  if (entry.source === 'agent') {
    const msg = entry.message || '';
    if (msg.includes('wget') || msg.includes('Wget')) return true;
  }
  return false;
}
