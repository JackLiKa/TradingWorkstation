/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 全局路由前綴：所有頁面和 API 代理都帶 /TradingWorkstation 前綴
  // 頁面：/TradingWorkstation/agent、/TradingWorkstation/screener 等
  // API 代理：/TradingWorkstation/api/* → 後端 /TradingWorkstation/api/*
  basePath: '/TradingWorkstation',
  // Docker 生產部署用 standalone 模式（自包含，無需 node_modules）
  output: 'standalone',
  // 生產環境關閉 sourcemap，防止源碼暴露
  productionBrowserSourceMaps: false,
  // 代理超時：回測等慢操作可能需要 3 分鐘，默認 30 秒不夠
  experimental: {
    proxyTimeout: 180000,
  },
  // ===== 安全頭（參考 jnuxky.xyz 安全兜底機制）=====
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          // 防止點擊劫持（頁面被 iframe 嵌入）
          { key: 'X-Frame-Options', value: 'DENY' },
          // 防止 MIME 嗅探
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          // 舊版瀏覽器 XSS 過濾
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          // 限制 Referer 洩露
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          // CSP — 限制資源加載來源，防範 XSS
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              // 允許內聯樣式（Next.js 需要）和內聯腳本（Next.js hydration 需要 nonce，這裡放寬）
              "style-src 'self' 'unsafe-inline'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              // 允許 ECharts 和外部圖表資源
              "img-src 'self' data: https:",
              // 允許連接後端 API 和 Agent
              "connect-src 'self' http://localhost:8090 http://localhost:8100",
              // 字體來源
              "font-src 'self' data:",
              // 禁止 object/embed
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join('; '),
          },
        ],
      },
    ];
  },
  async redirects() {
    return [
      // 根路徑重定向到 basePath，避免訪問 http://localhost:3010/ 時 404
      {
        source: '/',
        destination: '/TradingWorkstation',
        permanent: false,
        basePath: false,
      },
    ];
  },
  async rewrites() {
    // rewrites 的代理目標固定指向後端服務地址（不用 NEXT_PUBLIC_API_BASE，避免前綴重複）
    const backendHost = process.env.BACKEND_HOST || 'http://localhost:8090';
    const agentHost = process.env.AGENT_HOST || 'http://localhost:8100';
    return [
      // basePath 自動為 rewrite source 加前綴，實際匹配 /TradingWorkstation/api/:path*
      { source: '/api/:path*', destination: `${backendHost}/TradingWorkstation/api/:path*` },
      // agent 服務統一走 next 反代，避免瀏覽器直連 :8100 的 CORS 問題
      { source: '/agent-api/:path*', destination: `${agentHost}/api/agent/:path*` },
    ];
  },
};

module.exports = nextConfig;
