"""
Builds the static pages that are generated from site/data/members.js:

  site/members/<id>.html   one page per member (name, district and grade in the title)
  site/badges/<id>.svg     embeddable grade badge
  site/sitemap.xml         for search engines
  site/ads.txt             tells ad buyers that Google may sell this site's ad space

These files are not committed. The deploy workflows run this script just before publishing,
so the pages always match the nightly data. Run it by hand to preview the site locally:

  python build_pages.py

The grading below must stay in step with GRADING in site/app.js, which grades the same
data in the browser. tests/congress-report-card.spec.js checks that the two agree.
"""
import json
import shutil
from html import escape

from build_data import OUT as DATA_FILE, ROOT

SITE = ROOT / "site"
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


# ---------------------------------------------------------------- HTML

def footer(prefix=""):
    return f"""<footer class="site-footer">
    <div class="wrap">
      <nav aria-label="Site">
        <a href="{prefix or './'}">All members</a>
        <a href="{prefix}digest/">Weekly digest</a>
        <a href="{prefix}methodology.html">Methodology</a>
        <a href="{prefix}privacy.html">Privacy policy</a>
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


def member_page(m, data):
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
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="profile">
  <meta property="og:site_name" content="Congress Report Card">
  <meta property="og:title" content="{e(m['name'])} ({party}, {district(m)}): Grade {m['grade']}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{url}">
  <link rel="stylesheet" href="../styles.css">
  {ADSENSE_SNIPPET}
</head>
<body>
  <header class="masthead slim">
    <div class="wrap"><a class="home" href="../">Congress Report Card</a></div>
  </header>

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

      <div class="ad-slot" data-ad="member"></div>

      <section class="share" id="share" data-card="{e(json.dumps(card))}">
        <h2>Share this grade</h2>
        <img class="share-preview" id="share-preview" alt="Image card showing the grade for {e(m['name'])}" hidden>
        <div class="buttons">
          <button id="share-native" hidden>Share…</button>
          <button id="share-download">Download image</button>
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


def sitemap(members, generated):
    day = generated[:10]
    paths = ["", "digest/", "methodology.html", "privacy.html", "contact.html"] + [f"members/{m['id']}.html" for m in members]
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

    for name in ("members", "badges"):  # start clean so departed members don't linger
        shutil.rmtree(SITE / name, ignore_errors=True)
        (SITE / name).mkdir()
    for m in members:
        write(SITE / "members" / f"{m['id']}.html", member_page(m, data))
        write(SITE / "badges" / f"{m['id']}.svg", badge_svg(m))
    write(SITE / "sitemap.xml", sitemap(members, data["generated"]))
    print(f"Wrote {len(members)} member pages, {len(members)} badges and sitemap.xml")

    write(SITE / "ads.txt", f"google.com, {ADSENSE_PUBLISHER}, DIRECT, f08c47fec0942fa0\n")
    print("Wrote ads.txt")


if __name__ == "__main__":
    main()
