/**
 * The browser must compute exactly what Python computes.
 *
 * docs/engine.js ships the real parser and inspector sources, which the page runs under
 * Pyodide. This loads that bundle the same way the page does, runs it against the committed
 * sample export, and compares every field to a reference produced by native CPython.
 *
 * A drift here means visitors see different numbers than the test suite verifies — the
 * exact failure mode that shipping a JavaScript reimplementation would have risked.
 *
 *   node tools/test_engine_wasm.mjs [sample.csv] [reference.json]
 */
import { loadPyodide } from "pyodide";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const csvPath = process.argv[2] || resolve(ROOT, "docs/sample-usage.csv");
const refPath = process.argv[3] || resolve(ROOT, "tools/reference-sample.json");

let fails = 0;
const ok = (cond, label, extra = "") => {
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${label}${cond ? "" : "  " + extra}`);
  if (!cond) fails++;
};

// Load the shipped bundle exactly as the browser does (it assigns onto `window`).
globalThis.window = globalThis;
new Function(readFileSync(resolve(ROOT, "docs/engine.js"), "utf8"))();
const files = window.ENERGY_ENGINE_FILES;
ok(files && Object.keys(files).length >= 7, "engine bundle loaded",
   `got ${files ? Object.keys(files).length : 0} modules`);

const py = await loadPyodide();
await py.loadPackage(["pandas", "pydantic"]);

py.FS.mkdirTree("/engine");
for (const [rel, source] of Object.entries(files)) {
  const parts = rel.split("/");
  if (parts.length > 1) py.FS.mkdirTree("/engine/" + parts.slice(0, -1).join("/"));
  py.FS.writeFile("/engine/" + rel, source, { encoding: "utf8" });
}
py.FS.writeFile("/upload.csv", readFileSync(csvPath));

const raw = await py.runPythonAsync(`
import sys
sys.path.insert(0, "/engine")
from report.inspect import inspect_export
inspect_export("/upload.csv").model_dump_json()
`);

const wasm = JSON.parse(raw);
const ref = JSON.parse(readFileSync(refPath, "utf8"));

// source_name reflects the filename each side was handed; everything else must match.
const skip = new Set(["source_name"]);
const keys = Object.keys(ref).filter((k) => !skip.has(k));
const differing = keys.filter(
  (k) => JSON.stringify(ref[k]) !== JSON.stringify(wasm[k])
);
ok(differing.length === 0, `all ${keys.length} fields identical to native Python`,
   `differing: ${differing.join(", ")}`);
ok(wasm.total_kwh > 0 && wasm.n_intervals > 0, "the run produced real output");

console.log(fails === 0 ? "\nWASM ENGINE MATCHES NATIVE" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
