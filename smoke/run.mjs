/**
 * 用 esbuild 把 smoke/render-check.jsx 打包成 CJS 再在 Node 里执行，
 * 这样无需浏览器就能验证每个页面能否正常渲染。
 */

import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const outfile = join(mkdtempSync(join(tmpdir(), "yjsd-smoke-")), "bundle.cjs");

await build({
  entryPoints: ["smoke/render-check.jsx"],
  bundle: true,
  outfile,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  loader: { ".js": "jsx", ".jsx": "jsx" },
  logLevel: "warning",
});

// 页面里用到 fetch / localStorage，这里给出最小桩实现，避免 Node 环境报错。
const shim = `
const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  clear: () => store.clear(),
};
globalThis.fetch = () => Promise.reject(new Error('offline in smoke test'));
globalThis.window = undefined;
require(${JSON.stringify(outfile)});
`;

const shimFile = `${outfile}.shim.cjs`;
writeFileSync(shimFile, shim);

const result = spawnSync(process.execPath, [shimFile], { stdio: "inherit" });
process.exit(result.status ?? 1);
