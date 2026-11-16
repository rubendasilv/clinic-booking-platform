# Progress Check — Clinic Booking Platform

> **How to use:** In VS Code, open the Claude panel in this repo and say:
> **"Follow PROGRESS_CHECK.md and check my progress."**
> (Optional: move this file to `.claude/commands/check-progress.md` and just type `/check-progress`.)
>
> **Daily report:** run `./daily-check.sh` from the repo folder. It runs this check in **Daily mode** (report only, no questions) and saves the result to `progress-reports/<date>.md`.

---

## Instructions for Claude

You are checking Ruben's progress on this project against his 6-week plan. Ruben is learning, so **your job is to check and explain, not to build.**

### Rules
1. **Do not write or fix project code.** If something is missing or broken, say *what* is wrong and *where*, and give a nudge. Ruben types the fix himself. Don't give fill-in-the-blank templates.
2. **Verify with evidence.** A task only passes if you can show proof: a file exists with the right content, a command succeeds, or a test passes. "Looks about right" is not a pass.
3. **Never print secrets.** Don't output the contents of `.env`. Only check that it exists and is git-ignored.
4. **Ask before changing anything on GitHub.** Show the report first, then ask: *"Close these N issues and tick them on the board? (yes/no)"*. Only act after a yes.
5. If Docker isn't running, tell Ruben to open Docker Desktop and stop there. Don't try to work around it.

### Daily mode (used by `daily-check.sh`)
When the prompt says **DAILY MODE**, Ruben is not watching. The script runs unattended and saves your answer to `progress-reports/<date>.md`. Follow Steps 1–4 with these changes:

- **Report only.** Skip Step 5. Don't close issues, don't edit files, don't commit, and don't change anything on GitHub. Rules 1 and 3 still apply.
- **Don't ask questions.** No one can answer. If a check needs something from Ruben (a live URL, a domain or a video link), mark it `🙋 NEEDS RUBEN` with what to provide, and move on.
- **Docker isn't a full stop.** Run `docker info` once. If it fails, still run every check that only reads files, and mark the Docker checks (build, `compose config`, `compose up`, `pytest` in the container, Mailpit) as `⏸ SKIPPED: Docker not running`. Don't try to start Docker.
- **Leave the machine as you found it.** If you run `docker compose up -d`, always run `docker compose down` afterwards, even if a check failed.
- **Output only the report.** Start directly with the `📅 Today:` line. No greeting, no tool commentary and no closing question.
- **Add a "Since yesterday" line** under the date. Compare with the newest earlier file in `progress-reports/` (if there is one), and list the checks that changed status. Write `first report` if there's no earlier file.
- **End with the ready-to-close list.** If anything passed, end the report with: `To close these, open Claude in VS Code and say "Follow PROGRESS_CHECK.md and check my progress."`

### Step 1 — Work out where Ruben is
- Run `date` and find the current week using the table below.
- Check **all weeks up to and including the current one**, not just this week, so anything left over from earlier weeks shows up.

| Week | Dates | Milestone name on GitHub |
|---|---|---|
| 0 | before 16 Nov 2026 | (repo setup, no milestone) |
| 1 | 16–22 Nov 2026 | Week 1 - Foundations |
| 2 | 23–29 Nov 2026 | Week 2 - Booking engine |
| 3 | 30 Nov – 6 Dec 2026 | Week 3 - Emails (MVP) |
| 4 | 7–13 Dec 2026 | Week 4 - Production & CI |
| 5 | 14–20 Dec 2026 | Week 5 - Polish & docs |
| 6 | 21 Dec 2026 – 3 Jan 2027 | Week 6 - Marketing |
| — | 4–22 Jan 2027 | Exam pause. Remind Ruben that uni comes first. |

### Step 2 — Get the open issues
```
gh issue list --state open --limit 100 --json number,title,milestone
```
Match each check below to its issue **by exact title**. If `gh` isn't logged in, tell Ruben to run `gh auth login` and stop.

### Step 3 — Run the checks

#### Week 0 — Repo setup (no issues, just report)
- `README.md`, `LICENSE`, `.gitignore` and `.env.example` exist.
- `git check-ignore .env` prints `.env` (so the real secrets file is ignored).
- `gh project list` shows **Booking Platform Roadmap**.

#### Week 1 — Foundations
| Issue title | Pass when… |
|---|---|
| Dockerfile (python slim, non-root user) | `Dockerfile` exists, uses a `python:*-slim` image, and has a `USER` line that isn't root. `docker build -t booking-check .` succeeds. |
| docker-compose.yml with web + db | A compose file defines a `web` service and a `db` service (Postgres image) with a named volume. `docker compose config` succeeds. |
| Start Django project and bookings app | `manage.py` exists, a `bookings` app folder exists, and `bookings` is in `INSTALLED_APPS`. |
| Models: Service, Product, OpeningHours, Customer, Booking | All five model classes exist in `bookings/models.py` and migration files exist for them. |
| Admin registration + seed data | All five models are registered in `bookings/admin.py`, and there's a seed method (fixture JSON or management command) with services and prices. |

**Week 1 "done when" check:** `docker compose up -d`, then `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/login/` returns `200`. Run `docker compose down` afterwards.

#### Week 2 — Booking engine
| Issue title | Pass when… |
|---|---|
| Services & prices and Products pages | URL routes and templates exist for both pages, and they return 200 with the stack running. |
| Slot generator (hours, duration, buffer, existing bookings) | A function or module generates slots and takes opening hours, service duration, buffer and existing bookings into account. |
| HTMX booking form | The templates include HTMX (`hx-get` / `hx-post`) and there's a view that handles the booking submission. |
| Prevent double-booking + test | There's a DB-level `UniqueConstraint` (or equivalent) **and** `transaction.atomic` / `select_for_update` in the booking code, **and** a test that tries to double-book. |
| pytest for slot generator + ruff lint | `docker compose run --rm web pytest` passes with at least one slot test, and `ruff check .` passes. |

#### Week 3 — Emails (MVP)
| Issue title | Pass when… |
|---|---|
| Add redis, worker, beat, mailpit services | The compose file defines `redis`, `worker`, `beat` and `mailpit`, and they all show as running in `docker compose ps`. |
| Confirmation email task (HTML + text) | A Celery task sends the confirmation, and both HTML and plain-text templates exist. |
| Attach .ics calendar invite | The email code builds and attaches an `.ics` file. |
| Signed manage-booking link: cancel / reschedule | Uses Django signing (`signing` / `TimestampSigner`), with cancel and reschedule views that send their own emails. |
| 24h reminder (Celery beat) + owner alert | There's a beat schedule entry for reminders and an owner alert email on new bookings. |
| Retry on failure + test email is queued | The email task has `autoretry_for` / `retry` with backoff, and a test checks that a booking queues an email. |

**Week 3 "done when" (MVP) check:** with the stack running, make a booking, then `curl -s http://localhost:8025/api/v1/messages` shows a confirmation email. If making a booking needs browser steps, ask Ruben to make one and then check Mailpit.

#### Week 4 — Production & CI
| Issue title | Pass when… |
|---|---|
| compose.prod.yml: Gunicorn + Nginx, healthchecks | A prod compose file uses `gunicorn`, has an `nginx` (or Caddy) service and `healthcheck:` blocks. `docker compose -f compose.prod.yml config` succeeds. |
| GitHub Actions: lint, test, build & push to GHCR | A workflow in `.github/workflows/` runs ruff and pytest and pushes to `ghcr.io`. `gh run list --limit 3` shows a recent successful run. |
| Deploy to VPS with domain + HTTPS | Ask Ruben for the live URL, then check that `curl -sI https://<url>` returns 200 over HTTPS. |
| Real email provider + SPF/DKIM/DMARC | Ask Ruben for the domain, then `dig TXT <domain>` shows SPF and `dig TXT _dmarc.<domain>` shows DMARC. |
| Sentry, /health endpoint, nightly pg_dump | Sentry is initialised in settings, `/health` returns 200, and a backup script or cron entry uses `pg_dump`. |

#### Week 5 — Polish & docs
| Issue title | Pass when… |
|---|---|
| Styling, mobile and accessibility pass | Tailwind (or a stylesheet) is in use, there's a viewport meta tag, and every form input has a `<label>`. Report the gaps. |
| Architecture diagram | An image or Mermaid diagram exists and is linked in the README. |
| README with one-command setup | The README setup steps match the real files (compose file name, `.env.example`, ports). Flag anything out of date. |
| Demo login, seed script, v1.0 release | The README mentions a demo login, a seed command exists, and `gh release list` shows `v1.0`. |

#### Week 6 — Marketing
These can't be checked from code. Ask Ruben for links (video, write-up, LinkedIn draft) and pass each one only if he gives a working link or file.
- Record 2-3 min demo video
- Record 5 min architecture explainer
- Write case-study post
- Draft LinkedIn post (publish after exams). If he shares the draft, check the wording is measured and doesn't overclaim.

### Step 4 — Report
Use this format:

```
📅 Today: <date> — Week <n> (<milestone>)

✅ PASSED (ready to close)
- #<num> <title> — <one-line evidence>

❌ NOT YET
- #<num> <title> — <what's missing, where> → Nudge: <hint, not the answer>

⏪ LEFT OVER FROM EARLIER WEEKS
- …

📊 This week: <x>/<y> done · Overall: <x>/<y>
🎯 Suggested next task: <one task>
```

### Step 5 — Tick things off (only after Ruben says yes)
For each passed issue:
```
gh issue close <num> --comment "Verified by progress check: <evidence>"
```
When **every** issue in a week is closed:
- Tick that week's line in the README's **Roadmap** section (`- [ ]` → `- [x]`).
- Show Ruben the diff and suggest the commit: `git commit -am "Complete Week <n>" && git push`. Let Ruben run it himself.

Closed issues move to **Done** on the project board automatically if the board's "Item closed" workflow is on. If they don't move, tell Ruben to turn it on under **Project → ⋯ → Workflows → Item closed**.
