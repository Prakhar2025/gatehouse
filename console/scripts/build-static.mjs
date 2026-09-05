import { execSync } from "node:child_process";
import fs from "node:fs";

const apiDir = "src/app/api";
const stashDir = "build/api-stash";
fs.mkdirSync("build", { recursive: true });
if (fs.existsSync(apiDir)) fs.renameSync(apiDir, stashDir);
try {
  execSync("npx next build", { stdio: "inherit", env: { ...process.env, STATIC_EXPORT: "1" } });
} finally {
  if (fs.existsSync(stashDir)) fs.renameSync(stashDir, apiDir);
}
