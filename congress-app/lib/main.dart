import 'package:flutter/material.dart';

import 'api.dart';
import 'colors.dart';
import 'screens/about_screen.dart';
import 'screens/digest_screen.dart';
import 'screens/grading_screen.dart';
import 'screens/members_screen.dart';
import 'store.dart';

void main() {
  runApp(ReportCardApp(data: ReportApi()));
}

class ReportCardApp extends StatelessWidget {
  const ReportCardApp({super.key, required this.data});

  final ReportData data;

  ThemeData _theme(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: accentNavy,
      brightness: brightness,
    );
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      appBarTheme: const AppBarTheme(
        backgroundColor: accentNavy,
        foregroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Congress Report Card',
      debugShowCheckedModeBanner: false,
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      home: HomeShell(data: data),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.data});

  final ReportData data;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  late final _store = ReportStore(widget.data);
  int _tab = 0;

  @override
  void dispose() {
    _store.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // IndexedStack keeps each tab's scroll position and loaded data.
      body: IndexedStack(
        index: _tab,
        children: [
          MembersScreen(store: _store),
          DigestScreen(store: _store),
          GradingScreen(store: _store),
          AboutScreen(store: _store),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.groups_outlined),
            selectedIcon: Icon(Icons.groups),
            label: 'Members',
          ),
          NavigationDestination(
            icon: Icon(Icons.article_outlined),
            selectedIcon: Icon(Icons.article),
            label: 'Digest',
          ),
          NavigationDestination(
            icon: Icon(Icons.tune),
            label: 'Grading',
          ),
          NavigationDestination(
            icon: Icon(Icons.info_outline),
            selectedIcon: Icon(Icons.info),
            label: 'About',
          ),
        ],
      ),
    );
  }
}
