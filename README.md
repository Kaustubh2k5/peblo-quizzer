# Peblo Quiz Service

AI-powered educational content ingestion and adaptive quiz platform.
Ingests PDFs, extracts content, generates quiz questions via LLM, and
adjusts difficulty per student based on their performance.

---

## What This Does

1. **Ingest** — Upload a PDF → text is extracted, cleaned, and chunked
2. **Generate** — LLM reads each chunk and writes MCQ / True-False / Fill-in-the-blank questions
3. **Quiz** — Fetch questions filtered by topic, difficulty, subject, or grade
4. **Adapt** — Submit answers → system tracks performance and adjusts difficulty per student per topic

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.11) |
| Database | MongoDB 7 |
| Cache / Queue | Redis 7 |
| Reverse Proxy | Nginx |
| LLM | (swappable: OpenAI, Anthropic, Gemini) |
| Containerisation | Docker + Docker Compose |

---

## Prerequisites

Install these before starting:

- **Docker Desktop** — https://www.docker.com/products/docker-desktop
  - Includes Docker Engine + Docker Compose
  - macOS / Windows: install the app
  - Linux: `sudo apt install docker.io docker-compose-plugin`
- **Git** — https://git-scm.com

Verify both work:
```bash
docker --version        # Docker version 24+
docker compose version  # Docker Compose version 2+
git --version
```

---

## Quick Start (5 steps)

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/peblo-quiz-engine.git
cd peblo-quiz-engine
```

### Step 2 — Create your environment file

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in your API key.


**To use a different provider instead**, change `LLM_PROVIDER` and fill in that key:

```env
# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

# Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

# Google Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxx
```

Only the key matching your chosen `LLM_PROVIDER` is required. Leave the others blank.

### Step 3 — Build and start all services

```bash
docker compose up --build
```

This will:
- Pull MongoDB, Redis, and Nginx images (~500MB total, one-time download)
- Build the FastAPI container (installs all Python dependencies)
- Start all 4 services and wire them together

First build takes 2–4 minutes. Subsequent starts take ~10 seconds.

You should see logs like:
```
peblo_mongo  | MongoDB starting...
peblo_redis  | Ready to accept connections
peblo_api    | Connected to MongoDB
peblo_api    | Uvicorn running on http://0.0.0.0:8000
peblo_nginx  | start worker processes
```

### Step 4 — Verify it is running

Open your browser:

- **API docs (Swagger UI):** http://localhost/docs
- **Health check:** http://localhost/health
- **Root:** http://localhost/

Or with curl:
```bash
curl http://localhost/health
```

Expected response:
```json
{
  "api": "ok",
  "mongodb": "ok",
  "redis": "ok",
  "llm_provider": "nvidia",
  "llm_key_set": true,
  "overall": "ok"
}
```

### Step 5 — Run the smoke test

```bash
bash scripts/smoke_test.sh
```

This runs through the full flow automatically:
- Uploads a test PDF
- Waits for ingestion
- Generates quiz questions via the LLM
- Retrieves questions
- Submits correct and wrong answers
- Checks adaptive difficulty updated

---

## API Usage

### Upload a PDF

```bash
curl -X POST http://localhost/api/ingest \
  -F "file=@path/to/your.pdf"
```

Response:
```json
{
  "source_id": "abc-123",
  "filename": "your.pdf",
  "status": "processing",
  "message": "PDF accepted. Use GET /api/sources/abc-123 to check status."
}
```

### Check ingestion status

```bash
curl http://localhost/api/sources/abc-123
```

Wait until `"status": "done"` before generating questions.

### Generate quiz questions

```bash
curl -X POST http://localhost/api/generate-quiz \
  -H "Content-Type: application/json" \
  -d '{"source_id": "abc-123", "questions_per_chunk": 3}'
```

### Get quiz questions

```bash
# All questions
curl "http://localhost/api/quiz"

# Filter by topic and difficulty
curl "http://localhost/api/quiz?topic=photosynthesis&difficulty=easy"

# Auto-adapt difficulty for a student
curl "http://localhost/api/quiz?student_id=student_001&topic=math"

# Filter by subject and grade
curl "http://localhost/api/quiz?subject=Science&grade=3&limit=10"
```

### Submit an answer

```bash
curl -X POST http://localhost/api/submit-answer \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "student_001",
    "question_id": "question-uuid-here",
    "selected_answer": "3"
  }'
```

Response:
```json
{
  "answer_id": "...",
  "is_correct": true,
  "correct_answer": "3",
  "new_difficulty": "medium",
  "student_score": {
    "total_answered": 5,
    "total_correct": 4,
    "accuracy": 80.0,
    "difficulty_levels": {"Science": "medium"}
  }
}
```

### Student stats

```bash
curl http://localhost/api/students/student_001/stats
curl http://localhost/api/students/student_001/answers
```

---

## Running Tests

### Option A — Pytest (recommended)

Install test dependencies locally (outside Docker):
```bash
pip install pytest httpx
```

Make sure the Docker stack is running, then:
```bash
pytest tests/ -v
```

### Option B — Smoke test script

```bash
bash scripts/smoke_test.sh
```

No extra dependencies needed — just `curl` and `python3` (both pre-installed on macOS/Linux).

### Option C — Swagger UI

Open http://localhost/docs — every endpoint is interactive and testable in the browser.

---

## Switching LLM Provider

Edit `.env`, change two lines, restart:

```bash
# In .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key

# Then restart
docker compose restart api
```

No code changes needed. The provider abstraction layer handles everything.

**Supported providers and recommended models:**

| Provider | LLM_PROVIDER value | Recommended model |
|---|---|---|
| NVIDIA NIM | `nvidia` | `meta/llama-3.1-70b-instruct` |
| OpenAI | `openai` | `gpt-4o-mini` |
| Anthropic | `anthropic` | `claude-3-5-haiku-20241022` |
| Google | `gemini` | `gemini-1.5-flash` |

To change the model within NVIDIA NIM, update `NVIDIA_MODEL` in `.env`:
```env
NVIDIA_MODEL=mistralai/mistral-7b-instruct-v0.3
```

---

## Stopping and Restarting

```bash
# Stop all containers (data is preserved in volumes)
docker compose down

# Start again (no rebuild needed)
docker compose up

# Stop AND delete all data (wipe the database)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

---

## Project Structure

```
peblo-quiz-engine/
│
├── app/
│   ├── main.py                  # FastAPI app + startup
│   ├── api/
│   │   ├── ingest.py            # POST /api/ingest, POST /api/generate-quiz
│   │   ├── quiz.py              # GET /api/quiz, GET /api/topics
│   │   ├── answers.py           # POST /api/submit-answer, GET /api/students/...
│   │   └── health.py            # GET /health
│   ├── core/
│   │   ├── config.py            # All settings (reads from .env)
│   │   └── models.py            # Pydantic schemas for all data
│   ├── db/
│   │   ├── mongodb.py           # Async MongoDB connection + indexes
│   │   └── redis_client.py      # Async Redis connection
│   ├── llm/
│   │   ├── base.py              # BaseLLMProvider abstract class
│   │   ├── factory.py           # get_llm_provider() — reads LLM_PROVIDER env
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── gemini_provider.py
│   └── services/
│       ├── ingestion.py         # PDF extract → clean → chunk
│       ├── quiz_generator.py    # LLM prompt + JSON parsing
│       └── adaptive.py          # ELO-style difficulty tracking
│
├── nginx/
│   └── nginx.conf               # Reverse proxy + rate limiting
│
├── tests/
│   └── test_api.py              # Full pytest test suite
│
├── scripts/
│   └── smoke_test.sh            # curl-based end-to-end test
│
├── Dockerfile                   # FastAPI container recipe
├── docker-compose.yml           # All 4 services wired together
├── requirements.txt             # Python dependencies
├── .env.example                 # Template — copy to .env
├── .gitignore                   # Excludes .env, volumes, pycache
└── README.md
```

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `sources` | Ingested PDF metadata and status |
| `chunks` | Extracted text segments with grade/subject/topic |
| `questions` | Generated quiz questions with source traceability |
| `answers` | Student answer history |
| `students` | Per-student adaptive difficulty state |

Connect with MongoDB Compass at `mongodb://localhost:27017` to inspect data.

---

## Adaptive Difficulty Algorithm

Each student has a difficulty level per topic stored as a float `0.0 – 1.0`:

```
0.00 – 0.34  →  easy
0.35 – 0.69  →  medium
0.70 – 1.00  →  hard
```

On each answer:
- **Correct** → `new = min(1.0, current + 0.10 × (1 - current))`
- **Wrong**   → `new = max(0.0, current - 0.10 × current)`

New students start at `0.15` (easy). The level is cached in Redis for fast reads
and persisted to MongoDB for durability.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `nvidia` | Active provider |
| `NVIDIA_API_KEY` | If using nvidia | — | From build.nvidia.com |
| `OPENAI_API_KEY` | If using openai | — | From platform.openai.com |
| `ANTHROPIC_API_KEY` | If using anthropic | — | From console.anthropic.com |
| `GEMINI_API_KEY` | If using gemini | — | From aistudio.google.com |
| `MONGODB_URL` | No | `mongodb://mongo:27017` | Leave as-is in Docker |
| `REDIS_URL` | No | `redis://redis:6379/0` | Leave as-is in Docker |
| `MAX_FILE_SIZE_MB` | No | `20` | PDF upload size limit |
| `CHUNK_SIZE_CHARS` | No | `1500` | Characters per content chunk |
| `QUESTIONS_PER_CHUNK` | No | `3` | LLM questions per chunk |

---

## Common Issues

**`docker compose` command not found**
Use `docker-compose` (with hyphen) for older Docker versions:
```bash
docker-compose up --build
```

**Port 80 already in use**
Something else is using port 80 (another web server). Change the Nginx port in `docker-compose.yml`:
```yaml
ports:
  - "8080:80"   # access at http://localhost:8080 instead
```

**`llm_key_set: false` in health check**
Your API key is not set in `.env`. Open `.env`, check `NVIDIA_API_KEY` (or whichever provider you chose) has a value with no extra spaces.

**Ingestion stuck in `processing`**
Check the API container logs:
```bash
docker compose logs api --tail=50
```

**`connection refused` errors**
The containers might still be starting. Wait 10–15 seconds and try again.

---
