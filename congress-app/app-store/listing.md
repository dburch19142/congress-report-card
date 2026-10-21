# App Store listing

Everything App Store Connect asks for, ready to paste. Each field's limit is in brackets.
`check_listing.py` checks the lengths. Screenshots are in `screenshots/`; see "Screenshots"
below.

## App information

**Name** [30]

```
Congress Report Card
```

**Subtitle** [30]

```
Grades for every member
```

**Bundle ID:** `org.congressreportcard.congressReportCard`

**SKU** (any unique code, never shown to users)

```
congress-report-card-ios
```

**Primary category:** Reference
**Secondary category:** Education

**Content rights:** Yes, the app shows third-party content, and you have the rights to it. The
data is public government records (Voteview, Congress.gov, the Census Bureau), and the member
photos are official portraits in the public domain, from the unitedstates/images project.

## Version information

**Promotional text** [170] (can be changed at any time without a new version)

```
Every senator and representative, graded on the public record: votes attended, bills written, bills supported. Updated nightly. No account, no ads, no partisan scoring.
```

**Description** [4000]

```
How often does your member of Congress show up to vote? Do they write bills, and does any of it go anywhere? Congress Report Card answers those questions for every senator and representative, with a simple letter grade built only from the public record.

FIND YOUR MEMBERS
Search by name, state or ZIP code. A ZIP code search shows your House member and both of your senators, and tells you when a ZIP code crosses a district line.

SEE WHAT'S BEHIND EVERY GRADE
Each report card breaks the grade into three parts:
• Vote attendance (40%): the share of roll-call votes the member cast
• Bills written (35%): bills they sponsored, with more credit the further each one got, from introduction to becoming law
• Bills supported (25%): bills they cosponsored
You see the actual numbers behind each part, the bills that advanced, and links to the full record on Congress.gov.

COMPARE
See how a member ranks in their chamber, their party and their state's delegation, and how their attendance and bill numbers compare with the typical member. The States tab ranks every state's delegation by average score.

READ THE ANALYSIS
Articles explain what the record shows: who misses the most votes, every bill that became law, how the House and Senate compare, and how to read a report card. A weekly digest covers missed votes, grade changes and new laws.

GRADE YOUR WAY
Think attendance matters more, or cosponsoring less? Move the sliders and every grade updates instantly.

NONPARTISAN BY DESIGN
No vote is scored as right or wrong, and no issue position counts. Every member is graded by the same formula, and the method is published in full at congressreportcard.org.

ALWAYS CURRENT
The data comes from Voteview, Congress.gov and the Census Bureau, and is rebuilt every night, so the app always matches congressreportcard.org.

No account, no sign-up, no ads in the app, and nothing to set up. Congress Report Card is an independent project. It is not affiliated with Congress, any party or any campaign.
```

**Keywords** [100] (commas, no spaces after them; words already in the name aren't needed)

```
senator,representative,house,senate,vote,voting,attendance,bills,politics,civics,government,zip
```

**Support URL**

```
https://congressreportcard.org/contact.html
```

**Marketing URL**

```
https://congressreportcard.org/
```

**Privacy Policy URL**

```
https://congressreportcard.org/privacy.html
```

**Copyright**

```
2026 Darrell Burch
```

**What's New in This Version** [4000] (not shown for the first release; keep for 1.1)

```
• States: every state's delegation ranked by average score, with a page for each state
• Articles: the site's analysis of the current Congress, right in the app
• Each report card now shows how the member compares with their chamber, party and state
• Adjust grading, About, Privacy and Terms are now under More
```

## Age rating

Answer **None** or **No** to every question in the questionnaire: no violence, sexual content,
profanity, drugs, gambling, contests, horror, medical information, unrestricted web access or
user-generated content. The links open specific pages on congressreportcard.org and
Congress.gov, which isn't unrestricted web access. The result should be **4+**.

## App Privacy ("nutrition label")

Choose **Data Not Collected**. The app has no account, analytics, advertising or tracking code.
The grading weights are saved only on the device, and ZIP code searches run on the device
against a downloaded table.

One thing to know: articles and the site's own pages open in a Safari view inside the app, and
the website itself shows Google ads and counts visits (see the website's privacy policy). Apple
treats pages shown in a Safari view as web browsing, not data the app collects, so this doesn't
change the answer. If you add analytics or ads to the app itself later, update this section.

## Export compliance

Already answered in the app: `ITSAppUsesNonExemptEncryption` is `false` in
`ios/Runner/Info.plist`, because the app only uses standard HTTPS. App Store Connect won't ask on
each build.

## App Review information

**Sign-in required:** No.

**Notes for the reviewer**

```
Congress Report Card shows letter grades for every current member of the U.S. Congress, calculated from public records: roll-call votes from Voteview (UCLA) and legislation from the official Congress.gov API. The app reads the same nightly data files that congressreportcard.org publishes. No account is needed. To try the main features: search a ZIP code such as 18940 on the Members tab, tap a member to open their report card, then try the States and Articles tabs. The grades take no political position: a member's party and how they vote have no effect, and the full method is published at https://congressreportcard.org/methodology.html.
```

**Contact:** your name, phone number and email (App Review only uses these if they have
questions).

## Screenshots

Upload in this order. App Store Connect shows the first three in search results.

| File | Shows |
|---|---|
| `01-members.png` | Every member with their grade and the grade counts |
| `02-zip-code.png` | A ZIP code search: the House member and both senators |
| `03-report-card.png` | A report card with the three scores behind the grade |
| `04-how-they-compare.png` | How a member compares with their chamber, party and state |
| `05-states.png` | States ranked by their delegation's average score |
| `06-state-delegation.png` | One state's delegation |
| `07-articles.png` | The articles |

- `screenshots/iphone-6.9/` (1320 × 2868) goes in the **6.9" iPhone** slot. App Store Connect
  scales these down for smaller iPhones.
- `screenshots/ipad-13/` (2064 × 2752) goes in the **13" iPad** slot. It's needed because the
  app also runs on iPad.

The screenshots come from the web build of the app with the live data of the day they were
taken. The screens and data are the same as on iPhone; the system font differs slightly (Roboto
on the web, San Francisco on iPhone). To take them again, see `screenshots.mjs`. The examples
were picked to show a mix of parties: a Pennsylvania ZIP code with members of both parties, a
Republican's report card, a Democrat's comparison, and Virginia's split delegation.
