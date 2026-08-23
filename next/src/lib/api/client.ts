/**
 * @file 後端 API 客戶端 — 封裝 fetch 請求，統一處理錯誤和響應解析。
 * 所有請求經 next.config.js rewrites 代理到 Java 後端 (8090)。
 */

/** 後端統一響應格式（success + code + message + data） */
export interface ApiResponse<T> {
  success: boolean;
  code: string;
  message: string;
  data: T;
}

/** API 錯誤類，攜帶後端返回的錯誤 code */
export class ApiError extends Error {
  code: string;
  /**
   * @param code 錯誤碼（如 HTTP_500 或後端自定義 code）
   * @param message 錯誤消息
   */
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = 'ApiError';
  }
}

// API_BASE 用於構建後端請求 URL。默認為 /TradingWorkstation（與 basePath 一致），
// 這樣相對路徑 /api/dashboard/summary 會變成 /TradingWorkstation/api/dashboard/summary，
// 經 next.config.js rewrites 代理到後端 http://localhost:8090/TradingWorkstation/api/...
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/TradingWorkstation';

/** API Key（從環境變量讀取，若後端啟用認證則需設置 NEXT_PUBLIC_API_KEY） */
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

/** 構建帶 API Key 的請求頭。 */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...extra };
  if (API_KEY) headers['X-API-Key'] = API_KEY;
  return headers;
}

/**
 * 發送 GET 請求並解析後端統一響應格式。
 * @param input API 路徑（相對路徑如 `/dashboard/summary`，或完整 URL）
 * @returns 後端響應中的 data 字段（類型 T）
 * @throws ApiError 當 HTTP 狀態碼非 2xx 或 body.success 為 false 時拋出
 */
export async function apiFetch<T>(input: string): Promise<T> {
  const url = input.startsWith('http') ? input : `${API_BASE}/api${input}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.message || message;
    } catch {}
    throw new ApiError(`HTTP_${res.status}`, message);
  }
  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new ApiError(body.code, body.message);
  }
  return body.data;
}

/**
 * 發送 POST 請求並解析後端統一響應格式。
 * @param input API 路徑
 * @param payload 請求體（會被 JSON.stringify）
 * @param timeoutMs 超時毫秒（默認 30 秒，回測等慢操作可傳更大值）
 * @returns 後端響應中的 data 字段（類型 T）
 * @throws ApiError 當 HTTP 狀態碼非 2xx 或 body.success 為 false 時拋出
 */
export async function apiPost<T>(input: string, payload: unknown, timeoutMs = 30000): Promise<T> {
  const url = input.startsWith('http') ? input : `${API_BASE}/api${input}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        message = body.message || message;
      } catch {}
      throw new ApiError(`HTTP_${res.status}`, message);
    }
    const body: ApiResponse<T> = await res.json();
    if (!body.success) {
      throw new ApiError(body.code, body.message);
    }
    return body.data;
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      throw new ApiError('TIMEOUT', `请求超时（${timeoutMs / 1000}秒）`);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 發送 PUT 請求並解析後端統一響應格式。
 * @param input API 路徑
 * @param payload 請求體（會被 JSON.stringify）
 * @returns 後端響應中的 data 字段（類型 T）
 * @throws ApiError 當 HTTP 狀態碼非 2xx 或 body.success 為 false 時拋出
 */
export async function apiPut<T>(input: string, payload: unknown): Promise<T> {
  const url = input.startsWith('http') ? input : `${API_BASE}/api${input}`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.message || message;
    } catch {}
    throw new ApiError(`HTTP_${res.status}`, message);
  }
  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new ApiError(body.code, body.message);
  }
  return body.data;
}

/**
 * 發送 DELETE 請求並解析後端統一響應格式。
 * @param input API 路徑
 * @returns 後端響應中的 data 字段（類型 T）
 * @throws ApiError 當 HTTP 狀態碼非 2xx 或 body.success 為 false 時拋出
 */
export async function apiDelete<T>(input: string): Promise<T> {
  const url = input.startsWith('http') ? input : `${API_BASE}/api${input}`;
  const res = await fetch(url, { method: 'DELETE', headers: authHeaders() });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.message || message;
    } catch {}
    throw new ApiError(`HTTP_${res.status}`, message);
  }
  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new ApiError(body.code, body.message);
  }
  return body.data;
}

/**
 * 發送 PATCH 請求並解析後端統一響應格式。
 * @param input API 路徑
 * @param payload 請求體（會被 JSON.stringify）
 * @returns 後端響應中的 data 字段（類型 T）
 * @throws ApiError 當 HTTP 狀態碼非 2xx 或 body.success 為 false 時拋出
 */
export async function apiPatch<T>(input: string, payload: unknown): Promise<T> {
  const url = input.startsWith('http') ? input : `${API_BASE}/api${input}`;
  const res = await fetch(url, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.message || message;
    } catch {}
    throw new ApiError(`HTTP_${res.status}`, message);
  }
  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new ApiError(body.code, body.message);
  }
  return body.data;
}
