/**
 * Regression check for DynamoDB set normalization (what-broke 2026-09-01):
 * String Sets must survive the trip from DocumentClient to the browser as
 * plain string arrays, through every shape they appear in.
 */
import { toStringArray } from "../src/lib/aws";

const cases: Array<[unknown, string[]]> = [
  [undefined, []],
  [new Set(["A", "B"]), ["A", "B"]],
  [["x"], ["x"]],
  [{ SS: ["R1", "R2"] }, ["R1", "R2"]],
  [{}, []],
  [{ M: { inner: ["q"] } }, ["q"]],
  ["NONE", []], // scalars are not set shapes; absent reads as absent
];

let failed = false;
for (const [input, expected] of cases) {
  const got = toStringArray(input);
  const ok = JSON.stringify(got) === JSON.stringify(expected);
  if (!ok) {
    failed = true;
    console.error(`FAIL ${JSON.stringify(input)}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(got)}`);
  }
}
if (failed) process.exit(1);
console.log(`set normalization ok: ${cases.length} shapes`);
