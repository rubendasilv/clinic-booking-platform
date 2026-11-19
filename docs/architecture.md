# Architecture

## Containers

| Service | Image | Job |
|---|---|---|
| `web` | this repo | Django. `runserver` locally, Gunicorn in production. Runs migrations on start. |
| `worker` | this repo | Celery worker. Sends every email so the website never waits on the email provider. |
| `beat` | this repo | Celery beat. Every 15 min queues reminders; every 5 min frees unpaid holds. |
| `db` | postgres:16-alpine | All data. |
| `redis` | redis:7-alpine | Job queue between `web`/`beat` and `worker`. |
| `mailpit` | axllent/mailpit | Local only. Catches all email at http://localhost:8025. |
| `caddy` | caddy:2-alpine | Production only. HTTPS certificates, static files, proxy to `web`. |

`web`, `worker` and `beat` share one image, so they always run the same code.

## A booking, step by step

```mermaid
sequenceDiagram
    participant C as Client
    participant W as Django
    participant DB as Postgres
    participant Q as Redis
    participant K as Worker
    C->>W: choose treatment (HTMX)
    W->>DB: opening hours + bookings that day
    W-->>C: days and free times
    C->>W: Confirm booking
    W->>DB: BEGIN, lock nearby bookings, re-check slot, INSERT
    DB-->>W: OK (or exclusion constraint error = slot taken)
    W->>Q: after COMMIT: confirmation + owner alert jobs
    W-->>C: confirmation page with manage link
    Q->>K: jobs
    K->>C: email with .ics invite
```

## How double-booking is prevented

Three layers, each enough on its own for the normal case:

1. **Availability check:** the slot is recalculated inside the transaction just before saving.
2. **Row locks:** `select_for_update()` locks live bookings around the chosen time, so two requests queue instead of both passing the check.
3. **Database constraint:** an `ExclusionConstraint` on `tstzrange(start, blocks_until)` with `&&` (overlaps) means Postgres itself rejects any two live bookings whose times, including the clean-down buffer, overlap. This also covers staff adding bookings in the admin.

`test_two_people_booking_at_once_only_one_wins` fires two bookings for the same slot from two threads at the same moment and checks exactly one succeeds.

## Booking statuses

```mermaid
stateDiagram-v2
    [*] --> confirmed: no online deposit
    [*] --> pending_payment: Stripe deposit
    pending_payment --> confirmed: paid (webhook or return page)
    pending_payment --> expired: not paid within 30 min
    confirmed --> cancelled: client or staff
    confirmed --> completed: staff, after the visit
    confirmed --> no_show: staff, after the visit
```

Only `pending_payment` and `confirmed` block the diary.

## Manage links

The link in each email is `signing.dumps({booking, customer})` with a salt and timestamp. It can't be guessed or edited, expires after 180 days, and needs no login or stored token.

## Settings

Everything that differs between laptop and server comes from `.env` (see `.env.example`). With `DJANGO_DEBUG=False`, secure cookies, HTTPS proxy headers and other hardening switch on.
