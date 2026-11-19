# Going live

The prototype runs locally. To take real bookings it needs a server, a domain, a real email provider, and your real business details.

## 1. Replace the placeholders

Everything below lives in `.env` or the admin panel. No code changes needed.

- [ ] Business name, address, phone, email and social links (`BUSINESS_*` in `.env`)
- [ ] Treatments, durations, prices and deposits (admin → Services)
- [ ] Shop items and stock (admin → Products)
- [ ] Opening hours and holidays (admin → Opening hours, Closed days)
- [ ] Booking rules: notice period, how far ahead, cancellation window (`.env`)
- [ ] Policy page wording (`bookings/templates/bookings/policies.html`), checked by someone qualified
- [ ] Delete the demo bookings and demo admin: set `SEED_DEMO=0` and start from an empty database

## 2. Server and domain

1. Rent a small Linux VPS (2 GB RAM is enough to start) and buy a domain.
2. Point the domain's `A` record at the server's IP address.
3. On the server: install Docker, clone the repo, create `.env` with production values:
   - `DJANGO_DEBUG=False`
   - a long random `DJANGO_SECRET_KEY` (generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `DOMAIN=yourdomain.co.uk`, `SITE_URL=https://yourdomain.co.uk`
   - `DJANGO_ALLOWED_HOSTS=yourdomain.co.uk` and `DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.co.uk`
   - strong `POSTGRES_PASSWORD` and `DJANGO_SUPERUSER_PASSWORD`
4. `docker compose -f compose.prod.yml up -d`. Caddy fetches an HTTPS certificate automatically.
5. `docker compose -f compose.prod.yml exec web python manage.py createsuperuser` creates your admin login. Then add your treatments, prices and opening hours in the admin.
6. Add the backup script to cron (instructions at the top of `scripts/backup.sh`), and copy backups off the server.

## 3. Email

Use a transactional email provider (Postmark, Brevo, Amazon SES, Mailgun…). Put its SMTP details in `EMAIL_*`, and add the SPF, DKIM and DMARC DNS records it gives you, or confirmations will land in spam.

## 4. Deposits (optional)

1. Create a Stripe account. Use **test mode** keys first.
2. Set `STRIPE_SECRET_KEY`.
3. In Stripe → Developers → Webhooks, add `https://yourdomain.co.uk/payments/stripe/webhook/` for the `checkout.session.completed` event and put its signing secret in `STRIPE_WEBHOOK_SECRET`.
4. Book a treatment with Stripe's test card `4242 4242 4242 4242` and check the booking turns **Confirmed**.

## 5. Things outside the code to check

These are pointers to look into, not legal advice:

- **Licensing:** most London boroughs license laser treatments (a "special treatment licence"). Check with your borough council before advertising.
- **Laser safety:** a Laser Protection Adviser, local rules and staff training are normally expected for Class 4 lasers.
- **Insurance** that covers laser tattoo and hair removal.
- **Advertising rules:** the ASA/CAP rules on cosmetic procedures, including not targeting ads at under-18s, and evidence for any claims about results.
- **Data protection:** register with the ICO if required, and keep the privacy notice accurate. Treatment notes can count as health data.

## 6. Tracking marketing

Add UTM tags to every ad and bio link so the dashboard shows where bookings come from:

```
https://yourdomain.co.uk/?utm_source=tiktok&utm_medium=paid_social&utm_campaign=launch
https://yourdomain.co.uk/?utm_source=instagram&utm_medium=bio
```
