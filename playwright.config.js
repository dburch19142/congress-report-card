// @ts-check
const { defineConfig, devices } = require('@playwright/test');

// Tests run against the live site by default. To test a local copy:
//   python -m http.server 8000 --directory site
//   $env:BASE_URL = "http://localhost:8000"; npx playwright test
module.exports = defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL || 'https://congressreportcard.org',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testIgnore: /every-member/ },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] }, testIgnore: /every-member/ },
    { name: 'webkit', use: { ...devices['Desktop Safari'] }, testIgnore: /every-member/ },
    // One test per member of Congress (~540). Chromium only, to keep the run time down.
    // Run just these with: npx playwright test --project=every-member
    { name: 'every-member', use: { ...devices['Desktop Chrome'] }, testMatch: /every-member/ },
  ],
});
