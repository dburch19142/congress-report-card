"""
Builds the static pages that are generated from site/data/members.js:

  site/members/<id>.html   one page per member (name, district and grade in the title)
  site/badges/<id>.svg     embeddable grade badge
  site/states/             one page per state delegation, plus a ranking of all states
  site/articles/           the articles in articles/, wrapped in the site's header and footer
  site/sitemap.xml         for search engines
  site/ads.txt             tells ad buyers that Google may sell this site's ad space

These files are not committed. The deploy workflows run this script just before publishing,
so the pages always match the nightly data. Run it by hand to preview the site locally:

  python build_pages.py

The grading below must stay in step with GRADING in site/app.js, which grades the same
data in the browser. tests/congress-report-card.spec.js checks that the two agree.
"""
import copy
import json
import re
import shutil
import statistics
from datetime import date
from html import escape

from build_data import OUT as DATA_FILE, ROOT

SITE = ROOT / "site"
ARTICLES = ROOT / "articles"
SNAPSHOT = ROOT / "digest_snapshot.json"
SITE_URL = "https://congressreportcard.org"

# Google AdSense. The same snippet is in the <head> of the hand-written pages in site/.
ADSENSE_PUBLISHER = "pub-7873162278456307"
ADSENSE_SNIPPET = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                   f'?client=ca-{ADSENSE_PUBLISHER}"\n     crossorigin="anonymous"></script>')

# ---------------------------------------------------------------- grading (mirrors app.js)
GRADING = {
    "weights": {"attendance": 40, "sponsored": 35, "cosponsored": 25},
    "attendanceFloor": 0.85,
    "stagePoints": {"introduced": 1, "committee": 3, "passed": 6, "law": 10},
    "letters": [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"),
                (73, "C"), (70, "C-"), (67, "D+"), (63, "D"), (60, "D-"), (0, "F")],
    "partialTerm": 0.5,
    "percentileFloor": 50,
}
LABELS = {"attendance": "Vote attendance", "sponsored": "Bills written", "cosponsored": "Bills supported"}
PARTY = {"Democrat": "D", "Republican": "R", "Independent": "I"}
STAGE_NAMES = {"introduced": "Introduced", "committee": "Committee action",
               "passed": "Passed a chamber", "law": "Became law"}
GRADE_COLORS = {"A": "#1d7a4b", "B": "#4f8a2c", "C": "#b58a12", "D": "#c4631c", "F": "#b3372f"}
DELEGATE_STATES = {"DC", "PR", "GU", "AS", "VI", "MP"}
SPEAKER_ID = "J000299"
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AS": "American Samoa", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "GU": "Guam", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "MP": "Northern Mariana Islands", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VI": "U.S. Virgin Islands", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def clamp(x):
    return max(0, min(100, x))


def letter_of(score):
    return next(l for low, l in GRADING["letters"] if score >= low)


def legislative_points(bills):
    return sum(n * GRADING["stagePoints"][k] for k, n in bills["stages"].items())


def percentile_scorer(members, get_value):
    """Percentile rank within chamber (ties share the midpoint), 0-100."""
    by_chamber = {}
    for m in members:
        v = get_value(m)
        if v is not None:
            by_chamber.setdefault(m["chamber"], []).append(v)

    def score(m):
        v, values = get_value(m), by_chamber.get(m["chamber"])
        if v is None or not values or len(values) < 2:
            return None
        below = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
        return clamp(((below + (equal - 1) / 2) / (len(values) - 1)) * 100)
    return score


def from_percentile(p):
    floor = GRADING["percentileFloor"]
    return None if p is None else floor + (p * (100 - floor)) / 100


def compute_grades(members):
    weights = GRADING["weights"]
    sponsor = percentile_scorer(members, lambda m: legislative_points(m["bills"]) if m["bills"] else None)
    cosponsor = percentile_scorer(members, lambda m: m["bills"]["cosponsored"] if m["bills"] else None)
    for m in members:
        v = m["votes"]
        m["attendance"] = 1 - v["missed"] / v["eligible"] if v["eligible"] else None
        m["pctl"] = {"sponsored": sponsor(m), "cosponsored": cosponsor(m)}
        m["delegate"] = m["chamber"] == "House" and m["state"] in DELEGATE_STATES
        m["partial"] = not m["delegate"] and v["eligible"] < v["chamberTotal"] * GRADING["partialTerm"]
        floor = GRADING["attendanceFloor"]
        m["scores"] = {
            "attendance": None if m["attendance"] is None
            else clamp(((m["attendance"] - floor) / (1 - floor)) * 100),
            "sponsored": from_percentile(m["pctl"]["sponsored"]),
            "cosponsored": from_percentile(m["pctl"]["cosponsored"]),
        }
        total = w = 0
        for k, s in m["scores"].items():
            if s is not None and weights[k] > 0:
                total += s * weights[k]
                w += weights[k]
        m["score"] = total / w if w else None
        m["grade"] = "—" if m["score"] is None else letter_of(m["score"])


# ---------------------------------------------------------------- wording

def pct(x):
    return f"{x * 100:.1f}%"


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def count_of(n):
    return "none" if n == 0 else str(n)


def more_than(p, peers):
    """Turns a chamber percentile into words, e.g. 'more than 64% of senators'."""
    p = round(p or 0)
    if p >= 100:
        return f"more than any other {peers[:-1]}"
    if p <= 0:
        return f"less than nearly all other {peers}"
    return f"more than {p}% of {peers}"


def seat(m):
    """Short seat label, the same as on the home page."""
    if m["chamber"] == "Senate":
        return f"Senator · {m['state']}"
    if m["state"] in DELEGATE_STATES:
        return f"Delegate · {m['state']}"
    return f"Rep. · {m['state']} At-large" if not m["district"] else f"Rep. · {m['state']}-{m['district']}"


def district(m):
    """District for the page title: OH-3, AK At-large, or just the state."""
    if m["chamber"] == "Senate" or m["state"] in DELEGATE_STATES:
        return m["state"]
    return f"{m['state']} At-large" if not m["district"] else f"{m['state']}-{m['district']}"


def role(m):
    state = STATES.get(m["state"], m["state"])
    the = "the " if state.startswith(("District", "Northern", "U.S.")) else ""
    party = {"Democrat": "a Democrat", "Republican": "a Republican"}.get(m["party"], "an independent")
    if m["chamber"] == "Senate":
        return f"{party}, is a U.S. senator from {the}{state}"
    if m["delegate"]:
        return f"{party}, is the non-voting House delegate from {the}{state}"
    if not m["district"]:
        return f"{party}, represents {state}'s at-large congressional district in the U.S. House"
    return f"{party}, represents {state}'s {ordinal(m['district'])} congressional district in the U.S. House"


def summary(m, congress):
    peers = "senators" if m["chamber"] == "Senate" else "representatives"
    v, b, last = m["votes"], m["bills"], m["last"]
    out = [f"{m['name']}, {role(m)}."]
    if m["score"] is None:
        out.append(f"There is not enough data to grade {last} in the {ordinal(congress)} Congress yet.")
    else:
        out.append(f"{last} earns an overall grade of {m['grade']} ({m['score']:.0f} out of 100) "
                   f"for the {ordinal(congress)} Congress.")
    if v["eligible"]:
        out.append(f"{last} voted on {v['eligible'] - v['missed']:,} of {v['eligible']:,} roll calls "
                   f"({pct(m['attendance'])}) and missed {v['missed']:,}.")
    else:
        out.append(f"{last} has no recorded roll-call votes this Congress.")
    if b:
        advanced = b["sponsored"] - b["stages"]["introduced"]
        out.append(f"{last} sponsored {plural(b['sponsored'], 'bill')} and joint resolutions, "
                   f"{count_of(advanced)} of which moved past introduction and "
                   f"{count_of(b['stages']['law'])} of which became law. "
                   f"That is {more_than(m['pctl']['sponsored'], peers)} when bills are weighted by how far they got.")
        out.append(f"{last} also cosponsored {b['cosponsored']:,} bill{'' if b['cosponsored'] == 1 else 's'}, "
                   f"{more_than(m['pctl']['cosponsored'], peers)}.")
    if m["partial"]:
        out.append(f"{last} joined partway through this Congress, so the bill counts cover less time "
                   f"than they do for most members.")
    return " ".join(out)


# ---------------------------------------------------------------- comparisons

def graded(members):
    return [m for m in members if m["score"] is not None]


def a_grade(g):
    """'a B', 'an A-', 'an F'."""
    return f"{'an' if g[0] in 'AF' else 'a'} {g}"


def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def state_name(code):
    name = STATES.get(code, code)
    return f"the {name}" if name.startswith(("District", "Northern", "U.S.")) else name


def possessive(name):
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def build_context(members, snapshot=None):
    """Rankings, medians and last week's grades that the member and state pages compare against."""
    ctx = {"chamber": {}, "party": {}, "state": {}, "median": {}, "previous": {}, "snapshot_date": None}
    for chamber in ("House", "Senate"):
        ms = sorted(graded(m for m in members if m["chamber"] == chamber), key=lambda m: -m["score"])
        ctx["chamber"][chamber] = ms
        # Full-term voting members set the "typical member" figures.
        full = [m for m in ms if not m["partial"] and not m["delegate"]]
        ctx["median"][chamber] = {
            "attendance": statistics.median(m["attendance"] for m in full),
            "missed": statistics.median(m["votes"]["missed"] for m in full),
            "sponsored": statistics.median(m["bills"]["sponsored"] for m in full if m["bills"]),
            "cosponsored": statistics.median(m["bills"]["cosponsored"] for m in full if m["bills"]),
            "score": statistics.median(m["score"] for m in ms),
        }
        for m in ms:
            ctx["party"].setdefault((chamber, m["party"]), []).append(m)
    for m in sorted(graded(members), key=lambda m: -m["score"]):
        ctx["state"].setdefault(m["state"], []).append(m)
    if snapshot:
        old = copy.deepcopy(snapshot["members"])
        compute_grades(old)
        ctx["previous"] = {m["id"]: m for m in old}
        ctx["snapshot_date"] = snapshot["generated"][:10]
    return ctx


def long_date(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d:%B} {d.day}, {d.year}"


def comparison(m, ctx):
    """A few paragraphs, as HTML, on how a member compares with their chamber, party and state."""
    if m["score"] is None:
        return []
    e = escape
    last, chamber = e(m["last"]), m["chamber"]
    peers = "senators" if chamber == "Senate" else "House members"
    peer = "senator" if chamber == "Senate" else "House member"
    out = []

    ranked = ctx["chamber"][chamber]
    rank = ranked.index(m) + 1
    top = round(rank / len(ranked) * 100)
    party = ctx["party"][(chamber, m["party"])]
    party_word = {"Democrat": "Democrats", "Republican": "Republicans"}.get(m["party"], "independents")
    text = (f"{possessive(last)} overall score of {m['score']:.0f} ranks {ordinal(rank)} of {len(ranked)} {peers}"
            f"{f', in the top {max(top, 1)}%' if top <= 50 else ''}.")
    if len(party) > 1:
        text += f" Among the {len(party)} {party_word} in the {chamber}, {last} ranks {ordinal(party.index(m) + 1)}."
    text += f" The median score in the {chamber} is {ctx['median'][chamber]['score']:.0f}."
    if m["delegate"]:
        text += (" Delegates are ranked with the rest of the House, but they are eligible for far fewer votes, "
                 "so each missed vote moves their attendance score more.")
    out.append(text)

    delegation = ctx["state"].get(m["state"], [])
    if len(delegation) > 1:
        avg = statistics.mean(x["score"] for x in delegation)
        senators = sum(1 for x in delegation if x["chamber"] == "Senate")
        reps = len(delegation) - senators
        parts = [plural(senators, "senator")] if senators else []
        parts += [plural(reps, "representative")] if reps else []
        text = (f"{state_name(m['state'])} has {len(delegation)} members of Congress ({' and '.join(parts)}). "
                f"Their average score is {avg:.0f}, {a_grade(letter_of(avg))}. "
                f"{last} has the {ordinal(delegation.index(m) + 1)}-highest score in the delegation")
        best = delegation[0]
        text += ("." if best is m else
                 f"; the highest is {e(best['name'])}, with {a_grade(best['grade'])}.")
        text += f' <a href="../states/{m["state"].lower()}.html">See the whole delegation</a>.'
        out.append(text)

    med, v = ctx["median"][chamber], m["votes"]
    if v["eligible"]:
        diff = m["attendance"] - med["attendance"]
        how = ("about the same as" if abs(diff) < 0.0025 else
               f"{abs(diff) * 100:.1f} points {'above' if diff > 0 else 'below'}")
        text = (f"{last} voted on {pct(m['attendance'])} of the roll calls they were eligible for, {how} "
                f"the typical {peer} ({pct(med['attendance'])}).")
        if v["missed"] == 0:
            text += f" {last} has not missed a roll-call vote this Congress."
        out.append(text)

    b = m["bills"]
    if b:
        text = (f"{last} sponsored {plural(b['sponsored'], 'bill')} and cosponsored {b['cosponsored']:,}; "
                f"the typical {peer} sponsored {med['sponsored']:.0f} and cosponsored {med['cosponsored']:.0f}.")
        law = b["stages"]["law"]
        if law:
            text += f" Of {possessive(last)} bills, {law} became law."
        elif b["stages"]["passed"]:
            text += f" None has become law yet, but {count_of(b['stages']['passed'])} passed at least one chamber."
        if m["partial"]:
            text += f" {last} took office on {long_date(m['termStart'])}, so these totals cover a shorter period."
        out.append(text)

    old = ctx["previous"].get(m["id"])
    if old and old["score"] is not None:
        when = long_date(ctx["snapshot_date"])
        new_votes = v["eligible"] - old["votes"]["eligible"]
        new_missed = v["missed"] - old["votes"]["missed"]
        if old["grade"] == m["grade"]:
            text = f"{possessive(last)} grade is unchanged since the weekly digest of {when}."
        else:
            text = f"{possessive(last)} grade has moved from {old['grade']} to {m['grade']} since the weekly digest of {when}."
        if new_votes > 0:
            text += (f" Since then {last} has voted on {new_votes - new_missed} of {plural(new_votes, 'roll call')}.")
        out.append(text)
    return out


# ---------------------------------------------------------------- HTML

def site_header(prefix=""):
    """The slim header with the main menu. The home page has the same menu in its own header."""
    return f"""<header class="masthead slim">
    <div class="wrap bar">
      <a class="home" href="{prefix or './'}">Congress Report Card</a>
      <nav class="topnav" aria-label="Main">
        <a href="{prefix or './'}">Members</a>
        <a href="{prefix}states/">States</a>
        <a href="{prefix}articles/">Articles</a>
        <a href="{prefix}methodology.html">Methodology</a>
        <a href="{prefix}about.html">About</a>
      </nav>
    </div>
  </header>"""


def footer(prefix=""):
    return f"""<footer class="site-footer">
    <div class="wrap">
      <nav aria-label="Site">
        <a href="{prefix or './'}">All members</a>
        <a href="{prefix}states/">States</a>
        <a href="{prefix}articles/">Articles</a>
        <a href="{prefix}digest/">Weekly digest</a>
        <a href="{prefix}methodology.html">Methodology</a>
        <a href="{prefix}about.html">About</a>
        <a href="{prefix}privacy.html">Privacy policy</a>
        <a href="{prefix}terms.html">Terms</a>
        <a href="{prefix}contact.html">Contact</a>
      </nav>
      <p>Congress Report Card is an independent project. It is not affiliated with Congress, any party or any campaign.</p>
    </div>
  </footer>"""


def subject(k, m, detail, extra=""):
    s = m["scores"][k]
    l = "—" if s is None else letter_of(s)
    return f"""<div class="subject g-{l[0]}">
        <h3>{LABELS[k]} <span class="tag">{GRADING['weights'][k]}% of grade</span></h3>
        <span class="sg">{l}</span>
        <div class="meter"><span style="width:{s or 0:.1f}%"></span></div>
        <div class="detail">{detail}</div>{extra}</div>"""


def member_page(m, data, ctx):
    e = escape
    congress = data["congress"]
    v, b = m["votes"], m["bills"]
    peers = "senators" if m["chamber"] == "Senate" else "representatives"
    party = PARTY.get(m["party"], "I")
    url = f"{SITE_URL}/members/{m['id']}.html"
    badge = f"{SITE_URL}/badges/{m['id']}.svg"
    photo = f"https://unitedstates.github.io/images/congress/225x275/{m['id']}.jpg"
    title = f"{m['name']} ({party}, {district(m)}): Grade {m['grade']} | Congress Report Card"
    text = summary(m, congress)
    compare = "".join(f"<p>{p}</p>" for p in comparison(m, ctx))
    robots = '\n  <meta name="robots" content="noindex">' if m["score"] is None else ""
    description = (f"{m['name']} ({party}, {district(m)}) gets a grade of {m['grade']} for the "
                   f"{ordinal(congress)} Congress, based on vote attendance, bills written and bills supported.")

    attendance = (f"Voted on {v['eligible'] - v['missed']} of {v['eligible']} roll calls "
                  f"({pct(m['attendance'])}); missed {v['missed']}."
                  if v["eligible"] else "No roll-call votes recorded this Congress.")
    if m["id"] == SPEAKER_ID:
        attendance += (" By custom the Speaker votes only occasionally; votes skipped as Speaker "
                       "are not counted against them.")
    if m["delegate"]:
        attendance += (" Delegates may vote only in the Committee of the Whole, so they are "
                       "eligible for fewer roll calls.")
    no_bills = "Bill data is not available for this member yet."
    if b:
        sponsored = (f"Sponsored {plural(b['sponsored'], 'bill')} and joint resolutions. Legislative "
                     f"progress: {more_than(m['pctl']['sponsored'], peers)}.")
        if b["resolutions"]:
            sponsored += f" (Also {plural(b['resolutions'], 'simple resolution')}, not graded.)"
        stages = '<div class="stages">' + "".join(
            f"<div><b>{b['stages'][k]}</b>{n}</div>" for k, n in STAGE_NAMES.items()) + "</div>"
        cosponsored = (f"Cosponsored {plural(b['cosponsored'], 'bill')}, "
                       f"{more_than(m['pctl']['cosponsored'], peers)}.")
        notable = "".join(
            f'<li><span class="tag">{STAGE_NAMES[n["stage"]]}</span>'
            f'<a href="{e(n["url"])}" target="_blank" rel="noopener">{e(n["id"])}: {e(n["title"])}</a></li>'
            for n in b["notable"])
    else:
        sponsored, stages, cosponsored, notable = no_bills, "", no_bills, ""

    # Everything share.js needs to draw the image card.
    card = {
        "id": m["id"], "name": m["name"], "party": m["party"], "seat": seat(m), "grade": m["grade"],
        "congress": f"{ordinal(congress)} Congress", "url": url, "photo": photo,
        "scores": [{"label": LABELS[k], "score": s, "letter": "—" if s is None else letter_of(s)}
                   for k, s in m["scores"].items()],
    }
    share_text = f"{m['name']} gets a grade of {m['grade']} on Congress Report Card"
    embed = (f'<a href="{url}"><img src="{badge}" alt="{e(m["name"])}: grade {m["grade"]} on '
             f'Congress Report Card" height="28"></a>')

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <link rel="canonical" href="{url}">{robots}
  <meta property="og:type" content="profile">
  <meta property="og:site_name" content="Congress Report Card">
  <meta property="og:title" content="{e(m['name'])} ({party}, {district(m)}): Grade {m['grade']}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{url}">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link rel="icon" href="../favicon.png" type="image/png" sizes="64x64">
  <link rel="apple-touch-icon" href="../apple-touch-icon.png">
  <link rel="stylesheet" href="../styles.css">
  {ADSENSE_SNIPPET}
</head>
<body>
  {site_header("../")}

  <main class="wrap page">
    <article class="profile" data-id="{m['id']}">
      <div class="card-head">
        <img src="{photo}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{{className:'photo-fallback'}}))">
        <div>
          <h1 id="member-name">{e(m['name'])}</h1>
          <div class="meta"><span class="party-{party}">{e(m['party'])}</span> · {seat(m)}</div>
          <div class="meta">{STATES.get(m['state'], m['state'])} · {ordinal(congress)} Congress{' · <span class="tag">Partial term</span>' if m['partial'] else ''}</div>
        </div>
        <div class="grade g-{m['grade'][0]}" aria-label="Overall grade {m['grade']}">{m['grade']}</div>
      </div>

      <p class="summary-text">{e(text)}</p>

      <div class="subjects">
        {subject("attendance", m, attendance)}
        {subject("sponsored", m, sponsored, stages)}
        {subject("cosponsored", m, cosponsored)}
      </div>
      {f'<div class="advanced"><h4>Bills that advanced</h4><ul class="notable">{notable}</ul></div>' if notable else ''}
      {f'<section class="compare"><h2>How {e(m["last"])} compares</h2>{compare}</section>' if compare else ''}

      <div class="ad-slot" data-ad="member"></div>

      <section class="share" id="share" data-card="{e(json.dumps(card))}">
        <h2>Share this grade</h2>
        <img class="share-preview" id="share-preview" alt="Image card showing the grade for {e(m['name'])}" hidden>
        <div class="buttons">
          <button id="share-native" hidden>Share…</button>
          <button id="share-download">Download image</button>
          <button id="share-download-tall">Download tall image for TikTok</button>
          <button id="share-copy">Copy link</button>
          <a class="button" href="https://twitter.com/intent/tweet?text={e(share_text.replace(' ', '%20'))}&amp;url={url}" target="_blank" rel="noopener">Post on X ↗</a>
          <a class="button" href="https://www.facebook.com/sharer/sharer.php?u={url}" target="_blank" rel="noopener">Share on Facebook ↗</a>
        </div>
      </section>

      <section class="embed">
        <h2>Add this grade to your site</h2>
        <p>Paste this code into any web page. The badge updates on its own when the grade changes.</p>
        <p><img src="../badges/{m['id']}.svg" alt="{e(m['name'])}: grade {m['grade']} on Congress Report Card" height="28"></p>
        <textarea id="embed-code" readonly rows="3" aria-label="Badge embed code">{e(embed)}</textarea>
        <button id="embed-copy">Copy code</button>
      </section>

      <div class="card-links">
        <a href="../">Compare with all members</a>
        <a href="https://www.congress.gov/member/{m['id']}" target="_blank" rel="noopener">Full record on Congress.gov ↗</a>
        {f'<a href="{e(m["url"])}" target="_blank" rel="noopener">Official website ↗</a>' if m.get('url') else ''}
      </div>
      <p class="fineprint">Updated {e(data['generated'])}. This page uses the standard grading weights. <a href="../methodology.html">How grades are calculated</a>.</p>
    </article>
  </main>

  {footer("../")}
  <script src="../ads.js"></script>
  <script src="../analytics.js"></script>
  <script src="../share.js"></script>
</body>
</html>
"""


def badge_svg(m):
    color = GRADE_COLORS.get(m["grade"][0], "#5d6470")
    label = f"{escape(m['name'])}: grade {m['grade']} on Congress Report Card"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="196" height="28" role="img" aria-label="{label}">
<title>{label}</title>
<rect width="196" height="28" rx="5" fill="#1f3a5f"/>
<rect x="150" width="46" height="28" rx="5" fill="{color}"/>
<rect x="150" width="8" height="28" fill="{color}"/>
<text x="75" y="18.5" fill="#fff" font-family="Verdana,Segoe UI,sans-serif" font-size="11.5" text-anchor="middle">Congress Report Card</text>
<text x="173" y="19.5" fill="#fff" font-family="Georgia,serif" font-weight="700" font-size="15" text-anchor="middle">{m['grade']}</text>
</svg>
"""


def page_shell(prefix, path, title, description, body, ad=True, robots=""):
    """A generated text page (state, article) in the site's header and footer."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Congress Report Card</title>
  <meta name="description" content="{escape(description)}">
  <link rel="canonical" href="{SITE_URL}/{path}">{robots}
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Congress Report Card">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{SITE_URL}/{path}">
  <link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{prefix}favicon.png" type="image/png" sizes="64x64">
  <link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">
  <link rel="stylesheet" href="{prefix}styles.css">
  {ADSENSE_SNIPPET}
</head>
<body>
  {site_header(prefix)}

  <main class="wrap page prose">
    {body}
    {'<div class="ad-slot" data-ad="page"></div>' if ad else ''}
  </main>

  {footer(prefix)}
  <script src="{prefix}ads.js"></script>
  <script src="{prefix}analytics.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------- state pages

def state_codes(ctx):
    """States with a delegation worth a page: every state, not DC or the territories (one delegate each)."""
    return sorted((c for c in ctx["state"] if c not in DELEGATE_STATES), key=lambda c: STATES[c])


def state_ranking(ctx):
    rows = [(statistics.mean(m["score"] for m in ctx["state"][c]), c) for c in state_codes(ctx)]
    return [c for _, c in sorted(rows, reverse=True)]


def member_row(m, prefix):
    v, b = m["votes"], m["bills"]
    where = "Senate" if m["chamber"] == "Senate" else f"House, {district(m)}"
    return (f'<tr><td><a href="{prefix}members/{m["id"]}.html">{escape(m["name"])}</a></td>'
            f'<td>{where}</td>'
            f'<td class="party-{PARTY.get(m["party"], "I")}">{PARTY.get(m["party"], "I")}</td>'
            f'<td class="g-{m["grade"][0]}"><b>{m["grade"]}</b></td>'
            f'<td>{pct(m["attendance"]) if v["eligible"] else "—"}</td>'
            f'<td>{b["sponsored"] if b else "—"}</td><td>{b["stages"]["law"] if b else "—"}</td>'
            f'<td>{b["cosponsored"] if b else "—"}</td></tr>')


MEMBER_TABLE_HEAD = ('<thead><tr><th>Member</th><th>Seat</th><th>Party</th><th>Grade</th><th>Attendance</th>'
                     '<th>Bills</th><th>Laws</th><th>Cosponsored</th></tr></thead>')


def state_page(code, ctx, data):
    ms = ctx["state"][code]
    name = STATES[code]
    ranking = state_ranking(ctx)
    rank = ranking.index(code) + 1
    avg = statistics.mean(m["score"] for m in ms)
    national = statistics.mean(m["score"] for c in ("House", "Senate") for m in ctx["chamber"][c])
    senators = [m for m in ms if m["chamber"] == "Senate"]
    reps = [m for m in ms if m["chamber"] == "House"]
    words = {"Democrat": "Democrat", "Republican": "Republican", "Independent": "independent"}
    split = and_list(plural(n, words[p]) for p in words
                     for n in [sum(1 for m in ms if m["party"] == p)] if n)
    missed = sum(m["votes"]["missed"] for m in ms)
    eligible = sum(m["votes"]["eligible"] for m in ms)
    sponsored = sum(m["bills"]["sponsored"] for m in ms if m["bills"])
    laws = sum(m["bills"]["stages"]["law"] for m in ms if m["bills"])
    passed = sum(m["bills"]["stages"]["passed"] for m in ms if m["bills"])
    best, worst = ms[0], ms[-1]
    congress = ordinal(data["congress"])
    seats = [plural(len(senators), "senator")] if senators else []
    seats += [plural(len(reps), "representative")] if reps else []
    e = escape

    paras = [
        f"{name} sends {len(ms)} members to the {congress} Congress: {' and '.join(seats)}. "
        f"The delegation is made up of {split}.",
        f"The delegation's average score is {avg:.0f} out of 100, {a_grade(letter_of(avg))}. That ranks {name} "
        f"{ordinal(rank)} of the {len(ranking)} states, and it is "
        f"{'above' if avg > national + 0.5 else 'below' if avg < national - 0.5 else 'about the same as'} "
        f"the national average of {national:.0f}.",
        f"Together the delegation was eligible for {eligible:,} roll-call votes and missed {missed:,}, "
        f"an attendance rate of {pct(1 - missed / eligible)}. Its members sponsored {sponsored:,} bills and joint "
        f"resolutions. Of those, {count_of(laws)} became law and {count_of(passed)} more passed at "
        f"least one chamber.",
    ]
    if len(ms) > 1:
        paras.append(f'The highest score in the delegation belongs to <a href="../members/{best["id"]}.html">'
                     f'{e(best["name"])}</a> ({best["grade"]}, {best["score"]:.0f}). The lowest belongs to '
                     f'<a href="../members/{worst["id"]}.html">{e(worst["name"])}</a> '
                     f'({worst["grade"]}, {worst["score"]:.0f}).')
    if senators and reps:
        s_avg = statistics.mean(m["score"] for m in senators)
        r_avg = statistics.mean(m["score"] for m in reps)
        paras.append(f"{possessive(name)} senators average {s_avg:.0f} and its House members average {r_avg:.0f}. "
                     f"Senators are ranked only against other senators and representatives only against "
                     f"other representatives, so each number measures that group against its own chamber.")
    flagged = [m for m in ms if m["partial"]]
    if flagged:
        paras.append(f"{' and '.join(e(m['name']) for m in flagged)} took office partway through this Congress, "
                     f"so {'their grades cover' if len(flagged) > 1 else 'that grade covers'} a shorter record.")

    rows = "".join(member_row(m, "../") for m in ms)
    body = f"""<p class="eyebrow">State delegation · {congress} Congress</p>
    <h1>{name}</h1>
    {"".join(f"<p>{p}</p>" for p in paras)}
    <h2>Every member from {name}</h2>
    <div class="table-scroll"><table class="members-table">{MEMBER_TABLE_HEAD}<tbody>{rows}</tbody></table></div>
    <p class="fineprint">Members are listed from highest to lowest score. "Bills" counts bills and joint resolutions
    sponsored; "Laws" counts how many of those became law. Updated {e(data['generated'])}.
    <a href="../methodology.html">How grades are calculated</a> · <a href="./">All states</a></p>"""
    desc = (f"Report card for {possessive(name)} {len(ms)} members of Congress: grades, vote attendance and "
            f"bills for each senator and representative in the {congress} Congress.")
    return page_shell("../", f"states/{code.lower()}.html", f"{name} congressional delegation report card", desc, body)


def states_index(ctx, data):
    rows = []
    for i, c in enumerate(state_ranking(ctx), 1):
        ms = ctx["state"][c]
        a = statistics.mean(m["score"] for m in ms)
        att = 1 - sum(m["votes"]["missed"] for m in ms) / sum(m["votes"]["eligible"] for m in ms)
        rows.append(f'<tr><td>{i}</td><td><a href="{c.lower()}.html">{STATES[c]}</a></td><td>{len(ms)}</td>'
                    f'<td class="g-{letter_of(a)[0]}"><b>{letter_of(a)}</b></td><td>{a:.1f}</td><td>{pct(att)}</td></tr>')
    others = [m for c in sorted(ctx["state"]) if c in DELEGATE_STATES for m in ctx["state"][c]]
    other_list = "".join(f'<li><a href="../members/{m["id"]}.html">{escape(m["name"])}</a>, '
                         f'{state_name(m["state"])} ({m["grade"]})</li>' for m in others)
    body = f"""<p class="eyebrow">{ordinal(data['congress'])} Congress</p>
    <h1>Report cards by state</h1>
    <p class="lede">Each state's senators and representatives, ranked by the average score of the whole delegation.</p>
    <p>A delegation's average is the plain average of its members' overall scores, so no single member counts for
    more than another. Small states have only three members, which means one strong or weak record moves their
    average much more than it would in California or Texas. Select a state to see every member, their grade, how
    many votes they missed and how many of their bills became law.</p>
    <div class="table-scroll"><table class="members-table"><thead><tr><th>Rank</th><th>State</th><th>Members</th>
    <th>Grade</th><th>Average</th><th>Attendance</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
    <h2>DC and the territories</h2>
    <p>The District of Columbia, Puerto Rico, Guam, American Samoa, the U.S. Virgin Islands and the Northern Mariana
    Islands each send one non-voting delegate to the House. They are not ranked with the states.</p>
    <ul>{other_list}</ul>
    <p class="fineprint">Updated {escape(data['generated'])}. <a href="../methodology.html">How grades are calculated</a>.</p>"""
    desc = "Every state's congressional delegation ranked by average report card grade, with links to each member."
    return page_shell("../", "states/", "Report cards by state", desc, body)


# ---------------------------------------------------------------- articles

def load_articles():
    """Each file in articles/ starts with a JSON header in an HTML comment, then the article body."""
    out = []
    for path in sorted(ARTICLES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"\s*<!--(.*?)-->\s*", text, re.S)
        meta = json.loads(match.group(1))
        meta["slug"] = path.stem
        meta["body"] = text[match.end():]
        out.append(meta)
    return sorted(out, key=lambda a: (a["date"], a.get("order", 0)), reverse=True)


def link_members(html, members, prefix="../"):
    """Turns [[Member Name]] into a link to that member's page, or plain text if they have left Congress."""
    ids = {m["name"]: m["id"] for m in members}

    def link(match):
        name = match.group(1)
        return f'<a href="{prefix}members/{ids[name]}.html">{escape(name)}</a>' if name in ids else escape(name)
    return re.sub(r"\[\[([^\]]+)\]\]", link, html)


def article_page(a, articles, members):
    others = [x for x in articles if x is not a][:4]
    more = "".join(f'<li><a href="{x["slug"]}.html">{escape(x["title"])}</a></li>' for x in others)
    body = f"""<article class="article">
      <p class="eyebrow">Analysis · {long_date(a['date'])}</p>
      <h1>{escape(a['title'])}</h1>
      <p class="lede">{escape(a['description'])}</p>
      {link_members(a['body'], members)}
      <p class="fineprint">Figures are from the Congress Report Card data as of {long_date(a['date'])}. Grades
      change as Congress votes, so the numbers on member pages may have moved since. <a href="../methodology.html">How
      grades are calculated</a>.</p>
    </article>
    <section class="more"><h2>More articles</h2><ul>{more}</ul></section>"""
    return page_shell("../", f"articles/{a['slug']}.html", a["title"], a["description"], body)


def articles_index(articles):
    items = "".join(f"""<li><a href="{a['slug']}.html">{escape(a['title'])}</a>
        <span class="date">{long_date(a['date'])}</span><p>{escape(a['description'])}</p></li>"""
                    for a in articles)
    body = f"""<h1>Articles</h1>
    <p class="lede">What the record of the current Congress shows: attendance, the bills that became law, how the
    chambers and parties compare, and how to read a report card.</p>
    <ul class="article-list">{items}</ul>"""
    desc = "Analysis of the current Congress from the Congress Report Card data: votes missed, laws passed and how members compare."
    return page_shell("../", "articles/", "Articles", desc, body, ad=False)


# ---------------------------------------------------------------- sitemap

STATIC_PAGES = ["", "digest/", "methodology.html", "about.html", "contact.html", "privacy.html", "terms.html"]


def sitemap(members, generated, states=(), articles=()):
    """Every page meant to be indexed. Members without a grade yet are left out (their pages are noindex)."""
    day = generated[:10]
    paths = (STATIC_PAGES + [f"members/{m['id']}.html" for m in graded(members)]
             + ["states/"] + [f"states/{c.lower()}.html" for c in states]
             + ["articles/"] + [f"articles/{a['slug']}.html" for a in articles])
    urls = "".join(f"<url><loc>{SITE_URL}/{p}</loc><lastmod>{day}</lastmod></url>\n" for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    raw = DATA_FILE.read_text(encoding="utf-8")
    data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    members = data["members"]
    compute_grades(members)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else None
    ctx = build_context(members, snapshot)

    for name in ("members", "badges", "states", "articles"):  # start clean so departed members don't linger
        shutil.rmtree(SITE / name, ignore_errors=True)
        (SITE / name).mkdir()
    for m in members:
        write(SITE / "members" / f"{m['id']}.html", member_page(m, data, ctx))
        write(SITE / "badges" / f"{m['id']}.svg", badge_svg(m))
    print(f"Wrote {len(members)} member pages and {len(members)} badges")

    states = state_codes(ctx)
    for code in states:
        write(SITE / "states" / f"{code.lower()}.html", state_page(code, ctx, data))
    write(SITE / "states" / "index.html", states_index(ctx, data))
    print(f"Wrote {len(states)} state pages")

    articles = load_articles()
    for a in articles:
        write(SITE / "articles" / f"{a['slug']}.html", article_page(a, articles, members))
    write(SITE / "articles" / "index.html", articles_index(articles))
    # The same list for the mobile app, newest first.
    write(SITE / "articles" / "articles.json", json.dumps([
        {"title": x["title"], "description": x["description"], "date": x["date"],
         "url": f"{SITE_URL}/articles/{x['slug']}.html"} for x in articles], indent=1) + "\n")
    print(f"Wrote {len(articles)} articles")

    write(SITE / "sitemap.xml", sitemap(members, data["generated"], states, articles))
    print("Wrote sitemap.xml")

    write(SITE / "ads.txt", f"google.com, {ADSENSE_PUBLISHER}, DIRECT, f08c47fec0942fa0\n")
    print("Wrote ads.txt")


if __name__ == "__main__":
    main()
