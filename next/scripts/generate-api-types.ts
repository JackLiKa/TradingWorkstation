/**
 * generate-api-types.ts
 *
 * 從後端 Swagger/OpenAPI spec 自動生成前端 TypeScript 類型。
 *
 * 兩種模式（自動選擇）：
 *   1. URL 模式（優先）：從後端 `/TradingWorkstation/v3/api-docs` 拉取最新 spec
 *   2. 文件 fallback：後端未啟動時，從本地 `src/lib/api/openapi.json` 生成
 *
 * 輸出：`src/lib/api/generated.ts`
 *
 * 用法：
 *   npx tsx scripts/generate-api-types.ts            # 自動（先 URL 後文件）
 *   npx tsx scripts/generate-api-types.ts --url      # 僅 URL 模式
 *   npx tsx scripts/generate-api-types.ts --file     # 僅文件模式
 *
 * 等價的 npm scripts（見 package.json）：
 *   npm run gen:api        # openapi-typescript 直接從 URL 生成
 *   npm run gen:api:local  # openapi-typescript 從本地 openapi.json 生成
 *   npm run gen:api:smart  # 本腳本（自動選擇模式 + 刷新 openapi.json）
 */
import { writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = resolve(__dirname, "..");
const OUTPUT_FILE = resolve(ROOT, "src/lib/api/generated.ts");
const LOCAL_SPEC = resolve(ROOT, "src/lib/api/openapi.json");

// 後端 OpenAPI 端點（注意 context-path 前綴）
const BACKEND_API_DOCS =
  process.env.OPENAPI_URL ??
  "http://localhost:8090/TradingWorkstation/v3/api-docs";

const FETCH_TIMEOUT_MS = 5000;

type Mode = "auto" | "url" | "file";

function parseMode(): Mode {
  const arg = process.argv[2];
  if (arg === "--url") return "url";
  if (arg === "--file") return "file";
  return "auto";
}

/** 帶超時的 fetch，後端未啟動時快速失敗 */
async function fetchWithTimeout(url: string, ms: number): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    return await res.text();
  } finally {
    clearTimeout(timer);
  }
}

/** 把 spec 字符串寫入本地 openapi.json（刷新 fallback 文件） */
function refreshLocalSpec(spec: string): void {
  mkdirSync(dirname(LOCAL_SPEC), { recursive: true });
  writeFileSync(LOCAL_SPEC, spec, "utf8");
  console.log(`[gen:api] 已刷新本地 fallback: ${LOCAL_SPEC}`);
}

/** 用 openapi-typescript 從 spec 字符串生成 TypeScript 類型 */
async function generateFromSpec(spec: string, sourceLabel: string): Promise<void> {
  const ast = await openapiTS(spec, {
    // 後端 DTO 用 Java record，字段名即 JSON 字段名（無 @JsonProperty 改名）
    // 默認導出已能正確映射，這裡保持默認選項
    exportType: true,
    immutable: true,
  });
  const output = `/**\n * 自動生成 — 請勿手工編輯。\n * 由 \`npm run gen:api:smart\`（scripts/generate-api-types.ts）\n * 從後端 OpenAPI spec 生成。\n * 來源：${sourceLabel}\n * 生成時間：${new Date().toISOString()}\n */\n\n${astToString(ast)}`;
  mkdirSync(dirname(OUTPUT_FILE), { recursive: true });
  writeFileSync(OUTPUT_FILE, output, "utf8");
  console.log(`[gen:api] 來源: ${sourceLabel}`);
  console.log(`[gen:api] 輸出: ${OUTPUT_FILE}`);
}

async function main(): Promise<void> {
  const mode = parseMode();
  console.log(`[gen:api] 模式: ${mode}`);

  // 1. URL 模式（auto / url）：嘗試從後端拉取
  if (mode === "auto" || mode === "url") {
    try {
      console.log(`[gen:api] 嘗試從後端拉取: ${BACKEND_API_DOCS}`);
      const spec = await fetchWithTimeout(BACKEND_API_DOCS, FETCH_TIMEOUT_MS);
      console.log(`[gen:api] 拉取成功 (${spec.length} bytes)`);
      // 刷新本地 fallback 文件，確保離線時可用
      refreshLocalSpec(spec);
      await generateFromSpec(spec, BACKEND_API_DOCS);
      return;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[gen:api] 後端拉取失敗: ${msg}`);
      if (mode === "url") {
        // 顯式 --url 模式不 fallback
        console.error("[gen:api] --url 模式不 fallback 到本地文件，退出。");
        process.exit(1);
      }
      console.warn("[gen:api] 自動 fallback 到本地 openapi.json ...");
    }
  }

  // 2. 文件 fallback（auto / file）：從本地 openapi.json 生成
  if (!existsSync(LOCAL_SPEC)) {
    console.error(
      `[gen:api] 本地 fallback 不存在: ${LOCAL_SPEC}\n` +
        "[gen:api] 請先啟動後端並運行 `npm run gen:api:smart` 以生成 openapi.json，\n" +
        "[gen:api] 或手動保存後端 /TradingWorkstation/v3/api-docs 輸出到該路徑。"
    );
    process.exit(1);
  }

  const spec = await import("node:fs/promises").then((fs) =>
    fs.readFile(LOCAL_SPEC, "utf8")
  );
  await generateFromSpec(spec, `local file: ${LOCAL_SPEC}`);
}

main().catch((err) => {
  console.error("[gen:api] 生成失敗:", err);
  process.exit(1);
});
