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
await py.loadPackage(["pandas", "pydantic", "pyyaml"]);

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

// ---- the pricing half ------------------------------------------------------------------
//
// Session 28 put the tariff engine and the rate optimizer in the bundle, so the browser now
// produces DOLLAR figures. Parity matters more here than anywhere else on the page: a
// wasm/native divergence in the inspector shows a visitor the wrong chart, while one here
// shows them the wrong plan to be on.

const recRef = JSON.parse(readFileSync(resolve(ROOT, "tools/reference-recommendation.json"), "utf8"));
py.globals.set("_facts_json", JSON.stringify(recRef.facts));
const recRaw = await py.runPythonAsync(`
import json
from datetime import date
from pathlib import Path
from greenbutton.models import Utility
from report.inspect import _detect_and_parse
from report.recommend import HouseholdFacts, recommend, utility_blocker
series, _ = _detect_and_parse(Path("/upload.csv"))
facts = HouseholdFacts(**json.loads(_facts_json))
rec = recommend(series, facts, utility=Utility.PGE, as_of=date.fromisoformat("${recRef.as_of}"),
                specs_dir="/engine/tariffs/specs", with_sensitivity=False)
json.dumps({"rec": json.loads(rec.model_dump_json()),
            "sdge_blocked": utility_blocker(Utility.SDGE) is not None,
            "pge_blocked": utility_blocker(Utility.PGE) is not None})
`);
const priced = JSON.parse(recRaw);

ok(priced.rec.available === true, "the browser can price the in-scope household");
const refPlans = recRef.recommendation.plans.map((p) => `${p.name}=${p.annual}`);
const wasmPlans = priced.rec.plans.map((p) => `${p.name}=${p.annual}`);
ok(JSON.stringify(refPlans) === JSON.stringify(wasmPlans),
   `all ${refPlans.length} plan totals identical to native Python, to the cent`,
   `native ${refPlans.join(" ")} vs wasm ${wasmPlans.join(" ")}`);
ok(priced.rec.verdict === recRef.recommendation.verdict,
   "the verdict sentence is identical to native Python");
ok(JSON.stringify(priced.rec.why) === JSON.stringify(recRef.recommendation.why),
   "the component-level explanation is identical to native Python");

// The gate has to hold inside the browser too, where nothing else is watching it.
ok(priced.sdge_blocked === true, "SDG&E is refused in the browser, not just in pytest");
ok(priced.pge_blocked === false, "PG&E is not refused — the gate is per-utility, not blanket");

console.log(fails === 0 ? "\nWASM ENGINE MATCHES NATIVE" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
