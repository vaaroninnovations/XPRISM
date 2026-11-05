# XPRISM: Experimental Pharmacology Research & Interactive Student Module

**Aim:** XPRISM exists to put the 3Rs (Replacement, Reduction and Refinement) into everyday practice in
pharmacology education. It gives students realistic, interactive alternatives to animal experiments, so
that practical skills can be learned without harming animals, and it builds a lasting habit of ethical,
responsible research in line with CCSEA and PCI guidelines.

Created by **Dr. Vara Prasad Saka**, Aaron Innovations • drvaraprasadsaka@gmail.com

## Role-based platform

The 32 pharmacology simulations wrapped in a web application. It adds accounts and roles, classes
(batches), assignments with automatic marking, exam mode, grading and marks export, plus
data-protection features: consent, data download, deletion requests and an audit log. The Privacy
Policy, Terms of Service and Conditions of Use are built in.

It runs on one VPS: **Django 5.1 + PostgreSQL + gunicorn + nginx**. No external services or CDNs are
needed; fonts, CSS and JavaScript are all served by your own server.

---

## Roles

| Role | Created by | Can do |
|---|---|---|
| **Super Admin** | `bootstrap_lab` command | Create colleges (each comes with a College Admin), turn experiments on or off platform-wide, set college subscriptions, grant or revoke individual subscriptions for free-trial users (**Platform → Trial users**), see all audit logs and requests, use Django admin (`/admin/`) |
| **College Admin** | Super Admin | Add or deactivate faculty, lab assistants and other college admins; reset passwords; switch experiments on or off for the college; set the college's header line and grievance officer; see all batches; handle data-deletion requests; read the college audit log |
| **Faculty** | College Admin | Create batches (class code), enrol students by CSV/Excel or one by one, assign experiments (due date, attempts, marks, **exam mode** with time limit), review and grade submissions, give feedback, export marks to Excel/CSV, see viva item analysis |
| **Lab Assistant** | College Admin | See batches and submissions, enrol students, reset student passwords; **cannot** assign, grade or export marks |
| **Student** | Faculty (CSV / single) or self sign-up with a **class code** | Do assigned experiments and submit them, see provisional and final marks and feedback, practise any enabled experiment, download their data, request correction or deletion |
| **Free-trial user** | Self sign-up at `/accounts/trial/` (name, e-mail, institution) | Explore **each experiment once** (see below); no assignments or marks |
| **Visitor** | n/a | See the home page (`/`), and browse the catalogue (`/modules/`), documentation (`/documentation/`) and legal pages. Every experiment requires sign-in |

Students and staff added by someone else get a **temporary password** and must change it at first
sign-in. Every user must **accept the current Privacy Policy, Terms and Conditions** before using the
Lab, and accepts again whenever `POLICY_VERSION` changes (in `config/settings.py`).

## Free trial, subscriptions and the ethics agreement

Branding (name, creator, institution, aim) is set in `config/settings.py` (`SITE_*`). Logo files, colours and fonts are documented in `brand/README.md`. The text is shown in the header, the footer, the landing page and **About** (`/about/`).

**Ethics agreement pop-up.** After sign-in (and after any temporary-password and policy steps), every
user sees a pop-up they must accept before continuing. It covers:

- the **3Rs** (Replacement, Reduction, Refinement)
- the Indian framework: the Prevention of Cruelty to Animals Act 1960 and the 1998 Breeding and
  Experiments Rules, **CCSEA** (formerly CPCSEA), the **PCI** amendments that allow computer-assisted
  modules in place of animal experiments, and the role of **PETA India** (an NGO that campaigned for
  these changes; it is not a regulator)
- an undertaking that the simulations are for learning only

The agreement is stored as a consent record (`ethics-<ETHICS_VERSION>`). Changing `ETHICS_VERSION` in
`config/settings.py` makes everyone accept again. The full text is public at `/ethics/`.

**Free-trial rules** (shown in the same pop-up to trial users, with an extra required box):

1. A user without a subscription can open **each experiment once**.
2. The visit ends when the user returns to the home page, the Lab index or a dashboard, opens another experiment,
   signs out, or after `TRIAL_VISIT_MAX_HOURS` (default 3). Reloading the same page during the visit is
   fine.
3. After that, the experiment shows **"Subscription only"** (HTTP 402 page with subscription options).
   The index shows how many experiments are still free.

**Who has unlimited access:** super admins; users of a college whose subscription is active
(**Platform → Colleges → Edit**: "Subscription active" plus an optional "until" date); and trial users
granted an individual subscription under **Platform → Trial users**, which can also reset a trial.
Students of a college whose subscription lapses fall back to the one-visit rule.

**One free year:** visitors and free-trial users see a pop-up (on the home and modules pages, at most once
a week) and an "Apply here" bar on other pages. Applications go to the super admins by e-mail and under
**Platform → Free year**. Approving awards a year straight away: an individual gets an individual subscription
(an account is created if they have none), and a college gets a college subscription (a new college with its
College Admin, or an existing college chosen from the list). The applicant is e-mailed the decision, with a
link to set a password if a new account was made. Each e-mail address can hold one application, unless declined.

**Inviting colleges:** under **Platform → Free year → Invite colleges**, paste e-mail addresses to send each one a
separate invitation whose link opens the pop-up. An address is invited once, addresses that have applied are skipped,
every invitation has an opt-out link, and at most `FREE_YEAR_INVITES_PER_DAY` (default 200) go out in 24 hours.
Sending needs `EMAIL_HOST` to be set; without it the page refuses to send.

## Public demo logins

`manage.py setup_demo` creates "XPRISM Demo College" with one shared login per role, all with the password `Xprism@2026`:
`xprismadmin` (College Admin), `xprismfaculty` (Faculty), `xprismassistant` (Lab Assistant) and `xprismdemo` (Student),
plus a sample batch, assignments and submissions.

These logins are meant to be printed in adverts, so they are limited (`SHARED_DEMO_USERNAMES` in `.env`):

- They can look at everything in the demo college, and can assign, grade and submit. All other changes are refused,
  including passwords, adding or removing people, batches, college settings and data requests.
- Wrong passwords don't lock them, the audit log hides visitors' IP addresses, and the class code can't be used to join.
- Running `setup_demo` again puts the demo college back as it was and touches no other college. To do that nightly:
  `sudo cp deploy/demo-reset.sh /etc/cron.daily/xprism-demo-reset && sudo chmod +x /etc/cron.daily/xprism-demo-reset`

The student login gives unlimited practice on every enabled module, free of charge, for anyone who has the password.
To end the demo, deactivate the logins or set the demo college inactive under **Platform → Colleges**.

## How an assignment works

1. Faculty assigns an experiment to a batch. Students see it on **My assignments** and press **Start**.
2. The experiment opens with an **ASSIGNMENT** bar under the title. The student does the practical,
   fills the observation sheet, answers the viva and enters the unknown or numeric answer.
3. **Submit to faculty** shows a checklist (viva answered? answer entered? observations present?),
   then saves the observation tables, results summary, viva answers and answer.
4. **Automatic score** = viva 40% + correct unknown/numeric answer 30% (only for experiments that have
   one) + completed observation sheet 30%. This becomes provisional marks out of the assignment's
   maximum.
5. Faculty reviews each submission, can override the marks, adds feedback, and uses **Save & next** to
   move through the queue. The marks sheet shows each student's best attempt.

**Exam mode** starts a countdown when the student opens the experiment. The timer keeps running if they
close the tab, and the attempt is auto-submitted at zero. These are hidden and disabled:

- reference datasets
- auto-run, "complete all" and assistant buttons
- "skip waiting"
- the answer **Verify** buttons and results summaries
- viva marking: answers are recorded and marked only on submission

Limitation: the answer check runs in the student's browser. A student with technical knowledge could
read the true value from the page code. Faculty review remains the final authority, and each student
gets their own randomised unknowns.

## Privacy & legal (India: DPDP Act 2023 / DPDP Rules 2025)

- `/privacy/`, `/terms/` and `/conditions/` are filled from the `LEGAL_*` values in `.env`: organisation
  name, address, grievance officer, jurisdiction and hosting location. **Fill these in before going
  live**, and have the texts reviewed by your legal adviser.
- Each consent is stored with its policy version, time and IP address.
- **My data** lets each user download everything held about them (JSON) and request correction or
  deletion. College admins handle requests under **Requests**. Approving a deletion erases name, roll
  number, e-mail, submissions and feedback, and keeps de-identified marks.
- **Audit log**: sign-ins, lock-outs, account changes, uploads, assignments, submissions, grading,
  exports, consents and data requests. Entries cannot be edited.
- Security: hashed passwords, account lock after 5 failed sign-ins (15 min), per-IP throttling,
  nginx rate limit on the login page, CSRF protection, strict Content-Security-Policy, secure cookies
  over HTTPS, role and college scoping on every page and API call.

---

## Install on a VPS (Ubuntu 22.04 / 24.04)

Point your domain's DNS **A record** to the server, copy this folder to the server, then:

```bash
sudo bash deploy/setup.sh lab.example.com you@example.com
```

This installs Python, PostgreSQL and nginx, creates the database and a random secret key, installs the
app in `/opt/xprism`, and starts it as a systemd service with nightly backups. Then:

```bash
# 1. legal details + e-mail settings
sudo nano /opt/xprism/app/.env          # fill LEGAL_* (and EMAIL_* for password-reset e-mails)
sudo systemctl restart xprism

# 2. your super admin account
cd /opt/xprism/app
sudo -u xprism /opt/xprism/venv/bin/python manage.py bootstrap_lab \
     --admin-username superadmin --admin-email you@example.com --admin-password 'A-Strong-Password'

# 3. HTTPS
sudo certbot --nginx -d lab.example.com --redirect -m you@example.com --agree-tos
```

Open `https://lab.example.com` (HTTPS is required for sign-in, because session cookies are secure-only) and sign in as `superadmin`, then:

1. Go to **Platform → New college**. Note the College Admin's temporary password.
2. The College Admin adds faculty.
3. Faculty create batches, upload student lists and assign experiments.

**Try it with demo data first** (optional): `manage.py bootstrap_lab --demo-data` creates
"Demo College of Pharmacy" with these accounts:

| Account | Password |
|---|---|
| `demo-admin` | `Demo@Admin2026` |
| `demo-faculty` | `Demo@Faculty2026` |
| `demo-assistant` | `Demo@Assist2026` |
| `demo-bp001` … `demo-bp005` | `Demo@Student2026` |
| `trial-demo@example.com` (free-trial user, no college) | `Demo@Trial2026` |

Deactivate these accounts, or don't create them, on a live server.

**Updating** to a new version: unpack it on the server and run `sudo bash deploy/update.sh`. Your
`.env` and database are kept.

**Backups** are written to `/var/backups/xprism` daily and kept for 14 days. Copy them off the
server regularly.

**Server size:** 1 vCPU / 2 GB RAM is enough for a few hundred students. The simulations run in the
browser, so server load is light.

## Files

```
config/            Django settings (all deployment values come from .env)
lab/               models, roles/permissions, views, forms, management commands, tests
templates/         pages for every role, sign-in/consent, legal texts
experiments/       the 32 simulation pages (served through the app)
static/assets/     Tailwind CSS (compiled), fonts, Tone.js, bridge.js (submission/exam), viva.js
deploy/            setup.sh, update.sh, nginx + systemd configs, env.example, backup.sh
tests/             browser end-to-end tests (Playwright) used before release
```

## Testing done before release

- **26 Django tests** (`python manage.py test lab`):
  - permissions for every role, and isolation between colleges
  - consent gate and re-consent, forced password change, account lock-out, open-redirect protection
  - class-code sign-up, CSV and Excel upload, one-time credentials download
  - submission, scoring, attempt limits, exam time-out, late flag; grading and Excel/CSV export
  - data export, anonymising deletion, every page rendering for every role
- **62 end-to-end checks** in Chromium through nginx → gunicorn → PostgreSQL, covering the whole
  journey: visitor → super admin → college admin → faculty → students (practical + exam) →
  class-code sign-up → grading → export → lab assistant → deletion request → audit. No JavaScript
  errors, and **zero requests to external sites**.
- **All 32 experiments** opened through the app: practice-mode capture works and exam-mode shortcuts
  are hidden on every one.

To rebuild the CSS after editing templates:
`npx tailwindcss@3 -c tailwind.config.js -i tw-input.css -o static/assets/css/tailwind.css --minify`

The images in `static/assets/img/modules/` are screenshots of the simulations, one per module
(`<slug>.jpg`) plus the three `hero-*.jpg` shown on the home page. Add a new module's image there too.
