import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../digest.dart';
import '../store.dart';
import '../widgets.dart';

/// The site's weekly digest: roll calls held, who missed the most votes,
/// new laws and grade changes. Tapping a member opens their report card.
class DigestScreen extends StatefulWidget {
  const DigestScreen({super.key, required this.store});

  final ReportStore store;

  @override
  State<DigestScreen> createState() => _DigestScreenState();
}

class _DigestScreenState extends State<DigestScreen> {
  late Future<Digest> _future = widget.store.data.digest();
  final _recognizers = <TapGestureRecognizer>[];

  @override
  void dispose() {
    _disposeRecognizers();
    super.dispose();
  }

  void _disposeRecognizers() {
    for (final r in _recognizers) {
      r.dispose();
    }
    _recognizers.clear();
  }

  Future<void> _reload() {
    final future = widget.store.data.digest(refresh: true);
    setState(() => _future = future);
    return future.then<void>((_) {}).catchError((Object _) {});
  }

  void _open(DigestSpan span) {
    final id = span.memberId;
    if (id != null && widget.store.byId(id) != null) {
      openMember(context, widget.store, id);
    } else {
      openUrl(span.href!);
    }
  }

  TextSpan _span(DigestSpan span, Color linkColor) {
    if (span.href == null) return TextSpan(text: span.text);
    final recognizer = TapGestureRecognizer()..onTap = () => _open(span);
    _recognizers.add(recognizer);
    return TextSpan(
      text: span.text,
      style: TextStyle(color: linkColor, fontWeight: FontWeight.w600),
      recognizer: recognizer,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Weekly digest')),
      body: AsyncView<Digest>(
        future: _future,
        onRetry: _reload,
        builder: (context, digest) {
          _disposeRecognizers();
          return RefreshIndicator(
            onRefresh: _reload,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Text(digest.title,
                    style: Theme.of(context).textTheme.headlineSmall),
                for (final block in digest.blocks) _block(context, block),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _block(BuildContext context, DigestBlock block) {
    final theme = Theme.of(context);
    final body = Text.rich(
      TextSpan(children: [
        for (final s in block.spans) _span(s, theme.colorScheme.primary),
      ]),
      style: switch (block.kind) {
        BlockKind.heading => theme.textTheme.titleLarge,
        BlockKind.subheading => theme.textTheme.titleMedium,
        _ => theme.textTheme.bodyLarge,
      },
    );
    return switch (block.kind) {
      BlockKind.heading =>
        Padding(padding: const EdgeInsets.only(top: 24), child: body),
      BlockKind.subheading =>
        Padding(padding: const EdgeInsets.only(top: 16), child: body),
      BlockKind.paragraph =>
        Padding(padding: const EdgeInsets.only(top: 10), child: body),
      BlockKind.item => Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 28,
                child: Text(
                  block.number == null ? '•' : '${block.number}.',
                  style: theme.textTheme.bodyLarge,
                ),
              ),
              Expanded(child: body),
            ],
          ),
        ),
    };
  }
}
