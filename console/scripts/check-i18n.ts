/**
 * Locale parity check (doc 10 acceptance criterion 5). Fails when a key
 * exists in en but is missing in hi. Wired as an npm script so the console
 * CI picks it up the moment JS CI exists.
 */
import { execSync } from "node:child_process";
import { copyFor, locales, type CopyKey } from "../src/lib/i18n/index";

const enKeys = Object.keys(locales.en);
const missingHi = enKeys.filter((k) => locales.hi[k as CopyKey] === undefined);

if (missingHi.length > 0) {
  console.error("hi missing keys:", missingHi.join(", "));
  process.exit(1);
}

// spot-check interpolation renders without throwing
copyFor("en", "gate_all_clear_body", { screened: 14, silent: 12 });
copyFor("hi", "gate_needs_you_body", { open: 3 });

console.log(`i18n parity ok: ${enKeys.length} keys, en/hi aligned`);
execSync("echo parity-verified", { stdio: "inherit" });
