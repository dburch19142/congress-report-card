# Congress Report Card

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

## View the site

`site/` is plain HTML/CSS/JS with no build step. Open `site/index.html` directly, or serve it:

```powershell
python -m http.server 8000 --directory site
```

The site is published with GitHub Pages: `.github/workflows/pages.yml` deploys `site/` on every
push to `main`. To update the grades, rerun `build_data.py`, then commit and push `site/data/members.js`.

## Data sources

- Roster: [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
- Votes: [Voteview](https://voteview.com) roll-call files
- Legislation: [Congress.gov API](https://api.congress.gov)
- Photos: [unitedstates/images](https://github.com/unitedstates/images)

## Known limitations

- Bill progress comes from each bill's *latest action* text, so it is an approximation.
- Members who joined mid-Congress are labeled "Partial term"; their bill percentiles cover less time.
- Voteview doesn't count votes the Speaker skips by custom, and delegates are counted only on the
  votes they are allowed to cast.
