"""
Builds the weekly digest: what changed in the report-card data since the last digest.

  site/digest/index.html   the digest as a web page (also the text to paste into the email)
  site/digest/feed.xml     RSS feed with the latest digest, for sending it automatically later
  digest_snapshot.json     the data as of this digest, to compare against next week

The nightly workflow runs this after build_data.py. It only writes a new digest on
Saturdays (or if the last one is more than a week old), so the page stays the same all week.

Usage:
  python build_digest.py                      # as the nightly job runs it
  python build_digest.py --force              # build a digest now, whatever the day
  python build_digest.py --init-from OLD.js   # start the snapshot from an older members.js

Sending the email is done by hand: open site/digest/?send, copy the digest and paste it
into a new campaign in the email service.
"""
import argparse
import json
from datetime import date, datetime
from email.utils import format_datetime
from html import escape

from build_data import OUT as DATA_FILE, ROOT
from build_pages import PARTY, SITE, SITE_URL, compute_grades, district, footer, plural, write

SNAPSHOT = ROOT / "digest_snapshot.json"
OUT_DIR = SITE / "digest"
DIGEST_WEEKDAY = 5   # Saturday (Monday is 0), after the week's votes are in
TOP = 10             # how many members to list for missed votes
MOVERS = 5           # how many grade changes to list in each direction


def load_members_js(path):
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def slim(data):
    """The parts of the data needed to grade members and compare weeks."""
    members = []
    for m in data["members"]:
        b = m["bills"]
        members.append({
            **{k: m[k] for k in ("id", "name", "last", "chamber", "state", "district", "party", "votes")},
            "bills": b and {**{k: b[k] for k in ("sponsored", "stages", "resolutions", "cosponsored")},
                            "notable": [{"id": n["id"], "stage": n["stage"]} for n in b["notable"] if n["stage"] == "law"]},
        })
    return {"generated": data["generated"], "members": members}


def day(generated):
    return datetime.strptime(generated[:10], "%Y-%m-%d").date()


def long_date(d, year=True):
    return f"{d:%B} {d.day}" + (f", {d.year}" if year else "")


# ---------------------------------------------------------------- comparison

def compare(cur, prev):
    """Returns the facts for the digest. cur and prev are graded member lists."""
    before = {m["id"]: m for m in prev}
    both = [(m, before[m["id"]]) for m in cur if m["id"] in before]

    rolls = {}
    for chamber in ("House", "Senate"):
        now = next((m["votes"]["chamberTotal"] for m in cur if m["chamber"] == chamber), 0)
        then = next((m["votes"]["chamberTotal"] for m in prev if m["chamber"] == chamber), 0)
        rolls[chamber] = max(0, now - then)

    missed, perfect, voting = [], 0, 0
    for m, old in both:
        eligible = m["votes"]["eligible"] - old["votes"]["eligible"]
        skipped = m["votes"]["missed"] - old["votes"]["missed"]
        if eligible <= 0:
            continue
        voting += 1
        if skipped <= 0:
            perfect += 1
        else:
            missed.append((skipped, eligible, m))
    missed.sort(key=lambda x: (-x[0], -x[0] / x[1], x[2]["last"]))

    changed = [(m["score"] - old["score"], old["grade"], m) for m, old in both
               if m["score"] is not None and old["score"] is not None and m["grade"] != old["grade"]]
    up = sorted((c for c in changed if c[0] > 0), key=lambda c: -c[0])
    down = sorted((c for c in changed if c[0] < 0), key=lambda c: c[0])

    laws, seen = [], set()
    for m, old in both:
        if not m["bills"] or not old["bills"]:
            continue
        had = {n["id"] for n in old["bills"]["notable"] if n["stage"] == "law"}
        for n in m["bills"]["notable"]:
            if n["stage"] == "law" and n["id"] not in had and n["id"] not in seen:
                seen.add(n["id"])
                laws.append((n, m))

    now_ids = {m["id"] for m in cur}
    return {
        "rolls": rolls, "missed": missed, "perfect": perfect, "voting": voting,
        "changed": len(changed), "up": up, "down": down, "laws": laws,
        "joined": [m for m in cur if m["id"] not in before],
        "left": [m for m in prev if m["id"] not in now_ids],
    }


# ---------------------------------------------------------------- HTML

def who(m):
    """Linked name with party and district. Links are absolute so they work in an email."""
    return (f'<a href="{SITE_URL}/members/{m["id"]}.html">{escape(m["name"])}</a> '
            f'({PARTY.get(m["party"], "I")}, {district(m)})')


def digest_body(facts, start, end):
    r = facts["rolls"]
    out = [f"<p>Here is what changed in the public record of Congress from {long_date(start, False)} "
           f"to {long_date(end)}.</p>"]

    out.append("<h2>Votes this week</h2>")
    if not r["House"] and not r["Senate"]:
        out.append("<p>Neither chamber held a roll-call vote this week.</p>")
    else:
        held = lambda n: f"held {plural(n, 'roll-call vote')}" if n else "held no roll-call votes"
        out.append(f"<p>The House {held(r['House'])} and the Senate {held(r['Senate'])}. {facts['perfect']} of the {facts['voting']} members who could vote "
                   f"cast every vote.</p>")
        if facts["missed"]:
            out.append("<h2>Most votes missed this week</h2><ol>")
            out += [f"<li>{who(m)} missed {skipped} of {eligible}</li>"
                    for skipped, eligible, m in facts["missed"][:TOP]]
            out.append("</ol>")

    if facts["laws"]:
        out.append("<h2>Bills that became law</h2><ul>")
        out += [f'<li><a href="{escape(n["url"])}">{escape(n["id"])}</a>: {escape(n["title"])}. '
                f'Sponsored by {who(m)}.</li>' for n, m in facts["laws"]]
        out.append("</ul>")

    if facts["changed"]:
        out.append("<h2>Grade changes</h2>")
        out.append(f"<p>{plural(facts['changed'], 'member')} moved to a different letter grade. "
                   f"Bill scores are ranked within each chamber, so a grade can move when other "
                   f"members' records change.</p>")
        for title, rows in (("Biggest gains", facts["up"]), ("Biggest drops", facts["down"])):
            if rows:
                out.append(f"<h3>{title}</h3><ul>")
                out += [f"<li>{who(m)}: {old} to {m['grade']}</li>" for _, old, m in rows[:MOVERS]]
                out.append("</ul>")

    if facts["joined"] or facts["left"]:
        out.append("<h2>Arrivals and departures</h2><ul>")
        out += [f"<li>{who(m)} joined the {m['chamber']}.</li>" for m in facts["joined"]]
        out += [f"<li>{escape(m['name'])} ({PARTY.get(m['party'], 'I')}, {district(m)}) left the {m['chamber']}.</li>"
                for m in facts["left"]]
        out.append("</ul>")

    out.append(f'<p>See every member\'s grade at <a href="{SITE_URL}/">congressreportcard.org</a>, or read '
               f'<a href="{SITE_URL}/methodology.html">how grades are calculated</a>.</p>')
    return "\n      ".join(out)


def digest_page(body, title, end):
    url = f"{SITE_URL}/digest/"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Congress Report Card</title>
  <meta name="description" content="Weekly digest for the week ending {long_date(end)}: missed votes, grade changes and bills that became law.">
  <link rel="canonical" href="{url}">
  <link rel="alternate" type="application/rss+xml" title="Congress Report Card weekly digest" href="feed.xml">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <header class="masthead slim">
    <div class="wrap"><a class="home" href="../">Congress Report Card</a></div>
  </header>

  <main class="wrap page prose">
    <section class="send-tools" id="send-tools" hidden>
      <strong>Sending this week's email</strong>
      <p>Subject line: <span id="send-subject">{title}</span></p>
      <div class="buttons">
        <button id="copy-subject">Copy subject</button>
        <button id="copy-digest">Copy digest</button>
      </div>
      <p>Paste the digest into a text block in a new campaign.</p>
    </section>

    <p class="eyebrow">Weekly digest</p>
    <article id="digest">
      <h1>{title}</h1>
      {body}
    </article>

    <section class="signup" id="signup" hidden></section>
  </main>

  {footer("../")}
  <script src="../ads.js"></script>
  <script src="../analytics.js"></script>
  <script src="../signup.js"></script>
  <script>
    // Open this page with ?send on the end to get the copy buttons for the weekly email.
    if (new URLSearchParams(location.search).has("send")) {{
      const tools = document.getElementById("send-tools");
      const flash = (b, t) => {{ const old = b.textContent; b.textContent = t; setTimeout(() => {{ b.textContent = old; }}, 1800); }};
      tools.hidden = false;
      document.getElementById("copy-subject").onclick = (e) =>
        navigator.clipboard.writeText(document.getElementById("send-subject").textContent)
          .then(() => flash(e.target, "Copied"), () => flash(e.target, "Couldn't copy"));
      document.getElementById("copy-digest").onclick = (e) => {{
        const el = document.getElementById("digest");
        navigator.clipboard.write([new ClipboardItem({{
          "text/html": new Blob([el.innerHTML], {{ type: "text/html" }}),
          "text/plain": new Blob([el.innerText], {{ type: "text/plain" }}),
        }})]).then(() => flash(e.target, "Copied"), () => flash(e.target, "Couldn't copy"));
      }};
    }}
  </script>
</body>
</html>
"""


def feed(body, title, end):
    stamp = format_datetime(datetime(end.year, end.month, end.day, 12))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Congress Report Card weekly digest</title>
<link>{SITE_URL}/digest/</link>
<description>Missed votes, grade changes and bills that became law, every Saturday.</description>
<item>
<title>{escape(title)}</title>
<link>{SITE_URL}/digest/</link>
<guid isPermaLink="false">digest-{end.isoformat()}</guid>
<pubDate>{stamp}</pubDate>
<description><![CDATA[{body}]]></description>
</item>
</channel>
</rss>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="build a digest now, whatever the day")
    ap.add_argument("--init-from", metavar="MEMBERS_JS", help="start the snapshot from an older members.js")
    args = ap.parse_args()

    if args.init_from:
        from pathlib import Path
        old = slim(load_members_js(Path(args.init_from)))
        write(SNAPSHOT, json.dumps(old, separators=(",", ":")) + "\n")
        print(f"Snapshot set to the data from {old['generated']}")
        return

    data = load_members_js(DATA_FILE)
    today = day(data["generated"])
    if not SNAPSHOT.exists():
        write(SNAPSHOT, json.dumps(slim(data), separators=(",", ":")) + "\n")
        print("No earlier snapshot to compare with; saved one for next week's digest.")
        return

    prev = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    last = day(prev["generated"])
    age = (today - last).days
    due = (today.weekday() == DIGEST_WEEKDAY and age > 0) or age > 7
    if not (due or args.force):
        print(f"No digest today (last one {last}; the next is due on Saturday).")
        return

    cur = slim(data)
    # Titles and links for new laws come from the full data, not the slimmed copy.
    full = {m["id"]: m for m in data["members"]}
    compute_grades(cur["members"])
    compute_grades(prev["members"])
    for m in cur["members"]:
        if m["bills"]:
            m["bills"]["notable"] = full[m["id"]]["bills"]["notable"]
    facts = compare(cur["members"], prev["members"])

    title = f"Week ending {long_date(today)}"
    body = digest_body(facts, last, today)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write(OUT_DIR / "index.html", digest_page(body, title, today))
    write(OUT_DIR / "feed.xml", feed(body, title, today))
    write(SNAPSHOT, json.dumps(slim(data), separators=(",", ":")) + "\n")
    print(f"Wrote the digest for {last} to {today}: {facts['rolls']['House']} House and "
          f"{facts['rolls']['Senate']} Senate roll calls, {len(facts['laws'])} new laws, "
          f"{facts['changed']} grade changes")


if __name__ == "__main__":
    main()
