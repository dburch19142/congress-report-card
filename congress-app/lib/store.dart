import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'grading.dart';
import 'models.dart';

enum SortOrder {
  grade('Highest grade'),
  gradeAscending('Lowest grade'),
  attendanceAscending('Most votes missed'),
  name('Name');

  const SortOrder(this.label);
  final String label;
}

enum ZipState { idle, loading, ready, failed }

/// What a search made only of digits found: the note to show above the list
/// and the test for which members to list.
class ZipSearch {
  const ZipSearch(this.note, {this.matches, this.offerAddressLookup = false});

  final String note;
  final bool Function(Member)? matches;

  /// True when the ZIP code spans districts, so the note links to the
  /// House's look-up by street address.
  final bool offerAddressLookup;
}

const addressLookupUrl =
    'https://www.house.gov/representatives/find-your-representative';

final _digitsOnly = RegExp(r'^\d[\d\s-]*$');
final _zipCode = RegExp(r'^\d{5}(-?\d{4})?$');

/// The loaded data, the grading weights and the grades they produce. The
/// Members and Grading tabs share one of these, so moving a slider regrades
/// the list.
class ReportStore extends ChangeNotifier {
  ReportStore(this.data);

  static const _weightsKey = 'rc-weights';

  final ReportData data;

  Report? report;
  Weights weights = defaultWeights;
  List<Graded> graded = const [];
  Map<String, Graded> _byId = const {};

  ZipState zipState = ZipState.idle;
  Map<String, List<String>> _zips = const {};

  Graded? byId(String id) => _byId[id];

  Future<void> load({bool refresh = false}) async {
    final loaded = await data.report(refresh: refresh);
    if (report == null) weights = await _savedWeights();
    report = loaded;
    _regrade();
  }

  void _regrade() {
    graded = gradeMembers(report?.members ?? const [], weights);
    _byId = {for (final g in graded) g.member.id: g};
    notifyListeners();
  }

  void setWeight(Subject subject, int value) =>
      _setWeights(weights.withWeight(subject, value));

  void resetWeights() => _setWeights(defaultWeights);

  void _setWeights(Weights value) {
    if (value == weights) return;
    weights = value;
    _regrade();
    _saveWeights();
  }

  Future<Weights> _savedWeights() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getStringList(_weightsKey)?.map(int.parse).toList();
      if (saved != null && saved.length == Subject.values.length) {
        final w = Weights(
            attendance: saved[0], sponsored: saved[1], cosponsored: saved[2]);
        if (w.isValid) return w;
      }
    } catch (_) {
      // Unreadable settings fall back to the defaults.
    }
    return defaultWeights;
  }

  Future<void> _saveWeights() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(
          _weightsKey, weights.toList().map((w) => '$w').toList());
    } catch (_) {
      // The weights still apply until the app closes.
    }
  }

  // The ZIP code table is about 500 KB, so it loads the first time someone
  // types a ZIP code.
  void _loadZips() {
    if (zipState != ZipState.idle) return;
    zipState = ZipState.loading;
    data.zipDistricts().then((zips) {
      _zips = zips;
      zipState = ZipState.ready;
    }).catchError((Object _) {
      zipState = ZipState.failed;
    }).whenComplete(notifyListeners);
  }

  /// A search made only of digits is a ZIP code (ZIP+4 is accepted; the +4
  /// is ignored). Returns null for any other search.
  ZipSearch? zipSearch(String query) {
    if (!_digitsOnly.hasMatch(query)) return null;
    if (!_zipCode.hasMatch(query)) {
      return const ZipSearch(
          'Enter a 5-digit ZIP code to find your members of Congress.');
    }
    final zip = query.substring(0, 5);
    _loadZips();
    if (zipState == ZipState.loading) {
      return ZipSearch('Looking up ZIP code $zip…');
    }
    if (zipState == ZipState.failed) {
      return const ZipSearch(
          "ZIP code lookup couldn't be loaded. Try again, or search by state.");
    }
    final districts = _zips[zip] ?? const <String>[];
    if (districts.isEmpty) {
      return ZipSearch(
          "ZIP code $zip wasn't found. ZIP codes used only for PO boxes or a "
          "single building aren't included. Try a nearby ZIP code.");
    }
    final members = report?.members ?? const <Member>[];
    final states = {for (final d in districts) d.substring(0, 2)};
    final seats = {
      for (final m in members)
        if (!m.isSenator) m.districtKey
    };
    final names = districts.map(districtLabel).toList();
    final list = names.length > 1
        ? '${names.sublist(0, names.length - 1).join(', ')} and ${names.last}'
        : names.first;
    var note = districts.length == 1
        ? 'ZIP code $zip is in $list.'
        : 'ZIP code $zip covers parts of $list, so more than one House '
            'member is shown.';
    final vacant =
        districts.where((d) => !seats.contains(d)).map(districtLabel);
    if (vacant.isNotEmpty) {
      note += ' The House seat for ${vacant.join(' and ')} is currently '
          'vacant.';
    }
    return ZipSearch(
      note,
      offerAddressLookup: districts.length > 1,
      matches: (m) => m.isSenator
          ? states.contains(m.state)
          : districts.contains(m.districtKey),
    );
  }

  /// The members matching the search and filters, in [sort] order. The
  /// grade distribution counts these; the grade filter is applied after.
  List<Graded> filtered({
    String query = '',
    String? chamber,
    String? state,
    String? party,
    SortOrder sort = SortOrder.grade,
    ZipSearch? zip,
  }) {
    final q = query.trim().toLowerCase();
    bool matchesText(Member m) =>
        q.isEmpty ||
        m.name.toLowerCase().contains(q) ||
        m.state.toLowerCase() == q ||
        stateName(m.state).toLowerCase().contains(q);

    final list = graded.where((g) {
      final m = g.member;
      return (chamber == null || m.chamber == chamber) &&
          (state == null || m.state == state) &&
          (party == null || m.party == party) &&
          (zip != null ? zip.matches?.call(m) ?? false : matchesText(m));
    }).toList();

    int byName(Graded a, Graded b) => a.member.last.compareTo(b.member.last);
    // Ties fall back to the name so the order is the same on every run.
    int Function(Graded, Graded) by(num Function(Graded) key) => (a, b) {
          final c = key(a).compareTo(key(b));
          return c != 0 ? c : byName(a, b);
        };
    list.sort(switch (sort) {
      SortOrder.grade => by((g) => -(g.score ?? -1)),
      SortOrder.gradeAscending => by((g) => g.score ?? 999),
      SortOrder.attendanceAscending => by((g) => g.attendance ?? 2),
      SortOrder.name => byName,
    });
    return list;
  }
}
