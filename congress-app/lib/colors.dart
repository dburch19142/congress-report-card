import 'package:flutter/material.dart';

/// The site's navy accent (`--accent` in `site/styles.css`).
const accentNavy = Color(0xFF1F3A5F);

bool _dark(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark;

/// The site's colour for a grade band (`A`–`F`), in its light or dark shade.
Color gradeColor(BuildContext context, String band) {
  final dark = _dark(context);
  return switch (band) {
    'A' => dark ? const Color(0xFF5CC48D) : const Color(0xFF1D7A4B),
    'B' => dark ? const Color(0xFF9CCC6A) : const Color(0xFF4F8A2C),
    'C' => dark ? const Color(0xFFE3BF4F) : const Color(0xFFB58A12),
    'D' => dark ? const Color(0xFFEC9A5B) : const Color(0xFFC4631C),
    'F' => dark ? const Color(0xFFEC7D74) : const Color(0xFFB3372F),
    _ => Theme.of(context).colorScheme.outline,
  };
}

Color partyColor(BuildContext context, String party) {
  final dark = _dark(context);
  return switch (party) {
    'Democrat' => dark ? const Color(0xFF7FA6E6) : const Color(0xFF2F5FA7),
    'Republican' => dark ? const Color(0xFFE98A82) : const Color(0xFFB3372F),
    _ => dark ? const Color(0xFFB3A3E0) : const Color(0xFF6B5A9A),
  };
}
