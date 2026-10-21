import 'package:flutter/material.dart';

import '../compare.dart';
import '../grading.dart';
import '../models.dart';
import '../store.dart';
import '../widgets.dart';

/// Every state's delegation, ranked by the average score of its members.
/// DC and the territories, with one delegate each, are listed after.
class StatesScreen extends StatefulWidget {
  const StatesScreen({super.key, required this.store});

  final ReportStore store;

  @override
  State<StatesScreen> createState() => _StatesScreenState();
}

class _StatesScreenState extends State<StatesScreen> {
  late Future<void> _future = widget.store.ensureLoaded();

  Future<void> _reload() {
    final future = widget.store.load(refresh: true);
    setState(() => _future = future);
    return future.catchError((Object _) {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('States')),
      body: AsyncView<void>(
        future: _future,
        onRetry: _reload,
        builder: (context, _) => ListenableBuilder(
          listenable: widget.store,
          builder: (context, _) => _list(context),
        ),
      ),
    );
  }

  Widget _list(BuildContext context) {
    final compare = widget.store.compare;
    final others = [
      for (final entry in compare.byState.entries)
        if (delegateStates.contains(entry.key)) ...entry.value
    ];
    final small = Theme.of(context).textTheme.bodySmall;
    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              "Each state's senators and representatives, ranked by the "
              'average score of the whole delegation.',
            ),
          ),
          for (final (i, state) in compare.states.indexed)
            ListTile(
              leading: SizedBox(
                width: 28,
                child: Text('${i + 1}', style: small),
              ),
              title: Text(stateName(state)),
              subtitle: Text(
                '${plural(compare.byState[state]!.length, 'member')} · average '
                '${compare.average(state).toStringAsFixed(1)}',
              ),
              trailing: GradeBadge(letterOf(compare.average(state)), size: 40),
              onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => StateScreen(store: widget.store, state: state),
              )),
            ),
          if (others.isNotEmpty) ...[
            const Divider(height: 32),
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                'DC and the territories each send one non-voting delegate to '
                'the House. They are not ranked with the states.',
              ),
            ),
            for (final g in others) MemberTile(store: widget.store, graded: g),
          ],
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

/// One state's delegation: a summary and every member, best score first.
class StateScreen extends StatelessWidget {
  const StateScreen({super.key, required this.store, required this.state});

  final ReportStore store;
  final String state;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final compare = store.compare;
        final members = compare.byState[state] ?? const <Graded>[];
        return Scaffold(
          appBar: AppBar(title: Text(stateName(state))),
          body: ListView(
            children: [
              for (final p in compare.aboutState(state))
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: Text(p),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
                child: Text('Every member from ${stateName(state)}',
                    style: Theme.of(context).textTheme.titleMedium),
              ),
              for (final g in members) MemberTile(store: store, graded: g),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }
}
