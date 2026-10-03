/** 用纯 JS 的 @babel/parser 校验 src 下所有 JSX/JS 文件的语法（不依赖 esbuild）。 */
const fs = require("fs");
const path = require("path");
const { parse } = require("@babel/parser");

const root = path.resolve(__dirname, "..");
const src = path.join(root, "src");
const files = [];
(function walk(dir) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    const s = fs.statSync(p);
    if (s.isDirectory()) walk(p);
    else if (/\.(jsx?|tsx?)$/.test(f)) files.push(p);
  }
})(src);

let errors = 0;
for (const f of files) {
  const code = fs.readFileSync(f, "utf8");
  try {
    parse(code, { sourceType: "module", plugins: ["jsx", "typescript"] });
  } catch (e) {
    errors += 1;
    console.log("SYNTAX ERROR:", path.relative(root, f), "\n  ", e.message);
  }
}
console.log(`checked ${files.length} files, syntax errors: ${errors}`);
