# Podcast Generation System

Event-driven monorepo. A user submits a topic; three microservices collaborate to crawl the internet, filter content, generate a script, synthesise it with TTS, and save an MP3.

```
User → Request Processor → [topic-requested] → Content Crawler
                                                      ↓ [content-ready]
                                                  Generator → /podcasts/<id>.mp3
                                                      ↓ [podcast-generated]
                                              Request Processor (push status via WebSocket)
```

---

## Services

| Service | Language | Port | Responsibility |
|---|---|---|---|
| `request-processor` | TypeScript / NestJS | 3000 | REST API, CQRS, WebSocket status push |
| `content-crawler` | Python 3.11 | — | Crawl Wikipedia / DuckDuckGo / BBC RSS, filter, store |
| `generator` | Python 3.11 | — | Script writing (template), TTS via gTTS, save MP3 |

## Infrastructure

| Component | Image | Purpose |
|---|---|---|
| Kafka | `bitnami/kafka:3.7` (KRaft) | Event bus between services |
| MongoDB | `mongo:7-jammy` | Metadata store (podcasts, content chunks) |
| Nginx | `nginx:alpine` | API gateway on port 80 |

---

## Quick Start

```bash
# 1. Clone & enter
git clone <repo-url>
cd podcast-system

# 2. Start everything
docker compose up --build

# 3. Submit a topic
curl -s -X POST http://localhost/podcasts \
  -H "Content-Type: application/json" \
  -d '{"topic": "artificial intelligence", "durationHint": "medium"}' | jq

# → { "podcastId": "<uuid>", "status": "PENDING" }

# 4. Poll status
curl -s http://localhost/podcasts/<uuid> | jq

# 5. When status is DONE, find the MP3
ls podcasts/
```

## WebSocket real-time updates

```js
const socket = io("http://localhost");
socket.on("podcast:status", ({ podcastId, status }) => {
  console.log(podcastId, status); // PENDING → CRAWLING → GENERATING → DONE
});
```

---

## API Reference

### `POST /podcasts`
| Field | Type | Values |
|---|---|---|
| `topic` | string | Any topic (min 1 char) |
| `durationHint` | string | `short` · `medium` · `long` |

**Response 202**
```json
{ "podcastId": "uuid", "status": "PENDING" }
```

### `GET /podcasts/:id`
**Response 200**
```json
{
  "podcastId": "uuid",
  "topic": "artificial intelligence",
  "status": "DONE",
  "filePath": "/app/podcasts/uuid.mp3"
}
```

**Response 404** — podcast not found.

---

## Running Tests

```bash
# Request Processor (TypeScript)
cd services/request-processor
npm ci
npm test

# Content Crawler (Python)
cd services/content-crawler
pip install -r requirements.txt
pytest --cov=src --cov-report=term-missing

# Generator (Python)
cd services/generator
pip install -r requirements.txt
pytest --cov=src --cov-report=term-missing
```

---

## Design Patterns

| Pattern | Where |
|---|---|
| **CQRS** | Request Processor — `CreatePodcastCommand` / `GetPodcastStatusQuery` |
| **Repository** | All three services — interfaces isolate storage from domain logic |
| **Abstract Factory** | Content Crawler (`ContentSourceFactory` → crawlers) · Generator (`PodcastGeneratorFactory` → writer+TTS pairs) |
| **Strategy** | Crawler filters (`RelevanceFilter`, `QualityFilter`, `DeduplicationFilter`) · TTS engines · script writers |
| **Factory** | Request Processor `EventFactory` — stamps versioned Kafka event envelopes |
| **Observer / Event-driven** | Kafka topics between all services |
| **Dependency Injection** | NestJS IoC (RP) · `dependency-injector` (Python services) |

---

## Project Structure

```
podcast-system/
├── services/
│   ├── request-processor/   # TypeScript / NestJS
│   ├── content-crawler/     # Python
│   └── generator/           # Python
├── shared/
│   └── events/              # JSON schemas (single source of truth)
├── infrastructure/
│   └── nginx/
├── podcasts/                # Generated MP3s (Docker volume mount)
├── docker-compose.yml
└── .github/workflows/ci.yml
```
