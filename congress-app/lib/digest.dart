/// The weekly digest, read from the site's RSS feed (`digest/feed.xml`).
/// `build_digest.py` writes the body with only headings, paragraphs, lists
/// and links, so that is all this understands.
library;

enum BlockKind { heading, subheading, paragraph, item }

class DigestSpan {
  const DigestSpan(this.text, [this.href]);

  final String text;
  final String? href;

  /// The member's ID when the link goes to a report card page on the site.
  String? get memberId =>
      href == null ? null : _memberLink.firstMatch(href!)?.group(1);
}

class DigestBlock {
  const DigestBlock(this.kind, this.spans, {this.number});

  final BlockKind kind;
  final List<DigestSpan> spans;

  /// The position in a numbered list, or null for a bulleted one.
  final int? number;

  String get text => spans.map((s) => s.text).join();
}

class Digest {
  const Digest({required this.title, required this.blocks});

  /// Reads the newest item in the feed.
  factory Digest.fromFeed(String xml) {
    final item = _item.firstMatch(xml)?.group(1);
    if (item == null) throw const FormatException('The digest feed is empty');
    final title = _title.firstMatch(item)?.group(1) ?? 'Weekly digest';
    final body = _cdata.firstMatch(item)?.group(1) ?? '';

    final blocks = <DigestBlock>[];
    int? number; // set while inside a numbered list
    for (final m in _blocks.allMatches(body)) {
      final list = m.group(1), tag = m.group(2);
      if (list != null) {
        number = m.group(0)!.startsWith('</') || list == 'ul' ? null : 0;
        continue;
      }
      final spans = _spans(m.group(3)!);
      if (spans.isEmpty) continue;
      if (tag == 'li' && number != null) number = number + 1;
      blocks.add(DigestBlock(
        switch (tag) {
          'h2' => BlockKind.heading,
          'h3' => BlockKind.subheading,
          'li' => BlockKind.item,
          _ => BlockKind.paragraph,
        },
        spans,
        number: tag == 'li' ? number : null,
      ));
    }
    return Digest(title: _unescape(title), blocks: blocks);
  }

  final String title;
  final List<DigestBlock> blocks;
}

final _item = RegExp(r'<item>(.*?)</item>', dotAll: true);
final _title = RegExp(r'<title>(.*?)</title>', dotAll: true);
final _cdata = RegExp(r'<!\[CDATA\[(.*?)\]\]>', dotAll: true);
final _blocks = RegExp(r'</?(ol|ul)>|<(h2|h3|p|li)>(.*?)</\2>', dotAll: true);
final _link = RegExp(r'<a href="([^"]*)"[^>]*>(.*?)</a>', dotAll: true);
final _tag = RegExp(r'<[^>]+>');
final _space = RegExp(r'\s+');
final _entity = RegExp(r'&(#\d+|[a-z]+);');
final _memberLink =
    RegExp(r'^https://congressreportcard\.org/members/(\w+)\.html$');

List<DigestSpan> _spans(String html) {
  final spans = <DigestSpan>[];
  void add(String raw, [String? href]) {
    final text = _unescape(raw.replaceAll(_tag, '').replaceAll(_space, ' '));
    if (text.isNotEmpty) spans.add(DigestSpan(text, href));
  }

  var at = 0;
  for (final m in _link.allMatches(html)) {
    add(html.substring(at, m.start));
    add(m.group(2)!, _unescape(m.group(1)!));
    at = m.end;
  }
  add(html.substring(at));
  return spans;
}

String _unescape(String text) => text.replaceAllMapped(_entity, (m) {
      final name = m.group(1)!;
      if (name.startsWith('#')) {
        return String.fromCharCode(int.parse(name.substring(1)));
      }
      return const {
            'amp': '&',
            'lt': '<',
            'gt': '>',
            'quot': '"',
            'apos': "'"
          }[name] ??
          m.group(0)!;
    });
