# Clinic Booking Platform

A containerised booking system for a service business. Customers browse treatments and prices, book an available time slot, and receive an automatic email confirmation with a calendar invite. The demo is themed as a fictional laser clinic, *Clearline Laser Studio*.

> 🚧 **Status:** in active development. See the [project board](../../projects) and [milestones](../../milestones) for progress.

## Features (planned for v1.0)

- **Services, prices & products:** managed from the admin panel, no code changes needed
- **Booking flow:** choose a service, date and time slot, then confirm
- **Availability engine:** generates free slots from opening hours, service length and existing bookings
- **No double-booking:** enforced with a database constraint and a transaction
- **Automated emails:** confirmation with an `.ics` calendar invite, a 24-hour reminder, cancel/reschedule notices and owner alerts, sent in the background
- **Manage my booking:** cancel or reschedule through a signed link, no login needed
- **Fully containerised:** the whole stack starts with one command

## Tech stack

| Layer | Tool |
|---|---|
| Web framework | Django (Python) |
| Database | PostgreSQL |
| Background jobs | Celery + Redis |
| Frontend | Django templates, HTMX, Tailwind CSS |
| Serving | Gunicorn + Nginx |
| Containers | Docker, Docker Compose |
| Local email testing | Mailpit |
| CI/CD | GitHub Actions → GitHub Container Registry |

## Architecture

```
Browser ──> Nginx ──> Django (Gunicorn) ──> PostgreSQL
                          │
                          └──> Redis ──> Celery worker ──> Email provider / Mailpit
                                          Celery beat (scheduled reminders)
```

## Getting started

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone https://github.com/rubendasilv/clinic-booking-platform.git
cd clinic-booking-platform
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Website | http://localhost:8000 |
| Admin panel | http://localhost:8000/admin |
| Test inbox (Mailpit) | http://localhost:8025 |

## Roadmap

- [ ] Week 1: Foundations in containers
- [ ] Week 2: Booking engine
- [ ] Week 3: Automated emails (MVP)
- [ ] Week 4: Production deployment & CI/CD
- [ ] Week 5: Polish & documentation
- [ ] Week 6: Demo video & write-up

**Stretch goals:** Stripe deposits, bookings analytics dashboard, Kubernetes manifests.

## Author

**Ruben Da Silva Sequeira** · [LinkedIn](https://www.linkedin.com/in/ruben-da-silva-/) · [GitHub](https://github.com/rubendasilv)

## License

[MIT](LICENSE)
