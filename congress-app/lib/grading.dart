import 'models.dart';

/// The grading rules. They repeat `GRADING` in the site's `site/app.js`
/// (and `build_pages.py`); change all of them together.
const defaultWeights = Weights(attendance: 40, sponsored: 35, cosponsored: 25);
const attendanceFloor = 0.85; // attendance at or below this scores 0
const stagePoints = {'introduced': 1, 'committee': 3, 'passed': 6, 'law': 10};
const letterCutoffs = <(int, String)>[
  (93, 'A'),
  (90, 'A-'),
  (87, 'B+'),
  (83, 'B'),
  (80, 'B-'),
  (77, 'C+'),
  (73, 'C'),
  (70, 'C-'),
  (67, 'D+'),
  (63, 'D'),
  (60, 'D-'),
  (0, 'F'),
];
const partialTerm = 0.5; // eligible for under half the votes → partial term
// Bill scores come from chamber percentile ranks, mapped onto
// percentileFloor..100 so the chamber average earns a C, not an F.
const percentileFloor = 50.0;

const weightTotal = 100;
const weightStep = 5;
const noGrade = '—';

/// The three parts of the grade, in the order the site lists them.
enum Subject {
  attendance('Vote attendance'),
  sponsored('Bills written'),
  cosponsored('Bills supported');

  const Subject(this.label);
  final String label;
}

class Weights {
  const Weights({
    required this.attendance,
    required this.sponsored,
    required this.cosponsored,
  });

  final int attendance;
  final int sponsored;
  final int cosponsored;

  int operator [](Subject s) => switch (s) {
        Subject.attendance => attendance,
        Subject.sponsored => sponsored,
        Subject.cosponsored => cosponsored,
      };

  Weights _replace(Map<Subject, int> v) => Weights(
        attendance: v[Subject.attendance] ?? attendance,
        sponsored: v[Subject.sponsored] ?? sponsored,
        cosponsored: v[Subject.cosponsored] ?? cosponsored,
      );

  /// The three weights always add up to [weightTotal]. Changing one shares
  /// what is left between the other two, keeping their ratio (an even split
  /// if both are 0).
  Weights withWeight(Subject subject, int value) {
    final others = Subject.values.where((s) => s != subject).toList();
    final a = others[0], b = others[1];
    final rest = weightTotal - value, sum = this[a] + this[b];
    final share = sum == 0 ? rest / 2 : rest * this[a] / sum;
    final first = (share / weightStep).round() * weightStep;
    return _replace({subject: value, a: first, b: rest - first});
  }

  bool get isValid =>
      attendance >= 0 &&
      sponsored >= 0 &&
      cosponsored >= 0 &&
      attendance + sponsored + cosponsored == weightTotal;

  List<int> toList() => [attendance, sponsored, cosponsored];

  @override
  bool operator ==(Object other) =>
      other is Weights &&
      other.attendance == attendance &&
      other.sponsored == sponsored &&
      other.cosponsored == cosponsored;

  @override
  int get hashCode => Object.hash(attendance, sponsored, cosponsored);
}

String letterOf(double score) =>
    letterCutoffs.firstWhere((c) => score >= c.$1).$2;

String percent(double fraction) => '${(fraction * 100).toStringAsFixed(1)}%';

/// One member with the grade worked out for the current weights.
class Graded {
  Graded({
    required this.member,
    required this.attendance,
    required this.percentiles,
    required this.scores,
    required this.partial,
    required this.score,
  });

  final Member member;

  /// The share of roll calls the member voted on, or null with no votes.
  final double? attendance;

  /// Chamber percentile rank (0–100) for the two bill subjects.
  final Map<Subject, double?> percentiles;

  /// The 0–100 score for each subject, or null where there is no data.
  final Map<Subject, double?> scores;
  final bool partial;
  final double? score;

  String get grade => score == null ? noGrade : letterOf(score!);

  /// `A`, `B`, `C`, `D`, `F` or the dash, without the plus or minus.
  String get band => grade[0];

  String letterFor(Subject s) =>
      scores[s] == null ? noGrade : letterOf(scores[s]!);
}

int legislativePoints(Bills bills) => bills.stages.entries
    .fold(0, (sum, e) => sum + e.value * (stagePoints[e.key] ?? 0));

/// Percentile rank within the member's chamber (ties share the midpoint).
double? Function(Member) _percentileScorer(
    List<Member> members, num? Function(Member) value) {
  final byChamber = <String, List<num>>{};
  for (final m in members) {
    final v = value(m);
    if (v != null) (byChamber[m.chamber] ??= []).add(v);
  }
  return (m) {
    final v = value(m), list = byChamber[m.chamber];
    if (v == null || list == null || list.length < 2) return null;
    var below = 0, equal = 0;
    for (final x in list) {
      if (x < v) {
        below++;
      } else if (x == v) {
        equal++;
      }
    }
    final rank = (below + (equal - 1) / 2) / (list.length - 1) * 100;
    return rank.clamp(0, 100).toDouble();
  };
}

double? _fromPercentile(double? p) =>
    p == null ? null : percentileFloor + p * (100 - percentileFloor) / 100;

List<Graded> gradeMembers(List<Member> members, Weights weights) {
  final sponsorRank = _percentileScorer(
      members, (m) => m.bills == null ? null : legislativePoints(m.bills!));
  final cosponsorRank = _percentileScorer(members, (m) => m.bills?.cosponsored);

  return members.map((m) {
    final v = m.votes;
    final attendance = v.eligible == 0 ? null : 1 - v.missed / v.eligible;
    final percentiles = {
      Subject.sponsored: sponsorRank(m),
      Subject.cosponsored: cosponsorRank(m),
    };
    final scores = <Subject, double?>{
      Subject.attendance: attendance == null
          ? null
          : ((attendance - attendanceFloor) / (1 - attendanceFloor) * 100)
              .clamp(0, 100)
              .toDouble(),
      Subject.sponsored: _fromPercentile(percentiles[Subject.sponsored]),
      Subject.cosponsored: _fromPercentile(percentiles[Subject.cosponsored]),
    };
    var total = 0.0, weight = 0;
    for (final s in Subject.values) {
      final score = scores[s];
      if (score != null && weights[s] > 0) {
        total += score * weights[s];
        weight += weights[s];
      }
    }
    return Graded(
      member: m,
      attendance: attendance,
      percentiles: percentiles,
      scores: scores,
      partial: !m.isDelegate && v.eligible < v.chamberTotal * partialTerm,
      score: weight == 0 ? null : total / weight,
    );
  }).toList();
}
