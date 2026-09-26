/** Render each <section> of the deck to its own 1280x720 PNG. */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = resolve(ROOT, "web/slides");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(resolve(ROOT, "web/deck.html")).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(250);

const slides = await page.$$("section");
let i = 0;
for (const s of slides) {
  i += 1;
  await s.screenshot({ path: resolve(OUT, `slide-${String(i).padStart(2, "0")}.png`) });
}
await browser.close();
console.log(`${i} slides -> web/slides/`);
