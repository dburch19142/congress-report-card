// Takes the App Store screenshots from the web build of the app, at the exact sizes App Store
// Connect asks for (6.9" iPhone and 13" iPad), using the live site's current data.
//
// From congress-app/:
//   flutter build web --dart-define=SITE_BASE=
//   node app-store/screenshots.mjs
//
// The empty SITE_BASE makes the app read its data from the same address it is served from.
// This script downloads the live data next to the build and serves both, so the browser
// has no cross-site requests to make. Needs `npm install` in the repo root for Playwright.
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..', 'build', 'web');
const out = join(here, 'screenshots');
const site = 'https://congressreportcard.org';

const devices = [
  { folder: 'iphone-6.9', viewport: { width: 440, height: 956 }, scale: 3 }, // 1320 × 2868
  { folder: 'ipad-13', viewport: { width: 1032, height: 1376 }, scale: 2 }, // 2064 × 2752
];

// What each screenshot shows. Every shot starts from a fresh load of the app.
const shots = [
  { name: '01-members', steps: [] },
  { name: '02-zip-code', steps: [search('18940')] },
  { name: '03-report-card', steps: [search('Bacon'), tap('Don Bacon')] },
  { name: '04-how-they-compare', steps: [search('Panetta'), tap('Jimmy Panetta'), scrollTo('How Panetta compares')] },
  { name: '05-states', steps: [tap('States')] },
  { name: '06-state-delegation', steps: [tap('States'), tap('Virginia')] },
  { name: '07-articles', steps: [tap('Articles')] },
];

function search(text) {
  return async (page) => {
    const box = page.getByLabel('Name, state or ZIP code');
    await box.fill(text);
    await box.blur(); // hides the text cursor
    await settle(page);
  };
}

// Taps the first widget with [text] as one of its lines. A list row's text is the whole row,
// one part per line ("4\nVirginia\n13 members · average 84.4\nGrade B"), so an exact match
// wouldn't find it.
function tap(text) {
  return async (page) => {
    await page.getByText(new RegExp(`(^|\\n)${text}(\\n|$)`)).first().click();
    await settle(page);
  };
}

// Scrolls until the text is near the top of the screen.
function scrollTo(text) {
  return async (page) => {
    const { width, height } = page.viewportSize();
    await page.mouse.move(width / 2, height / 2);
    for (let i = 0; i < 40; i++) {
      const box = await page.getByText(text, { exact: true }).first().boundingBox().catch(() => null);
      if (box && box.y < height * 0.3) break;
      await page.mouse.wheel(0, box ? Math.min(box.y - 120, 300) : 300);
      await page.waitForTimeout(150);
    }
    await settle(page);
  };
}

async function settle(page) {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
}

async function downloadData() {
  for (const file of ['data/members.js', 'data/zips.js', 'digest/feed.xml', 'articles/articles.json']) {
    const response = await fetch(`${site}/${file}`);
    if (!response.ok) throw new Error(`${file}: ${response.status}`);
    await mkdir(dirname(join(web, file)), { recursive: true });
    await writeFile(join(web, file), Buffer.from(await response.arrayBuffer()));
  }
}

function serve() {
  const types = {
    '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
    '.wasm': 'application/wasm', '.xml': 'application/xml', '.png': 'image/png', '.ttf': 'font/ttf',
    '.otf': 'font/otf',
  };
  const server = createServer(async (req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = join(web, path.endsWith('/') ? `${path}index.html` : path);
    try {
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end();
    }
  });
  return new Promise((resolve) => server.listen(0, () => resolve(server)));
}

await downloadData();
const server = await serve();
const url = `http://localhost:${server.address().port}/`;
const browser = await chromium.launch();
try {
  for (const device of devices) {
    await mkdir(join(out, device.folder), { recursive: true });
    const context = await browser.newContext({ viewport: device.viewport, deviceScaleFactor: device.scale });
    const page = await context.newPage();
    for (const shot of shots) {
      await page.goto(url);
      await page.waitForSelector('flt-semantics-placeholder', { state: 'attached' });
      // Turns on Flutter's accessibility layer so widgets can be found by their text.
      await page.evaluate(() => document.querySelector('flt-semantics-placeholder').click());
      await page.getByText('Show only A grades', { exact: false }).first().waitFor();
      await settle(page);
      for (const step of shot.steps) await step(page);
      // Lets member photos finish fading in.
      await page.waitForTimeout(1500);
      const path = join(out, device.folder, `${shot.name}.png`);
      await page.screenshot({ path });
      console.log(path);
    }
    await context.close();
  }
} finally {
  await browser.close();
  server.close();
}
