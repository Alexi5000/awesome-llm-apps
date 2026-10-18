import assert from "node:assert/strict";
import { diffLines } from "diff";

for (const [before, after] of [
  ["keep\nold\n", "keep\nnew\n"],
  ["", "# New skill\n"],
  ["# Removed skill\n", ""],
  ["same\n", "same\n"],
  ["line without newline", "line without newline\n"],
]) {
  const parts = diffLines(before, after);
  assert.equal(parts.filter(part => !part.added).map(part => part.value).join(""), before);
  assert.equal(parts.filter(part => !part.removed).map(part => part.value).join(""), after);
  assert.ok(parts.every(part => typeof part.value === "string" && typeof part.count === "number"));
}
const replacement = diffLines("keep\nold\n", "keep\nnew\n");
assert.ok(replacement.some(part => part.removed && part.value === "old\n"));
assert.ok(replacement.some(part => part.added && part.value === "new\n"));
console.log("PASS: replacement, insertion, deletion, unchanged text, and newline boundaries");
