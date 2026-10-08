/// The data classes for the site's `data/members.js`, plus the wording the
/// site uses for seats, parties and states.
library;

const stateNames = <String, String>{
  'AL': 'Alabama',
  'AK': 'Alaska',
  'AS': 'American Samoa',
  'AZ': 'Arizona',
  'AR': 'Arkansas',
  'CA': 'California',
  'CO': 'Colorado',
  'CT': 'Connecticut',
  'DE': 'Delaware',
  'DC': 'District of Columbia',
  'FL': 'Florida',
  'GA': 'Georgia',
  'GU': 'Guam',
  'HI': 'Hawaii',
  'ID': 'Idaho',
  'IL': 'Illinois',
  'IN': 'Indiana',
  'IA': 'Iowa',
  'KS': 'Kansas',
  'KY': 'Kentucky',
  'LA': 'Louisiana',
  'ME': 'Maine',
  'MD': 'Maryland',
  'MA': 'Massachusetts',
  'MI': 'Michigan',
  'MN': 'Minnesota',
  'MS': 'Mississippi',
  'MO': 'Missouri',
  'MT': 'Montana',
  'NE': 'Nebraska',
  'NV': 'Nevada',
  'NH': 'New Hampshire',
  'NJ': 'New Jersey',
  'NM': 'New Mexico',
  'NY': 'New York',
  'NC': 'North Carolina',
  'ND': 'North Dakota',
  'MP': 'Northern Mariana Islands',
  'OH': 'Ohio',
  'OK': 'Oklahoma',
  'OR': 'Oregon',
  'PA': 'Pennsylvania',
  'PR': 'Puerto Rico',
  'RI': 'Rhode Island',
  'SC': 'South Carolina',
  'SD': 'South Dakota',
  'TN': 'Tennessee',
  'TX': 'Texas',
  'UT': 'Utah',
  'VT': 'Vermont',
  'VI': 'U.S. Virgin Islands',
  'VA': 'Virginia',
  'WA': 'Washington',
  'WV': 'West Virginia',
  'WI': 'Wisconsin',
  'WY': 'Wyoming',
};

/// Delegates and the Resident Commissioner vote only in the Committee of the
/// Whole, so they are eligible for far fewer roll calls.
const delegateStates = {'DC', 'PR', 'GU', 'AS', 'VI', 'MP'};

/// The Speaker of the House votes only at their discretion.
const speakerId = 'J000299';

const stageNames = <String, String>{
  'introduced': 'Introduced',
  'committee': 'Committee action',
  'passed': 'Passed a chamber',
  'law': 'Became law',
};

String stateName(String code) => stateNames[code] ?? code;

class Votes {
  const Votes({
    required this.eligible,
    required this.missed,
    required this.chamberTotal,
  });

  factory Votes.fromJson(Map<String, dynamic> json) => Votes(
        eligible: json['eligible'] as int? ?? 0,
        missed: json['missed'] as int? ?? 0,
        chamberTotal: json['chamberTotal'] as int? ?? 0,
      );

  final int eligible;
  final int missed;
  final int chamberTotal;
}

class NotableBill {
  const NotableBill({
    required this.id,
    required this.title,
    required this.stage,
    required this.url,
  });

  factory NotableBill.fromJson(Map<String, dynamic> json) => NotableBill(
        id: json['id'] as String? ?? '',
        title: json['title'] as String? ?? '',
        stage: json['stage'] as String? ?? '',
        url: json['url'] as String? ?? '',
      );

  final String id;
  final String title;
  final String stage;
  final String url;
}

class Bills {
  const Bills({
    required this.sponsored,
    required this.stages,
    required this.resolutions,
    required this.cosponsored,
    required this.notable,
  });

  factory Bills.fromJson(Map<String, dynamic> json) => Bills(
        sponsored: json['sponsored'] as int? ?? 0,
        stages: (json['stages'] as Map<String, dynamic>? ?? {})
            .map((k, v) => MapEntry(k, v as int)),
        resolutions: json['resolutions'] as int? ?? 0,
        cosponsored: json['cosponsored'] as int? ?? 0,
        notable: (json['notable'] as List? ?? [])
            .map((n) => NotableBill.fromJson(n as Map<String, dynamic>))
            .toList(),
      );

  final int sponsored;

  /// How many sponsored bills reached each stage, keyed as in [stageNames].
  final Map<String, int> stages;
  final int resolutions;
  final int cosponsored;
  final List<NotableBill> notable;
}

class Member {
  const Member({
    required this.id,
    required this.name,
    required this.last,
    required this.chamber,
    required this.state,
    required this.party,
    required this.votes,
    this.district,
    this.url,
    this.bills,
  });

  factory Member.fromJson(Map<String, dynamic> json) => Member(
        id: json['id'] as String,
        name: json['name'] as String,
        last: json['last'] as String? ?? json['name'] as String,
        chamber: json['chamber'] as String,
        state: json['state'] as String,
        district: json['district'] as int?,
        party: json['party'] as String? ?? 'Independent',
        url: json['url'] as String?,
        votes: Votes.fromJson(json['votes'] as Map<String, dynamic>? ?? {}),
        bills: json['bills'] == null
            ? null
            : Bills.fromJson(json['bills'] as Map<String, dynamic>),
      );

  final String id;
  final String name;
  final String last;
  final String chamber;
  final String state;
  final int? district;
  final String party;
  final String? url;
  final Votes votes;

  /// Null when the data was built without bill data.
  final Bills? bills;

  bool get isSenator => chamber == 'Senate';
  bool get isDelegate => !isSenator && delegateStates.contains(state);

  /// The state and district as the ZIP code table writes it, e.g. `GA5`,
  /// with 0 for an at-large seat.
  String get districtKey => '$state${district ?? 0}';

  String get seat {
    if (isSenator) return 'Senator · $state';
    if (isDelegate) return 'Delegate · $state';
    final d = district ?? 0;
    return d == 0 ? 'Rep. · $state At-large' : 'Rep. · $state-$d';
  }

  String get photoUrl =>
      'https://unitedstates.github.io/images/congress/225x275/$id.jpg';
  String get reportCardUrl => 'https://congressreportcard.org/members/$id.html';
  String get congressGovUrl => 'https://www.congress.gov/member/$id';
}

class Report {
  const Report({
    required this.congress,
    required this.generated,
    required this.hasBills,
    required this.members,
  });

  factory Report.fromJson(Map<String, dynamic> json) => Report(
        congress: json['congress'] as int? ?? 0,
        generated: json['generated'] as String? ?? '',
        hasBills: json['hasBills'] as bool? ?? false,
        members: (json['members'] as List? ?? [])
            .map((m) => Member.fromJson(m as Map<String, dynamic>))
            .toList(),
      );

  final int congress;
  final String generated;
  final bool hasBills;
  final List<Member> members;

  String get congressLabel =>
      '${congress}th Congress${congress == 119 ? ' · 2025–2027' : ''}';
}

/// `GA5` → `GA-5`, `AK0` → `AK At-large`, `DC0` → `District of Columbia`.
String districtLabel(String key) {
  final state = key.substring(0, 2);
  final number = int.tryParse(key.substring(2)) ?? 0;
  if (delegateStates.contains(state)) return stateName(state);
  return number == 0 ? '$state At-large' : '$state-$number';
}
