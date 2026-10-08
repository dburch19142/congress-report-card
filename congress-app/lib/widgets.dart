import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'colors.dart';
import 'grading.dart';
import 'models.dart';
import 'screens/member_screen.dart';
import 'store.dart';

/// Shows a spinner while [future] loads, an error with a retry button if it
/// fails, and [builder] once it has data.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    super.key,
    required this.future,
    required this.onRetry,
    required this.builder,
  });

  final Future<T> future;
  final VoidCallback onRetry;
  final Widget Function(BuildContext context, T data) builder;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off, size: 40),
                  const SizedBox(height: 12),
                  const Text(
                    "Couldn't load the latest data. Check your connection "
                    'and try again.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: onRetry,
                    child: const Text('Try again'),
                  ),
                ],
              ),
            ),
          );
        }
        return builder(context, snapshot.data as T);
      },
    );
  }
}

class SearchField extends StatelessWidget {
  const SearchField({
    super.key,
    required this.controller,
    required this.hint,
    required this.onChanged,
  });

  final TextEditingController controller;
  final String hint;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        textInputAction: TextInputAction.search,
        decoration: InputDecoration(
          hintText: hint,
          prefixIcon: const Icon(Icons.search),
          suffixIcon: controller.text.isEmpty
              ? null
              : IconButton(
                  tooltip: 'Clear search',
                  icon: const Icon(Icons.clear),
                  onPressed: () {
                    controller.clear();
                    onChanged('');
                  },
                ),
          isDense: true,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
    );
  }
}

/// The letter grade in a rounded square of the grade's colour.
class GradeBadge extends StatelessWidget {
  const GradeBadge(this.grade, {super.key, this.size = 48, this.label});

  final String grade;
  final double size;

  /// What a screen reader says in place of the bare letter.
  final String? label;

  @override
  Widget build(BuildContext context) {
    final color = gradeColor(context, grade[0]);
    return Semantics(
      label: label ?? 'Grade $grade',
      excludeSemantics: true,
      child: Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: color.withOpacity(0.14),
          border: Border.all(color: color, width: 1.5),
          borderRadius: BorderRadius.circular(size / 5),
        ),
        child: Text(
          grade,
          style: TextStyle(
            color: color,
            fontSize: size * 0.42,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

/// The member's official portrait, or a plain tile when there isn't one.
class MemberPhoto extends StatelessWidget {
  const MemberPhoto(this.member, {super.key, this.width = 44});

  final Member member;
  final double width;

  @override
  Widget build(BuildContext context) {
    final height = width * 275 / 225;
    final fallback = Container(
      width: width,
      height: height,
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Icon(Icons.person,
          size: width * 0.6, color: Theme.of(context).colorScheme.outline),
    );
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: Image.network(
        member.photoUrl,
        width: width,
        height: height,
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, __, ___) => fallback,
        loadingBuilder: (_, child, progress) =>
            progress == null ? child : fallback,
      ),
    );
  }
}

class Tag extends StatelessWidget {
  const Tag(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: Theme.of(context)
            .textTheme
            .labelSmall
            ?.copyWith(color: scheme.onSurfaceVariant),
      ),
    );
  }
}

/// "Democrat · Rep. · GA-5", with the party in its colour.
class PartyAndSeat extends StatelessWidget {
  const PartyAndSeat(this.member, {super.key});

  final Member member;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall;
    return Text.rich(
      TextSpan(children: [
        TextSpan(
          text: member.party,
          style: TextStyle(
            color: partyColor(context, member.party),
            fontWeight: FontWeight.w600,
          ),
        ),
        TextSpan(text: ' · ${member.seat}'),
      ]),
      style: style,
    );
  }
}

/// One row of the members list.
class MemberTile extends StatelessWidget {
  const MemberTile({super.key, required this.store, required this.graded});

  final ReportStore store;
  final Graded graded;

  @override
  Widget build(BuildContext context) {
    final m = graded.member;
    final attendance = graded.attendance;
    final small = Theme.of(context).textTheme.bodySmall;
    return InkWell(
      onTap: () => openMember(context, store, m.id),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            MemberPhoto(m),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(m.name,
                      style: Theme.of(context)
                          .textTheme
                          .titleSmall
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  PartyAndSeat(m),
                  Wrap(
                    spacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        attendance == null
                            ? 'No votes recorded'
                            : '${percent(attendance)} of votes',
                        style: small,
                      ),
                      if (graded.partial) const Tag('Partial term'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            GradeBadge(graded.grade),
          ],
        ),
      ),
    );
  }
}

void openMember(BuildContext context, ReportStore store, String id) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => MemberScreen(store: store, memberId: id),
    ),
  );
}

/// Opens a web page in the browser.
Future<void> openUrl(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null) return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}
