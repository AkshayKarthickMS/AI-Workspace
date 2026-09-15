# Deploying AegisOS publicly (free tier)

This is a step-by-step guide to get a public, working instance of AegisOS live for free, using:

- **Vercel** — frontend (Next.js has first-class support there)
- **Render** — backend (a real, always-running server process; needed because the API uses `BackgroundTasks`, Server-Sent Events, and an in-process LangGraph checkpoint file — none of which fit a stateless serverless platform like Vercel/Netlify)
- **Neon** — free Postgres + pgvector (serverless, no credit card required)
- **Upstash** — free Redis (serverless, no credit card required)
- **Groq** — free-tier hosted inference for the LLM (open-weight models, OpenAI-compatible API)
- **Hugging Face** — free-tier Inference API for embeddings

None of these require a credit card for the free tier as of writing. All the code changes needed for this are already in the repo (`render.yaml`, the provider changes in `apps/api/app/llm/` and `apps/api/app/retrieval/embeddings.py`) — this doc is just the account setup and button-clicking.

## Before you start: what this deployment does and doesn't give you

- **No real authentication.** AegisOS runs in "local-dev identity mode" — anyone can type any identity string and act as that user, in any workspace. A visible banner in the UI says this. Don't put real names or sensitive data into a public deployment of this. See `ARCHITECTURE.md` §12 for what real auth would need to replace this.
- **The LLM and embeddings are hosted, not local**, for this deployment only (`AGENTS.md` documents this as an explicit, scoped exception — local dev and tests are unaffected).
- **Artifacts, uploaded datasets, and in-flight runs can be lost on a cold start or redeploy.** Render's free tier has an ephemeral filesystem (no persistent disk) and spins the service down after 15 minutes of no traffic, waking it back up on the next request (30-60s cold start). The LangGraph checkpoint file, generated report artifacts, and any file a user uploaded via the mission creation screen all live on that filesystem. A run that's mid-flight when the service restarts won't resume correctly; a report artifact or uploaded dataset from before a restart won't be usable after. This is a real limitation of the free tier, not a bug — acceptable for a demo, not for anything that needs durability. (Upgrading to a paid Render plan with a persistent disk, or moving artifacts/uploads to object storage, would fix this — out of scope here.)
- **Groq's free tier has rate limits** that can trip under heavy or concurrent use; a request that hits them will show up as a failed run rather than crash the whole service.
- **The live SSE timeline may not stream in real time through Vercel's rewrite** to an external backend (platform proxy timeouts can cut off long-lived streaming connections). This isn't fatal: the run detail panel polls the REST endpoint independently of SSE and still shows current status/results either way — only the live event-by-event timeline view is affected.

## 1. Create the free accounts and collect credentials

Do these in any order; you'll paste the results into Render in step 3.

### Neon (Postgres + pgvector)

1. Sign up at https://neon.tech (GitHub login is fastest).
2. Create a new project (any region close to you).
3. On the project dashboard, copy the **connection string** — it looks like `postgresql://<user>:<password>@<host>/<db>?sslmode=require`.
4. Rewrite it for SQLAlchemy's psycopg v3 driver: change `postgresql://` to `postgresql+psycopg://` at the start. Keep everything else, including `?sslmode=require`.
5. Save this as `AEGIS_DATABASE_URL` for step 3. pgvector doesn't need a manual setup step — AegisOS's migration runs `CREATE EXTENSION IF NOT EXISTS vector` itself on first boot, and Neon supports that extension out of the box.

### Upstash (Redis)

1. Sign up at https://upstash.com.
2. Create a new Redis database (any region).
3. On the database's detail page, copy the **`rediss://` connection URL** (note the double `s` — TLS). It looks like `rediss://default:<password>@<host>:<port>`.
4. Save this as `AEGIS_REDIS_URL`.

### Groq (LLM)

1. Sign up at https://console.groq.com.
2. Create an API key (Settings → API Keys).
3. Save it as `AEGIS_HUGGINGFACE_API_KEY` (yes, "huggingface" in the name — that setting is a generic OpenAI-chat-compatible client, not Hugging-Face-specific; see the docstring in `apps/api/app/llm/huggingface.py`).
4. Check https://console.groq.com/docs/models for the current list of supported models and pick one that (a) supports JSON mode (`response_format: json_object`) and (b) actually lists Developer-plan rate limits rather than "Contact Sales" (several of Groq's Llama models moved to Enterprise-only pricing after this doc was written) — `openai/gpt-oss-120b` is a good free-tier default as of writing, already set in `render.yaml`, but Groq's lineup and pricing tiers change over time, so confirm it's still listed on the free Developer plan before you deploy.

### Hugging Face (embeddings)

1. Sign up at https://huggingface.co.
2. Create an access token: Settings → Access Tokens → New token (read access is enough).
3. Save it as `AEGIS_EMBEDDING_API_KEY`.

## 2. Push the repo to GitHub (if you haven't already)

Render and Vercel both deploy by connecting to a GitHub (or GitLab/Bitbucket) repository. If this repo isn't pushed yet:

```powershell
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin feature/fresh-requirements
```

(Or push to `main` if you'd rather deploy from there — either branch works, just be consistent with what you pick in Render/Vercel below.)

## 3. Deploy the backend to Render

1. Sign up at https://render.com (GitHub login is fastest — it also makes connecting the repo a one-click step).
2. New → Blueprint → pick this GitHub repo. Render reads `render.yaml` from the repo root automatically and shows you the `aegisos-api` service it defines.
3. When prompted for the env vars marked `sync: false` (Render will list them), paste in:
   - `AEGIS_DATABASE_URL` — from Neon (step 1)
   - `AEGIS_REDIS_URL` — from Upstash (step 1)
   - `AEGIS_HUGGINGFACE_API_KEY` — your Groq key (step 1)
   - `AEGIS_EMBEDDING_API_KEY` — your Hugging Face token (step 1)
   - `AEGIS_CORS_ORIGINS` — leave as `http://localhost:3000` for now; you'll come back and update this once you have the Vercel URL in step 4.
4. Deploy. Render builds `infra/docker/api.Dockerfile`, which runs the Alembic migration (including creating the pgvector extension) automatically on container start, then starts the server. First build takes a few minutes.
5. Once it's live, note the public URL Render gives you (something like `https://aegisos-api.onrender.com`). Confirm it works: visit `https://aegisos-api.onrender.com/health` — you should see `{"status":"ok",...}`.

## 4. Deploy the frontend to Vercel

1. Sign up at https://vercel.com (GitHub login is fastest).
2. Add New → Project → import this GitHub repo.
3. In the project's configuration screen, set **Root Directory** to `apps/web`. Vercel auto-detects it as a Next.js app; leave the build/output settings as detected.
4. Add an environment variable: `API_INTERNAL_URL` = the Render backend URL from step 3 (e.g. `https://aegisos-api.onrender.com`, no trailing slash).
5. Deploy. Vercel gives you a public URL (something like `https://aegisos.vercel.app`).

## 5. Close the loop: point the backend's CORS at the frontend

1. Back in Render, open the `aegisos-api` service → Environment.
2. Set `AEGIS_CORS_ORIGINS` to your Vercel URL from step 4 (e.g. `https://aegisos.vercel.app`).
3. Save — Render redeploys automatically.

(Strictly, the frontend talks to the backend through Next.js's own server-side `/backend/*` rewrite — see `apps/web/next.config.ts` — so the browser never calls Render directly and CORS mostly doesn't come into play for the app itself. Setting it anyway is cheap defensive practice and matters if you ever call the API directly, e.g. from `/docs`.)

## 6. Verify the golden path

Visit your Vercel URL (the public marketing/pricing pages live at `/` and `/pricing`; the product itself is under `/app`) and walk through: open the app → set an identity → create a workspace → create a mission (upload your own CSV/Excel, or try the demo dataset path `data/demo/sales_data.csv`) → start a run → approve the plan → wait for it to reach "Completed" → view the report artifact → try the knowledge base and audit explorer.

The first request after any idle period will be slow (Render's free-tier cold start, ~30-60s) — that's expected, not a bug.

## Troubleshooting

- **Health check fails / service won't start on Render**: check the Render service's logs. A migration failure (e.g. wrong `AEGIS_DATABASE_URL`) will show up here before uvicorn ever starts.
- **Frontend shows "API unavailable"**: confirm `API_INTERNAL_URL` on Vercel exactly matches the Render URL (no trailing slash), and that `https://<render-url>/health` responds directly.
- **A run fails immediately with an LLM or embedding error**: check the Groq/Hugging Face API keys are correct and their free-tier rate limits haven't been hit; check the Groq model name in `render.yaml` is still valid (Groq's lineup changes — see step 1).
- **A run that was in progress disappears after a while**: this is the ephemeral-filesystem limitation described above, not a new bug — see "Before you start."
