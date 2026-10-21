# Congress Report Card app

A Flutter app for [congressreportcard.org](https://congressreportcard.org):
a letter grade for every current U.S. Representative and Senator, based on
vote attendance and legislative record. It has no data of its own. Every
screen reads the files the site publishes for its own pages
(`data/members.js`, `data/zips.js`, `digest/feed.xml` and
`articles/articles.json`, built by the scripts in the repo root), so the app
shows the same nightly data as the site.

## Screens

- **Members**: every member with their grade. Search by name, state or ZIP
  code; filter by chamber, state and party; sort by grade, votes missed or
  name. The row of letters counts the listed members by grade, and tapping
  a letter shows only that grade.
- **Report card**: tap any member for the overall grade, the three subject
  grades with the record behind each one, the bills that advanced, how the
  member compares with their chamber, party and state, and links to their
  page on the site, Congress.gov and their official website.
  The link button in the top bar copies the address of their page.
- **States**: every state's delegation ranked by its members' average score,
  then DC and the territories. Tapping a state shows a summary and every
  member from it.
- **Articles**: the site's articles, newest first. Each opens in a browser
  view inside the app.
- **Digest**: the site's weekly digest. Tapping a member's name opens their
  report card.
- **More**: **Adjust grading** (the three weight sliders from the site's
  "Adjust grading" panel; the weights are saved on the device), when the
  data was last updated, the data sources, and the site's methodology,
  about, privacy, terms and contact pages.

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
- `lib/articles.dart`: the article list.
- `lib/compare.dart`: rankings by chamber, party and state, and the
  comparison text. It follows `comparison` in `build_pages.py`, but uses the
  weights set in the app, and has no "since last week" line because the app
  doesn't get the digest snapshot.
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

## Build in GitHub Actions (no Mac needed)

`.github/workflows/ios.yml` runs on every change to `congress-app/`:

- **test** runs `flutter test` on Linux.
- **build** makes an unsigned release build for iPhone on a Mac runner. It
  proves the app compiles with Xcode; the unsigned `Runner.app` is kept as a
  run artifact for a week. It can't be installed on a phone.

To send a build to TestFlight, open **Actions → iOS app → Run workflow**,
tick **Upload to TestFlight** and run it. The **testflight** job signs the
app and uploads it to App Store Connect. The build number is the workflow's
run number, so every upload is newer than the last. It needs these
repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | What it is |
|---|---|
| `APPLE_TEAM_ID` | The 10-character Team ID from **Membership details** at developer.apple.com |
| `IOS_DISTRIBUTION_CERT_P12_BASE64` | The Apple Distribution certificate and its private key as a `.p12`, base64-encoded |
| `IOS_DISTRIBUTION_CERT_PASSWORD` | The password chosen when making the `.p12` |
| `IOS_PROVISIONING_PROFILE_BASE64` | An App Store provisioning profile for the app's bundle identifier, base64-encoded |
| `APP_STORE_CONNECT_KEY_ID` | The Key ID of an App Store Connect API key (role: App Manager) |
| `APP_STORE_CONNECT_ISSUER_ID` | The Issuer ID shown above the list of API keys |
| `APP_STORE_CONNECT_PRIVATE_KEY` | The full text of the key's `.p8` file, including the BEGIN and END lines |

Making them without a Mac (Git Bash has `openssl` and `base64`):

1. In App Store Connect, create the app with the bundle identifier
   `org.congressreportcard.congressReportCard` (register it first under
   **Certificates, Identifiers & Profiles → Identifiers** if it isn't listed).
2. Make a key and a certificate signing request:
   `openssl req -new -newkey rsa:2048 -nodes -keyout dist.key -out dist.csr -subj "/CN=Congress Report Card"`.
   Upload `dist.csr` under **Certificates → + → Apple Distribution** and
   download `distribution.cer`.
3. Combine them into a `.p12`:
   `openssl x509 -inform DER -in distribution.cer -out dist.pem` then
   `openssl pkcs12 -export -legacy -inkey dist.key -in dist.pem -out dist.p12`
   (choose a password; it is `IOS_DISTRIBUTION_CERT_PASSWORD`).
4. Under **Profiles → + → App Store Connect**, make a profile for the app's
   identifier with that certificate, and download it.
5. Under **Users and Access → Integrations → App Store Connect API**, make a
   key and download the `.p8` (it can only be downloaded once).
6. Encode the two files for the secrets: `base64 -w0 dist.p12` and
   `base64 -w0 <profile>.mobileprovision`.

Keep `dist.key`, `dist.p12` and the `.p8` somewhere safe and out of this
repository. The certificate and profile expire after a year; make new ones
and update the secrets when they do.

The name under the icon on the home screen is "Report Card"
(`CFBundleDisplayName` in `ios/Runner/Info.plist`); the full name would be
cut off there. The icon is the site's flag mark on the site's navy
(`ios/Runner/Assets.xcassets/AppIcon.appiconset`).
