/// One of the site's articles, from `articles/articles.json`.
class Article {
  const Article({
    required this.title,
    required this.description,
    required this.date,
    required this.url,
  });

  factory Article.fromJson(Map<String, dynamic> json) => Article(
        title: json['title'] as String,
        description: json['description'] as String? ?? '',
        date: DateTime.parse(json['date'] as String),
        url: json['url'] as String,
      );

  /// The file lists the newest first; this keeps that order.
  static List<Article> listFromJson(List<dynamic> json) =>
      [for (final item in json) Article.fromJson(item as Map<String, dynamic>)];

  final String title;
  final String description;
  final DateTime date;
  final String url;

  static const _months = [
    'January', 'February', 'March', 'April', 'May', 'June', 'July', //
    'August', 'September', 'October', 'November', 'December',
  ];

  /// e.g. "October 21, 2026".
  String get dateLabel =>
      '${_months[date.month - 1]} ${date.day}, ${date.year}';
}
