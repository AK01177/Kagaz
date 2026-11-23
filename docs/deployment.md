# Deployment

Frontend on **Vercel**, backend on **Render**, with **Supabase** (Auth + Postgres), **AWS S3** (uploaded files) and **Redis** (token cache).

## 1. One-time setup
1. **Supabase** – Authentication → enable *Confirm email* (users must confirm before signing in). Database → run `create extension if not exists vector;` (the migrations also try).
2. **S3** – create a *private* bucket (block all public access) and an IAM user limited to it with `s3:PutObject`, `GetObject`, `DeleteObject`, `ListBucket`.
3. **Render** – New → Blueprint → pick this repo (`render.yaml`). It creates the API and a Redis (Key Value) instance. Fill every `sync: false` variable:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` (add manually) |
| `DATABASE_URL` | Supabase Postgres URI, `postgresql+psycopg2://...` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | from Supabase → Project Settings → API |
| `CORS_ALLOWED_ORIGINS` | your Vercel URL, `https://...` only |
| `S3_DOCUMENT_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | from step 2 |
| `OPENROUTER_API_KEY`, `GEMINI_API_KEY` | AI features |

   Migrations (`alembic upgrade head`) run automatically on every start.
4. **Vercel** – import the repo, set *Root Directory* to `frontend`, and add:
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` = your Render URL.
   These are baked in at build time, so redeploy after changing them. Then put the Vercel URL into Render's `CORS_ALLOWED_ORIGINS`.

## 2. Checks
- `GET /api/health` – process is alive (used by Render/Docker).
- `GET /api/health/ready` – database, Redis, S3 and Supabase all answer; returns 503 otherwise. Point an uptime monitor here.

## 3. Production rules
- Never run `python -m app.db.seed_demo` in production (it creates known-password accounts). Create the first system admin by hand in Supabase + the `users`/`memberships` tables.
- Never commit `.env` files. Keep the S3 bucket private.
- A revoked or logged-out token can still work for up to `TOKEN_CACHE_TTL_SECONDS` (60 s) when Redis is on.

## 4. Run everything locally with Docker
```
cp backend/.env.example backend/.env   # fill Supabase values
export NEXT_PUBLIC_SUPABASE_URL=... NEXT_PUBLIC_SUPABASE_ANON_KEY=...
docker compose up --build
```
Frontend: http://localhost:3002, API: http://localhost:8001. Postgres (pgvector), Redis and uploads use local volumes.
