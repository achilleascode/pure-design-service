# Pure Design Generator

LoyJoy → Vercel-Python-Service → Gemini 3.1 Flash Image → Pixel-Composite → Supabase.

Async-Polling-Pattern: `POST /api/generate` startet einen Job, returnt `job_id`.
LoyJoy pollt `GET /api/status?job_id=…` bis `status=done` und zeigt `image_url`.

## Architektur (kurz)

```
LoyJoy → /api/generate ── insert job ──► Supabase Postgres
            │                  │
            ▼                  ▼
       returnt job_id      fire-and-forget POST /api/worker?job_id=…
            │
            ▼
LoyJoy pollt /api/status?job_id=… alle 3s
            │
            ◄── { status, image_url }

/api/worker:
  pre_filter → prompt_builder → gemini_image → heuristics
              → vision_judge → composite → storage  (Retry-Loop max 3)
```

## Local Dev

```bash
cd pure-design-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env mit echten Keys füllen
python3 tests/test_composite.py
```

## Supabase Setup

1. Postgres-Tabelle anlegen:
   ```bash
   psql "$SUPABASE_DB_URL" -f supabase/migrations/001_design_jobs.sql
   ```
   Oder via Supabase Studio → SQL Editor → Inhalt der `.sql` einfügen + Run.

2. Storage-Bucket anlegen: Name `pure-design-mockups`, Public **off**, RLS auf Service-Role beschränken.

## Vercel Deploy

**Voraussetzung:** Vercel Pro Account (60s Function-Timeout). Hobby (10s) ist zu kurz.

```bash
cd pure-design-service
vercel login
vercel link            # Projekt anlegen / verknüpfen

# Secrets setzen (jede Variable wird einmal abgefragt)
vercel env add GEMINI_API_KEY            production
vercel env add ANTHROPIC_API_KEY         production   # optional, Fallback Vision-Judge
vercel env add SUPABASE_URL              production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel env add SUPABASE_STORAGE_BUCKET   production   # = pure-design-mockups
vercel env add WORKER_SECRET             production   # langer Random-String
vercel env add SELF_BASE_URL             production   # = https://<projekt>.vercel.app

vercel --prod
```

Nach Deploy: URL kopieren (`https://<projekt>.vercel.app`) und nochmal als `SELF_BASE_URL` setzen (re-deploy).

## API

### POST /api/generate

Request:
```json
{ "prompt": "neon cyberpunk botanical with violet glow", "session_id": "optional" }
```

Response (sync, <1s):
```json
{ "job_id": "uuid", "status": "queued" }
```

Bei sofortigem Reject:
```json
{ "job_id": "uuid", "status": "rejected", "reason": "…", "category": "minor|brand|drugs|…" }
```

### GET /api/status?job_id=…

Response:
```json
{
  "job_id": "uuid",
  "status": "queued|processing|done|failed|rejected",
  "image_url": "https://…signedurl…/2026-05-11/uuid.png",
  "reason_code": null,
  "attempts": 1
}
```

### POST /api/worker?job_id=… (intern)

Geschützt durch Header `x-worker-secret: $WORKER_SECRET`. Sollte nur vom `/api/generate`-Trigger oder Manual-Re-Run aufgerufen werden.

## LoyJoy-Bot-Konfiguration

Im bestehenden Bot diese Schritte einbauen:

1. **API-Client (POST)** → URL `https://<projekt>.vercel.app/api/generate`,
   Body `{"prompt": "${user_design_wish}"}`,
   Response-Mapping `/job_id` → `${design_job_id}`,
   `/status` → `${design_status}`.

2. **Bei `design_status == "rejected"`** → Text mit `reason` an User, Bot fragt erneut nach Wunsch.

3. **Loop-Modul (max 12 Iterationen, Wait 3s):**
   - API-Client (GET) `https://<projekt>.vercel.app/api/status?job_id=${design_job_id}`,
     Mapping `/status` → `${design_status}`, `/image_url` → `${design_image_url}`.
   - IF `design_status == "done"` → Loop verlassen.
   - IF `design_status == "failed"` → Loop verlassen + Error-Pfad.

4. **Image-Modul** zeigt `${design_image_url}` im Chat.

5. **Error-Pfad** (`failed` oder Loop-Timeout) → Default-Text + Option neuen Wunsch einzugeben.

## Pipeline-Verhalten

| Stage | Aktion bei Fail | Retry-Hint |
|-------|----------------|------------|
| Pre-Filter (Rule) | sofort `rejected` | – |
| Pre-Filter (LLM) | sofort `rejected` | – |
| Prompt-Builder | fallback auf Original-Prompt | – |
| Gemini Safety-Block | nächster Try | safer abstract botanical |
| Heuristik (zu dunkel/flach) | nächster Try | richer detail, balanced exposure |
| Vision-Judge fail | nächster Try | Hint aus Verdict übernommen |
| Composite/Upload fail | nächster Try | – |
| Nach 3 fails | Job-Status `failed`, Reason `all_attempts_exhausted` | – |

| Try | Modell | Temperatur |
|-----|--------|------------|
| 1 | gemini-3.1-flash-image-preview | 0.7 |
| 2 | gemini-3.1-flash-image-preview | 0.85 |
| 3 | gemini-3-pro-image-preview | 1.0 |

## Wichtige Konstanten (`lib/composite.py`)

```
TEMPLATE_W × TEMPLATE_H = 1080 × 1350
SLOT (x, y, w, h)        = 234, 240, 612, 925   (Aspect 2:3)
```

Assets unter `assets/`:
- `backdrop_base.png` (1080×1350) — Original Studio-Backdrop
- `bottom_overlay.png` (1080×1350, Alpha) — Crop y=970..1350 mit Buds + Boden + Domain

## Tests

```bash
python3 tests/test_composite.py
```

Snapshot-Check:
- Output 1080×1350 ✓
- Slot-Mitte enthält KI-Bild-Farbe ✓
- Logo oben erhalten ✓
- Domain unten erhalten ✓
- Buds rechts unten erhalten ✓

## Bekannte Limits / TODOs

- Gemini 3.1 Flash ignoriert `imageSize: "2K"` häufig → wir nutzen 1K als Default, 3-Pro nur für Retry-3.
- Vercel Hobby (10s) blockiert den Worker komplett. **Pro tier zwingend.**
- Falls Vercel `waitUntil`-Trigger nicht zuverlässig: Migration zu Inngest oder Trigger.dev.
- Vision-Judge fail-open bei API-Fehler — produktiv evtl. fail-closed mit Default-Fallback-Bild.
- LoyJoy-Polling-Loop muss max 36s abdecken; bei Modell-Switch in Try 3 plus Pro-Image-Gen können wir an die 60s kommen.
