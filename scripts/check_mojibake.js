const fs = require("fs");
const path = require("path");

const root = process.argv[2];
if (!root) {
  console.error("Usage: node scripts/check_mojibake.js <root>");
  process.exit(1);
}

const quotedPattern = /"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'/g;
const targetExtensions = new Set([".js", ".jsx", ".ts", ".tsx"]);
const failures = [];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath);
      continue;
    }

    if (!targetExtensions.has(path.extname(entry.name))) {
      continue;
    }

    const text = fs.readFileSync(fullPath, "utf8");
    let match;
    while ((match = quotedPattern.exec(text))) {
      const body = match[0].slice(1, -1);
      if (body.includes("\uFFFD")) {
        failures.push(fullPath);
        break;
      }
    }
  }
}

walk(root);

if (failures.length > 0) {
  console.error("Mojibake-like quoted strings found:");
  for (const file of failures) {
    console.error(file);
  }
  process.exit(1);
}

console.log(`No mojibake-like quoted strings found in ${root}`);
