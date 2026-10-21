"""Smoke tests for congressreportcard.org, in Python.

The same checks as congress-report-card.spec.js, written for pytest and Playwright.

One-time setup:
    pip install pytest-playwright
    playwright install

Run it either way:
    python tests/test_congress_report_card.py        (or the Run button in VS Code)
    pytest tests/test_congress_report_card.py

Extra options go on the end of either command:
    --headed                      watch the browser
    --browser firefox             chromium (default), firefox or webkit
    -k "ZIP"                      only tests whose name matches

Tests run against the live site by default. To test a local copy:
    python -m http.server 8000 --directory site
    $env:BASE_URL = "http://localhost:8000"; pytest tests/test_congress_report_card.py
"""
import os
import re
import struct
import sys
from datetime import datetime, timezone

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "https://congressreportcard.org")

GRADE_ORDER = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "—"]


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


# Each test gets a fresh browser context, so localStorage is empty and the
# site starts from the default grading weights.
@pytest.fixture(autouse=True)
def home_page(page: Page):
    page.goto("/")
    expect(page.locator("#grid .member").first).to_be_attached()


def member_count(page: Page) -> int:
    return page.evaluate("() => window.REPORT_DATA.members.length")


def grid_grades(page: Page) -> list[str]:
    return [t.strip() for t in page.locator("#grid .member .grade").all_text_contents()]


def assert_sorted(values, reverse=False):
    assert len(values) > 1
    for i in range(1, len(values)):
        before, after = values[i - 1], values[i]
        in_order = before >= after if reverse else before <= after
        assert in_order, f"item {i} is out of order: {before} then {after}"


def assert_best_grade_first(page: Page):
    assert_sorted([GRADE_ORDER.index(g) for g in grid_grades(page)])


def test_01_home_page_loads(page: Page):
    total = member_count(page)

    expect(page).to_have_title("Congress Report Card")
    expect(page.locator("h1")).to_have_text("Congress Report Card")
    expect(page.locator("#congress-label")).to_be_attached()

    # Every member is listed by default
    expect(page.locator("#count")).to_have_text(f"{total} of {total} members")
    expect(page.locator("#grid .member")).to_have_count(total)

    expect(page.locator("#chamber option:checked")).to_have_text("Both chambers")
    expect(page.locator("#state option:checked")).to_have_text("All states")
    expect(page.locator("#party option:checked")).to_have_text("All parties")
    expect(page.locator("#sort option:checked")).to_have_text("Sort: highest grade")

    for letter in ["A", "B", "C", "D", "F"]:
        expect(page.locator(f"#summary button[data-g='{letter}']")).to_be_attached()

    # Bill data is loaded, so the warning is hidden
    expect(page.locator("#notice")).to_be_hidden()

    # State list has one entry per state/territory, plus "All states"
    state_count = page.evaluate("() => new Set(window.REPORT_DATA.members.map((m) => m.state)).size")
    expect(page.locator("#state option")).to_have_count(state_count + 1)


def test_02_search_by_name_and_state(page: Page):
    total = member_count(page)
    count = page.locator("#count")
    search = page.locator("#q")

    senator = page.evaluate("() => window.REPORT_DATA.members.find((m) => m.chamber === 'Senate').name")
    search.fill(senator)
    expect(page.locator("#grid .member").first.locator(".name")).to_have_text(senator)
    matches = page.evaluate(
        "(q) => window.REPORT_DATA.members.filter((m) => m.name.toLowerCase().includes(q)).length",
        senator.lower())
    expect(count).to_have_text(f"{matches} of {total} members")

    search.fill("Ohio")
    ohio = page.evaluate(
        "() => window.REPORT_DATA.members.filter("
        "(m) => m.state === 'OH' || m.name.toLowerCase().includes('ohio')).length")
    expect(count).to_have_text(f"{ohio} of {total} members")
    expect(page.locator("#grid .member").filter(has_not_text=re.compile(r"· OH"))).to_have_count(0)

    # Nonsense search returns nothing
    search.fill("zzqqxxnomatch")
    expect(count).to_have_text(f"0 of {total} members")
    expect(page.locator("#grid .member")).to_have_count(0)

    search.fill("")
    expect(count).to_have_text(f"{total} of {total} members")


def test_03_chamber_state_and_party_filters(page: Page):
    total = member_count(page)
    count = page.locator("#count")
    cards = page.locator("#grid .member")

    def count_where(**fields):
        return page.evaluate(
            "(f) => window.REPORT_DATA.members.filter("
            "(m) => Object.entries(f).every(([k, v]) => m[k] === v)).length",
            fields)

    page.locator("#chamber").select_option(label="Senate")
    expect(count).to_have_text(f"{count_where(chamber='Senate')} of {total} members")
    expect(cards.filter(has_not_text=re.compile(r"Senator ·"))).to_have_count(0)

    page.locator("#chamber").select_option(label="House")
    expect(count).to_have_text(f"{count_where(chamber='House')} of {total} members")
    expect(cards.filter(has_text=re.compile(r"Senator ·"))).to_have_count(0)

    page.locator("#chamber").select_option(label="Both chambers")
    page.locator("#state").select_option(label="Ohio")
    expect(count).to_have_text(f"{count_where(state='OH')} of {total} members")

    page.locator("#state").select_option(label="All states")
    page.locator("#party").select_option(label="Independent")
    expect(count).to_have_text(f"{count_where(party='Independent')} of {total} members")
    expect(cards.filter(has_not=page.locator(".party-I"))).to_have_count(0)

    # Filters combine
    page.locator("#party").select_option(label="Republican")
    page.locator("#chamber").select_option(label="Senate")
    expect(count).to_have_text(
        f"{count_where(party='Republican', chamber='Senate')} of {total} members")


def test_04_sort_orders(page: Page):
    sort = page.locator("#sort")

    # Default sort: best grade first
    assert_best_grade_first(page)

    sort.select_option(label="Sort: lowest grade")
    assert_sorted([GRADE_ORDER.index(g) for g in grid_grades(page)], reverse=True)

    # Lowest attendance first
    sort.select_option(label="Sort: most votes missed")
    attendance = []
    for text in page.locator("#grid .member").all_text_contents():
        m = re.search(r"([\d.]+)% of votes", text)
        attendance.append(float(m.group(1)) if m else 200)
    assert_sorted(attendance)

    # Compared in the browser so the collation matches the site's own sort
    sort.select_option(label="Sort: name")
    misplaced = page.evaluate("""() => {
        const last = Object.fromEntries(window.REPORT_DATA.members.map((m) => [m.id, m.last]));
        const names = [...document.querySelectorAll('#grid .member')].map((e) => last[e.dataset.id]);
        const i = names.findIndex((v, n) => n > 0 && names[n - 1].localeCompare(v) > 0);
        return i === -1 ? null : `${names[i - 1]} then ${names[i]}`;
    }""")
    assert misplaced is None, f"names out of order: {misplaced}"


def test_05_grade_distribution_filter(page: Page):
    total = member_count(page)
    count = page.locator("#count")
    a_button = page.locator("#summary button[data-g='A']")
    f_button = page.locator("#summary button[data-g='F']")

    expect(a_button).to_have_attribute("aria-pressed", "false")
    a_button.click()
    expect(a_button).to_have_attribute("aria-pressed", "true")

    a_count = page.locator("#grid .member").count()
    expect(count).to_have_text(f"{a_count} of {total} members · showing A grades")
    assert [g for g in grid_grades(page) if not g.startswith("A")] == []

    # Switching letters replaces the filter
    f_button.click()
    expect(a_button).to_have_attribute("aria-pressed", "false")
    expect(f_button).to_have_attribute("aria-pressed", "true")
    assert [g for g in grid_grades(page) if g != "F"] == []

    # Clicking again clears the filter
    f_button.click()
    expect(count).to_have_text(f"{total} of {total} members")

    # Bar totals add up to the graded members
    bar_total = sum(int(re.match(r"\d+", text.strip()).group())
                    for text in page.locator("#summary .n").all_text_contents())
    assert bar_total == page.locator("#grid .grade:not(.g-—)").count()


def test_06_member_detail_card(page: Page):
    card = page.locator("#card")
    first = page.locator("#grid .member").first
    member_id = first.get_attribute("data-id")
    member_name = first.locator(".name").inner_text().strip()
    member_grade = first.locator(".grade").inner_text().strip()

    first.click()
    expect(card).to_be_visible()
    expect(page.locator("#card-name")).to_have_text(member_name)
    # Card grade matches the list
    expect(card.locator(".card-head .grade")).to_have_text(member_grade)

    # Attendance, bills written, bills supported
    expect(card.locator(".subject")).to_have_count(3)
    expect(card.locator(".subject").first.locator("h3")).to_have_text("Vote attendance 40% of grade")
    expect(card.locator(f"a[href='https://www.congress.gov/member/{member_id}']")).to_be_attached()

    # URL links to the open card
    expect(page).to_have_url(re.compile(f"#{member_id}$"))

    card.locator(".close").click()
    expect(card).to_be_hidden()
    # The hash is cleared by the dialog's close event, which fires just after it hides
    expect(page).not_to_have_url(re.compile("#"))

    # Escape closes the card
    page.locator("#grid .member").nth(1).click()
    expect(card).to_be_visible()
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()

    # Deep link opens the card on load. The query string forces a full page
    # load; changing only the hash would not rerun the site's startup code.
    page.goto(f"/?deeplink#{member_id}")
    expect(card).to_be_visible()
    expect(page.locator("#card-name")).to_have_text(member_name)


def test_07_adjust_grading_weights(page: Page):
    panel = page.locator("#weights")
    button = page.locator("#weights-btn")
    card = page.locator("#card")
    saved_weights = "() => localStorage.getItem('rc-weights')"

    expect(panel).to_be_hidden()
    expect(button).to_have_attribute("aria-expanded", "false")
    button.click()
    expect(panel).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")

    expect(page.locator("#wv-attendance")).to_have_text("40")
    expect(page.locator("#wv-sponsored")).to_have_text("35")
    expect(page.locator("#wv-cosponsored")).to_have_text("25")

    # Grade on attendance only
    page.locator("#w-attendance").fill("100")
    page.locator("#w-sponsored").fill("0")
    page.locator("#w-cosponsored").fill("0")
    expect(page.locator("#wv-attendance")).to_have_text("100")
    expect(page.locator("#wv-sponsored")).to_have_text("0")
    assert page.evaluate(saved_weights) == '{"attendance":100,"sponsored":0,"cosponsored":0}'

    # Weights survive a reload
    page.reload()
    expect(page.locator("#grid .member").first).to_be_attached()
    expect(page.locator("#w-attendance")).to_have_value("100")
    expect(page.locator("#w-cosponsored")).to_have_value("0")

    page.locator("#grid .member").first.click()
    expect(card).to_be_visible()
    expect(card.locator(".subject").first.locator(".tag")).to_have_text("100% of grade")
    card.locator(".close").click()
    expect(card).to_be_hidden()

    # Moving one slider rebalances the other two so the total stays 100
    button.click()
    page.locator("#w-sponsored").fill("50")
    expect(page.locator("#w-attendance")).to_have_value("50")
    expect(page.locator("#w-cosponsored")).to_have_value("0")
    page.locator("#w-cosponsored").fill("20")
    expect(page.locator("#wv-attendance")).to_have_text("40")
    expect(page.locator("#wv-sponsored")).to_have_text("40")
    expect(page.locator("#wv-cosponsored")).to_have_text("20")
    assert page.evaluate(saved_weights) == '{"attendance":40,"sponsored":40,"cosponsored":20}'

    page.locator("#reset-weights").click()
    expect(page.locator("#wv-attendance")).to_have_text("40")
    expect(page.locator("#w-sponsored")).to_have_value("35")
    expect(page.locator("#w-cosponsored")).to_have_value("25")
    # Grades are back after reset
    assert_best_grade_first(page)


def test_08_methodology_and_sources(page: Page):
    method = page.locator("#methodology")

    expect(method.locator("h2")).to_have_text("How grades are calculated")
    expect(method.locator("h3")).to_have_text(
        ["Vote attendance", "Bills written", "Bills supported", "Letter grade"])

    for url in ["https://github.com/unitedstates/congress-legislators", "https://voteview.com", "https://api.congress.gov"]:
        expect(method.locator(f"a[href='{url}']")).to_be_attached()

    # Data timestamp is shown
    expect(page.locator("#generated")).to_have_text(
        re.compile(r"^Updated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\.$"))

    # Nightly update ran within the last 3 days
    generated = page.evaluate("() => window.REPORT_DATA.generated")
    built = datetime.strptime(generated, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - built).total_seconds() / 86400
    assert age_days < 3, f"data was generated {generated}"


def test_09_data_integrity(page: Page):
    data = page.evaluate("() => window.REPORT_DATA")
    members = data["members"]
    senate = [m for m in members if m["chamber"] == "Senate"]
    house = [m for m in members if m["chamber"] == "House"]

    # IDs of the members that fail a check, so a failure names them
    def failing(ok):
        return [m["id"] for m in members if not ok(m)]

    # 535 voting members + 6 delegates, allowing for vacancies
    assert 530 <= len(members) <= 541
    assert 95 <= len(senate) <= 100
    assert 430 <= len(house) <= 441

    # No state has more than two senators
    per_state = {}
    for m in senate:
        per_state[m["state"]] = per_state.get(m["state"], 0) + 1
    assert {state: n for state, n in per_state.items() if n > 2} == {}

    assert len({m["id"] for m in members}) == len(members)

    # Every member has a valid ID, name, chamber, party and state
    assert failing(lambda m: re.fullmatch(r"[A-Z]\d{6}", m["id"]) and m["name"] and m["last"]
                   and m["chamber"] in ("House", "Senate")
                   and m["party"] in ("Democrat", "Republican", "Independent")
                   and re.fullmatch(r"[A-Z]{2}", m["state"])) == []

    # Vote counts are consistent
    assert failing(lambda m: m["votes"]["eligible"] >= 0 and m["votes"]["missed"] >= 0
                   and m["votes"]["missed"] <= m["votes"]["eligible"] <= m["votes"]["chamberTotal"]) == []
    assert failing(lambda m: m["attendance"] is None or 0 <= m["attendance"] <= 1) == []

    # Bill data is loaded for everyone
    assert data["hasBills"]
    assert failing(lambda m: m.get("bills") and m["bills"]["sponsored"] >= 0
                   and m["bills"]["cosponsored"] >= 0) == []

    # Every notable-bill link goes to congress.gov
    notable_urls = [n["url"] for m in members if m.get("bills") for n in m["bills"]["notable"]]
    assert [url for url in notable_urls if not url.startswith("https://www.congress.gov/")] == []

    # With default weights everyone gets a real letter grade
    assert failing(lambda m: m["grade"] in GRADE_ORDER[:-1]) == []
    assert failing(lambda m: 0 <= m["score"] <= 100) == []


def test_10_more_interactions(page: Page):
    total = member_count(page)
    count = page.locator("#count")
    cards = page.locator("#grid .member")
    card = page.locator("#card")

    # A state abbreviation matches that state.
    # Same rule as the site: name, state abbreviation or state name
    page.locator("#q").fill("oh")
    oh_matches = page.evaluate("""() => window.REPORT_DATA.members.filter((m) =>
        m.state === 'OH' || m.name.toLowerCase().includes('oh') ||
        (STATES[m.state] || '').toLowerCase().includes('oh')).length""")
    expect(count).to_have_text(f"{oh_matches} of {total} members")

    page.locator("#q").fill("")
    expect(count).to_have_text(f"{total} of {total} members")

    # Every partial-term member, and only they, carry the Partial term tag
    partial = page.evaluate("() => window.REPORT_DATA.members.filter((m) => m.partial).length")
    expect(cards.locator(".tag")).to_have_count(partial)

    # Delegates from DC and the territories are labeled
    delegates = page.evaluate("() => window.REPORT_DATA.members.filter((m) => m.delegate).length")
    expect(cards.filter(has_text=re.compile(r"Delegate ·"))).to_have_count(delegates)

    # Clicking the backdrop outside the card closes it
    cards.first.click()
    expect(card).to_be_visible()
    page.mouse.click(5, 5)
    expect(card).to_be_hidden()

    cards.first.click()
    expect(card).to_be_visible()
    # Outside links open in a new tab with rel=noopener
    unsafe_links = card.locator(".notable a").evaluate_all(
        "(links) => links.filter((a) => a.target !== '_blank' || !a.rel.includes('noopener')).map((a) => a.href)")
    assert unsafe_links == []
    # Bill progress shows all four stages
    expect(card.locator(".stages div")).to_have_count(4)
    card.locator(".close").click()
    expect(card).to_be_hidden()

    # A deep link to an unknown member doesn't open a card or break the page
    page.goto("/?bad#NOTAMEMBER")
    expect(cards.first).to_be_attached()
    expect(card).to_be_hidden()
    expect(count).to_have_text(f"{total} of {total} members")


@pytest.mark.browser_context_args(viewport={"width": 390, "height": 844})
def test_11_phone_layout(page: Page):
    card = page.locator("#card")

    # No horizontal scrolling at phone width
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0

    expect(page.locator("#q")).to_be_visible()
    expect(page.locator("#weights-btn")).to_be_visible()
    expect(page.locator("#grid .member").first.locator(".grade")).to_be_visible()

    # The member card fits on screen
    page.locator("#grid .member").first.click()
    expect(card).to_be_visible()
    box = card.bounding_box()
    assert box["x"] >= 0
    assert box["x"] + box["width"] <= 390

    card.locator(".close").click()
    expect(card).to_be_hidden()


def test_12_search_by_zip_code(page: Page):
    total = member_count(page)
    count = page.locator("#count")
    note = page.locator("#zip-note")
    cards = page.locator("#grid .member")
    search = page.locator("#q")

    expect(note).to_be_hidden()

    # A ZIP in one district: its representative and both senators
    search.fill("10001")
    expect(note).to_have_text("ZIP code 10001 is in NY-12.")
    expected = page.evaluate("""() => window.REPORT_DATA.members.filter((m) =>
        m.state === 'NY' && (m.chamber === 'Senate' || m.district === 12)).length""")
    expect(count).to_have_text(f"{expected} of {total} members")
    expect(cards.filter(has_text=re.compile(r"Senator · NY"))).to_have_count(2)
    expect(cards.filter(has_not_text=re.compile(r"Senator · NY|Rep\. · NY-12"))).to_have_count(0)

    # A ZIP split between districts lists each one and links to the address lookup
    search.fill("43215")
    expect(note).to_contain_text("covers parts of OH-15 and OH-3")
    expect(note.locator("a[href='https://www.house.gov/representatives/find-your-representative']")).to_be_attached()
    expect(cards.filter(has_not_text=re.compile(r"Senator · OH|Rep\. · OH-(3|15)$", re.MULTILINE))).to_have_count(0)

    # ZIP+4 works, and other filters still apply
    search.fill("43215-1234")
    page.locator("#chamber").select_option(label="Senate")
    expect(cards).to_have_count(2)
    page.locator("#chamber").select_option(label="Both chambers")

    search.fill("432")
    expect(note).to_have_text("Enter a 5-digit ZIP code to find your members of Congress.")
    expect(cards).to_have_count(0)

    search.fill("00000")
    expect(note).to_contain_text("ZIP code 00000 wasn't found.")
    expect(cards).to_have_count(0)

    # Clearing the search brings everyone back
    search.fill("")
    expect(note).to_be_hidden()
    expect(count).to_have_text(f"{total} of {total} members")


def test_13_member_page_share_image_and_badge(page: Page):
    # What the home page says about the first few members
    sample = page.evaluate("""() => window.REPORT_DATA.members.slice(0, 5)
        .map((m) => ({ id: m.id, name: m.name, grade: m.grade }))""")

    # The member pages are graded by build_pages.py; they must agree with the home page
    for m in sample:
        page.goto(f"/members/{m['id']}.html")
        expect(page.locator("#member-name")).to_have_text(m["name"])
        expect(page.locator(".card-head .grade")).to_have_text(m["grade"])
        title = page.title()
        assert title.startswith(f"{m['name']} ("), title
        assert title.endswith(f": Grade {m['grade']} | Congress Report Card"), title

    m = sample[0]
    page.goto(f"/members/{m['id']}.html")
    expect(page.locator(".summary-text")).to_contain_text(f"overall grade of {m['grade']}")
    expect(page.locator(".subject")).to_have_count(3)
    expect(page.locator("link[rel=canonical]")).to_have_attribute(
        "href", f"https://congressreportcard.org/members/{m['id']}.html")

    # The share image is drawn in the browser and can be downloaded
    expect(page.locator("#share-preview")).to_be_visible()
    size = page.locator("#share-preview").evaluate(
        "(img) => img.decode().then(() => [img.naturalWidth, img.naturalHeight])")
    assert size == [1200, 630]
    with page.expect_download() as download:
        page.locator("#share-download").click()
    assert download.value.suggested_filename.endswith("-report-card.png")

    # The tall version for TikTok is 1080 by 1920
    with page.expect_download() as tall:
        page.locator("#share-download-tall").click()
    assert tall.value.suggested_filename.endswith("-report-card-tall.png")
    with open(tall.value.path(), "rb") as f:
        png = f.read(24)
    assert struct.unpack(">II", png[16:24]) == (1080, 1920)

    # The badge shows the same grade, and the embed code points at the live site
    badge = page.request.get(f"/badges/{m['id']}.svg")
    assert badge.ok
    assert f">{m['grade']}</text>" in badge.text()
    expect(page.locator("#embed-code")).to_have_value(re.compile(
        rf'^<a href="https://congressreportcard\.org/members/{m["id"]}\.html">'
        rf'<img src="https://congressreportcard\.org/badges/{m["id"]}\.svg"'))

    # The home page card links to the member page
    page.goto(f"/?card#{m['id']}")
    page.locator(f"#card a[href='members/{m['id']}.html']").click()
    expect(page.locator("#member-name")).to_have_text(m["name"])


def test_14_methodology_privacy_and_contact_pages(page: Page):
    footer = page.locator(".site-footer nav a")
    expect(footer).to_have_text(["All members", "Weekly digest", "Methodology", "Privacy policy", "Contact"])

    footer.filter(has_text="Methodology").click()
    expect(page.locator("h1")).to_have_text("How grades are calculated")
    expect(page).to_have_title("How grades are calculated | Congress Report Card")

    page.locator(".site-footer nav a", has_text="Privacy policy").click()
    expect(page.locator("h1")).to_have_text("Privacy policy")
    expect(page.locator("main")).to_contain_text(re.compile(r"Last updated \w+ \d{1,2}, \d{4}"))
    expect(page.locator("main")).to_contain_text("Google AdSense")
    expect(page.locator("main a[href^='mailto:']")).to_be_attached()

    page.locator(".site-footer nav a", has_text="Contact").click()
    expect(page.locator("h1")).to_have_text("Contact")
    expect(page.locator("main a[href^='mailto:']")).to_be_attached()

    page.locator(".site-footer nav a", has_text="All members").click()
    expect(page.locator("#grid .member").first).to_be_attached()

    # The short link for the TikTok profile lands on the home page, tagged for the visitor counter
    page.goto("/tiktok/")
    expect(page).to_have_url(re.compile(r"/\?utm_source=tiktok$"))
    expect(page.locator("#grid .member").first).to_be_attached()

    # The browser tab shows the flag icon
    expect(page.locator("link[rel='icon'][type='image/svg+xml']")).to_have_attribute("href", "favicon.svg")
    for icon in ["/favicon.svg", "/favicon.png", "/favicon.ico", "/apple-touch-icon.png"]:
        assert page.request.get(icon).ok, icon

    # Search engines: robots.txt points at a sitemap listing every member page
    assert "Sitemap: https://congressreportcard.org/sitemap.xml" in page.request.get("/robots.txt").text()
    sitemap = page.request.get("/sitemap.xml").text()
    total = member_count(page)
    assert len(re.findall(r"/members/[A-Z]\d{6}\.html</loc>", sitemap)) == total


def test_15_weekly_digest_and_email_sign_up(page: Page):
    # The sign-up box shows only once a MailerLite form is configured in signup.js
    configured = page.evaluate("() => Boolean(SIGNUP.formAction || SIGNUP.pageUrl)")
    signup = page.locator("#signup")
    if configured:
        expect(signup).to_be_visible()
        expect(signup.locator("input[type='email'], a.button")).to_be_visible()
    else:
        expect(signup).to_be_hidden()

    page.locator(".site-footer nav a", has_text="Weekly digest").click()
    expect(page.locator("h1")).to_have_text(re.compile(r"^Week ending \w+ \d{1,2}, \d{4}$"))
    expect(page.locator("#digest h2").first).to_have_text("Votes this week")
    # Links in the digest are absolute so they work when pasted into an email
    relative = page.locator("#digest a").evaluate_all(
        "(links) => links.map((a) => a.getAttribute('href')).filter((h) => !/^https:\\/\\//.test(h))")
    assert relative == []

    # The copy buttons for sending the email appear only with ?send
    expect(page.locator("#send-tools")).to_be_hidden()
    page.goto("/digest/?send")
    expect(page.locator("#send-tools")).to_be_visible()
    expect(page.locator("#send-subject")).to_have_text(page.locator("h1").inner_text())

    feed = page.request.get("/digest/feed.xml")
    assert feed.ok
    assert "<title>Week ending " in feed.text()

    # The digest is no more than 8 days old
    heading = page.locator("h1").inner_text().strip()
    ended = datetime.strptime(heading, "Week ending %B %d, %Y").replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - ended).total_seconds() / 86400 < 9


def test_16_ad_slots(page: Page):
    # Where ads may appear. The privacy and contact pages carry none.
    expected = {
        "/": ["home"],
        "/methodology.html": ["page"],
        "/digest/": ["page"],
        "/privacy.html": [],
        "/contact.html": [],
    }
    member_id = page.evaluate("() => window.REPORT_DATA.members[0].id")
    expected[f"/members/{member_id}.html"] = ["member"]

    for path, slots in expected.items():
        page.goto(path)
        found = page.locator(".ad-slot").evaluate_all("(els) => els.map((e) => e.dataset.ad)")
        assert found == slots, path
        if not slots:
            continue

        # A slot shows an ad only when its ad unit ID is set in ads.js; otherwise it stays empty
        configured = page.evaluate("(name) => Boolean(AD_SLOTS[name])", slots[0])
        slot = page.locator(".ad-slot")
        if configured:
            expect(slot.locator("ins.adsbygoogle")).to_have_attribute("data-ad-client", "ca-pub-7873162278456307")
            expect(slot.locator(".ad-label")).to_have_text("Advertisement")
        else:
            expect(slot).to_be_empty()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))
