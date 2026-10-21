import 'package:flutter/material.dart';

import '../articles.dart';
import '../store.dart';
import '../widgets.dart';

/// The site's articles, newest first. Each one opens in an in-app browser.
class ArticlesScreen extends StatefulWidget {
  const ArticlesScreen({super.key, required this.store});

  final ReportStore store;

  @override
  State<ArticlesScreen> createState() => _ArticlesScreenState();
}

class _ArticlesScreenState extends State<ArticlesScreen> {
  late Future<List<Article>> _future = widget.store.data.articles();

  Future<void> _reload() {
    final future = widget.store.data.articles(refresh: true);
    setState(() => _future = future);
    return future.then<void>((_) {}).catchError((Object _) {});
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Articles')),
      body: AsyncView<List<Article>>(
        future: _future,
        onRetry: _reload,
        builder: (context, articles) => RefreshIndicator(
          onRefresh: _reload,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: articles.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final a = articles[i];
              return ListTile(
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                title: Text(a.title,
                    style: text.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700)),
                subtitle: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(a.dateLabel, style: text.labelSmall),
                      const SizedBox(height: 4),
                      Text(a.description),
                    ],
                  ),
                ),
                onTap: () => openUrl(a.url, inApp: true),
              );
            },
          ),
        ),
      ),
    );
  }
}
