Browser end-to-end tests (need Node + Playwright: `npm i playwright && npx playwright install chromium`).
They expect the site at http://127.0.0.1:8095 with a fresh database plus `bootstrap_lab --admin-username superadmin --admin-password 'Super@Admin2026'`
(and `--demo-data` for e2e_experiments.js). Run: `node tests/e2e_roles.js` and `node tests/e2e_experiments.js`.
