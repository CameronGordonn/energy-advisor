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

// The announcer is the live region, and it only works if it is in the accessibility tree
// BEFORE the text arrives — which is exactly what #status cannot be, since it is toggled
// with `hidden`. So it must be present, un-hidden and empty on load.
const announcer = doc.getElementById("announcer");
ok(announcer !== null && !announcer.hidden && announcer.textContent === "",
   "an empty, un-hidden live region exists on load");
ok(announcer && announcer.getAttribute("role") === "status" &&
   announcer.getAttribute("aria-live") === "polite",
   "the live region is polite and announces on its own");

// Render the REAL inspection the Python engine produced from the real export.
window.__renderInspection(inspection, false);

const results = doc.getElementById("results");
ok(!results.hidden, "results revealed after render");
ok(doc.getElementById("demoBanner").hidden, "demo banner stays hidden for a real file");

// Revealing a region by un-hiding it is silent. A keyboard or screen-reader user has to be
// told the analysis arrived and be put where it is — both, not either.
ok(/analysis ready/i.test(announcer.textContent),
   "the arrival of results is announced", announcer.textContent);
ok(results.getAttribute("tabindex") === "-1" && doc.activeElement === results,
   "focus moves into the results region", String(doc.activeElement && doc.activeElement.id));

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

// No dollar figure may appear in the LOAD-SHAPE half of the report. That half runs for
// every visitor, including the ones the engine may not price, so a dollar reaching it would
// escape the gate entirely. The pricing section (03) is where money is allowed, and only
// when `report.recommend` has said so — asserted separately below.
const computed = ["stats", "findings", "hourChart", "monthChart", "fileTable", "warnBox"]
  .map(id => doc.getElementById(id).textContent).join(" ");
ok(!/\$\d/.test(computed), "no dollar amount in any computed output",
   (computed.match(/\$\d[\d.,]*/g) || []).join(" "));
ok(/\$2 per month/.test(results.textContent),
   "the reconciliation gate is still explained to the reader");

// Demo mode must announce itself.
window.__renderInspection(inspection, true);
ok(!doc.getElementById("demoBanner").hidden, "demo banner shows in demo mode");
// ⭐ The guarantee changed in session 28 and the assertion changed with it. The worked
// example used to be an invented profile, and the banner had to say so. It is now the
// author's own real household — the one the ±$2 table is built from — so the thing that
// must never stop being true is that the banner says WHOSE data it is and that it is not
// the reader's. Asserting the guarantee, not a phrasing.
const banner = doc.getElementById("demoBanner").textContent;
ok(/example/i.test(banner) && /not your data|not a finding about you/i.test(banner),
   "the worked example says whose data it is and that it is not the reader's",
   banner.slice(0, 160));
ok(/author|own/i.test(banner) && /\u00b1\$2|within .{0,4}\$2/.test(banner),
   "the worked example is attributed and carries its reconciliation claim",
   banner.slice(0, 160));

// ---- pricing (section 03) -------------------------------------------------------------
//
// The tool used to end at load shape. It now answers the question it exists to answer for
// the households it can prove it prices correctly, and refuses by name for the rest. Both
// halves are pinned, and the refusal is pinned harder.

const caseStudy = JSON.parse(readFileSync(`${REPO}/docs/case-study.json`, "utf8"));
window.__renderRecommendation(caseStudy.recommendation);

const priceOut = doc.getElementById("priceOut");
ok(!priceOut.hidden && doc.getElementById("priceGate").hidden &&
   doc.getElementById("factsForm").hidden, "an available recommendation shows the answer only");
const verdict = doc.getElementById("verdict").textContent;
ok(verdict.trim().length > 40, "the verdict is a sentence, not a number", verdict);

const planRows = doc.querySelectorAll("#planTable tbody tr");
ok(planRows.length === caseStudy.recommendation.plans.length,
   `every modelled plan is listed (${caseStudy.recommendation.plans.length})`,
   `got ${planRows.length}`);
ok(doc.querySelectorAll("#planTable tr.win").length === 1, "exactly one winner is marked");
ok(/\$[\d,]+\.\d\d/.test(doc.getElementById("planTable").textContent),
   "the ranking is denominated in dollars");
ok(doc.querySelectorAll("#planTable th[scope]").length >= 3, "the ranking's headers carry scope");
ok(doc.querySelector("#planTable caption") !== null, "the ranking has a caption");
ok(doc.getElementById("flipNote").textContent.length > 30,
   "the shift that would overturn the ranking is stated");
ok(doc.querySelectorAll("#assumeList li").length >= 3,
   "the assumptions behind the ranking are listed");

// ⭐ The refusal. This is the honest-broker invariant as a DOM assertion: a blocked
// household must see reasons and NOT A SINGLE dollar figure anywhere in the section.
window.__renderGate([{
  code: "UTILITY_NOT_RECONCILED",
  detail: "The bill engine has never reproduced a real SDG&E statement within 2 dollars.",
}]);
ok(!doc.getElementById("priceGate").hidden && doc.getElementById("priceOut").hidden,
   "a blocked household sees the refusal instead of the answer");
ok(doc.querySelectorAll("#priceGateList li").length === 1, "the refusal lists its reason");
ok(/UTILITY NOT RECONCILED/.test(doc.getElementById("priceGateList").textContent),
   "the reason is named, not merely described");
// Scoped to what the ENGINE wrote. The surrounding prose links "how the ±$2 rule works",
// which is the gate being quoted at the reader, not a price computed for them.
const gateRegion = doc.getElementById("priceGateText").textContent +
  " " + doc.getElementById("priceGateList").textContent;
ok(!/\$\d/.test(gateRegion), "no dollar figure survives a refusal",
   (gateRegion.match(/\$\d[\d.,]*/g) || []).join(" "));
ok(/\u00b1\$2/.test(doc.getElementById("priceGate").textContent),
   "the refusal still quotes the rule it is enforcing");

console.log(fails === 0 ? "\nALL RENDER CHECKS PASSED" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
