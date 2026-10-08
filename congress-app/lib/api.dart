import 'dart:convert';

import 'package:http/http.dart' as http;

import 'digest.dart';
import 'models.dart';

/// Where the app gets its data. The screens depend on this rather than on
/// [ReportApi] directly so tests can supply canned data.
abstract class ReportData {
  Future<Report> report({bool refresh = false});

  /// ZIP code → the districts it covers, e.g. `{'01007': ['MA1', 'MA2']}`.
  Future<Map<String, List<String>>> zipDistricts();
  Future<Digest> digest({bool refresh = false});
}

/// Reads the data files congressreportcard.org publishes for its own pages,
/// so the app shows the same nightly data as the site. Override the host for
/// local testing with `--dart-define=SITE_BASE=http://localhost:8000`.
class ReportApi implements ReportData {
  ReportApi({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? _defaultBaseUrl;

  static const _defaultBaseUrl = String.fromEnvironment(
    'SITE_BASE',
    defaultValue: 'https://congressreportcard.org',
  );

  final http.Client _client;
  final String _baseUrl;

  Report? _report;
  Map<String, List<String>>? _zips;
  Digest? _digest;

  Future<String> _get(String path) async {
    final response = await _client
        .get(Uri.parse('$_baseUrl$path'))
        .timeout(const Duration(seconds: 30));
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode);
    }
    return utf8.decode(response.bodyBytes);
  }

  @override
  Future<Report> report({bool refresh = false}) async {
    if (_report != null && !refresh) return _report!;
    final body = jsObject(await _get('/data/members.js'));
    return _report = Report.fromJson(body);
  }

  @override
  Future<Map<String, List<String>>> zipDistricts() async {
    if (_zips != null) return _zips!;
    final body = jsObject(await _get('/data/zips.js'));
    return _zips = body.map(
      (zip, districts) => MapEntry(zip, (districts as String).split(' ')),
    );
  }

  @override
  Future<Digest> digest({bool refresh = false}) async {
    if (_digest != null && !refresh) return _digest!;
    return _digest = Digest.fromFeed(await _get('/digest/feed.xml'));
  }
}

/// The site's data files are scripts of the form `window.NAME = {...};`.
/// This returns the object.
Map<String, dynamic> jsObject(String script) {
  final start = script.indexOf('{'), end = script.lastIndexOf('}');
  if (start < 0 || end < start) {
    throw const FormatException('No data object in the file');
  }
  return jsonDecode(script.substring(start, end + 1)) as Map<String, dynamic>;
}

class ApiException implements Exception {
  ApiException(this.statusCode);

  final int statusCode;

  @override
  String toString() =>
      'congressreportcard.org answered with status $statusCode';
}
