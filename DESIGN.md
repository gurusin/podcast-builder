# Podcast Generation System — Architecture & Design

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Style](#2-architecture-style)
3. [Service Responsibilities](#3-service-responsibilities)
4. [Event-Driven Communication](#4-event-driven-communication)
5. [Design Patterns](#5-design-patterns)
6. [Data Architecture](#6-data-architecture)
7. [Infrastructure Decisions](#7-infrastructure-decisions)
8. [Technology Stack Rationale](#8-technology-stack-rationale)
9. [Key Architectural Decision Records (ADRs)](#9-key-architectural-decision-records-adrs)
10. [SOLID Compliance](#10-solid-compliance)
11. [Testing Strategy](#11-testing-strategy)
12. [Trade-offs & Known Constraints](#12-trade-offs--known-constraints)

---

## 1. System Overview

The system accepts a user-supplied topic and autonomously produces an MP3 podcast episode. Three independent microservices collaborate exclusively through an event bus — no service calls another directly.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              User / Client                              │
│                POST /podcasts  ──►  GET /podcasts/:id                   │
│                       WebSocket: podcast:status events                  │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │ HTTP / WS
                            ▼
              ┌─────────────────────────┐
              │    Request Processor     │  TypeScript · NestJS
              │  REST · CQRS · WS · DI  │
              └────────────┬────────────┘
                           │ publishes
                           ▼
              ┌─────────────────────────┐
              │         Kafka            │  topic: topic-requested
              └────────────┬────────────┘
                           │ consumes
                           ▼
              ┌─────────────────────────┐
              │    Content Crawler       │  Python
              │  Factory · Strategy · DI │
              └────────────┬────────────┘
                           │ publishes
                           ▼
              ┌─────────────────────────┐
              │         Kafka            │  topic: content-ready
              └────────────┬────────────┘
                           │ consumes
                           ▼
              ┌─────────────────────────┐
              │       Generator          │  Python
              │  Factory · Strategy · DI │
              └────────────┬────────────┘
                           │ publishes
                           ▼
              ┌─────────────────────────┐
              │         Kafka            │  topic: podcast-generated
              └────────────┬────────────┘
                           │ consumes
                           ▼
              ┌─────────────────────────┐
              │    Request Processor     │  pushes status via WebSocket
              └─────────────────────────┘
```

### End-to-End Status Flow

```
PENDING  →  CRAWLING  →  GENERATING  →  DONE
 (RP)         (CC)          (Gen)       (Gen + WS push to client)
```

Each transition is written to MongoDB by the service responsible for that stage. A client polling `GET /podcasts/:id` or connected via WebSocket always sees accurate live state.

---

## 2. Architecture Style

### Microservices with Event-Driven Integration

Each service is independently deployable, owns its bounded context, and communicates only through Kafka events. This was chosen over:

| Alternative | Why rejected |
|---|---|
| Monolith | Crawling is I/O-bound (network), generation is CPU-bound (TTS). Separate processes allow independent scaling. |
| Synchronous HTTP between services | Tight coupling — a slow crawler blocks the API. Removes the ability to retry independently. |
| Shared database integration | Services would share schema, making independent deployment and schema evolution impossible. |
| GraphQL federation | Overkill for a linear pipeline with no complex querying between services. |

### Why a Linear Pipeline?

The domain is inherently sequential: you cannot generate a script before you have content, and you cannot synthesise audio before you have a script. A pipeline maps directly to the domain. Stages are decoupled via Kafka so each can fail, retry, and scale independently.

---

## 3. Service Responsibilities

### 3.1 Request Processor (TypeScript / NestJS)

**Owns:** The `podcasts` collection (write model). All user-facing HTTP and WebSocket interfaces.

**Does:**
- Validates and accepts user requests
- Persists initial podcast document (status: PENDING)
- Publishes `TopicRequested` event to Kafka
- Listens for `PodcastGenerated` events and updates status to DONE
- Pushes real-time status to connected WebSocket clients
- Exposes query endpoint for polling clients

**Does not:** crawl, filter, write scripts, or touch audio.

**Why NestJS?** NestJS ships a first-class CQRS module, IoC container, WebSocket gateway abstraction, and Mongoose integration. These eliminate boilerplate that would otherwise obscure the design patterns. Express would require assembling the same capabilities manually.

---

### 3.2 Content Crawler (Python)

**Owns:** `raw_content` and `filtered_content` collections. Updates `podcasts.status` to CRAWLING.

**Does:**
- Consumes `TopicRequested` events
- Crawls three independent sources in parallel (Wikipedia, DuckDuckGo, BBC RSS)
- Persists raw chunks before filtering (allows reprocessing without re-crawling)
- Runs a three-stage filter pipeline (quality → deduplication → relevance)
- Persists filtered chunks
- Publishes `ContentReady` event

**Does not:** generate scripts, synthesise audio, or serve HTTP.

**Why Python?** NLP tooling (scikit-learn TF-IDF, BeautifulSoup, feedparser) is vastly more mature in the Python ecosystem than in Node.js. Async I/O via `asyncio`/`aiokafka` handles the high-concurrency crawling workload efficiently.

---

### 3.3 Generator (Python)

**Owns:** Generated MP3 files on disk. Updates `podcasts.status` to GENERATING, DONE, or FAILED.

**Does:**
- Consumes `ContentReady` events
- Loads filtered content and podcast metadata from MongoDB
- Generates a structured podcast script
- Synthesises audio via TTS engine
- Saves MP3 to the shared podcasts volume
- Publishes `PodcastGenerated` event

**Does not:** crawl, filter, or serve HTTP.

**Why Python?** TTS libraries (gTTS, pyttsx3, ElevenLabs SDK) and LLM SDKs are first-class Python citizens. The Strategy pattern makes it trivial to swap TTS providers without changing any surrounding code.

---

## 4. Event-Driven Communication

### Kafka Topics

| Topic | Producer | Consumer | Payload |
|---|---|---|---|
| `topic-requested` | Request Processor | Content Crawler | `{ eventType, version, podcastId, topic, durationHint, ts }` |
| `content-ready` | Content Crawler | Generator | `{ eventType, version, podcastId, chunkCount, ts }` |
| `podcast-generated` | Generator | Request Processor | `{ eventType, version, podcastId, filePath, durationSecs, ts }` |

### Event Envelope Design

Every event carries a fixed envelope:

```json
{
  "eventType": "TopicRequested",
  "version": "1.0",
  "podcastId": "uuid-v4",
  "ts": "2026-08-11T09:00:00.000Z",
  ...domainPayload
}
```

**Why a versioned envelope?** If the payload schema changes, consumers can inspect `version` and handle both old and new shapes during a rolling deployment without a flag day.

**Why `podcastId` in every event?** Every downstream consumer needs to correlate the event to a specific podcast. Carrying the ID in the envelope avoids consumers having to parse domain-specific fields just for routing.

### Consumer Group Isolation

Each service uses its own consumer group ID:

| Service | Group ID |
|---|---|
| Content Crawler | `content-crawler-group` |
| Generator | `generator-group` |
| Request Processor | `request-processor-group` |

This means each group maintains its own committed offset. A service can be restarted and replay from its last committed position without affecting other services.

### Manual Offset Commit

The Content Crawler uses `enable_auto_commit=False` and commits offsets only after `process()` succeeds. If crawling fails mid-way, the event is reprocessed on restart. This provides at-least-once delivery semantics, which is correct here because all write operations are idempotent (upsert by `podcastId`).

---

## 5. Design Patterns

### 5.1 CQRS (Command Query Responsibility Segregation)

**Where:** Request Processor — `CreatePodcastCommand` / `GetPodcastStatusQuery`.

**Why:**
- Write path (`CreatePodcastCommand`) is triggered by user action, involves UUID generation, MongoDB write, Kafka publish, and is low-frequency.
- Read path (`GetPodcastStatusQuery`) is triggered by polling or the status page and is high-frequency.
- Separating them allows the read model to be optimised (e.g., a Redis cache in front of Mongo) without touching the write path. NestJS's `CommandBus` and `QueryBus` enforce this separation at the framework level.

```
POST /podcasts
  └─► CommandBus.execute(CreatePodcastCommand)
        └─► CreatePodcastHandler
              ├─ repo.create(PENDING)
              ├─ EventFactory.createTopicRequestedEvent(...)
              └─ KafkaProducer.publish('topic-requested', event)

GET /podcasts/:id
  └─► QueryBus.execute(GetPodcastStatusQuery)
        └─► GetPodcastStatusHandler
              └─ repo.findById(id) → PodcastDocument | 404
```

---

### 5.2 Repository Pattern

**Where:** All three services — `IPodcastRepository` (RP), `RawContentRepository` / `FilteredContentRepository` (CC), `PodcastMetaRepository` / `FilteredContentRepository` (Gen).

**Why:**
- Business logic (handlers, orchestrators) never imports a Mongoose model or Motor collection directly. It depends on an abstract interface.
- Swapping MongoDB for PostgreSQL or an in-memory store in tests requires only a new class that implements the interface — no changes to handlers or orchestrators.
- Test doubles are trivial: `jest.fn()` / `MagicMock` stubs for each interface method.

```typescript
// Handler depends on the interface, not the implementation
constructor(
  @Inject(PODCAST_REPOSITORY)
  private readonly repo: IPodcastRepository,  // ← interface
) {}
```

The concrete implementation (`PodcastRepository`) is bound to the token in the module — swappable without touching the handler.

---

### 5.3 Abstract Factory

**Where:**
- Content Crawler — `ContentSourceFactory` (abstract) → `WebCrawlerFactory`, `WikipediaCrawlerFactory`, `RSSCrawlerFactory`
- Generator — `BasePodcastGeneratorFactory` (abstract) → `StandardPodcastGeneratorFactory`, `MockPodcastGeneratorFactory`

**Why Abstract Factory over simple Factory Method?**

The Abstract Factory creates *families* of related objects. In the Content Crawler, each factory produces a crawler that is semantically consistent with its source type. In the Generator, the factory produces a matched `ScriptWriter` + `TTSEngine` pair — the two are coupled by format (e.g., a "conversational" script needs a voice-optimised TTS, not a robotic one). Separating their creation would risk mismatched pairs.

```python
class StandardPodcastGeneratorFactory(BasePodcastGeneratorFactory):
    def create_script_writer(self) -> BaseScriptWriter:
        return TemplateScriptWriter()

    def create_tts_engine(self) -> BaseTTSEngine:
        return GTTSEngine()          # matched pair — both are "standard" format
```

Switching to an LLM-based pipeline means adding `LLMPodcastGeneratorFactory` that returns `LLMScriptWriter` + `ElevenLabsTTSEngine` — one change point, no risk of mixed pairs.

---

### 5.4 Strategy Pattern

**Where:**
- Content Crawler — `QualityFilter`, `DeduplicationFilter`, `RelevanceFilter` (all implement `BaseFilterStrategy`)
- Generator — `BaseScriptWriter` (script writing algorithm), `BaseTTSEngine` (synthesis algorithm)
- Request Processor — `INotificationStrategy` (`WebSocketNotificationStrategy`)

**Why:**
- Filter algorithms are independently swappable and composable. The `FilterPipeline` applies strategies left-to-right without knowing their implementations.
- Adding a new filter (e.g., a toxicity filter) means adding one class and one line in the pipeline — zero changes to the orchestrator.
- TTS engines differ by provider contract. Wrapping each behind `BaseTTSEngine.synthesize(text, path) -> float` means the orchestrator never knows whether it is calling Google, AWS Polly, or ElevenLabs.

```python
class FilterPipeline:
    def run(self, chunks: list[dict]) -> list[dict]:
        for strategy in self._strategies:   # strategies injected, not hardcoded
            chunks = strategy.filter(chunks)
        return chunks
```

---

### 5.5 Factory (EventFactory)

**Where:** Request Processor — `EventFactory.createTopicRequestedEvent(...)`.

**Why:**
- Every Kafka event must carry `eventType`, `version`, and `ts`. Without a factory, command handlers would each stamp these fields, creating duplication and a risk of inconsistency (e.g., wrong version string in one place).
- `EventFactory` is the single place that knows the envelope contract. Tests assert on the factory's output once — not on every handler that would otherwise duplicate the logic.

---

### 5.6 Observer / Event-Driven (Kafka)

**Where:** All service boundaries. Kafka producers and consumers in every service.

**Why Kafka over direct Observer implementations?**
- Kafka is a durable, ordered, replayable log. If the Generator crashes mid-processing, it replays `content-ready` from its last committed offset on restart — no data loss.
- Direct in-process Observer (EventEmitter, etc.) would require all three services to run in the same process, defeating microservice isolation.
- Kafka decouples publisher from subscriber in time. The Content Crawler can produce events while the Generator is temporarily down; the Generator processes them when it comes back up.

---

### 5.7 Dependency Injection

**Where:** All services.

**Request Processor:** NestJS IoC container. Every class declares its dependencies via constructor parameters decorated with `@Inject()`. The module wires concrete implementations to interface tokens:

```typescript
{
  provide: PODCAST_REPOSITORY,
  useClass: PodcastRepository,
}
```

**Python services:** `dependency-injector` `DeclarativeContainer`. Singletons and factories are declared at container level; orchestrators and consumers receive all dependencies via constructor — no `new` keyword, no global state.

**Why DI matters here:**
- Tests swap real infrastructure (Kafka, MongoDB) for mocks by overriding the container binding — one line change, not scattered `if TEST_MODE` conditionals throughout business logic.
- Adding a new dependency to the orchestrator means adding a constructor parameter and one container line — the call site (consumer) does not change.

---

## 6. Data Architecture

### MongoDB Collections

| Collection | Owner | Schema |
|---|---|---|
| `podcasts` | Request Processor (write), all services (status updates) | `{ podcastId, topic, durationHint, status, filePath?, createdAt, updatedAt }` |
| `raw_content` | Content Crawler | `{ podcastId, chunks: [{url, title, content}], createdAt }` |
| `filtered_content` | Content Crawler (write), Generator (read) | `{ podcastId, chunks: [{url, title, content, score}], createdAt }` |

### Why Store Raw Content Before Filtering?

The raw content is persisted before the filter pipeline runs. This is a deliberate choice:

- If the filter algorithm is improved or a bug is found, the raw content can be reprocessed without re-crawling the internet.
- Crawling is the most expensive and flaky operation (external network, rate limits). Separating storage from filtering means a filter bug costs a pipeline re-run, not a re-crawl.

### Why MongoDB Over a Relational DB?

- Content chunks are variable-length, unstructured text arrays. Storing them as JSONB in Postgres is possible but adds friction — no schema migration needed as chunk shape evolves.
- Podcast metadata is a flat document with an optional `filePath` field. A relational schema would have a nullable column; the document model expresses optionality naturally.
- Motor (async MongoDB driver) integrates cleanly with Python's `asyncio` event loop — no thread-pool overhead for DB calls in the Kafka consumer loop.

### Shared Volume for Audio Files

Generated MP3s are written to `/app/podcasts` inside the Generator container, which is bind-mounted to `./podcasts/` on the host. The file path stored in MongoDB (`/app/podcasts/<uuid>.mp3`) is the container-internal path — the Request Processor returns this path as-is. In production this would be replaced by an S3 pre-signed URL.

---

## 7. Infrastructure Decisions

### 7.1 Kafka (Confluent Platform `cp-kafka:7.6.1`)

**KRaft mode (no ZooKeeper):** ZooKeeper is deprecated as of Kafka 3.x and removed in 4.x. KRaft embeds the controller directly in the broker process, removing an entire infrastructure dependency.

**Single broker:** Sufficient for development and moderate production load. The `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1` setting reflects this — in production this would be 3 with 3 brokers.

**Auto topic creation:** Enabled (`KAFKA_AUTO_CREATE_TOPICS_ENABLE: true`) so no manual setup script is required before first run. In production, topics would be pre-created with explicit partition counts and retention policies.

**Why Confluent image over Bitnami?** Confluent publishes consistent, semantically versioned tags (`7.6.1`) with multi-arch support (amd64 + arm64). Bitnami's short version tags (`3.7`, `3.6`) are not reliably published to Docker Hub.

---

### 7.2 MongoDB (`mongo:7-jammy`)

**Why MongoDB over Redis?**

Redis was considered as the lightweight NoSQL store. It is rejected here because:
- Content chunks can be tens of kilobytes each, and storing hundreds of them per podcast as Redis hashes/lists creates significant memory pressure (Redis is an in-memory store).
- MongoDB's document model maps naturally to the chunk arrays without encoding/decoding overhead.
- MongoDB supports indexed queries on `podcastId` natively; Redis would require maintaining a separate index structure manually.

Redis remains an appropriate choice for the status cache layer (future enhancement) — not for primary document storage.

---

### 7.3 Nginx (API Gateway)

A single-service reverse proxy that:
- Exposes one public port (80) — internal service ports are not published to the host
- Passes WebSocket upgrade headers (`Connection: upgrade`) so the NestJS WebSocket gateway works through the proxy
- Provides a natural integration point for TLS termination, rate limiting, and auth in production

---

### 7.4 Docker Compose

Used for local development and CI. Each service's `Dockerfile` is multi-stage:
1. **Builder stage** — full dev dependencies, TypeScript compilation (RP) or just dependency install (Python)
2. **Runner stage** — production dependencies only, compiled artefacts copied from builder

`healthcheck` on Kafka and MongoDB ensures dependent services (`request-processor`, crawlers) only start once infrastructure is ready, preventing connection-refused errors at startup.

---

## 8. Technology Stack Rationale

| Decision | Chosen | Alternatives Considered | Reason |
|---|---|---|---|
| RP language | TypeScript / NestJS | Go, Python/FastAPI | NestJS has native CQRS, IoC, WebSocket, and Mongoose modules — all required patterns ship out of the box |
| Crawler/Generator language | Python 3.11 | Node.js, Go | NLP (scikit-learn), web scraping (BeautifulSoup), and TTS (gTTS) ecosystems are mature Python-first |
| Message broker | Kafka | RabbitMQ, Redis Streams | Kafka's durable, replayable log is essential for at-least-once delivery on long-running pipeline steps; RabbitMQ deletes messages on acknowledgement |
| NoSQL DB | MongoDB | Redis, CouchDB, DynamoDB Local | Best fit for variable-length document arrays; Motor gives true async; widely supported |
| DI (Python) | `dependency-injector` | Manual wiring, `injector` | Declarative container syntax, explicit singletons, supports factory providers for topic-dependent strategies |
| TTS (default) | gTTS | pyttsx3, AWS Polly | gTTS requires no system audio libraries (works in slim Docker images), no API key, free — ideal default with the Strategy pattern making it swappable |
| Relevance scoring | TF-IDF cosine similarity | Embedding similarity, BM25 | Zero external API calls, runs offline in the container, sufficient for topic relevance at this scale |

---

## 9. Key Architectural Decision Records (ADRs)

### ADR-001: Services communicate only via Kafka — no direct HTTP calls

**Status:** Accepted

**Context:** Services need to pass data between stages of the pipeline.

**Decision:** All inter-service communication goes through Kafka topics. No service exposes an internal HTTP endpoint called by another service.

**Consequences:**
- (+) Services are independently deployable and restartable without affecting pipeline correctness
- (+) Kafka's offset commit provides a natural at-least-once retry mechanism
- (+) New pipeline stages can be inserted by adding a new consumer/producer pair without modifying existing services
- (-) Debugging requires reading Kafka logs in addition to service logs
- (-) Eventual consistency — the client polls or uses WebSocket; there is no synchronous response from the pipeline

---

### ADR-002: Raw content is stored before filtering

**Status:** Accepted

**Context:** Content chunks could be filtered in memory and only the filtered set persisted.

**Decision:** Both raw and filtered chunks are persisted to separate MongoDB collections.

**Consequences:**
- (+) Filter algorithm changes do not require re-crawling
- (+) Audit trail of what was crawled vs. what was accepted
- (+) Debugging filter false-positives/negatives is possible post-hoc
- (-) Approximately 2× storage usage per podcast

---

### ADR-003: The Generator reads podcast metadata (topic, durationHint) from MongoDB rather than the event payload

**Status:** Accepted

**Context:** `content-ready` only carries `podcastId` and `chunkCount`. The Generator needs `topic` and `durationHint` to write the script.

**Decision:** Generator queries the `podcasts` collection by `podcastId` to retrieve these fields.

**Consequences:**
- (+) Event payloads remain minimal — each event carries only what the next stage produced, not a growing accumulation of upstream context
- (+) Single source of truth for podcast metadata — no duplication across events
- (-) Generator makes an additional MongoDB read per event

**Alternative rejected:** Carrying `topic` and `durationHint` in the `content-ready` event. This would require the Content Crawler to pass through data it does not own or produce, creating a shotgun-data anti-pattern.

---

### ADR-004: MockTTSEngine and MockPodcastGeneratorFactory are production code, not test utilities

**Status:** Accepted

**Context:** Tests need to avoid network calls to Google's TTS API.

**Decision:** `MockTTSEngine` and `MockPodcastGeneratorFactory` live in `src/` alongside production code, selected via the `GENERATOR_MODE=mock` environment variable.

**Consequences:**
- (+) Tests use the real container and real orchestrator — only the TTS engine is swapped
- (+) The same factory switch can be used in CI/CD environments without network access
- (+) Validates the Abstract Factory selection mechanism itself
- (-) Mock classes ship in the production image — acceptable for this scale; in a stricter environment they would live in a separate test package

---

### ADR-005: CQRS without an event store (no event sourcing)

**Status:** Accepted

**Context:** CQRS is commonly paired with Event Sourcing.

**Decision:** CQRS is implemented as a command/query bus separation only. MongoDB stores current state — not an event log.

**Consequences:**
- (+) Significantly simpler implementation — no projection rebuild, no snapshot logic
- (+) `GET /podcasts/:id` reads the current document directly — no state replay required
- (-) No audit log of state transitions (PENDING → CRAWLING → GENERATING → DONE)
- (-) Cannot reconstruct historical state at a point in time

**Rationale:** The domain does not require temporal queries or audit history. Kafka already provides a replayable log of domain events — a separate event store would duplicate that capability.

---

## 10. SOLID Compliance

| Principle | How applied |
|---|---|
| **Single Responsibility** | Each class has one reason to change. `EventFactory` only stamps envelopes. `FilterPipeline` only chains strategies. `KafkaProducer` only serialises and sends. |
| **Open/Closed** | Adding a new crawler source = new class implementing `BaseCrawler` + new factory — no existing class is modified. Adding a new filter = new `BaseFilterStrategy` subclass + one line in the pipeline constructor. |
| **Liskov Substitution** | `MockTTSEngine` and `GTTSEngine` are interchangeable behind `BaseTTSEngine.synthesize()`. The orchestrator's behaviour is identical regardless of which implementation is injected. |
| **Interface Segregation** | `IPodcastRepository` exposes only `create`, `findById`, and `updateStatus`. `PodcastStatusRepository` in the Content Crawler exposes only `set_crawling`. Neither interface exposes methods irrelevant to its consumer. |
| **Dependency Inversion** | High-level modules (handlers, orchestrators) depend on abstract interfaces. Low-level modules (Mongoose repositories, gTTS engine) implement those interfaces. Concretions are bound in the DI container — not in business logic. |

---

## 11. Testing Strategy

### Pyramid

```
        /\
       /  \   E2E (docker compose)
      /────\
     /      \  Integration (testcontainers — future)
    /────────\
   /          \ Unit (Jest / pytest — current)
  /────────────\
```

### Unit Tests (current)

All tests run without real Kafka or MongoDB. Dependencies are replaced with:
- **TypeScript:** `jest.fn()` stubs for repository methods, `jest.spyOn` for Kafka producer
- **Python:** `unittest.mock.AsyncMock` / `MagicMock` for Motor collections and aiokafka

Coverage threshold: **80% statements, branches, functions, lines** — enforced as a CI hard gate.

### What is explicitly NOT unit-tested

- Mongoose schema definitions (no branch logic)
- Enum files (no branch logic)
- DTO classes with only decorator metadata

These are excluded from coverage collection in `jest.config.js`.

### Test-First Discipline

Tests are written against the public interface of each class before the implementation exists. The test file imports the class, asserts on its method return values and side effects, and fails on first run. The implementation is then written to make the tests pass.

---

## 12. Script Validation & Feedback Loop

Before synthesising any script to audio, the Generator runs a **ValidationPipeline** that gates on both deterministic and semantic quality signals.  This guards against hallucinated content and degenerate outputs without blocking the pipeline on transient infrastructure issues.

### Validator Funnel (cheapest → most expensive)

```
Script
  │
  ▼
WordCountValidator          — O(n) word split; rejects scripts outside per-duration bounds
  │  pass
  ▼
BannedContentValidator      — regex scan; hard-blocks any profanity / harmful instructions
  │  pass
  ▼
GroundednessValidator       — TF-IDF cosine similarity between script and source chunks ≥ 0.10
  │  pass                     (lightweight "LLM-as-judge" proxy, no API call required)
  ▼
LLMJudgeValidator           — Claude Haiku scores groundedness 0–1; threshold 0.60
  │  pass                     (enabled only when VALIDATION_LLM_ENABLED=true + ANTHROPIC_API_KEY set)
  ▼
TTS Synthesis
```

The funnel is ordered so that each expensive check is only reached if all cheaper checks pass.

### Retry / Feedback Loop

When validation fails the orchestrator retries up to **3 times**, expanding the `content_limit` (chars per chunk fed to the writer) by 50 % on each attempt so the script pulls in more verbatim source text, directly improving groundedness scores:

```
Attempt 1 — content_limit = base (e.g. 700 chars for medium)
Attempt 2 — content_limit = 1.5× base  (validation critique logged as warning)
Attempt 3 — content_limit = 2.0× base  (last chance)
  → if still failing: podcast status → FAILED, exception raised
```

The `ValidationResult` from each failing step includes a `critique` string (reason for failure) that is logged and can be surfaced to monitoring.  A future extension could publish a `ScriptValidationFailed` Kafka event for external observability or human review queues.

### LLM-as-Judge Design Rationale

The `LLMJudgeValidator` is implemented but **disabled by default** (no API key required to run the system).  When enabled, it sends the generated script plus truncated source content to Claude Haiku with a structured JSON-output prompt.  Any API failure is treated as a **soft pass** (score = 0.5) so a transient network error never blocks audio delivery.

The groundedness check uses TF-IDF cosine similarity as a deterministic, zero-cost proxy for the same question.  In practice this catches most hallucination cases (vocabulary absent from source ≈ invented facts) without API latency.

### ADR-006: Validate before TTS, not after

Synthesising a podcast with gTTS costs ~14 seconds of real time and external API quota.  Placing validation before TTS means bad scripts are detected in milliseconds (deterministic validators) or seconds (LLM judge), wasting no synthesis resources on content that would be rejected anyway.

---

## 13. Trade-offs & Known Constraints

| Area | Current State | Production Recommendation |
|---|---|---|
| **Kafka replication** | Single broker, replication factor 1 | 3 brokers, replication factor 3 |
| **MongoDB** | No authentication, no replica set | Atlas or self-hosted replica set with auth |
| **TTS** | gTTS (Google, free, network-dependent) | ElevenLabs or AWS Polly for quality + reliability |
| **Script writing** | Template-based | LLM (Claude API) via `LLMScriptWriter` strategy — interface already defined |
| **Audio delivery** | File path returned in API response | S3 pre-signed URL with CDN |
| **Auth** | None | JWT at the Nginx gateway level |
| **Observability** | `logging` module only | OpenTelemetry traces + Prometheus metrics |
| **Idempotency** | Not enforced on `topic-requested` | Deduplicate by `podcastId` in the crawler's Kafka consumer before processing |
