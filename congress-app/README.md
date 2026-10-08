# Congress Report Card app

A Flutter app for [congressreportcard.org](https://congressreportcard.org):
a letter grade for every current U.S. Representative and Senator, based on
vote attendance and legislative record. It has no data of its own. Every
screen reads the files the site publishes for its own pages
(`data/members.js`, `data/zips.js` and `digest/feed.xml`, built by
the scripts in the repo root), so the app shows the same nightly data as the
site.

## Screens

- **Members**: every member with their grade. Search by name, state or ZIP
  code; filter by chamber, state and party; sort by grade, votes missed or
  name. The row of letters counts the listed members by grade, and tapping
  a letter shows only that grade.
- **Report card**: tap any member for the overall grade, the three subject
  grades with the record behind each one, the bills that advanced, and
  links to their page on the site, Congress.gov and their official website.
  The link button in the top bar copies the address of their page.
- **Digest**: the site's weekly digest. Tapping a member's name opens their
  report card.
- **Grading**: the three weight sliders from the site's "Adjust grading"
  panel, and how grades are calculated. The weights are saved on the device.
- **About**: when the data was last updated, the data sources, and the
  site's methodology, privacy and contact pages.

Pull down on the members list or the digest to reload it from the site.

## Layout

- `lib/api.dart`: `ReportApi`, the HTTP client, behind the `ReportData`
  interface the screens use (tests swap in canned data).
- `lib/models.dart`: the data classes for `members.js`.
- `lib/grading.dart`: the grading rules. They repeat `GRADING` in
  `../site/app.js` and `../build_pages.py`; change all
  three together.
- `lib/store.dart`: the loaded data, the weights and the grades, shared by
  the tabs, plus the search, ZIP code lookup, filters and sort orders.
- `lib/digest.dart`: reads the newest digest out of the RSS feed.
- `lib/screens/`: one file per screen. `lib/widgets.dart` has the shared
  loading and error view, search box, grade badge and member row.
- `test/widget_test.dart`: grading, parsing, search and one walk-through
  per screen.

## Run it

```bash
flutter pub get
flutter test
flutter run
```

The app reads `https://congressreportcard.org` by default. To run it
against a local copy of the site (`python -m http.server 8000 --directory
site` in the repo root):

```bash
flutter run --dart-define=SITE_BASE=http://localhost:8000
```

Without a Mac, `flutter run -d chrome` shows the same app in a browser.

## Build for iPhone (on a Mac)

The iOS build needs Xcode and CocoaPods, so it has to be done on a Mac.

1. `flutter pub get`, then `open ios/Runner.xcworkspace`.
2. In Xcode: **Runner → Signing & Capabilities** → choose your Apple
   Developer team. The bundle identifier is
   `org.congressreportcard.congressReportCard`; change it here if you want
   a different one (it must match the app record in App Store Connect).
3. Plug in an iPhone and `flutter run --release` to try it on the device.
4. For TestFlight or the App Store: create the app in App Store Connect
   with the same bundle identifier, then `flutter build ipa` and upload
   `build/ios/ipa/*.ipa` with Xcode's Organizer or the Transporter app.

The name under the icon on the home screen is "Report Card"
(`CFBundleDisplayName` in `ios/Runner/Info.plist`); the full name would be
cut off there. The icon is the site's flag mark on the site's navy
(`ios/Runner/Assets.xcassets/AppIcon.appiconset`).
