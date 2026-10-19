// Run with a separately identified Playwright Chromium, never a primary browser.
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "../screensaver");

(async () => {
  const server = http.createServer(async (req, res) => {
    try {
      const name = new URL(req.url, "http://localhost").pathname.slice(1);
      if (!["index.html", "main.css", "main.js", "config.json", "preview.html", "preview.css", "preview.js"].includes(name)) {
        res.writeHead(404).end(); return;
      }
      const types = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };
      res.setHeader("Content-Type", types[path.extname(name)]);
      res.end(await fs.readFile(path.join(root, name)));
    } catch { res.writeHead(500).end(); }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    const base = `http://127.0.0.1:${server.address().port}`;
    const inspect = await browser.newPage();
    async function pixels() {
      const data = (await page.screenshot()).toString("base64");
      return inspect.evaluate(async data => {
        const img = new Image(); img.src = `data:image/png;base64,${data}`; await img.decode();
        const canvas = document.createElement("canvas"); canvas.width = img.width; canvas.height = img.height;
        const ctx = canvas.getContext("2d"); ctx.drawImage(img, 0, 0);
        const rgba = ctx.getImageData(0, 0, img.width, img.height).data;
        let lit = 0, max = 0;
        for (let i = 0; i < rgba.length; i += 4) {
          if (rgba[i] || rgba[i + 1] || rgba[i + 2]) lit++;
          max = Math.max(max, rgba[i], rgba[i + 1], rgba[i + 2]);
        }
        return { lit, max };
      }, data);
    }
    for (const query of ["mode=black", "brightness=0", "size=NaN"]) {
      await page.goto(`${base}/index.html?${query}`);
      await page.waitForLoadState("networkidle");
      assert.deepEqual(await pixels(), { lit: 0, max: 0 }, query);
    }
    await page.goto(`${base}/index.html?size=32&brightness=10&speed=200`);
    await page.locator("#ball").waitFor({ state: "visible" });
    const start = await page.locator("#ball").boundingBox();
    const pixel = await pixels();
    assert(pixel.lit > 700 && pixel.lit < 900, JSON.stringify(pixel));
    assert.equal(pixel.max, 26);
    await page.waitForFunction(({ x, y }) => {
      const rect = document.getElementById("ball").getBoundingClientRect();
      return Math.abs(rect.x - x) > 8 || Math.abs(rect.y - y) > 8;
    }, start);
    await page.clock.install();
    for (const viewport of [{ width: 1280, height: 800 }, { width: 320, height: 200 }]) {
      await page.setViewportSize(viewport);
      for (let i = 0; i < 8; i++) {
        await page.clock.fastForward(13750);
        const rect = await page.locator("#ball").boundingBox();
        assert(rect.x >= 0 && rect.y >= 0 && rect.x + rect.width <= viewport.width + .01 && rect.y + rect.height <= viewport.height + .01, JSON.stringify(rect));
      }
    }
    await page.route("**/config.json", route => route.fulfill({ status: 500, body: "unavailable" }));
    await page.goto(`${base}/index.html`);
    await page.waitForLoadState("networkidle");
    assert.deepEqual(await pixels(), { lit: 0, max: 0 });
    await page.unroute("**/config.json");
    const preview = await browser.newPage({ viewport: { width: 1000, height: 1200 } });
    await preview.goto(`${base}/preview.html`);
    await preview.locator('[name="mode"]').selectOption("black");
    await preview.locator('[name="mode"]').selectOption("ball");
    assert.equal(await preview.locator("#size-value").innerText(), "32 px");
    assert.equal(await preview.locator('[name="brightness"]').isDisabled(), false);
    const output = process.env.SCREENSAVER_PREVIEW || path.join(os.tmpdir(), "quiet-ball-preview.png");
    await preview.screenshot({ path: output, fullPage: true });
    assert.deepEqual(errors, []);
    console.log(`Screensaver browser checks passed; preview: ${output}`);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
