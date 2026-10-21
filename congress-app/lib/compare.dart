import 'grading.dart';
import 'models.dart';

/// How members compare with their chamber, party and state. The wording
/// follows the "How [member] compares" section of the site's member pages
/// (`comparison` in `build_pages.py`).

String ordinal(int n) {
  final teen = n % 100 >= 10 && n % 100 <= 20;
  final suffix = teen
      ? 'th'
      : switch (n % 10) { 1 => 'st', 2 => 'nd', 3 => 'rd', _ => 'th' };
  return '$n$suffix';
}

/// 4526 → "4,526".
String count(int n) => n
    .toString()
    .replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

String plural(int n, String word) => '$n $word${n == 1 ? '' : 's'}';

String possessive(String name) => name.endsWith('s') ? "$name'" : "$name's";

/// 'a B', 'an A-', 'an F'.
String aGrade(String grade) => '${'AF'.contains(grade[0]) ? 'an' : 'a'} $grade';

double median(List<num> values) {
  if (values.isEmpty) return 0;
  final sorted = [...values]..sort();
  final mid = sorted.length ~/ 2;
  return sorted.length.isOdd
      ? sorted[mid].toDouble()
      : (sorted[mid - 1] + sorted[mid]) / 2;
}

double mean(Iterable<num> values) =>
    values.isEmpty ? 0 : values.fold<num>(0, (a, b) => a + b) / values.length;

/// The typical member of one chamber.
class ChamberMedians {
  const ChamberMedians({
    required this.attendance,
    required this.sponsored,
    required this.cosponsored,
    required this.score,
  });

  final double attendance;
  final double sponsored;
  final double cosponsored;
  final double score;
}

/// Rankings and medians for the whole of Congress under the current weights.
class Comparisons {
  Comparisons(List<Graded> graded) {
    final withGrade = graded.where((g) => g.score != null).toList()
      ..sort((a, b) => b.score!.compareTo(a.score!));
    for (final g in withGrade) {
      final m = g.member;
      (byChamber[m.chamber] ??= []).add(g);
      (byParty['${m.chamber}|${m.party}'] ??= []).add(g);
      (byState[m.state] ??= []).add(g);
    }
    for (final entry in byChamber.entries) {
      // Full-term voting members set the "typical member" figures.
      final full =
          entry.value.where((g) => !g.partial && !g.member.isDelegate).toList();
      final source = full.isEmpty ? entry.value : full;
      medians[entry.key] = ChamberMedians(
        attendance: median([
          for (final g in source)
            if (g.attendance != null) g.attendance!
        ]),
        sponsored: median([
          for (final g in source)
            if (g.member.bills != null) g.member.bills!.sponsored
        ]),
        cosponsored: median([
          for (final g in source)
            if (g.member.bills != null) g.member.bills!.cosponsored
        ]),
        score: median([for (final g in entry.value) g.score!]),
      );
    }
    states = byState.keys.where((s) => !delegateStates.contains(s)).toList()
      ..sort((a, b) => average(b).compareTo(average(a)));
  }

  /// Graded members, highest score first.
  final byChamber = <String, List<Graded>>{};
  final byParty = <String, List<Graded>>{};
  final byState = <String, List<Graded>>{};
  final medians = <String, ChamberMedians>{};

  /// State codes (not DC or the territories), best average first.
  late final List<String> states;

  double average(String state) =>
      mean([for (final g in byState[state] ?? const <Graded>[]) g.score!]);

  double get nationalAverage => mean([
        for (final list in byChamber.values)
          for (final g in list) g.score!
      ]);

  int stateRank(String state) => states.indexOf(state) + 1;

  /// Paragraphs comparing [g] with their chamber, party and state, or none
  /// when the member has no grade.
  List<String> about(Graded g) {
    if (g.score == null) return const [];
    final m = g.member;
    final last = m.last;
    final senate = m.isSenator;
    final peers = senate ? 'senators' : 'House members';
    final peer = senate ? 'senator' : 'House member';
    final out = <String>[];

    final ranked = byChamber[m.chamber]!;
    final rank = ranked.indexOf(g) + 1;
    // Rounded up, so the share is never overstated.
    final top = (rank / ranked.length * 100).ceil();
    var text = "${possessive(last)} overall score of ${g.score!.round()} ranks "
        '${ordinal(rank)} of ${ranked.length} $peers'
        '${top <= 50 ? ', in the top $top%' : ''}.';
    final party = byParty['${m.chamber}|${m.party}']!;
    if (party.length > 1) {
      final word = switch (m.party) {
        'Democrat' => 'Democrats',
        'Republican' => 'Republicans',
        _ => 'independents',
      };
      text += ' Among the ${party.length} $word in the ${m.chamber}, $last '
          'ranks ${ordinal(party.indexOf(g) + 1)}.';
    }
    text += ' The median score in the ${m.chamber} is '
        '${medians[m.chamber]!.score.round()}.';
    if (m.isDelegate) {
      text += ' Delegates are ranked with the rest of the House, but they are '
          'eligible for far fewer votes, so each missed vote moves their '
          'attendance score more.';
    }
    out.add(text);

    final delegation = byState[m.state] ?? const <Graded>[];
    if (delegation.length > 1) {
      final senators = delegation.where((x) => x.member.isSenator).length;
      final reps = delegation.length - senators;
      final seats = [
        if (senators > 0) plural(senators, 'senator'),
        if (reps > 0) plural(reps, 'representative'),
      ];
      final avg = average(m.state);
      final best = delegation.first;
      out.add('${stateName(m.state)} has ${delegation.length} members of '
          'Congress (${seats.join(' and ')}). Their average score is '
          '${avg.round()}, ${aGrade(letterOf(avg))}. '
          '${identical(best, g) ? '$last has the highest score in the delegation.' : '$last has the ${ordinal(delegation.indexOf(g) + 1)}-highest score in the delegation; the highest is ${best.member.name}, with ${aGrade(best.grade)}.'}');
    }

    final med = medians[m.chamber]!;
    final v = m.votes;
    if (v.eligible > 0) {
      final diff = g.attendance! - med.attendance;
      final how = diff.abs() < 0.0025
          ? 'about the same as'
          : '${(diff.abs() * 100).toStringAsFixed(1)} points '
              '${diff > 0 ? 'above' : 'below'}';
      var line = '$last voted on ${percent(g.attendance!)} of the roll calls '
          'they were eligible for, $how the typical $peer '
          '(${percent(med.attendance)}).';
      if (v.missed == 0) {
        line += ' $last has not missed a roll-call vote this Congress.';
      }
      out.add(line);
    }

    final b = m.bills;
    if (b != null) {
      var line = '$last sponsored ${plural(b.sponsored, 'bill')} and '
          'cosponsored ${count(b.cosponsored)}; the typical $peer sponsored '
          '${med.sponsored.round()} and cosponsored ${med.cosponsored.round()}.';
      final law = b.stages['law'] ?? 0, passed = b.stages['passed'] ?? 0;
      if (law > 0) {
        line += ' Of ${possessive(last)} bills, $law became law.';
      } else if (passed > 0) {
        line += ' None has become law yet, but $passed passed at least one '
            'chamber.';
      }
      if (g.partial) {
        line += ' $last joined partway through this Congress, so these '
            'totals cover a shorter period.';
      }
      out.add(line);
    }
    return out;
  }

  /// Paragraphs describing one state's delegation.
  List<String> aboutState(String state) {
    final ms = byState[state] ?? const <Graded>[];
    if (ms.isEmpty) return const [];
    final name = stateName(state);
    final senators = ms.where((g) => g.member.isSenator).toList();
    final reps = ms.where((g) => !g.member.isSenator).toList();
    final seats = [
      if (senators.isNotEmpty) plural(senators.length, 'senator'),
      if (reps.isNotEmpty) plural(reps.length, 'representative'),
    ];
    final words = {
      'Democrat': 'Democrat',
      'Republican': 'Republican',
      'Independent': 'independent',
    };
    final split = [
      for (final p in words.keys)
        if (ms.any((g) => g.member.party == p))
          plural(ms.where((g) => g.member.party == p).length, words[p]!)
    ];
    final avg = average(state), national = nationalAverage;
    final missed = ms.fold<int>(0, (a, g) => a + g.member.votes.missed);
    final eligible = ms.fold<int>(0, (a, g) => a + g.member.votes.eligible);
    final sponsored =
        ms.fold<int>(0, (a, g) => a + (g.member.bills?.sponsored ?? 0));
    final laws =
        ms.fold<int>(0, (a, g) => a + (g.member.bills?.stages['law'] ?? 0));
    final out = [
      '$name sends ${ms.length} members to Congress: ${seats.join(' and ')}. '
          'The delegation is made up of ${_andList(split)}.',
      "The delegation's average score is ${avg.round()} out of 100, "
          '${aGrade(letterOf(avg))}. That ranks $name '
          '${ordinal(stateRank(state))} of the ${states.length} states, '
          '${avg > national + 0.5 ? 'above' : avg < national - 0.5 ? 'below' : 'about the same as'} '
          'the national average of ${national.round()}.',
      if (eligible > 0)
        'Together the delegation was eligible for ${count(eligible)} roll-call votes '
            'and missed ${count(missed)}, an attendance rate of '
            '${percent(1 - missed / eligible)}. Its members sponsored '
            '${count(sponsored)} bills and joint resolutions, and $laws of them '
            'became law.',
    ];
    if (senators.isNotEmpty && reps.isNotEmpty) {
      out.add("${possessive(name)} senators average "
          '${mean([for (final g in senators) g.score!]).round()} and its House '
          'members average ${mean([for (final g in reps) g.score!]).round()}. '
          'Each group is ranked only against its own chamber.');
    }
    return out;
  }
}

String _andList(List<String> items) => items.length < 2
    ? items.join()
    : '${items.sublist(0, items.length - 1).join(', ')} and ${items.last}';
