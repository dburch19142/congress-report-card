# Congress Report Card

[![Nightly data update](https://github.com/dburch19142/congress-report-card/actions/workflows/update-data.yml/badge.svg)](https://github.com/dburch19142/congress-report-card/actions/workflows/update-data.yml)
[![Deploy site to GitHub Pages](https://github.com/dburch19142/congress-report-card/actions/workflows/pages.yml/badge.svg)](https://github.com/dburch19142/congress-report-card/actions/workflows/pages.yml)

A static website that gives every current U.S. Representative and Senator a letter grade for the
current Congress (119th, 2025–2027). Grades are based on:

| Component        | Default weight | Measure                                                             |
|------------------|---------------:|---------------------------------------------------------------------|
| Vote attendance  | 40%            | % of roll-call votes cast (100% → 100 pts, ≤85% → 0 pts)            |
| Bills written    | 35%            | Sponsored bills, weighted by progress; chamber rank mapped to 50–100 (average = 75, a C) |
| Bills supported  | 25%            | Cosponsored bills; chamber rank mapped to 50–100 (average = 75, a C) |

Visitors can change the weights with the **Adjust grading** panel. All grading rules are in the
`GRADING` object at the top of `site/app.js`.

## Build the data

Requires Python 3.9+ (standard library only).

1. Get a free Congress.gov API key at https://api.congress.gov/sign-up/
2. Run:

   ```powershell
   $env:CONGRESS_API_KEY = "your_key"
   python build_data.py
   ```

   The first full run makes about 1,500 API calls and takes around 20–30 minutes. Responses are
   cached in `.cache/`, so if a run is interrupted, rerunning picks up where it left off. Delete
   `.cache/` to fetch fresh bill data.

   Without a key, `python build_data.py --no-bills` builds attendance-only grades.

The ZIP code search uses `site/data/zips.js`, which lists the congressional district(s) for each
ZIP code. District lines don't change during a Congress, so it isn't part of the nightly update.
Rebuild it with `python build_zips.py` when a new Congress starts.

## View the site

`site/` is plain HTML/CSS/JS with no build step. Open `site/index.html` directly, or serve it:

```powershell
python -m http.server 8000 --directory site
```

The member pages (`site/members/`), grade badges (`site/badges/`) and `site/sitemap.xml` are
generated from the data and are not committed. Build them before previewing locally:

```powershell
python build_pages.py
```

Both deploy workflows run this step, so the published pages always match the nightly data.
`build_pages.py` repeats the grading rules from `site/app.js`; change both together. A smoke test
checks that they agree.

The site is published with GitHub Pages: `.github/workflows/pages.yml` deploys `site/` on every
push to `main`.

The data refreshes automatically: `.github/workflows/update-data.yml` runs every night at
09:00 UTC, rebuilds `site/data/members.js` using the `CONGRESS_API_KEY` repository secret, commits
it and redeploys the site. It can also be run by hand from the repo's **Actions** tab
(**Nightly data update → Run workflow**). If more than 5% of members fail to load, the build stops
and the site keeps the previous day's data.

## Ads

Ads are off until a publisher ID is set. After AdSense approves the site:

1. Paste the publisher ID into `ADSENSE_CLIENT` in `site/ads.js`. The next deploy loads the
   AdSense script on every page and publishes `ads.txt`.
2. In AdSense, open **Privacy & messaging → European regulations** and create the consent
   message. Google shows it to visitors in Europe through the same script.
3. In AdSense, open **Brand safety → Content → Blocking controls → Sensitive categories** and
   block **Politics**, so ads don't make the grades look biased.

## Data sources

- Roster: [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
- Votes: [Voteview](https://voteview.com) roll-call files
- Legislation: [Congress.gov API](https://api.congress.gov)
- Photos: [unitedstates/images](https://github.com/unitedstates/images)
- ZIP code districts: [Census Bureau relationship files](https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html)

## Known limitations

- About 15% of ZIP codes cross a district line. The site shows every House member for those ZIP
  codes and links to the House's street-address lookup. ZIP codes used only for PO boxes or a
  single building aren't in the Census data.
- Bill progress comes from each bill's *latest action* text, so it is an approximation.
- Members who joined mid-Congress are labeled "Partial term"; their bill percentiles cover less time.
- Voteview doesn't count votes the Speaker skips by custom, and delegates are counted only on the
  votes they are allowed to cast.
