/**
 * @file API 客戶端 + 工具函數單元測試。
 *
 * 覆蓋：
 * 1. API client 構建 URL 正確（basePath 前綴）
 * 2. ApiError 類型守衛與錯誤碼傳遞
 * 3. 格式化工具函數（formatPercent / formatCurrency / formatVolume）
 * 4. className 合併工具 cn
 * 5. useEChartsOption 空態判斷工具 isEmptyData
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiFetch, apiPost, ApiError } from '../client';
import { formatPercent, formatCurrency, formatVolume, formatNumber, pctClass, describeCross } from '../../format';
import { cn } from '../../utils';
import { isEmptyData } from '@/hooks/useEChartsOption';

// ===== fetch mock =====
const fetchMock = vi.fn();
const originalFetch = globalThis.fetch;

beforeEach(() => {
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

/** 構造一個成功的後端統一響應 mock */
function mockOkResponse(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ success: true, code: 'OK', message: 'ok', data }),
  };
}

/** 構造一個 HTTP 錯誤的 mock */
function mockErrorResponse(status: number, message: string) {
  return {
    ok: false,
    status,
    json: async () => ({ success: false, code: `HTTP_${status}`, message }),
  };
}

// ===== 1. API client URL 構建 =====
describe('API client URL 構建', () => {
  it('apiFetch 為相對路徑添加 basePath + /api 前綴', async () => {
    fetchMock.mockResolvedValue(mockOkResponse({ hello: 'world' }));
    await apiFetch('/dashboard/summary');
    const calledUrl = fetchMock.mock.calls[0][0];
    // 默認 API_BASE = /TradingWorkstation，路徑應為 /TradingWorkstation/api/dashboard/summary
    expect(calledUrl).toBe('/TradingWorkstation/api/dashboard/summary');
  });

  it('apiFetch 對完整 http URL 不添加前綴', async () => {
    fetchMock.mockResolvedValue(mockOkResponse({}));
    await apiFetch('http://localhost:8090/TradingWorkstation/api/health');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toBe('http://localhost:8090/TradingWorkstation/api/health');
  });

  it('apiPost 為相對路徑添加 basePath + /api 前綴', async () => {
    fetchMock.mockResolvedValue(mockOkResponse({ id: 1 }));
    await apiPost('/backtest/run', { code: 'sh.600000' });
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toBe('/TradingWorkstation/api/backtest/run');
  });

  it('apiPost 傳遞 JSON body 和 POST method', async () => {
    fetchMock.mockResolvedValue(mockOkResponse({ id: 1 }));
    await apiPost('/screener/run', { filters: [] });
    const callOpts = fetchMock.mock.calls[0][1];
    expect(callOpts.method).toBe('POST');
    expect(callOpts.body).toBe(JSON.stringify({ filters: [] }));
    expect(callOpts.headers['Content-Type']).toBe('application/json');
  });
});

// ===== 2. ApiError 類型守衛 + 錯誤傳遞 =====
describe('ApiError 類型守衛與錯誤傳遞', () => {
  it('ApiError 是 Error 子類，攜帶 code', () => {
    const err = new ApiError('HTTP_500', '伺服器內部錯誤');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe('HTTP_500');
    expect(err.message).toBe('伺服器內部錯誤');
    expect(err.name).toBe('ApiError');
  });

  it('apiFetch 在 HTTP 非 2xx 時拋出 ApiError', async () => {
    fetchMock.mockResolvedValue(mockErrorResponse(500, '伺服器內部錯誤'));
    await expect(apiFetch('/dashboard/summary')).rejects.toThrow();
    try {
      await apiFetch('/dashboard/summary');
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).code).toBe('HTTP_500');
    }
  });

  it('apiFetch 在 body.success=false 時拋出 ApiError 攜帶後端 code', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: false, code: 'BIZ_ERROR', message: '業務異常' }),
    });
    await expect(apiFetch('/stock/movers')).rejects.toThrow('業務異常');
    try {
      await apiFetch('/stock/movers');
    } catch (e) {
      expect((e as ApiError).code).toBe('BIZ_ERROR');
    }
  });

  it('instanceof ApiError 可作類型守衛區分錯誤來源', () => {
    const apiErr = new ApiError('TIMEOUT', '超時');
    const genericErr = new Error('普通錯誤');
    expect(apiErr instanceof ApiError).toBe(true);
    expect(genericErr instanceof ApiError).toBe(false);
  });
});

// ===== 3. 格式化工具函數 =====
describe('格式化工具函數', () => {
  it('formatPercent 格式化百分比', () => {
    expect(formatPercent(3.14159, 2)).toBe('3.14%');
    expect(formatPercent(-0.5, 2)).toBe('-0.50%');
    expect(formatPercent(null)).toBe('0.00%');
    expect(formatPercent(undefined)).toBe('0.00%');
    expect(formatPercent(10, 0)).toBe('10%');
  });

  it('formatCurrency 自動轉換億/萬單位', () => {
    expect(formatCurrency(150_000_000)).toBe('1.50 亿');
    expect(formatCurrency(50_000)).toBe('5.00 万');
    expect(formatCurrency(null)).toBe('0');
    expect(formatCurrency(999)).toBe('999.00');
  });

  it('formatVolume 自動轉換億/萬單位', () => {
    expect(formatVolume(200_000_000)).toBe('2.00亿');
    expect(formatVolume(30_000)).toBe('3.00万');
    expect(formatVolume(null)).toBe('-');
    expect(formatVolume(500)).toBe('500');
  });

  it('formatNumber 固定小數位', () => {
    expect(formatNumber(3.14159, 2)).toBe('3.14');
    expect(formatNumber(null)).toBe('-');
    expect(formatNumber(undefined)).toBe('-');
  });

  it('pctClass 根據漲跌幅返回顏色類名', () => {
    expect(pctClass(5.0)).toBe('text-up');
    expect(pctClass(-3.0)).toBe('text-down');
    expect(pctClass(0)).toBe('text-slate-300');
    expect(pctClass(null)).toBe('text-slate-300');
  });

  it('describeCross 交叉信號中文描述', () => {
    expect(describeCross('golden_cross')).toBe('金叉');
    expect(describeCross('death_cross')).toBe('死叉');
    expect(describeCross('none')).toBe('无交叉');
    expect(describeCross('unknown')).toBe('不限');
  });
});

// ===== 4. className 合併工具 cn =====
describe('cn className 合併工具', () => {
  it('合併多個類名', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('處理條件類名（false / undefined 被忽略）', () => {
    expect(cn('base', false && 'hidden', undefined, 'visible')).toBe('base visible');
  });

  it('tailwind-merge 去重衝突類名（後定義覆蓋）', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });
});

// ===== 5. isEmptyData 空態判斷 =====
describe('isEmptyData 空態判斷', () => {
  it('null / undefined 為空', () => {
    expect(isEmptyData(null)).toBe(true);
    expect(isEmptyData(undefined)).toBe(true);
  });

  it('空數組為空', () => {
    expect(isEmptyData([])).toBe(true);
  });

  it('非空數組不為空', () => {
    expect(isEmptyData([1, 2, 3])).toBe(false);
  });

  it('空對象為空', () => {
    expect(isEmptyData({})).toBe(true);
  });

  it('空字符串為空', () => {
    expect(isEmptyData('')).toBe(true);
  });

  it('非空字符串不為空', () => {
    expect(isEmptyData('hello')).toBe(false);
  });

  it('數字不為空', () => {
    expect(isEmptyData(0)).toBe(false);
    expect(isEmptyData(42)).toBe(false);
  });
});
