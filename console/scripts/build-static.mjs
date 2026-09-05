import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const apiDir = "src/app/api";
const stashDir = "build/api-stash";
fs.mkdirSync("build", { recursive: true });
if (fs.existsSync(apiDir)) fs.renameSync(apiDir, stashDir);
try {
  execSync("npx next build", { stdio: "inherit", env: { ...process.env, STATIC_EXPORT: "1" } });
} finally {
  if (fs.existsSync(stashDir)) fs.renameSync(stashDir, apiDir);
}

/**
 * The export emits `console.html`, but the bucket is served through a REST
 * origin that resolves a bare `/console` to the key `console`, which does not
 * exist. Mirroring each page to `<route>/index.html` makes extensionless URLs
 * resolve without a CloudFront function or website-hosting endpoint, and
 * makes the upload a plain `s3 sync --delete` with nothing to remember.
 */
const mirrorToIndex = (dir) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "_next") continue;
      mirrorToIndex(full);
    } else if (entry.name.endsWith(".html") && entry.name !== "index.html") {
      const target = path.join(dir, entry.name.replace(/\.html$/, ""), "index.html");
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.copyFileSync(full, target);
    }
  }
};
mirrorToIndex("out");
console.log("static export mirrored to directory indexes");
