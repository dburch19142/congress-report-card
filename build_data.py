"""
Builds site/data/members.js — the raw record for every current member of Congress.

Sources (all public):
  * Roster ........ https://github.com/unitedstates/congress-legislators
  * Roll-call votes https://voteview.com (every member's vote on every roll call)
  * Legislation ... https://api.congress.gov (free key: https://api.congress.gov/sign-up/)

Usage:
  set CONGRESS_API_KEY=your_key        (PowerShell: $env:CONGRESS_API_KEY="your_key")
  python build_data.py                 # full build
  python build_data.py --no-bills      # attendance only, no API key needed
  python build_data.py --limit 5       # only fetch bills for 5 members (testing)

  The key can also be saved on one line in a file named .congress_api_key next to this script.

Grades are NOT computed here — the site computes them from these raw numbers so the
weighting can be adjusted in the browser. See site/app.js (GRADING).
"""
import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

CONGRESS = 119
ROOT = Path(__file__).parent
CACHE = ROOT / ".cache"
CACHE_MAX_AGE = 20 * 3600  # seconds; lets an interrupted run resume, but each day's build is fresh
MAX_FAILURE_RATE = 0.05    # refuse to write output if more members than this fail to load
OUT = ROOT / "site" / "data" / "members.js"

LEGISLATORS_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
VOTEVIEW = "https://voteview.com/static/data/out"
API = "https://api.congress.gov/v3"

# Voteview cast codes: 1-3 yea, 4-6 nay, 7-8 present, 9 not voting, 0 not in office
MISSED = {9}
NOT_IN_OFFICE = {0}

# Bills and joint resolutions can become law; simple/concurrent resolutions cannot.
LAW_TYPES = {"HR", "S", "HJRES", "SJRES"}


def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "congress-report-card/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60 * (attempt + 1)
                print(f"  rate limited; waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
            elif e.code >= 500 and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}")


def cached_json(key, url):
    path = CACHE / f"{key}.json"
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass  # partial file from an interrupted run; fetch again
    data = json.loads(fetch(url))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)  # atomic, so an interrupted run never leaves a half-written file
    return data


# ---------------------------------------------------------------- roster

def load_roster():
    people = json.loads(fetch(LEGISLATORS_URL))
    roster = {}
    for p in people:
        term = p["terms"][-1]
        bio = p["id"]["bioguide"]
        name = p["name"]
        roster[bio] = {
            "id": bio,
            "name": name.get("official_full") or f'{name["first"]} {name["last"]}',
            "last": name["last"],
            "chamber": "Senate" if term["type"] == "sen" else "House",
            "state": term["state"],
            "district": term.get("district"),
            "party": term["party"],
            "termStart": term["start"],
            "url": term.get("url"),
        }
    return roster


# ---------------------------------------------------------------- votes

def load_attendance():
    """Returns {bioguide: {...}} and per-chamber roll-call totals."""
    members_csv = fetch(f"{VOTEVIEW}/members/HS{CONGRESS}_members.csv")
    icpsr_to_bio = {}
    for row in csv.DictReader(io.StringIO(members_csv)):
        if row["bioguide_id"]:
            icpsr_to_bio[(row["chamber"], row["icpsr"])] = row["bioguide_id"]

    stats, totals = {}, {}
    for ch, prefix in (("House", "H"), ("Senate", "S")):
        votes_csv = fetch(f"{VOTEVIEW}/votes/{prefix}{CONGRESS}_votes.csv")
        rolls = set()
        for row in csv.DictReader(io.StringIO(votes_csv)):
            rolls.add(row["rollnumber"])
            bio = icpsr_to_bio.get((ch, row["icpsr"]))
            code = int(row["cast_code"])
            if not bio or code in NOT_IN_OFFICE:
                continue
            s = stats.setdefault(bio, {"eligible": 0, "missed": 0})
            s["eligible"] += 1
            if code in MISSED:
                s["missed"] += 1
        totals[ch] = len(rolls)
    return stats, totals


# ---------------------------------------------------------------- bills

def stage(action_text):
    """Classifies a bill's furthest progress from its latest action text."""
    t = (action_text or "").lower()
    if "became public law" in t or "became private law" in t or "signed by president" in t:
        return "law"
    if "presented to president" in t or "passed/agreed to in" in t or "passed senate" in t \
            or "passed house" in t or "received in the" in t or "held at the desk" in t \
            or "resolving differences" in t or "vetoed" in t:
        return "passed"
    if "reported" in t or ("placed on" in t and "calendar" in t) or "discharged" in t:
        return "committee"
    return "introduced"


def member_bills(bio, kind, key):
    """kind: 'sponsored' or 'cosponsored'. Stops paginating once past this Congress."""
    field = f"{kind}Legislation"
    items, offset = [], 0
    while True:
        url = f"{API}/member/{bio}/{kind}-legislation?format=json&limit=250&offset={offset}&api_key={key}"
        page = cached_json(f"{CONGRESS}/{bio}-{kind}-{offset}", url)
        batch = page.get(field, [])
        for b in batch:
            if b.get("congress") == CONGRESS and b.get("type"):
                items.append(b)
        older = any((b.get("congress") or 0) < CONGRESS for b in batch)
        if older or not page.get("pagination", {}).get("next") or not batch:
            return items
        offset += 250


def summarize_bills(bio, key):
    sponsored = member_bills(bio, "sponsored", key)
    cosponsored = member_bills(bio, "cosponsored", key)
    counts = {"introduced": 0, "committee": 0, "passed": 0, "law": 0}
    resolutions = 0
    notable = []
    for b in sponsored:
        if b["type"] not in LAW_TYPES:
            resolutions += 1
            continue
        st = stage((b.get("latestAction") or {}).get("text"))
        counts[st] += 1
        if st != "introduced":
            notable.append({
                "id": f'{b["type"]} {b["number"]}',
                "title": b.get("title", ""),
                "stage": st,
                "url": f'https://www.congress.gov/bill/{CONGRESS}th-congress/'
                       f'{"house" if b["type"].startswith("H") else "senate"}-'
                       f'{ {"HR": "bill", "S": "bill", "HJRES": "joint-resolution", "SJRES": "joint-resolution"}[b["type"]] }/{b["number"]}',
            })
    order = {"law": 0, "passed": 1, "committee": 2}
    notable.sort(key=lambda n: order[n["stage"]])
    return {
        "sponsored": sum(counts.values()),
        "stages": counts,
        "resolutions": resolutions,
        "cosponsored": sum(1 for b in cosponsored if b["type"] in LAW_TYPES),
        "notable": notable[:8],
    }


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-bills", action="store_true", help="skip Congress.gov (no key needed)")
    ap.add_argument("--limit", type=int, help="only fetch bills for the first N members")
    ap.add_argument("--workers", type=int, default=8, help="parallel Congress.gov requests")
    args = ap.parse_args()

    key = os.environ.get("CONGRESS_API_KEY")
    key_file = ROOT / ".congress_api_key"
    if not key and key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
    fetch_bills = not args.no_bills
    if fetch_bills and not key:
        print("No CONGRESS_API_KEY set — building attendance only.\n"
              "Get a free key at https://api.congress.gov/sign-up/ for bill data.", file=sys.stderr)
        fetch_bills = False

    print("Loading roster…")
    roster = load_roster()
    print(f"  {len(roster)} current members")

    print("Loading roll-call votes…")
    attendance, totals = load_attendance()
    print(f"  House {totals['House']} roll calls, Senate {totals['Senate']}")

    ids = sorted(roster)
    members = [roster[bio] for bio in ids]
    for m in members:
        a = attendance.get(m["id"], {"eligible": 0, "missed": 0})
        m["votes"] = {**a, "chamberTotal": totals[m["chamber"]]}
        m["bills"] = None

    if fetch_bills:
        todo = members[:args.limit] if args.limit else members
        done = 0

        def work(m):
            try:
                m["bills"] = summarize_bills(m["id"], key)
                return None
            except Exception as e:  # keep going; the site shows "no data" for this member
                return e

        # Congress.gov responses are slow (~6s each), so fetch several members at once.
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for m, err in zip(todo, pool.map(work, todo)):
                done += 1
                print(f"  [{done}/{len(todo)}] bills: {m['name']}" + (f"  FAILED: {err}" if err else ""))

        failed = sum(1 for m in todo if m["bills"] is None)
        if failed > len(todo) * MAX_FAILURE_RATE:
            sys.exit(f"{failed} of {len(todo)} members failed to load; not writing {OUT.name}")

    payload = {
        "congress": CONGRESS,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "hasBills": any(m["bills"] for m in members),
        "members": members,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.REPORT_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
