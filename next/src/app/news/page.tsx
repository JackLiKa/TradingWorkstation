/**
 * @file NewsPage 財經新聞頁 — 展示華爾街見聞最新新聞、語義檢索、同步管理。
 * 支持頻道切換、關鍵詞搜索、向量庫語義檢索、定時同步。
 */
'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { ErrorState } from '@/components/ui/ErrorState';
import { agentApi, type WallstreetcnNewsItem } from '@/lib/api/agent';
import { Newspaper, Search, Database, ExternalLink, Loader2 } from 'lucide-react';

/** 頻道選項 */
const CHANNELS = [
  { value: 'a-stock', label: 'A 股' },
  { value: 'global', label: '全球' },
  { value: 'us-stock', label: '美股' },
  { value: 'hk-stock', label: '港股' },
  { value: 'forex', label: '外匯' },
  { value: 'commodity', label: '商品' },
];

export default function NewsPage() {
  const [channel, setChannel] = useState('a-stock');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [vectorQuery, setVectorQuery] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<WallstreetcnNewsItem[]>([]);
  const [vectorSearching, setVectorSearching] = useState(false);
  const [vectorResults, setVectorResults] = useState<WallstreetcnNewsItem[]>([]);

  // 抓取最新新聞
  const { data: latestData, error: latestError, mutate: mutateLatest, isValidating } = useSWR(
    `wallstreetcn-latest-${channel}`,
    () => agentApi.getWallstreetcnLatest(channel, 20),
    { refreshInterval: 60000 }
  );

  // 對最新新聞去重（按 uri + title 組合去重，避免 React key 衝突）
  const dedupedLatestNews = useMemo(() => {
    if (!latestData?.news) return [];
    return dedupNews(latestData.news);
  }, [latestData]);

  // 對搜索結果去重
  const dedupedSearchResults = useMemo(() => dedupNews(searchResults), [searchResults]);

  // 對語義檢索結果去重
  const dedupedVectorResults = useMemo(() => dedupNews(vectorResults), [vectorResults]);

  // 向量庫狀態
  const { data: vectorStatus } = useSWR('news-vector-status', () => agentApi.getNewsVectorStatus(), {
    refreshInterval: 30000,
  });

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await agentApi.syncWallstreetcnNews(channel, 20);
      setSyncResult(`抓取 ${result.fetched} 條，新存入 ${result.stored} 條，重複 ${result.duplicated} 條`);
      await mutateLatest();
    } catch (e) {
      setSyncResult(`同步失敗: ${(e as Error).message}`);
    } finally {
      setSyncing(false);
    }
  };

  const handleSearch = async () => {
    if (!searchKeyword.trim()) return;
    setSearching(true);
    try {
      const result = await agentApi.searchWallstreetcn(searchKeyword, 10);
      setSearchResults(result.news);
    } catch (e) {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleVectorSearch = async () => {
    if (!vectorQuery.trim()) return;
    setVectorSearching(true);
    try {
      const result = await agentApi.vectorSearchNews(vectorQuery, 10, channel, 7);
      setVectorResults(result.news);
    } catch (e) {
      setVectorResults([]);
    } finally {
      setVectorSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 頁面標題 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Newspaper className="w-6 h-6 text-accent" />
          <h1 className="text-xl font-bold text-slate-100">財經新聞</h1>
          <Badge variant="info">華爾街見聞</Badge>
        </div>
        <div className="flex items-center gap-2">
          {vectorStatus && (
            <Badge variant={vectorStatus.available ? 'success' : 'danger'}>
              <Database className="w-3 h-3 mr-1" />
              向量庫 {vectorStatus.available ? '可用' : '不可用'}
            </Badge>
          )}
          <Button onClick={handleSync} disabled={syncing} size="sm">
            {syncing ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Newspaper className="w-4 h-4 mr-1" />}
            同步新聞
          </Button>
          <RefreshButton onClick={() => mutateLatest()} isLoading={isValidating} />
        </div>
      </div>

      {syncResult && (
        <div className="rounded-lg border border-accent/30 bg-accent/5 px-4 py-2 text-sm text-accent">
          {syncResult}
        </div>
      )}

      {/* 頻道切換 */}
      <Card>
        <CardHeader>
          <CardTitle>頻道選擇</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {CHANNELS.map((ch) => (
              <button
                key={ch.value}
                onClick={() => setChannel(ch.value)}
                className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                  channel === ch.value
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-muted hover:border-accent/50'
                }`}
              >
                {ch.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 最新新聞列表 */}
      <Card>
        <CardHeader>
          <CardTitle>最新新聞 — {CHANNELS.find((c) => c.value === channel)?.label}</CardTitle>
        </CardHeader>
        <CardContent>
          {latestError && <ErrorState message={`載入失敗: ${(latestError as Error).message}`} onRetry={() => mutateLatest()} />}
          {dedupedLatestNews.length > 0 ? (
            <div className="space-y-3">
              {dedupedLatestNews.map((n, i) => (
                <NewsCard key={`${n.uri}-${i}`} news={n} />
              ))}
            </div>
          ) : (
            !latestError && <div className="text-muted text-sm">載入中或無數據...</div>
          )}
        </CardContent>
      </Card>

      {/* 關鍵詞搜索 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <Search className="w-4 h-4 inline mr-2" />
            關鍵詞搜索
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              placeholder="搜索關鍵詞（如「半導體」「新能源」「英偉達」）"
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <Button onClick={handleSearch} disabled={searching || !searchKeyword.trim()}>
              {searching ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Search className="w-4 h-4 mr-1" />}
              搜索
            </Button>
          </div>
          {dedupedSearchResults.length > 0 && (
            <div className="space-y-2">
              {dedupedSearchResults.map((n, i) => (
                <NewsCard key={`${n.uri}-${i}`} news={n} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 向量庫語義檢索 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <Database className="w-4 h-4 inline mr-2" />
            語義檢索（向量庫）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!vectorStatus?.available && (
            <div className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/30 rounded p-2">
              向量庫不可用 — 需要 Milvus + sentence-transformers。請確保 Agent 依賴已安裝。
            </div>
          )}
          <div className="flex gap-2">
            <Input
              value={vectorQuery}
              onChange={(e) => setVectorQuery(e.target.value)}
              placeholder="語義查詢（如「半導體行業利好，A股市場震盪」）"
              onKeyDown={(e) => e.key === 'Enter' && handleVectorSearch()}
              disabled={!vectorStatus?.available}
            />
            <Button onClick={handleVectorSearch} disabled={vectorSearching || !vectorQuery.trim() || !vectorStatus?.available}>
              {vectorSearching ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Database className="w-4 h-4 mr-1" />}
              檢索
            </Button>
          </div>
          {dedupedVectorResults.length > 0 && (
            <div className="space-y-2">
              {dedupedVectorResults.map((n, i) => (
                <NewsCard key={`${n.uri}-${i}`} news={n} showSimilarity />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** 單條新聞卡片 */
function NewsCard({ news, showSimilarity = false }: { news: WallstreetcnNewsItem; showSimilarity?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-3 hover:border-accent/30 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <a
            href={news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-slate-100 hover:text-accent flex items-start gap-1"
          >
            <span className="flex-1">{news.title}</span>
            <ExternalLink className="w-3 h-3 flex-shrink-0 mt-1 text-muted" />
          </a>
          {news.summary && (
            <p className="text-xs text-muted mt-1 line-clamp-2">{news.summary}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted">
            <span>{news.source}</span>
            {news.date && <span>·</span>}
            {news.date && <span>{news.date.slice(0, 10)}</span>}
            {news.channel && <span>·</span>}
            {news.channel && <Badge variant="info">{news.channel}</Badge>}
            {showSimilarity && news.similarity !== undefined && (
              <>
                <span>·</span>
                <span className="text-accent">相似度: {news.similarity}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 去重新聞列表 — 按 uri 優先去重，uri 為空時按 title 去重 */
function dedupNews(news: WallstreetcnNewsItem[]): WallstreetcnNewsItem[] {
  const seen = new Set<string>();
  return news.filter((n) => {
    const key = n.uri || n.title;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
