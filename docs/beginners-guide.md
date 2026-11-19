# Running it for the first time (step by step)

This guide assumes you've only ever run code from VS Code. It's written for a Mac.

## 1. Install Docker Desktop

Download it from https://www.docker.com/products/docker-desktop/, install it, and open it. Wait until the whale icon in the menu bar stops animating. Docker must be open whenever you run the project.

## 2. Open a terminal in VS Code

In VS Code: **Terminal → New Terminal**. A panel opens at the bottom. You type commands there and press Enter.

## 3. Get the code

```bash
cd ~/Documents
git clone https://github.com/rubendasilv/clinic-booking-platform.git
cd clinic-booking-platform
code .
```

- `cd` means "go into this folder".
- `git clone` downloads the repository.
- `code .` opens the folder in VS Code. Open a new terminal in that window for the next steps.

## 4. Create your settings file

```bash
cp .env.example .env
```

`cp` copies a file. `.env` holds your settings and passwords. Git ignores it, so it never gets uploaded.

## 5. Start everything

```bash
docker compose up --build
```

The first time, Docker downloads Python, Postgres and Redis, which takes a few minutes. Lots of logs scroll past. That's normal. When you see `Starting development server at http://0.0.0.0:8000/`, it's ready.

Open http://localhost:8000 in your browser.

## 6. Try it

1. Book an appointment on the website.
2. Open http://localhost:8025. The confirmation email is there, with the calendar invite attached.
3. Click **Change or cancel** in that email and move the booking.
4. Log in at http://localhost:8000/admin with `admin` / `clearline-demo`. Change a price and refresh the website.
5. Open http://localhost:8000/dashboard and download the bookings CSV.

## 7. Stop it

Click in the terminal and press `Ctrl+C`. Next time, `docker compose up` is enough (`--build` is only needed after changing `requirements.txt` or the `Dockerfile`).

## If something goes wrong

| You see | Do this |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop isn't open. Open it and wait. |
| `port is already allocated` | Something else is using port 8000. Stop it, or change `"8000:8000"` to `"8001:8000"` in `docker-compose.yml`. |
| The page won't load | Check the terminal for a red error and the line above it. |
| You want a clean database | `docker compose down -v` then `docker compose up`. |

## Running the tests

```bash
docker compose run --rm web pytest
```

You should see a line of dots and `39 passed`.
