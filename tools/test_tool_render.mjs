/**
 * The display layer must render a real inspection correctly.
 *
 * render() is pure (inspection JSON -> DOM), so it runs headlessly in jsdom via the page's
 * __renderInspection hook, without booting Pyodide. This checks the numbers reach the page,
 * the charts have the right shape, the peak window is highlighted, and — the one that
 * matters most — that nothing computed from a user's file is ever denominated in dollars.
 *
 *   node tools/test_tool_render.mjs [inspection.json]
 */
import { JSDOM } from "jsdom";
import { readFileSync } from "fs";

import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const inspection = JSON.parse(readFileSync(
  process.argv[2] || `${REPO}/tools/reference-sample.json`, "utf8"));

const dom = new JSDOM(readFileSync(`${REPO}/docs/index.html`, "utf8"), {
  runScripts: "dangerously",
  url: "https://example.invalid/",
});
const { window } = dom;
const doc = window.document;

let fails = 0;
const ok = (cond, label, extra = "") => {
  if (cond) console.log(`  PASS  ${label}`);
  else { console.log(`  FAIL  ${label}  ${extra}`); fails++; }
};

// The page must be inert before any file is given to it.
ok(doc.getElementById("results").hidden, "results hidden before any file is analysed");
ok(doc.getElementById("status").hidden, "no status shown on load");
ok(typeof window.__renderInspection === "function", "render hook is present");

// Render the REAL inspection the Python engine produced from the real export.
window.__renderInspection(inspection, false);

const results = doc.getElementById("results");
ok(!results.hidden, "results revealed after render");
ok(doc.getElementById("demoBanner").hidden, "demo banner stays hidden for a real file");

const statsText = doc.getElementById("stats").textContent;
ok(/[\d,]+ kWh/.test(statsText), "total kWh shown", statsText.slice(0, 120));
ok(/\d+%/.test(statsText), "peak share shown as a percentage", statsText.slice(0, 160));
ok((statsText.match(/\d+%/g) || []).length >= 2, "both peak and overnight shares shown");

const findings = doc.querySelectorAll("#findings .finding");
ok(findings.length === inspection.findings.length,
   `all ${inspection.findings.length} findings rendered`, `got ${findings.length}`);
ok([...findings].every(f => /good|watch|info/.test(f.className)),
   "every finding carries a severity class");
ok(findings[0].querySelector("h4").textContent.includes("peak hours"),
   "peak finding leads the list");

const hourBars = doc.querySelectorAll("#hourChart rect");
ok(hourBars.length === 25, "24 hour bars + 1 peak-window shading", `got ${hourBars.length}`);
const accentBars = [...hourBars].filter(r => r.getAttribute("fill") === "var(--accent)");
ok(accentBars.length === 5, "exactly the 5 peak hours are highlighted", `got ${accentBars.length}`);
ok(doc.querySelectorAll("#hourChart title").length === 24, "every hour bar has a tooltip");

const monthBars = doc.querySelectorAll("#monthChart rect");
ok(monthBars.length === inspection.by_month.length,
   `${inspection.by_month.length} month bars`, `got ${monthBars.length}`);

const fileTable = doc.getElementById("fileTable").textContent;
ok(/PG&E/.test(fileTable), "utility shown in the file table");
ok(/\d+ minutes/.test(fileTable), "reading interval shown");
ok(/\d{4}-\d{2}-\d{2}/.test(fileTable), "DST transition surfaced");
ok(/Yes/.test(fileTable), "bill-comparable verdict shown");

// No dollar figure may appear in anything COMPUTED from the user's file. (The static
// "within +/-$2 per month" gate quote in the explainer section is deliberate copy, not
// output, so it is excluded — the point is that no per-user price is ever derived.)
const computed = ["stats", "findings", "hourChart", "monthChart", "fileTable", "warnBox"]
  .map(id => doc.getElementById(id).textContent).join(" ");
ok(!/\$\d/.test(computed), "no dollar amount in any computed output",
   (computed.match(/\$\d[\d.,]*/g) || []).join(" "));
ok(/\$2 per month/.test(results.textContent),
   "the reconciliation gate is still explained to the reader");

// Demo mode must announce itself.
window.__renderInspection(inspection, true);
ok(!doc.getElementById("demoBanner").hidden, "demo banner shows in demo mode");
// The wording is the page's to choose; what it must never stop doing is telling the
// reader the numbers are not a real household's. Assert the GUARANTEE, not one phrasing:
// it has to name the data as fabricated AND say plainly that it is not real.
const banner = doc.getElementById("demoBanner").textContent;
ok(/specimen|demonstration|invented|synthetic|sample/i.test(banner) && /not a real/i.test(banner),
   "demo banner explains the data is synthetic", banner.slice(0, 120));

console.log(fails === 0 ? "\nALL RENDER CHECKS PASSED" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
