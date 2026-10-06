// Saves reel.html as one PNG per frame. Run by make_reel.py:
//   node reel/render.js <frames folder> [fps] [facebook|tiktok]
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('@playwright/test');

(async () => {
  const out = process.argv[2];
  const fps = Number(process.argv[3] || 30);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto(pathToFileURL(path.join(__dirname, 'reel.html')).href + '#render,' + (process.argv[4] || 'facebook'));
  await page.evaluate(() => document.fonts.ready);

  const frames = Math.round((await page.evaluate(() => window.DURATION)) / 1000 * fps);
  for (let i = 0; i < frames; i++) {
    await page.evaluate((ms) => window.seek(ms), (i * 1000) / fps);
    await page.screenshot({ path: path.join(out, `f_${String(i).padStart(4, '0')}.png`) });
    if (i % 60 === 0) console.log(`frame ${i} of ${frames}`);
  }
  await browser.close();
})();
