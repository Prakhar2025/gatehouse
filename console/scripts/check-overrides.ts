/**
 * Override reduction check. The live review counters and the "flagged wrong"
 * filter both read this reduction, so a re-tap that inflates the denominator
 * or a stale label that wins over a newer one is a measurement lie, not a
 * cosmetic bug. Wired as an npm script alongside the i18n parity check.
 */
import { reduceOverrides } from "../src/lib/aws";

let failures = 0;

function check(name: string, actual: unknown, expected: unknown): void {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    console.error(`FAIL ${name}\n  expected ${b}\n  actual   ${a}`);
    failures += 1;
  }
}

const row = (sk: string, caseId: string, agree: boolean, createdAt?: number) => ({
  sk,
  case_id: caseId,
  agree,
  created_at: createdAt ?? 0,
});

// An empty table is an empty summary, never a divide-by-zero or a null.
check("empty", reduceOverrides([]), { total: 0, disagreed: 0, labels: {} });

// One tap per case: counts are the obvious ones.
check(
  "distinct cases",
  reduceOverrides([
    row("OVERRIDE#1000#case-a", "case-a", true),
    row("OVERRIDE#2000#case-b", "case-b", false),
  ]),
  { total: 2, disagreed: 1, labels: { "case-a": true, "case-b": false } },
);

// The defect this guards: three taps on one case counted as three labels and
// inflated the disagreement rate. It is one case with one standing label.
check(
  "re-taps collapse to one case",
  reduceOverrides([
    row("OVERRIDE#1000#case-a", "case-a", false),
    row("OVERRIDE#2000#case-a", "case-a", false),
    row("OVERRIDE#3000#case-a", "case-a", true),
  ]),
  { total: 1, disagreed: 0, labels: { "case-a": true } },
);

// Scan order is arbitrary, so the newest tap must win regardless of arrival.
check(
  "newest tap wins out of order",
  reduceOverrides([
    row("OVERRIDE#3000#case-a", "case-a", false),
    row("OVERRIDE#1000#case-a", "case-a", true),
  ]),
  { total: 1, disagreed: 1, labels: { "case-a": false } },
);

// Same created_at second: the millisecond stamp in sk breaks the tie.
check(
  "same second resolves on the sk millisecond stamp",
  reduceOverrides([
    row("OVERRIDE#1700000000100#case-a", "case-a", true, 1700000000),
    row("OVERRIDE#1700000000900#case-a", "case-a", false, 1700000000),
  ]),
  { total: 1, disagreed: 1, labels: { "case-a": false } },
);

// A malformed sk falls back to created_at rather than poisoning the map.
check(
  "malformed sk falls back to created_at",
  reduceOverrides([
    { sk: "OVERRIDE#nonsense", case_id: "case-a", agree: true, created_at: 10 },
    { sk: "OVERRIDE#alsobad", case_id: "case-a", agree: false, created_at: 20 },
  ]),
  { total: 1, disagreed: 1, labels: { "case-a": false } },
);

// Rows without a case id are audit noise, never a phantom label.
check(
  "rows without a case id are dropped",
  reduceOverrides([{ sk: "OVERRIDE#1000#", agree: false }]),
  { total: 0, disagreed: 0, labels: {} },
);

// A missing agree field is not an agreement.
check(
  "absent agree is treated as disagreement, never silently true",
  reduceOverrides([{ sk: "OVERRIDE#1000#case-a", case_id: "case-a" }]),
  { total: 1, disagreed: 1, labels: { "case-a": false } },
);

if (failures > 0) {
  console.error(`override reduction: ${failures} check(s) failed`);
  process.exit(1);
}
console.log("override reduction ok: 8 checks, latest-label-per-case holds");
