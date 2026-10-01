// @ts-check
// Smoke tests for congressreportcard.org, converted from congress-report-card.side.
const { test, expect } = require('@playwright/test');

const GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', '—'];

// Each test gets a fresh browser context, so localStorage is empty and the
// site starts from the default grading weights.
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#grid .member').first()).toBeAttached();
});

const memberCount = (page) => page.evaluate(() => window.REPORT_DATA.members.length);

async function gridGrades(page) {
  return (await page.locator('#grid .member .grade').allTextContents()).map((t) => t.trim());
}

function expectSorted(values, compare) {
  expect(values.length).toBeGreaterThan(1);
  const outOfOrder = values.findIndex((v, i) => i > 0 && compare(values[i - 1], v) > 0);
  expect(outOfOrder, `item ${outOfOrder} is out of order: ${values[outOfOrder - 1]} then ${values[outOfOrder]}`).toBe(-1);
}

async function expectBestGradeFirst(page) {
  const ranks = (await gridGrades(page)).map((g) => GRADE_ORDER.indexOf(g));
  expectSorted(ranks, (a, b) => a - b);
}

test('01 Home page loads', async ({ page }) => {
  const total = await memberCount(page);

  await expect(page).toHaveTitle('Congress Report Card');
  await expect(page.locator('h1')).toHaveText('Congress Report Card');
  await expect(page.locator('#congress-label')).toBeAttached();

  // Every member is listed by default
  await expect(page.locator('#count')).toHaveText(`${total} of ${total} members`);
  await expect(page.locator('#grid .member')).toHaveCount(total);

  await expect(page.locator('#chamber option:checked')).toHaveText('Both chambers');
  await expect(page.locator('#state option:checked')).toHaveText('All states');
  await expect(page.locator('#party option:checked')).toHaveText('All parties');
  await expect(page.locator('#sort option:checked')).toHaveText('Sort: highest grade');

  for (const letter of ['A', 'B', 'C', 'D', 'F']) {
    await expect(page.locator(`#summary button[data-g='${letter}']`)).toBeAttached();
  }

  // Bill data is loaded, so the warning is hidden
  await expect(page.locator('#notice')).toBeHidden();

  // State list has one entry per state/territory, plus "All states"
  const stateCount = await page.evaluate(() => new Set(window.REPORT_DATA.members.map((m) => m.state)).size);
  await expect(page.locator('#state option')).toHaveCount(stateCount + 1);
});

test('02 Search by name and state', async ({ page }) => {
  const total = await memberCount(page);
  const count = page.locator('#count');
  const search = page.locator('#q');

  const senator = await page.evaluate(() => window.REPORT_DATA.members.find((m) => m.chamber === 'Senate').name);
  await search.fill(senator);
  await expect(page.locator('#grid .member').first().locator('.name')).toHaveText(senator);
  const matches = await page.evaluate(
    (q) => window.REPORT_DATA.members.filter((m) => m.name.toLowerCase().includes(q)).length,
    senator.toLowerCase());
  await expect(count).toHaveText(`${matches} of ${total} members`);

  await search.fill('Ohio');
  const ohio = await page.evaluate(
    () => window.REPORT_DATA.members.filter((m) => m.state === 'OH' || m.name.toLowerCase().includes('ohio')).length);
  await expect(count).toHaveText(`${ohio} of ${total} members`);
  await expect(page.locator('#grid .member').filter({ hasNotText: /· OH/ })).toHaveCount(0);

  // Nonsense search returns nothing
  await search.fill('zzqqxxnomatch');
  await expect(count).toHaveText(`0 of ${total} members`);
  await expect(page.locator('#grid .member')).toHaveCount(0);

  await search.fill('');
  await expect(count).toHaveText(`${total} of ${total} members`);
});

test('03 Chamber, state and party filters', async ({ page }) => {
  const total = await memberCount(page);
  const count = page.locator('#count');
  const cards = page.locator('#grid .member');
  const countWhere = (filter) => page.evaluate(
    (f) => window.REPORT_DATA.members.filter((m) => Object.entries(f).every(([k, v]) => m[k] === v)).length,
    filter);

  await page.locator('#chamber').selectOption({ label: 'Senate' });
  await expect(count).toHaveText(`${await countWhere({ chamber: 'Senate' })} of ${total} members`);
  await expect(cards.filter({ hasNotText: /Senator ·/ })).toHaveCount(0);

  await page.locator('#chamber').selectOption({ label: 'House' });
  await expect(count).toHaveText(`${await countWhere({ chamber: 'House' })} of ${total} members`);
  await expect(cards.filter({ hasText: /Senator ·/ })).toHaveCount(0);

  await page.locator('#chamber').selectOption({ label: 'Both chambers' });
  await page.locator('#state').selectOption({ label: 'Ohio' });
  await expect(count).toHaveText(`${await countWhere({ state: 'OH' })} of ${total} members`);

  await page.locator('#state').selectOption({ label: 'All states' });
  await page.locator('#party').selectOption({ label: 'Independent' });
  await expect(count).toHaveText(`${await countWhere({ party: 'Independent' })} of ${total} members`);
  await expect(cards.filter({ hasNot: page.locator('.party-I') })).toHaveCount(0);

  // Filters combine
  await page.locator('#party').selectOption({ label: 'Republican' });
  await page.locator('#chamber').selectOption({ label: 'Senate' });
  await expect(count).toHaveText(
    `${await countWhere({ party: 'Republican', chamber: 'Senate' })} of ${total} members`);
});

test('04 Sort orders', async ({ page }) => {
  const sort = page.locator('#sort');

  // Default sort: best grade first
  await expectBestGradeFirst(page);

  await sort.selectOption({ label: 'Sort: lowest grade' });
  const ranks = (await gridGrades(page)).map((g) => GRADE_ORDER.indexOf(g));
  expectSorted(ranks, (a, b) => b - a);

  // Lowest attendance first
  await sort.selectOption({ label: 'Sort: most votes missed' });
  const attendance = (await page.locator('#grid .member').allTextContents()).map((text) => {
    const m = text.match(/([\d.]+)% of votes/);
    return m ? Number(m[1]) : 200;
  });
  expectSorted(attendance, (a, b) => a - b);

  // Compared in the browser so the collation matches the site's own sort
  await sort.selectOption({ label: 'Sort: name' });
  const misplaced = await page.evaluate(() => {
    const last = Object.fromEntries(window.REPORT_DATA.members.map((m) => [m.id, m.last]));
    const names = [...document.querySelectorAll('#grid .member')].map((e) => last[e.dataset.id]);
    const i = names.findIndex((v, n) => n > 0 && names[n - 1].localeCompare(v) > 0);
    return i === -1 ? null : `${names[i - 1]} then ${names[i]}`;
  });
  expect(misplaced, 'names out of order').toBeNull();
});

test('05 Grade distribution filter', async ({ page }) => {
  const total = await memberCount(page);
  const count = page.locator('#count');
  const aButton = page.locator("#summary button[data-g='A']");
  const fButton = page.locator("#summary button[data-g='F']");

  await expect(aButton).toHaveAttribute('aria-pressed', 'false');
  await aButton.click();
  await expect(aButton).toHaveAttribute('aria-pressed', 'true');

  const aCount = await page.locator('#grid .member').count();
  await expect(count).toHaveText(`${aCount} of ${total} members · showing A grades`);
  expect((await gridGrades(page)).filter((g) => !g.startsWith('A'))).toEqual([]);

  // Switching letters replaces the filter
  await fButton.click();
  await expect(aButton).toHaveAttribute('aria-pressed', 'false');
  await expect(fButton).toHaveAttribute('aria-pressed', 'true');
  expect((await gridGrades(page)).filter((g) => g !== 'F')).toEqual([]);

  // Clicking again clears the filter
  await fButton.click();
  await expect(count).toHaveText(`${total} of ${total} members`);

  // Bar totals add up to the graded members
  const barTotal = (await page.locator('#summary .n').allTextContents())
    .reduce((sum, text) => sum + parseInt(text, 10), 0);
  expect(barTotal).toBe(await page.locator('#grid .grade:not(.g-—)').count());
});

test('06 Member detail card', async ({ page }) => {
  const card = page.locator('#card');
  const first = page.locator('#grid .member').first();
  const memberId = await first.getAttribute('data-id');
  const memberName = (await first.locator('.name').innerText()).trim();
  const memberGrade = (await first.locator('.grade').innerText()).trim();

  await first.click();
  await expect(card).toBeVisible();
  await expect(page.locator('#card-name')).toHaveText(memberName);
  // Card grade matches the list
  await expect(card.locator('.card-head .grade')).toHaveText(memberGrade);

  // Attendance, bills written, bills supported
  await expect(card.locator('.subject')).toHaveCount(3);
  await expect(card.locator('.subject').first().locator('h3')).toHaveText('Vote attendance 40% of grade');
  await expect(card.locator(`a[href='https://www.congress.gov/member/${memberId}']`)).toBeAttached();

  // URL links to the open card
  await expect(page).toHaveURL(new RegExp(`#${memberId}$`));

  await card.locator('.close').click();
  await expect(card).toBeHidden();
  // The hash is cleared by the dialog's close event, which fires just after it hides
  await expect(page).not.toHaveURL(/#/);

  // Escape closes the card
  await page.locator('#grid .member').nth(1).click();
  await expect(card).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(card).toBeHidden();

  // Deep link opens the card on load. The query string forces a full page
  // load; changing only the hash would not rerun the site's startup code.
  await page.goto(`/?deeplink#${memberId}`);
  await expect(card).toBeVisible();
  await expect(page.locator('#card-name')).toHaveText(memberName);
});

test('07 Adjust grading weights', async ({ page }) => {
  const panel = page.locator('#weights');
  const button = page.locator('#weights-btn');
  const card = page.locator('#card');

  await expect(panel).toBeHidden();
  await expect(button).toHaveAttribute('aria-expanded', 'false');
  await button.click();
  await expect(panel).toBeVisible();
  await expect(button).toHaveAttribute('aria-expanded', 'true');

  await expect(page.locator('#wv-attendance')).toHaveText('40');
  await expect(page.locator('#wv-sponsored')).toHaveText('35');
  await expect(page.locator('#wv-cosponsored')).toHaveText('25');

  // Grade on attendance only
  await page.locator('#w-attendance').fill('100');
  await page.locator('#w-sponsored').fill('0');
  await page.locator('#w-cosponsored').fill('0');
  await expect(page.locator('#wv-attendance')).toHaveText('100');
  await expect(page.locator('#wv-sponsored')).toHaveText('0');
  expect(await page.evaluate(() => localStorage.getItem('rc-weights')))
    .toBe('{"attendance":100,"sponsored":0,"cosponsored":0}');

  // Weights survive a reload
  await page.reload();
  await expect(page.locator('#grid .member').first()).toBeAttached();
  await expect(page.locator('#w-attendance')).toHaveValue('100');
  await expect(page.locator('#w-cosponsored')).toHaveValue('0');

  await page.locator('#grid .member').first().click();
  await expect(card).toBeVisible();
  await expect(card.locator('.subject').first().locator('.tag')).toHaveText('100% of grade');
  await card.locator('.close').click();
  await expect(card).toBeHidden();

  // All weights zero: nobody can be graded
  await button.click();
  for (const key of ['attendance', 'sponsored', 'cosponsored']) {
    await page.locator(`#w-${key}`).fill('0');
  }
  expect((await gridGrades(page)).filter((g) => g !== '—')).toEqual([]);

  await page.locator('#reset-weights').click();
  await expect(page.locator('#wv-attendance')).toHaveText('40');
  await expect(page.locator('#w-sponsored')).toHaveValue('35');
  await expect(page.locator('#w-cosponsored')).toHaveValue('25');
  // Grades are back after reset
  await expectBestGradeFirst(page);
});

test('08 Methodology and sources', async ({ page }) => {
  const method = page.locator('#methodology');

  await expect(method.locator('h2')).toHaveText('How grades are calculated');
  await expect(method.locator('h3')).toHaveText(
    ['Vote attendance', 'Bills written', 'Bills supported', 'Letter grade']);

  for (const url of ['https://github.com/unitedstates/congress-legislators', 'https://voteview.com', 'https://api.congress.gov']) {
    await expect(method.locator(`a[href='${url}']`)).toBeAttached();
  }

  // Data timestamp is shown
  await expect(page.locator('#generated')).toHaveText(/^Updated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\.$/);

  // Nightly update ran within the last 3 days
  const generated = await page.evaluate(() => window.REPORT_DATA.generated);
  const ageDays = (Date.now() - Date.parse(generated.replace(' UTC', 'Z').replace(' ', 'T'))) / 86400000;
  expect(ageDays, `data was generated ${generated}`).toBeLessThan(3);
});

test('09 Data integrity', async ({ page }) => {
  const data = await page.evaluate(() => window.REPORT_DATA);
  const members = data.members;
  const senate = members.filter((m) => m.chamber === 'Senate');
  const house = members.filter((m) => m.chamber === 'House');
  // IDs of the members that fail a check, so a failure names them
  const failing = (ok) => members.filter((m) => !ok(m)).map((m) => m.id);

  // 535 voting members + 6 delegates, allowing for vacancies
  expect(members.length).toBeGreaterThanOrEqual(530);
  expect(members.length).toBeLessThanOrEqual(541);
  expect(senate.length).toBeGreaterThanOrEqual(95);
  expect(senate.length).toBeLessThanOrEqual(100);
  expect(house.length).toBeGreaterThanOrEqual(430);
  expect(house.length).toBeLessThanOrEqual(441);

  // No state has more than two senators
  const perState = {};
  senate.forEach((m) => { perState[m.state] = (perState[m.state] || 0) + 1; });
  expect(Object.entries(perState).filter(([, n]) => n > 2)).toEqual([]);

  expect(new Set(members.map((m) => m.id)).size).toBe(members.length);

  // Every member has a valid ID, name, chamber, party and state
  expect(failing((m) => /^[A-Z]\d{6}$/.test(m.id) && m.name && m.last &&
    ['House', 'Senate'].includes(m.chamber) &&
    ['Democrat', 'Republican', 'Independent'].includes(m.party) &&
    /^[A-Z]{2}$/.test(m.state))).toEqual([]);

  // Vote counts are consistent
  expect(failing((m) => m.votes.eligible >= 0 && m.votes.missed >= 0 &&
    m.votes.missed <= m.votes.eligible && m.votes.eligible <= m.votes.chamberTotal)).toEqual([]);
  expect(failing((m) => m.attendance === null || (m.attendance >= 0 && m.attendance <= 1))).toEqual([]);

  // Bill data is loaded for everyone
  expect(data.hasBills).toBeTruthy();
  expect(failing((m) => m.bills && m.bills.sponsored >= 0 && m.bills.cosponsored >= 0)).toEqual([]);

  // Every notable-bill link goes to congress.gov
  const notableUrls = members.flatMap((m) => (m.bills ? m.bills.notable : [])).map((n) => n.url);
  expect(notableUrls.filter((url) => !/^https:\/\/www\.congress\.gov\//.test(url))).toEqual([]);

  // With default weights everyone gets a real letter grade
  expect(failing((m) => GRADE_ORDER.slice(0, -1).includes(m.grade))).toEqual([]);
  expect(failing((m) => m.score >= 0 && m.score <= 100)).toEqual([]);
});

test('10 More interactions', async ({ page }) => {
  const total = await memberCount(page);
  const count = page.locator('#count');
  const cards = page.locator('#grid .member');
  const card = page.locator('#card');

  // A state abbreviation matches that state.
  // Same rule as the site: name, state abbreviation or state name
  await page.locator('#q').fill('oh');
  const ohMatches = await page.evaluate(() => window.REPORT_DATA.members.filter((m) =>
    m.state === 'OH' || m.name.toLowerCase().includes('oh') ||
    (STATES[m.state] || '').toLowerCase().includes('oh')).length);
  await expect(count).toHaveText(`${ohMatches} of ${total} members`);

  await page.locator('#q').fill('');
  await expect(count).toHaveText(`${total} of ${total} members`);

  // Every partial-term member, and only they, carry the Partial term tag
  const partial = await page.evaluate(() => window.REPORT_DATA.members.filter((m) => m.partial).length);
  await expect(cards.locator('.tag')).toHaveCount(partial);

  // Delegates from DC and the territories are labeled
  const delegates = await page.evaluate(() => window.REPORT_DATA.members.filter((m) => m.delegate).length);
  await expect(cards.filter({ hasText: /Delegate ·/ })).toHaveCount(delegates);

  // Clicking the backdrop outside the card closes it
  await cards.first().click();
  await expect(card).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(card).toBeHidden();

  await cards.first().click();
  await expect(card).toBeVisible();
  // Outside links open in a new tab with rel=noopener
  const unsafeLinks = await card.locator('.notable a').evaluateAll(
    (links) => links.filter((a) => a.target !== '_blank' || !a.rel.includes('noopener')).map((a) => a.href));
  expect(unsafeLinks).toEqual([]);
  // Bill progress shows all four stages
  await expect(card.locator('.stages div')).toHaveCount(4);
  await card.locator('.close').click();
  await expect(card).toBeHidden();

  // A deep link to an unknown member doesn't open a card or break the page
  await page.goto('/?bad#NOTAMEMBER');
  await expect(cards.first()).toBeAttached();
  await expect(card).toBeHidden();
  await expect(count).toHaveText(`${total} of ${total} members`);
});

test.describe('phone', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('11 Phone layout', async ({ page }) => {
    const card = page.locator('#card');

    // No horizontal scrolling at phone width
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    await expect(page.locator('#q')).toBeVisible();
    await expect(page.locator('#weights-btn')).toBeVisible();
    await expect(page.locator('#grid .member').first().locator('.grade')).toBeVisible();

    // The member card fits on screen
    await page.locator('#grid .member').first().click();
    await expect(card).toBeVisible();
    const box = await card.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(390);

    await card.locator('.close').click();
    await expect(card).toBeHidden();
  });
});
