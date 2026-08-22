/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 全局路由前綴：所有頁面和 API 代理都帶 /TradingWorkstation 前綴
  // 頁面：/TradingWorkstation/agent、/TradingWorkstation/screener 等
  // API 代理：/TradingWorkstation/api/* → 後端 /TradingWorkstation/api/*
  basePath: '/TradingWorkstation',
  // Docker 生產部署用 standalone 模式（自包含，無需 node_modules）
  output: 'standalone',
  // 代理超時：回測等慢操作可能需要 3 分鐘，默認 30 秒不夠
  experimental: {
    proxyTimeout: 180000,
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
