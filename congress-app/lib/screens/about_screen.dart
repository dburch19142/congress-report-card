import 'package:flutter/material.dart';

import '../store.dart';
import '../widgets.dart';

const _site = 'https://congressreportcard.org';

/// Where the data comes from, when it was last updated and the site's
/// methodology, privacy and contact pages.
class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key, required this.store});

  final ReportStore store;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('About')),
      body: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final report = store.report;
          return ListView(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (report != null)
                      Text(report.congressLabel, style: text.labelLarge),
                    const SizedBox(height: 8),
                    const Text(
                      'How often does your representative show up to vote, '
                      'and how much legislation do they write and support? '
                      'Each grade comes only from the public record.',
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Congress Report Card is an independent project. It is '
                      'not affiliated with Congress, any party or any '
                      'campaign.',
                    ),
                    if (report != null && report.generated.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text('Updated ${report.generated}.',
                          style: text.bodySmall),
                    ],
                  ],
                ),
              ),
              const Divider(),
              const _Link('congressreportcard.org', _site),
              const _Link('Methodology', '$_site/methodology.html'),
              const _Link('Privacy policy', '$_site/privacy.html'),
              const _Link('Contact', '$_site/contact.html'),
              const Divider(),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Text('Data sources', style: text.titleMedium),
              ),
              const _Link('Rosters: congress-legislators',
                  'https://github.com/unitedstates/congress-legislators'),
              const _Link('Roll-call votes: Voteview', 'https://voteview.com'),
              const _Link(
                  'Legislation: Congress.gov', 'https://api.congress.gov'),
              const _Link('ZIP code districts: Census Bureau',
                  'https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html'),
              const _Link('Photos: unitedstates/images',
                  'https://github.com/unitedstates/images'),
            ],
          );
        },
      ),
    );
  }
}

class _Link extends StatelessWidget {
  const _Link(this.label, this.url);

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(label),
      trailing: const Icon(Icons.open_in_new, size: 18),
      onTap: () => openUrl(url),
    );
  }
}
