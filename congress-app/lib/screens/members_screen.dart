import 'package:flutter/material.dart';

import '../colors.dart';
import '../grading.dart';
import '../models.dart';
import '../store.dart';
import '../widgets.dart';

const _bands = ['A', 'B', 'C', 'D', 'F'];

/// Every member with their grade: search by name, state or ZIP code, filter
/// by chamber, state, party and grade, and sort.
class MembersScreen extends StatefulWidget {
  const MembersScreen({super.key, required this.store});

  final ReportStore store;

  @override
  State<MembersScreen> createState() => _MembersScreenState();
}

class _MembersScreenState extends State<MembersScreen> {
  final _search = TextEditingController();
  late Future<void> _future = widget.store.load();

  String _query = '';
  String _chamber = '';
  String _state = '';
  String _party = '';
  String _band = '';
  SortOrder _sort = SortOrder.grade;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _reload() {
    final future = widget.store.load(refresh: true);
    setState(() => _future = future);
    return future.catchError((Object _) {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Congress Report Card')),
      body: AsyncView<void>(
        future: _future,
        onRetry: _reload,
        builder: (context, _) => ListenableBuilder(
          listenable: widget.store,
          builder: (context, _) => _content(context),
        ),
      ),
    );
  }

  Widget _content(BuildContext context) {
    final store = widget.store;
    final query = _query.trim();
    final zip = store.zipSearch(query);
    final base = store.filtered(
      query: query,
      chamber: _chamber.isEmpty ? null : _chamber,
      state: _state.isEmpty ? null : _state,
      party: _party.isEmpty ? null : _party,
      sort: _sort,
      zip: zip,
    );
    final shown =
        _band.isEmpty ? base : base.where((g) => g.band == _band).toList();
    final total = store.graded.length;
    final states = {for (final g in store.graded) g.member.state}.toList()
      ..sort((a, b) => stateName(a).compareTo(stateName(b)));

    return Column(
      children: [
        SearchField(
          controller: _search,
          hint: 'Name, state or ZIP code',
          onChanged: (text) => setState(() => _query = text),
        ),
        SizedBox(
          height: 40,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            children: [
              _FilterMenu(
                label: 'Both chambers',
                value: _chamber,
                options: const {'House': 'House', 'Senate': 'Senate'},
                onChanged: (v) => setState(() => _chamber = v),
              ),
              _FilterMenu(
                label: 'All states',
                value: _state,
                options: {for (final s in states) s: stateName(s)},
                onChanged: (v) => setState(() => _state = v),
              ),
              _FilterMenu(
                label: 'All parties',
                value: _party,
                options: const {
                  'Democrat': 'Democrat',
                  'Republican': 'Republican',
                  'Independent': 'Independent',
                },
                onChanged: (v) => setState(() => _party = v),
              ),
              _FilterMenu(
                label: 'Sort',
                value: _sort.name,
                required: true,
                options: {for (final s in SortOrder.values) s.name: s.label},
                onChanged: (v) =>
                    setState(() => _sort = SortOrder.values.byName(v)),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _reload,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              itemCount: shown.length + 1,
              itemBuilder: (context, i) {
                if (i > 0) {
                  return MemberTile(store: store, graded: shown[i - 1]);
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _GradeSummary(
                      members: base,
                      selected: _band,
                      onSelected: (band) =>
                          setState(() => _band = _band == band ? '' : band),
                    ),
                    if (zip != null) _ZipNote(zip),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
                      child: Text(
                        '${shown.length} of $total members'
                        '${_band.isEmpty ? '' : ' · showing $_band grades'}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}

/// A chip that opens a menu. Unless [required], the menu starts with
/// [label], which clears the filter.
class _FilterMenu extends StatelessWidget {
  const _FilterMenu({
    required this.label,
    required this.value,
    required this.options,
    required this.onChanged,
    this.required = false,
  });

  final String label;
  final String value;
  final Map<String, String> options;
  final ValueChanged<String> onChanged;
  final bool required;

  // PopupMenuButton treats a null value as "dismissed", so the entry that
  // clears the filter needs a value of its own.
  static const _all = '\u0000';

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final active = !required && value.isNotEmpty;
    final text = required
        ? '$label: ${options[value]}'
        : (active ? options[value] ?? value : label);
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: PopupMenuButton<String>(
        tooltip: label,
        initialValue: value.isEmpty ? _all : value,
        onSelected: (v) => onChanged(v == _all ? '' : v),
        itemBuilder: (_) => [
          if (!required) PopupMenuItem(value: _all, child: Text(label)),
          for (final e in options.entries)
            PopupMenuItem(value: e.key, child: Text(e.value)),
        ],
        child: Container(
          padding: const EdgeInsets.only(left: 12, right: 6),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: active ? scheme.secondaryContainer : null,
            border: Border.all(
                color: active ? scheme.secondaryContainer : scheme.outline),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(text, style: Theme.of(context).textTheme.labelLarge),
              const Icon(Icons.arrow_drop_down, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

/// How many of the listed members earned each letter. Tapping a letter
/// shows only those members; tapping it again shows everyone.
class _GradeSummary extends StatelessWidget {
  const _GradeSummary({
    required this.members,
    required this.selected,
    required this.onSelected,
  });

  final List<Graded> members;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final counts = {for (final b in _bands) b: 0};
    for (final g in members) {
      if (counts.containsKey(g.band)) counts[g.band] = counts[g.band]! + 1;
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
      child: Row(
        children: [
          for (final band in _bands)
            Expanded(
              child: _GradeCount(
                band: band,
                count: counts[band]!,
                selected: selected == band,
                onTap: () => onSelected(band),
              ),
            ),
        ],
      ),
    );
  }
}

class _GradeCount extends StatelessWidget {
  const _GradeCount({
    required this.band,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  final String band;
  final int count;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = gradeColor(context, band);
    return Semantics(
      button: true,
      selected: selected,
      label: 'Show only $band grades, $count '
          '${count == 1 ? 'member' : 'members'}',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: BoxDecoration(
              color: color.withOpacity(selected ? 0.22 : 0.08),
              border: Border.all(
                  color: selected ? color : Colors.transparent, width: 1.5),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              children: [
                Text(
                  band,
                  style: TextStyle(
                    color: color,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text('$count', style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ZipNote extends StatelessWidget {
  const _ZipNote(this.zip);

  final ZipSearch zip;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(zip.note),
          if (zip.offerAddressLookup)
            TextButton(
              style: TextButton.styleFrom(padding: EdgeInsets.zero),
              onPressed: () => openUrl(addressLookupUrl),
              child: const Text('Look up yours by street address'),
            ),
        ],
      ),
    );
  }
}
