/* 独立 esbuild CLI 打包脚本（绕开 vite/rollup/esbuild-JS-API 卡顿）。
 * 直接调用 @esbuild/win32-x64/esbuild.exe 命令行完成打包，
 * 产物结构与 vite build 一致：dist/index.html + dist/assets/index-<hash>.js/.css。
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { writeFileSync, mkdirSync, readFileSync, rmSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const outDir = join(root, "dist");
const assetsDir = join(outDir, "assets");

// 定位 esbuild CLI（根目录那份，已确认能跑）
const esbCli = join(root, "node_modules", "@esbuild", "win32-x64", "esbuild.exe");
if (!existsSync(esbCli)) throw new Error("找不到 esbuild.exe: " + esbCli);

if (existsSync(assetsDir)) rmSync(assetsDir, { recursive: true, force: true });
mkdirSync(assetsDir, { recursive: true });

// 入口入口文件
const entry = join(root, "src", "main.jsx");
const cssEntry = join(root, "src", "styles.css");

// 1) 打包 JS（输出到临时目录，再重命名为带 hash 的文件）
const tmpJs = join(outDir, "tmp-bundle.js");
const args = [
  entry,
  "--bundle",
  "--format=esm",
  "--target=es2020",
  "--jsx=automatic",
  "--minify",
  "--outfile=" + tmpJs,
  "--loader:.js=jsx",
  "--loader:.jsx=jsx",
];
console.log("RUN esbuild CLI:", esbCli, args.slice(0, 4).join(" "), "...");
execFileSync(esbCli, args, { encoding: "utf8", timeout: 120000 });

const jsCode = readFileSync(tmpJs, "utf8");
const jsHash = createHash("sha1").update(jsCode).digest("hex").slice(0, 8);
const jsName = `index-${jsHash}.js`;
writeFileSync(join(assetsDir, jsName), jsCode);
rmSync(tmpJs, { force: true });

// 2) 处理 CSS（esbuild CLI 不打包 CSS，直接复制 + 加 hash）
const cssCode = readFileSync(cssEntry, "utf8");
const cssHash = createHash("sha1").update(cssCode).digest("hex").slice(0, 8);
const cssName = `index-${cssHash}.css`;
writeFileSync(join(assetsDir, cssName), cssCode);

// 3) 生成 index.html
const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#171514" />
    <meta
      name="description"
      content="一键山大——本地优先的山东大学通知智能整理台"
    />
    <title>一键山大</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" crossorigin src="./assets/${jsName}"></script>
    <link rel="stylesheet" crossorigin href="./assets/${cssName}">
  </body>
</html>
`;
writeFileSync(join(outDir, "index.html"), html);

console.log("BUILD_OK");
console.log("JS", jsName, (jsCode.length / 1024).toFixed(1) + "KB");
console.log("CSS", cssName, (cssCode.length / 1024).toFixed(1) + "KB");
