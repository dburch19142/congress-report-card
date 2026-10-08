import 'dart:async';
import 'dart:io';

import 'package:congress_report_card/api.dart';
import 'package:congress_report_card/digest.dart';
import 'package:congress_report_card/grading.dart';
import 'package:congress_report_card/main.dart';
import 'package:congress_report_card/models.dart';
import 'package:congress_report_card/store.dart';
import 'package:congress_report_card/widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

Member _member(
  String id,
  String name,
  String chamber,
  String state,
  String party, {
  int? district,
  int eligible = 100,
  int missed = 0,
  int chamberTotal = 100,
  Map<String, int> stages = const {},
  int cosponsored = 0,
  List<NotableBill> notable = const [],
}) =>
    Member(
      id: id,
      name: name,
      last: name.split(' ').last,
      chamber: chamber,
      state: state,
      district: district,
      party: party,
      url: 'https://example.gov/$id',
      votes:
          Votes(eligible: eligible, missed: missed, chamberTotal: chamberTotal),
      bills: Bills(
        sponsored: stages.values.fold(0, (a, b) => a + b),
        stages: {
          for (final s in stageNames.keys) s: stages[s] ?? 0,
        },
        resolutions: 0,
        cosponsored: cosponsored,
        notable: notable,
      ),
    );

// Worked out by hand from the rules in grading.dart, default weights:
//   Alpha   attendance 100, written 100, supported 100 → 100.0  A
//   Bravo   attendance 33.3, written 50, supported 50  → 43.3   F
//   Charlie attendance 100, written 75, supported 75   → 85.0   B (partial)
//   Delta   attendance 86.7, written 100, supported 100 → 94.7  A
//   Echo    attendance 0, written 50, supported 50     → 30.0   F
final _members = [
  _member('A000001', 'Ann Alpha', 'House', 'GA', 'Democrat',
      district: 5,
      stages: {'introduced': 2, 'law': 1},
      cosponsored: 50,
      notable: const [
        NotableBill(
          id: 'HR 1',
          title: 'Example Act',
          stage: 'law',
          url: 'https://www.congress.gov/bill/119th-congress/house-bill/1',
        ),
      ]),
  _member('B000002', 'Bob Bravo', 'House', 'GA', 'Republican',
      district: 6, missed: 10, stages: {'introduced': 1}, cosponsored: 10),
  _member('C000003', 'Cy Charlie', 'House', 'AK', 'Republican',
      district: 0, eligible: 40, stages: {'introduced': 3}, cosponsored: 30),
  _member('D000004', 'Dee Delta', 'Senate', 'GA', 'Democrat',
      eligible: 200,
      missed: 4,
      chamberTotal: 200,
      stages: {'passed': 1},
      cosponsored: 100),
  _member('E000005', 'Ed Echo', 'Senate', 'GA', 'Independent',
      eligible: 200, missed: 40, chamberTotal: 200, cosponsored: 5),
];

const _feed = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Congress Report Card weekly digest</title>
<item>
<title>Week ending October 3, 2026</title>
<description><![CDATA[<p>Here is what changed.</p>
  <h2>Most votes missed this week</h2><ol>
  <li><a href="https://congressreportcard.org/members/E000005.html">Ed Echo</a> (I, GA) missed 8 of 12</li>
  <li><a href="https://congressreportcard.org/members/B000002.html">Bob &quot;Bo&quot; Bravo</a> (R, GA-6) missed 3 of 12</li>
  </ol>
  <h2>Bills that became law</h2><ul>
  <li><a href="https://www.congress.gov/bill/119th-congress/house-bill/1">HR 1</a>: Example Act.</li>
  </ul>]]></description>
</item>
</channel></rss>''';

class FakeData implements ReportData {
  @override
  Future<Report> report({bool refresh = false}) async => Report(
        congress: 119,
        generated: '2026-10-07 16:22 UTC',
        hasBills: true,
        members: _members,
      );

  @override
  Future<Map<String, List<String>>> zipDistricts() async => {
        '30303': ['GA5'],
        '30004': ['GA6', 'GA7'],
        '99501': ['AK0'],
      };

  @override
  Future<Digest> digest({bool refresh = false}) async => Digest.fromFeed(_feed);
}

// A 1×1 transparent PNG. The test binding answers every HTTP request with
// status 400, so the tests serve this for the members' photos instead.
const _pixel = <int>[
  0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, //
  0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
  0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
  0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
  0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
];

class _PhotoOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) => _PhotoClient();
}

class _PhotoClient extends Fake implements HttpClient {
  @override
  bool autoUncompress = true;

  @override
  Future<HttpClientRequest> getUrl(Uri url) async => _PhotoRequest();
}

class _PhotoRequest extends Fake implements HttpClientRequest {
  @override
  Future<HttpClientResponse> close() async => _PhotoResponse();
}

class _PhotoResponse extends Fake implements HttpClientResponse {
  @override
  int get statusCode => HttpStatus.ok;

  @override
  int get contentLength => _pixel.length;

  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;

  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int> event)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) =>
      Stream.value(_pixel).listen(onData,
          onError: onError, onDone: onDone, cancelOnError: cancelOnError);
}

Future<ReportStore> _loadedStore() async {
  final store = ReportStore(FakeData());
  await store.load();
  return store;
}

Finder _tile(String name) =>
    find.ancestor(of: find.text(name), matching: find.byType(MemberTile));

String _gradeOf(WidgetTester tester, String name) => tester
    .widget<GradeBadge>(
        find.descendant(of: _tile(name), matching: find.byType(GradeBadge)))
    .grade;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('grading', () {
    test('matches the site for the default weights', () {
      final graded = {
        for (final g in gradeMembers(_members, defaultWeights)) g.member.last: g
      };
      expect(graded['Alpha']!.score, closeTo(100, 0.01));
      expect(graded['Bravo']!.score, closeTo(43.33, 0.01));
      expect(graded['Charlie']!.score, closeTo(85, 0.01));
      expect(graded['Delta']!.score, closeTo(94.67, 0.01));
      expect(graded['Echo']!.score, closeTo(30, 0.01));
      expect(
        graded.values.map((g) => g.grade),
        ['A', 'F', 'B', 'A', 'F'],
      );
      expect(graded['Charlie']!.partial, isTrue);
      expect(graded['Alpha']!.partial, isFalse);
      expect(percent(graded['Delta']!.attendance!), '98.0%');
    });

    test('letter cut-offs', () {
      expect(letterOf(93), 'A');
      expect(letterOf(92.99), 'A-');
      expect(letterOf(60), 'D-');
      expect(letterOf(59.9), 'F');
    });

    test('weights always add up to 100', () {
      expect(defaultWeights.withWeight(Subject.attendance, 100).toList(),
          [100, 0, 0]);
      // 30 left over, shared 35:25 and rounded to the step.
      expect(defaultWeights.withWeight(Subject.attendance, 70).toList(),
          [70, 20, 10]);
      // Both others at zero: an even split.
      const allAttendance =
          Weights(attendance: 100, sponsored: 0, cosponsored: 0);
      expect(allAttendance.withWeight(Subject.attendance, 50).toList(),
          [50, 25, 25]);
    });

    test('a subject with no weight is left out of the grade', () async {
      final store = await _loadedStore();
      store.setWeight(Subject.attendance, 100);
      expect(store.byId('D000004')!.grade, 'B');
      expect(store.byId('C000003')!.grade, 'A');
      store.resetWeights();
      expect(store.byId('D000004')!.grade, 'A');
    });
  });

  group('data files', () {
    test('reads the object out of a site data script', () {
      expect(jsObject('window.REPORT_DATA = {"congress":119};'),
          {'congress': 119});
      expect(() => jsObject('not data'), throwsFormatException);
    });

    test('ReportApi reads members.js and zips.js', () async {
      final api = ReportApi(
        baseUrl: 'https://example.org',
        client: MockClient((request) async {
          if (request.url.path == '/data/members.js') {
            return http.Response(
              'window.REPORT_DATA = {"congress":119,"generated":"now",'
              '"hasBills":false,"members":[{"id":"X000001","name":"Zoë X",'
              '"last":"X","chamber":"Senate","state":"GA","district":null,'
              '"party":"Democrat","votes":{"eligible":10,"missed":1,'
              '"chamberTotal":10}}]};',
              200,
              headers: {
                'content-type': 'application/javascript; charset=utf-8'
              },
            );
          }
          if (request.url.path == '/data/zips.js') {
            return http.Response(
                'window.ZIP_DISTRICTS = {"01007":"MA1 MA2"};', 200);
          }
          return http.Response('', 404);
        }),
      );
      final report = await api.report();
      expect(report.members.single.name, 'Zoë X');
      expect(report.members.single.bills, isNull);
      expect(report.members.single.seat, 'Senator · GA');
      expect(await api.zipDistricts(), {
        '01007': ['MA1', 'MA2']
      });
      expect(api.digest(), throwsA(isA<ApiException>()));
    });

    test('reads the newest digest from the feed', () {
      final digest = Digest.fromFeed(_feed);
      expect(digest.title, 'Week ending October 3, 2026');
      expect(digest.blocks.map((b) => b.kind), [
        BlockKind.paragraph,
        BlockKind.heading,
        BlockKind.item,
        BlockKind.item,
        BlockKind.heading,
        BlockKind.item,
      ]);
      expect(digest.blocks[2].number, 1);
      expect(digest.blocks[3].number, 2);
      expect(digest.blocks[3].text, 'Bob "Bo" Bravo (R, GA-6) missed 3 of 12');
      expect(digest.blocks[3].spans.first.memberId, 'B000002');
      expect(digest.blocks[5].number, isNull);
      expect(digest.blocks[5].spans.first.memberId, isNull);
    });
  });

  group('search', () {
    test('by name, state code and state name', () async {
      final store = await _loadedStore();
      List<String> names(String q) =>
          store.filtered(query: q).map((g) => g.member.last).toList();
      expect(names('brav'), ['Bravo']);
      expect(names('ak'), ['Charlie']);
      expect(names('alaska'), ['Charlie']);
      expect(names(''), ['Alpha', 'Delta', 'Charlie', 'Bravo', 'Echo']);
    });

    test('filters and sort orders', () async {
      final store = await _loadedStore();
      List<String> names(List<Graded> list) =>
          list.map((g) => g.member.last).toList();
      expect(names(store.filtered(chamber: 'Senate')), ['Delta', 'Echo']);
      expect(
          names(store.filtered(state: 'GA', party: 'Republican')), ['Bravo']);
      expect(names(store.filtered(sort: SortOrder.attendanceAscending)).first,
          'Echo');
      expect(names(store.filtered(sort: SortOrder.name)),
          ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo']);
    });

    test('by ZIP code', () async {
      final store = await _loadedStore();
      expect(store.zipSearch('Alpha'), isNull);
      expect(store.zipSearch('303')!.note, contains('5-digit ZIP code'));
      expect(store.zipSearch('30303')!.note, contains('Looking up'));
      await Future<void>.delayed(Duration.zero);

      final one = store.zipSearch('30303-1234')!;
      expect(one.note, 'ZIP code 30303 is in GA-5.');
      expect(
        store.filtered(zip: one).map((g) => g.member.last),
        ['Alpha', 'Delta', 'Echo'],
      );

      final split = store.zipSearch('30004')!;
      expect(split.offerAddressLookup, isTrue);
      expect(split.note, contains('covers parts of GA-6 and GA-7'));
      expect(split.note, contains('seat for GA-7 is currently vacant'));

      expect(
          store.zipSearch('99501')!.note, 'ZIP code 99501 is in AK At-large.');
      expect(store.zipSearch('00000')!.note, contains("wasn't found"));
    });
  });

  group('screens', () {
    Future<void> pumpApp(WidgetTester tester) async {
      HttpOverrides.global = _PhotoOverrides();
      await tester.pumpWidget(ReportCardApp(data: FakeData()));
      await tester.pumpAndSettle();
    }

    testWidgets('members list, search and grade filter', (tester) async {
      await pumpApp(tester);
      expect(find.text('5 of 5 members'), findsOneWidget);
      expect(_gradeOf(tester, 'Ann Alpha'), 'A');
      expect(_gradeOf(tester, 'Bob Bravo'), 'F');
      expect(find.text('Partial term'), findsOneWidget);
      expect(find.text('90.0% of votes'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'delta');
      await tester.pumpAndSettle();
      expect(find.text('1 of 5 members'), findsOneWidget);
      expect(find.text('Ann Alpha'), findsNothing);

      await tester.enterText(find.byType(TextField), '');
      await tester.pumpAndSettle();
      await tester.tap(find.bySemanticsLabel(RegExp('Show only F grades')));
      await tester.pumpAndSettle();
      expect(find.text('2 of 5 members · showing F grades'), findsOneWidget);
      expect(find.text('Ann Alpha'), findsNothing);
      expect(find.text('Ed Echo'), findsOneWidget);
    });

    testWidgets('ZIP code search lists the House member and senators',
        (tester) async {
      await pumpApp(tester);
      await tester.enterText(find.byType(TextField), '30303');
      await tester.pumpAndSettle();
      expect(find.text('ZIP code 30303 is in GA-5.'), findsOneWidget);
      expect(find.text('3 of 5 members'), findsOneWidget);
      expect(find.text('Bob Bravo'), findsNothing);
    });

    testWidgets('tapping a member opens their report card', (tester) async {
      await pumpApp(tester);
      await tester.tap(find.text('Ann Alpha'));
      await tester.pumpAndSettle();
      expect(find.text('Georgia · 119th Congress'), findsOneWidget);
      expect(find.text('Voted on 100 of 100 roll calls (100.0%); missed 0.'),
          findsOneWidget);
      expect(find.textContaining('Sponsored 3 bills and joint resolutions'),
          findsOneWidget);
      expect(find.text('40% of grade'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('HR 1: Example Act'), 200);
      expect(find.text('Became law'), findsWidgets);
    });

    testWidgets('moving a weight regrades the list', (tester) async {
      await pumpApp(tester);
      expect(_gradeOf(tester, 'Dee Delta'), 'A');

      await tester.tap(find.text('Grading'));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(Slider).first, const Offset(1000, 0));
      await tester.pumpAndSettle();
      expect(
        tester.widgetList<Slider>(find.byType(Slider)).map((s) => s.value),
        [100, 0, 0],
      );

      await tester.tap(find.text('Members'));
      await tester.pumpAndSettle();
      expect(_gradeOf(tester, 'Dee Delta'), 'B');

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getStringList('rc-weights'), ['100', '0', '0']);
    });

    testWidgets('saved weights are used on the next launch', (tester) async {
      SharedPreferences.setMockInitialValues({
        'rc-weights': ['100', '0', '0'],
      });
      await pumpApp(tester);
      expect(_gradeOf(tester, 'Dee Delta'), 'B');
    });

    testWidgets('digest links open the member', (tester) async {
      await pumpApp(tester);
      await tester.tap(find.text('Digest'));
      await tester.pumpAndSettle();
      expect(find.text('Week ending October 3, 2026'), findsOneWidget);
      expect(find.text('Most votes missed this week'), findsOneWidget);

      await tester.tapOnText(find.textRange.ofSubstring('Ed Echo'));
      await tester.pumpAndSettle();
      expect(find.text('Georgia · 119th Congress'), findsOneWidget);
      expect(find.textContaining('missed 40'), findsOneWidget);
    });

    testWidgets('about shows when the data was updated', (tester) async {
      await pumpApp(tester);
      await tester.tap(find.text('About'));
      await tester.pumpAndSettle();
      expect(find.text('Updated 2026-10-07 16:22 UTC.'), findsOneWidget);
      expect(find.text('119th Congress · 2025–2027'), findsOneWidget);
    });
  });
}
