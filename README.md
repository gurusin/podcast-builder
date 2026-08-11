# Podcast Generation System

Event-driven monorepo. A user submits a topic; three microservices collaborate to crawl the internet, filter content, generate a script, validate it for accuracy, synthesise it with TTS, and serve an MP3.

```
User → Nginx (port 80)
         │
         ├─ POST /podcasts ──→ Request Processor (NestJS)
         │                          │ [topic-requested] Kafka
         │                          ↓
         │                    Content Crawler (Python)
         │                     • Wikipedia (summary + related via OpenSearch)
         │                     • BBC News RSS
         │                     • DuckDuckGo Instant Answers
         │                     • Primary-source tagging + filter pipeline
         │                          │ [content-ready] Kafka
         │                          ↓
         │                    Generator (Python)
         │                     • Script writing (narrative prose)
         │                     • Validation pipeline (4 validators + retry)
         │                     • gTTS synthesis → MP3
         │                          │ [podcast-generated] Kafka
         │                          ↓
         │                    Request Processor (status → DONE)
         │
         └─ GET /audio/<id>.mp3 ──→ Nginx static file (Nginx serves MP3)
```

---

## Services

| Service | Language | Port | Responsibility |
|---|---|---|---|
| `request-processor` | TypeScript / NestJS | 3000 (internal) | REST API, CQRS, WebSocket status push |
| `content-crawler` | Python 3.11 | — | Crawl web sources, filter, persist chunks |
| `generator` | Python 3.11 | — | Script writing, validation, TTS synthesis |

## Infrastructure

| Component | Image | Purpose |
|---|---|---|
| Kafka | `confluentinc/cp-kafka:7.6.1` (KRaft, no ZooKeeper) | Event bus between services |
| MongoDB | `mongo:7-jammy` | Metadata: podcasts, raw chunks, filtered chunks |
| Nginx | `nginx:alpine` | API gateway on port 80; serves MP3s at `/audio/` |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/gurusin/podcast-builder.git
cd podcast-builder/podcast-system

# 2. Start everything (first run builds all images)
docker compose up --build

# 3. Submit a topic
curl -s -X POST http://localhost/podcasts \
  -H "Content-Type: application/json" \
  -d '{"topic": "artificial intelligence", "durationHint": "medium"}' | jq

# → { "podcastId": "<uuid>", "status": "PENDING" }

# 4. Poll until DONE
curl -s http://localhost/podcasts/<uuid> | jq

# 5. When status is DONE, play the podcast in a browser
open http://localhost/audio/<uuid>.mp3
# or download it
curl -o podcast.mp3 http://localhost/audio/<uuid>.mp3
```

---

## API Reference

### `POST /podcasts`

| Field | Type | Values |
|---|---|---|
| `topic` | string | Any topic (min 1 char) |
| `durationHint` | string | `short` · `medium` · `long` |

**Response 201**
```json
{ "podcastId": "uuid", "status": "PENDING" }
```

### `GET /podcasts/:id`

**Response 200**
```json
{
  "podcastId": "uuid",
  "topic": "artificial intelligence",
  "durationHint": "medium",
  "status": "DONE",
  "audioUrl": "/audio/uuid.mp3",
  "createdAt": "2026-08-11T10:00:00.000Z",
  "updatedAt": "2026-08-11T10:01:30.000Z"
}
```

Status values: `PENDING` → `CRAWLING` → `GENERATING` → `DONE` | `FAILED`

**Response 404** — podcast not found.

### `GET /audio/:id.mp3`

Returns the generated MP3 file directly (`Content-Type: audio/mpeg`). Served by Nginx from the shared `podcasts/` volume.

---

## WebSocket Real-time Status

Connect to the Nginx gateway to receive live status pushes without polling.

```js
// Using the test script in docs/ws-test.js
cd docs && npm install
node ws-test.js "machine learning" short
```

Or wire it yourself:
```js
const { io } = require("socket.io-client");
const socket = io("http://localhost");
socket.on("podcast:status", ({ podcastId, status, audioUrl }) => {
  console.log(podcastId, status);   // PENDING → CRAWLING → GENERATING → DONE
  if (status === "DONE") console.log("Listen at:", "http://localhost" + audioUrl);
});
```

---

## Content Pipeline

### Crawlers

Three parallel crawlers fetch content for each topic:

| Crawler | Source | Notes |
|---|---|---|
| `WikipediaCrawler` | Wikipedia REST API | Summary + 4 related articles via OpenSearch. Primary article bypasses relevance filter (tagged `_primary=True`) to prevent TF-IDF IDF normalisation from dropping the most important source. |
| `RSSCrawler` | BBC News RSS | Filters entries mentioning the topic by title/summary. |
| `WebCrawler` | DuckDuckGo Instant Answers | Skips disambiguation pages (`Type=D`) — these return album/film/book stubs unrelated to the topic. Only includes entries ≥ 150 chars. |

### Filter Pipeline (Content Crawler)

```
Raw chunks (all 3 crawlers)
  │
  ├─ Primary chunks (Wikipedia main article) ──────────────────────────┐
  │                                                                     │
  └─ Secondary chunks ──→ QualityFilter (≥ 50 chars)                   │
                          → DeduplicationFilter (first-100-char prefix) │
                          → RelevanceFilter (TF-IDF cosine ≥ 0.02,     │
                                            topic built per-request)   │
                                                                        │
                     ← merge + final DeduplicationFilter ←─────────────┘
                          │
                      filtered_content (MongoDB)
```

### Script Writer

Produces naturally spoken prose (no `[SECTION 1]` markers read aloud by TTS):
- Chunks sorted by relevance score descending; primary sources sort first
- Natural spoken transitions between topics
- Sentence-boundary clipping — never cuts mid-sentence
- Content limit expands per retry attempt (see Validation below)

---

## Script Validation Pipeline

Before any TTS synthesis, the Generator runs a **ValidationPipeline** — cheapest checks first so expensive steps are only reached by scripts that already pass basic gates.

```
Script
  ↓
WordCountValidator        — word count within duration-hint bounds (microseconds)
  ↓ pass
BannedContentValidator    — regex blocklist: profanity / harmful instructions (microseconds)
  ↓ pass
GroundednessValidator     — TF-IDF cosine similarity (script vs source chunks ≥ 0.10)
  ↓ pass                    lightweight LLM-as-judge proxy, zero API cost
LLMJudgeValidator         — Claude Haiku scores groundedness 0–1, threshold 0.60
  ↓ pass                    disabled by default; enable with env vars (see below)
TTS Synthesis
```

### Retry / Feedback Loop

Validation failure triggers a retry (up to 3 attempts). Each retry expands the `content_limit` (chars per chunk) by 50% so more source verbatim text is included, directly improving groundedness:

```
Attempt 1: content_limit = base
Attempt 2: content_limit = 1.5× base  ← validation critique logged
Attempt 3: content_limit = 2.0× base  ← last chance
→ if still failing: status → FAILED
```

### Enable LLM-as-Judge (Optional)

Add to the `generator` service in `docker-compose.yml`:
```yaml
environment:
  VALIDATION_LLM_ENABLED: "true"
  ANTHROPIC_API_KEY: "sk-ant-..."
```

When disabled (default), the system still validates via TF-IDF groundedness — no API key required.

---

## Design Patterns

| Pattern | Where |
|---|---|
| **CQRS** | Request Processor — `CreatePodcastCommand` / `GetPodcastStatusQuery` via NestJS `CommandBus`/`QueryBus` |
| **Repository** | All three services — interfaces decouple domain logic from MongoDB |
| **Abstract Factory** | Content Crawler: `ContentSourceFactory` hierarchy (Web / Wikipedia / RSS) · Generator: `PodcastGeneratorFactory` (writer + TTS pairs) |
| **Strategy** | Filter strategies (`QualityFilter`, `DeduplicationFilter`, `RelevanceFilter`) · Validators (`WordCountValidator`, `BannedContentValidator`, `GroundednessValidator`, `LLMJudgeValidator`) · TTS engines · Script writers |
| **Pipeline** | `FilterPipeline` (crawler) · `ValidationPipeline` (generator) — ordered strategy chains with early exit |
| **Factory** | Request Processor `EventFactory` — stamps versioned Kafka event envelopes |
| **Observer / Event-driven** | Kafka topics: `topic-requested` · `content-ready` · `podcast-generated` |
| **Dependency Injection** | NestJS IoC (Request Processor) · `dependency-injector` (Python services) |

---

## Running Tests

```bash
# Request Processor (TypeScript)
cd services/request-processor
npm ci && npm test

# Content Crawler (Python)
cd services/content-crawler
pip install -r requirements.txt
pytest --cov=src --cov-report=term-missing

# Generator (Python)
cd services/generator
pip install -r requirements.txt
pytest --cov=src --cov-report=term-missing
```

CI runs on every push via `.github/workflows/ci.yml` with 80% coverage gate enforced.

---

## Project Structure

```
podcast-system/
├── services/
│   ├── request-processor/          # TypeScript / NestJS
│   │   └── src/
│   │       ├── podcast/
│   │       │   ├── commands/       # CQRS write side
│   │       │   ├── queries/        # CQRS read side
│   │       │   └── kafka/          # Producer + Consumer with retry
│   │       └── main.ts
│   ├── content-crawler/            # Python
│   │   └── src/
│   │       ├── crawlers/           # Wikipedia, RSS, DuckDuckGo
│   │       ├── filters/            # Quality, Dedup, Relevance + Pipeline
│   │       ├── factories/          # Abstract Factory per crawler family
│   │       └── repositories/       # Raw + filtered content, podcast status
│   └── generator/                  # Python
│       └── src/
│           ├── writers/            # TemplateScriptWriter (narrative prose)
│           ├── tts/                # GTTSEngine + MockTTSEngine
│           ├── validation/         # ValidationPipeline + 4 validators
│           ├── factories/          # StandardFactory / MockFactory
│           └── repositories/       # FilteredContent + PodcastMeta
├── shared/
│   └── events/                     # JSON Schema event contracts
├── infrastructure/
│   └── nginx/nginx.conf            # Gateway + /audio/ static serving
├── docs/
│   ├── architecture.html           # Visual system diagram
│   └── ws-test.js                  # WebSocket test client
├── podcasts/                       # Generated MP3s (Docker volume)
├── DESIGN.md                       # Full architecture + ADRs
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## Architecture Deep-Dive

See [`DESIGN.md`](DESIGN.md) for:
- Full event flow and status lifecycle
- All Architectural Decision Records (ADRs)
- Validation pipeline funnel rationale
- SOLID compliance notes
- Trade-offs and production recommendations
