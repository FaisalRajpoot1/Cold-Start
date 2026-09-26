/**
 * Screenshot a local page at an exact size.
 *
 *   node video/shoot.mjs web/cover.html web/cover.png 1200 630
 *
 * Deterministic by construction: a fixed viewport, deviceScaleFactor 1, and a
 * wait for webfonts to settle so the output does not depend on network timing.
 */
import { chromium } from "playwright";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdirSync } from "node:fs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [src, out, w = "1200", h = "630"] = process.argv.slice(2);
if (!src || !out) {
  console.error("usage: node video/shoot.mjs <page.html> <out.png> [w] [h]");
  process.exit(1);
}

const width = Number(w), height = Number(h);
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width, height },
  deviceScaleFactor: 1,
});
await page.goto(pathToFileURL(resolve(ROOT, src)).href, { waitUntil: "networkidle" });
// Webfonts decide the layout. Wait for them rather than guessing with a sleep.
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(250);

mkdirSync(dirname(resolve(ROOT, out)), { recursive: true });
await page.screenshot({ path: resolve(ROOT, out), clip: { x: 0, y: 0, width, height } });
await browser.close();
console.log(`${out}  ${width}x${height}`);
