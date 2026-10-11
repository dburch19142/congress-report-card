// @ts-check
// One test per member of Congress. Each checks that member's card on the home page,
// their own page (/members/<id>.html) and their grade badge, and that all three agree.
//
// The list of members comes from site/data/members.js in this checkout, which is the
// same file the deploy publishes. Test "00" confirms the live site lists the same people.
// Runs in Chromium only (see playwright.config.js) to keep the run time reasonable.
const fs = require('fs');
const path = require('path');
const { test: base, expect } = require('@playwright/test');

const DATA_FILE = path.join(__dirname, '..', 'site', 'data', 'members.js');
const source = fs.readFileSync(DATA_FILE, 'utf8');
const DATA = JSON.parse(source.slice(source.indexOf('{'), source.lastIndexOf('}') + 1));
const MEMBERS = DATA.members;

// The home page is loaded once per worker and shared by that worker's tests,
// rather than reloaded for each of the ~540 members.
const test = base.extend({
  home: [async ({ browser }, use, workerInfo) => {
    const context = await browser.newContext({ baseURL: workerInfo.project.use.baseURL });
    const page = await context.newPage();
    await page.goto('/');
    await expect(page.locator('#grid .member').first()).toBeAttached();
    // Grades as the site computes them in the browser, with the default weights
    const grades = await page.evaluate(
      () => Object.fromEntries(window.REPORT_DATA.members.map((m) => [m.id, m.grade])));
    await use({ page, grades });
    await context.close();
  }, { scope: 'worker' }],
});

test('00 Live site lists the same members', async ({ home }) => {
  const live = Object.keys(home.grades).sort();
  const local = MEMBERS.map((m) => m.id).sort();
  expect(live.filter((id) => !local.includes(id)), 'on the live site but not in members.js').toEqual([]);
  expect(local.filter((id) => !live.includes(id)), 'in members.js but not on the live site').toEqual([]);
});

for (const m of MEMBERS) {
  test(`${m.id} ${m.name} (${m.chamber}, ${m.state})`, async ({ page, request, home }) => {
    const grade = home.grades[m.id];
    expect(grade, 'member is missing from the live home page').toBeTruthy();

    // ---- Home page card
    const card = home.page.locator('#card');
    if (await card.isVisible()) await home.page.keyboard.press('Escape');
    await home.page.locator(`#grid .member[data-id='${m.id}']`).click();
    await expect(card).toBeVisible();
    await expect.soft(home.page.locator('#card-name'), 'home card name').toHaveText(m.name);
    await expect.soft(card.locator('.card-head .grade'), 'home card grade').toHaveText(grade);
    await expect.soft(card.locator('.subject'), 'home card subjects').toHaveCount(3);
    await expect.soft(card.locator(`a[href='https://www.congress.gov/member/${m.id}']`)).toBeAttached();
    await expect.soft(card.locator(`a[href='members/${m.id}.html']`), 'link to member page').toBeAttached();
    await home.page.keyboard.press('Escape');
    await expect(card).toBeHidden();

    // ---- Member page
    const scriptErrors = [];
    page.on('pageerror', (err) => scriptErrors.push(err.message));
    const response = await page.goto(`/members/${m.id}.html`);
    expect(response?.status(), 'member page status').toBe(200);

    await expect.soft(page.locator('#member-name'), 'page name').toHaveText(m.name);
    await expect.soft(page.locator('.card-head .grade'), 'page grade matches home page').toHaveText(grade);
    const title = await page.title();
    expect.soft(title.startsWith(`${m.name} (`), `title: ${title}`).toBeTruthy();
    expect.soft(title.endsWith(`: Grade ${grade} | Congress Report Card`), `title: ${title}`).toBeTruthy();
    if (grade !== '—') {
      await expect.soft(page.locator('.summary-text'), 'summary').toContainText(`overall grade of ${grade}`);
    }
    await expect.soft(page.locator('.subject'), 'page subjects').toHaveCount(3);
    await expect.soft(page.locator('link[rel=canonical]')).toHaveAttribute(
      'href', `https://congressreportcard.org/members/${m.id}.html`);
    await expect.soft(page.locator(`a[href='https://www.congress.gov/member/${m.id}']`)).toBeAttached();
    expect.soft(scriptErrors, 'script errors on the member page').toEqual([]);

    // ---- Badge
    const badge = await request.get(`/badges/${m.id}.svg`);
    expect.soft(badge.ok(), 'badge status').toBeTruthy();
    if (badge.ok()) expect.soft(await badge.text(), 'badge grade').toContain(`>${grade}</text>`);
  });
}
