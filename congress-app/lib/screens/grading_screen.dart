import 'package:flutter/material.dart';

import '../grading.dart';
import '../store.dart';
import '../widgets.dart';

const _methodologyUrl = 'https://congressreportcard.org/methodology.html';

/// The site's "Adjust grading" panel and its summary of how grades are
/// calculated.
class GradingScreen extends StatelessWidget {
  const GradingScreen({super.key, required this.store});

  final ReportStore store;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Grading')),
      body: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final hasBills = store.report?.hasBills ?? true;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text('Adjust grading', style: text.titleLarge),
              const SizedBox(height: 8),
              const Text(
                'The grade is a weighted average of three scores. Change '
                'the weights to match what matters to you. They always add '
                'up to 100, so moving one adjusts the other two.',
              ),
              const SizedBox(height: 8),
              for (final subject in Subject.values)
                _WeightSlider(
                  subject: subject,
                  value: store.weights[subject],
                  onChanged: subject == Subject.attendance || hasBills
                      ? (v) => store.setWeight(subject, v)
                      : null,
                ),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: store.weights == defaultWeights
                      ? null
                      : store.resetWeights,
                  child: const Text('Reset to defaults'),
                ),
              ),
              const Divider(height: 40),
              Text('How grades are calculated', style: text.titleLarge),
              const _Method(
                'Vote attendance',
                'This is the share of roll-call votes the member cast while '
                    'in office. Voting "present" counts as attending. 100% '
                    'attendance scores 100 points and 85% or lower scores 0, '
                    'on a straight line in between. By custom the Speaker of '
                    'the House votes only occasionally, so the votes they '
                    "skip as Speaker aren't counted against them. Delegates "
                    'from DC and the territories are counted only on the '
                    'votes they are allowed to cast.',
              ),
              const _Method(
                'Bills written',
                'Bills and joint resolutions the member sponsored, with '
                    'points for how far each one got: introduced (1), acted '
                    'on in committee (3), passed a chamber (6), became law '
                    '(10). The member is ranked against their own chamber: '
                    'the top member scores 100, the chamber average scores '
                    '75 (a C) and the lowest scores 50. Simple resolutions, '
                    "such as commemorations, don't count.",
              ),
              const _Method(
                'Bills supported',
                'The number of bills and joint resolutions the member '
                    'cosponsored, ranked within their chamber the same way: '
                    '100 for the top member, 75 for the average, 50 for the '
                    'lowest.',
              ),
              const _Method(
                'Letter grade',
                'A is 93 and up, A− 90 and up, B+ 87 and up, B 83 and up, '
                    'B− 80 and up, and so on down to F below 60. A member '
                    'who joined partway through the Congress gets a partial '
                    'term label. Their bill counts cover less time, so read '
                    'those grades with care.',
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => openUrl(_methodologyUrl),
                  icon: const Icon(Icons.open_in_new, size: 18),
                  label: const Text('Read the full methodology'),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _WeightSlider extends StatelessWidget {
  const _WeightSlider({
    required this.subject,
    required this.value,
    required this.onChanged,
  });

  final Subject subject;
  final int value;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(subject.label, style: text.titleSmall),
              Text('$value', style: text.titleSmall),
            ],
          ),
        ),
        Slider(
          value: value.toDouble(),
          max: weightTotal.toDouble(),
          divisions: weightTotal ~/ weightStep,
          label: '$value',
          semanticFormatterCallback: (v) =>
              '${subject.label} weight ${v.round()}',
          onChanged: onChanged == null ? null : (v) => onChanged!(v.round()),
        ),
      ],
    );
  }
}

class _Method extends StatelessWidget {
  const _Method(this.title, this.body);

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(body),
        ],
      ),
    );
  }
}
