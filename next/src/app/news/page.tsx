/**
 * @file NewsPage 財經新聞頁 — 雙 Tab：數據庫新聞（分頁）+ 實時抓取（預覽）+ 語義檢索。
 *
 * Tab 1: 數據庫新聞 — 從 Java 後端 /api/news 分頁查詢已入庫新聞（守護進程定時抓取）
 * Tab 2: 實時抓取 — 直接調 Agent API 實時抓取華爾街見聞最新新聞（預覽用）
 * Tab 3: 語義檢索 — 向量庫語義搜索
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
import {
  agentApi,
  newsDbApi,
  type WallstreetcnNewsItem,
  type DbNewsItem,
} from '@/lib/api/agent';
import { Newspaper, Search, Database, ExternalLink, Loader2, ChevronLeft, ChevronRight, Zap } from 'lucide-react';

type TabKey = 'database' | 'live' | 'vector';

const TABS: { key: TabKey; label: string; icon: typeof Newspaper }[] = [
  { key: 'database', label: '數據庫新聞', icon: Database },
  { key: 'live', label: '實時抓取', icon: Zap },
  { key: 'vector', label: '語義檢索', icon: Search },
];

/** 頻道選項 */
const CHANNELS = [
  { value: 'a-stock', label: 'A 股' },
  { value: 'global', label: '全球' },
  { value: 'us-stock', label: '美股' },
  { value: 'hk-stock', label: '港股' },
  { value: 'forex', label: '外匯' },
  { value: 'commodity', label: '商品' },
];

const PAGE_SIZE = 20;

export default function NewsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('database');

  // ===== 數據庫新聞 Tab 狀態 =====
  const [dbPage, setDbPage] = useState(0);
  const [dbChannel, setDbChannel] = useState<string>(''); // 空 = 全部頻道

  // ===== 實時抓取 Tab 狀態 =====
  const [liveChannel, setLiveChannel] = useState('a-stock');
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  // ===== 語義檢索 Tab 狀態 =====
  const [searchKeyword, setSearchKeyword] = useState('');
  const [vectorQuery, setVectorQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<WallstreetcnNewsItem[]>([]);
  const [vectorSearching, setVectorSearching] = useState(false);
  const [vectorResults, setVectorResults] = useState<WallstreetcnNewsItem[]>([]);

  // ===== 數據庫新聞查詢 =====
  const dbQueryKey = dbChannel
    ? `news-db-channel-${dbChannel}-${dbPage}`
    : `news-db-latest-${dbPage}`;
  const { data: dbPageData, error: dbError, mutate: mutateDb, isValidating: dbLoading } = useSWR(
    dbQueryKey,
    () => dbChannel
      ? newsDbApi.listByChannel(dbChannel, dbPage, PAGE_SIZE)
      : newsDbApi.listLatest(dbPage, PAGE_SIZE),
    { revalidateOnFocus: false }
  );

  // ===== 實時抓取 =====
  const { data: latestData, error: latestError, mutate: mutateLatest, isValidating: liveLoading } = useSWR(
    `wallstreetcn-latest-${liveChannel}`,
    () => agentApi.getWallstreetcnLatest(liveChannel, 20),
    { refreshInterval: 60000, revalidateOnFocus: false }
  );

  // ===== 向量庫狀態 =====
  const { data: vectorStatus } = useSWR('news-vector-status', () => agentApi.getNewsVectorStatus(), {
    refreshInterval: 30000,
    revalidateOnFocus: false,
  });

  // 去重
  const dedupedLiveNews = useMemo(() => {
    if (!latestData?.news) return [];
    return dedupNews(latestData.news);
  }, [latestData]);

  const dedupedSearchResults = useMemo(() => dedupNews(searchResults), [searchResults]);
  const dedupedVectorResults = useMemo(() => dedupNews(vectorResults), [vectorResults]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await agentApi.syncWallstreetcnNews(liveChannel, 20);
      const filteredInfo = 'filtered' in result ? `，過濾噪音 ${(result as any).filtered} 條` : '';
      setSyncResult(`抓取 ${result.fetched} 條，新存入 ${result.stored} 條，重複 ${result.duplicated} 條${filteredInfo}`);
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
      const result = await agentApi.vectorSearchNews(vectorQuery, 10, liveChannel, 7);
      setVectorResults(result.news);
    } catch (e) {
      setVectorResults([]);
    } finally {
      setVectorSearching(false);
    }
  };

  // 分頁信息
  const totalPages = dbPageData?.totalPages ?? 0;
  const currentPage = dbPageData?.number ?? 0;
  const totalElements = dbPageData?.totalElements ?? 0;

  return (
    <div className="space-y-6">
      {/* 頁面標題 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Newspaper className="w-6 h-6 text-accent" />
          <h1 className="text-xl font-bold text-slate-100">財經新聞</h1>
          <Badge variant="info">華爾街見聞</Badge>
          {totalElements > 0 && activeTab === 'database' && (
            <Badge variant="success">數據庫 {totalElements} 條</Badge>
          )}
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
        </div>
      </div>

      {syncResult && (
        <div className="rounded-lg border border-accent/30 bg-accent/5 px-4 py-2 text-sm text-accent">
          {syncResult}
        </div>
      )}

      {/* Tab 切換 */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ===== Tab 1: 數據庫新聞（分頁）===== */}
      {activeTab === 'database' && (
        <>
          {/* 頻道過濾 */}
          <Card>
            <CardHeader>
              <CardTitle>頻道過濾</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => { setDbChannel(''); setDbPage(0); }}
                  className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                    dbChannel === ''
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border text-muted hover:border-accent/50'
                  }`}
                >
                  全部
                </button>
                {CHANNELS.map((ch) => (
                  <button
                    key={ch.value}
                    onClick={() => { setDbChannel(ch.value); setDbPage(0); }}
                    className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                      dbChannel === ch.value
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

          {/* 新聞列表 */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>
                  數據庫新聞
                  {dbChannel && ` — ${CHANNELS.find((c) => c.value === dbChannel)?.label}`}
                  {totalElements > 0 && ` （共 ${totalElements} 條）`}
                </CardTitle>
                <RefreshButton onClick={() => mutateDb()} isLoading={dbLoading} />
              </div>
            </CardHeader>
            <CardContent>
              {dbError && <ErrorState message={`載入失敗: ${(dbError as Error).message}`} onRetry={() => mutateDb()} />}
              {dbPageData && dbPageData.content.length > 0 ? (
                <div className="space-y-3">
                  {dbPageData.content.map((n) => (
                    <DbNewsCard key={n.id} news={n} />
                  ))}
                </div>
              ) : (
                !dbError && !dbLoading && <div className="text-muted text-sm">無數據。守護進程會定時抓取新聞入庫。</div>
              )}
              {dbLoading && !dbPageData && <div className="text-muted text-sm">載入中...</div>}

              {/* 分頁控件 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
                  <span className="text-xs text-muted">
                    第 {currentPage + 1} / {totalPages} 頁
                  </span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setDbPage(Math.max(0, currentPage - 1))}
                      disabled={currentPage === 0}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      上一頁
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setDbPage(Math.min(totalPages - 1, currentPage + 1))}
                      disabled={currentPage >= totalPages - 1}
                    >
                      下一頁
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ===== Tab 2: 實時抓取（預覽）===== */}
      {activeTab === 'live' && (
        <>
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
                    onClick={() => setLiveChannel(ch.value)}
                    className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                      liveChannel === ch.value
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

          {/* 實時新聞列表 */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>實時新聞 — {CHANNELS.find((c) => c.value === liveChannel)?.label}</CardTitle>
                <RefreshButton onClick={() => mutateLatest()} isLoading={liveLoading} />
              </div>
            </CardHeader>
            <CardContent>
              {latestError && <ErrorState message={`載入失敗: ${(latestError as Error).message}`} onRetry={() => mutateLatest()} />}
              {dedupedLiveNews.length > 0 ? (
                <div className="space-y-3">
                  {dedupedLiveNews.map((n, i) => (
                    <LiveNewsCard key={`${n.uri}-${i}`} news={n} />
                  ))}
                </div>
              ) : (
                !latestError && <div className="text-muted text-sm">載入中或無數據...</div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ===== Tab 3: 語義檢索 ===== */}
      {activeTab === 'vector' && (
        <>
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
                    <LiveNewsCard key={`${n.uri}-${i}`} news={n} />
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
                    <LiveNewsCard key={`${n.uri}-${i}`} news={n} showSimilarity />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/** 數據庫新聞卡片 */
function DbNewsCard({ news }: { news: DbNewsItem }) {
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
            {news.publishedAt && <span>·</span>}
            {news.publishedAt && <span>{news.publishedAt.slice(0, 16).replace('T', ' ')}</span>}
            {news.channel && <span>·</span>}
            {news.channel && <Badge variant="info">{news.channel}</Badge>}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 實時抓取新聞卡片 */
function LiveNewsCard({ news, showSimilarity = false }: { news: WallstreetcnNewsItem; showSimilarity?: boolean }) {
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
