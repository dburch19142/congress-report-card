import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../colors.dart';
import '../grading.dart';
import '../models.dart';
import '../store.dart';
import '../widgets.dart';

const _noBills = 'Bill data is not available yet.';

String _plural(int n, String word) => '$n $word${n == 1 ? '' : 's'}';

/// One member's report card: the overall grade, the three subject grades
/// with the record behind each, and the bills that advanced.
class MemberScreen extends StatelessWidget {
  const MemberScreen({super.key, required this.store, required this.memberId});

  final ReportStore store;
  final String memberId;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final graded = store.byId(memberId);
        return Scaffold(
          appBar: AppBar(
            title: Text(graded?.member.name ?? 'Report card'),
            actions: [
              if (graded != null)
                IconButton(
                  tooltip: 'Copy link to report card',
                  icon: const Icon(Icons.link),
                  onPressed: () => _copyLink(context, graded.member),
                ),
            ],
          ),
          body: graded == null
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      'This member is no longer in Congress.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              : _card(context, graded),
        );
      },
    );
  }

  Future<void> _copyLink(BuildContext context, Member m) async {
    await Clipboard.setData(ClipboardData(text: m.reportCardUrl));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Link copied')),
    );
  }

  Widget _card(BuildContext context, Graded g) {
    final m = g.member, v = m.votes, b = m.bills;
    final chamberWord = m.isSenator ? 'senators' : 'representatives';
    final text = Theme.of(context).textTheme;

    var attendance = v.eligible == 0
        ? 'No roll-call votes recorded this Congress.'
        : 'Voted on ${v.eligible - v.missed} of ${v.eligible} roll calls '
            '(${percent(g.attendance!)}); missed ${v.missed}.';
    if (m.id == speakerId) {
      attendance += ' By custom the Speaker votes only occasionally; votes '
          'skipped as Speaker are not counted against them.';
    }
    if (m.isDelegate) {
      attendance += ' Delegates may vote only in the Committee of the Whole, '
          'so they are eligible for fewer roll calls.';
    }

    var sponsored = _noBills;
    if (b != null) {
      sponsored = 'Sponsored ${_plural(b.sponsored, 'bill')} and joint '
          'resolutions, more legislative progress than '
          '${(g.percentiles[Subject.sponsored] ?? 0).round()}% of '
          '$chamberWord.';
      if (b.resolutions > 0) {
        sponsored += ' (Also ${_plural(b.resolutions, 'simple resolution')}, '
            'not graded.)';
      }
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            MemberPhoto(m, width: 72),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(m.name,
                      style: text.titleLarge
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  PartyAndSeat(m),
                  Text(
                    '${stateName(m.state)} · '
                    '${store.report?.congressLabel.split(' · ').first ?? ''}',
                    style: text.bodySmall,
                  ),
                  if (g.partial)
                    const Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: Tag('Partial term'),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            GradeBadge(g.grade, size: 64, label: 'Overall grade ${g.grade}'),
          ],
        ),
        const SizedBox(height: 16),
        _SubjectCard(
          graded: g,
          subject: Subject.attendance,
          weight: store.weights[Subject.attendance],
          detail: attendance,
        ),
        _SubjectCard(
          graded: g,
          subject: Subject.sponsored,
          weight: store.weights[Subject.sponsored],
          detail: sponsored,
          extra: b == null ? null : _Stages(b),
        ),
        _SubjectCard(
          graded: g,
          subject: Subject.cosponsored,
          weight: store.weights[Subject.cosponsored],
          detail: b == null
              ? _noBills
              : 'Cosponsored ${b.cosponsored} bills, more than '
                  '${(g.percentiles[Subject.cosponsored] ?? 0).round()}% of '
                  '$chamberWord.',
        ),
        if (b != null && b.notable.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(0, 12, 0, 4),
            child: Text('Bills that advanced', style: text.titleMedium),
          ),
          for (final bill in b.notable)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text('${bill.id}: ${bill.title}'),
              subtitle: Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Tag(stageNames[bill.stage] ?? bill.stage),
                ),
              ),
              trailing: const Icon(Icons.open_in_new, size: 18),
              onTap: () => openUrl(bill.url),
            ),
        ],
        const Divider(height: 32),
        _LinkTile('Report card page, sharing and badge', m.reportCardUrl),
        _LinkTile('Full record on Congress.gov', m.congressGovUrl),
        if (m.url != null && m.url!.isNotEmpty)
          _LinkTile('Official website', m.url!),
      ],
    );
  }
}

class _SubjectCard extends StatelessWidget {
  const _SubjectCard({
    required this.graded,
    required this.subject,
    required this.weight,
    required this.detail,
    this.extra,
  });

  final Graded graded;
  final Subject subject;
  final int weight;
  final String detail;
  final Widget? extra;

  @override
  Widget build(BuildContext context) {
    final letter = graded.letterFor(subject);
    final score = graded.scores[subject];
    final color = gradeColor(context, letter[0]);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(subject.label,
                          style: Theme.of(context).textTheme.titleMedium),
                      Tag('$weight% of grade'),
                    ],
                  ),
                ),
                GradeBadge(letter,
                    size: 40, label: '${subject.label} grade $letter'),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (score ?? 0) / 100,
                minHeight: 8,
                color: color,
                backgroundColor: color.withOpacity(0.15),
              ),
            ),
            const SizedBox(height: 10),
            Text(detail),
            if (extra != null) ...[const SizedBox(height: 10), extra!],
          ],
        ),
      ),
    );
  }
}

/// How many sponsored bills reached each stage.
class _Stages extends StatelessWidget {
  const _Stages(this.bills);

  final Bills bills;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final stage in stageNames.entries)
          Expanded(
            child: Column(
              children: [
                Text('${bills.stages[stage.key] ?? 0}',
                    style: text.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700)),
                Text(stage.value,
                    textAlign: TextAlign.center, style: text.labelSmall),
              ],
            ),
          ),
      ],
    );
  }
}

class _LinkTile extends StatelessWidget {
  const _LinkTile(this.label, this.url);

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      trailing: const Icon(Icons.open_in_new, size: 18),
      onTap: () => openUrl(url),
    );
  }
}
