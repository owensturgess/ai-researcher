# RED Step: Write Exactly One Failing Test

You are the **Test Writer** in a TDD loop. Your job is to write exactly ONE failing test for the behavior described below. The test must target observable behavior through the public interface only.

## Rules

1. Write **exactly one test** — do not write multiple tests or test helpers.
2. The test MUST target **observable behavior through the public interface** described in the interfaces section below.
3. Do NOT access private/internal methods, attributes, or implementation details.
4. Do NOT mock internal collaborators — only mock at system boundaries (external APIs, databases, filesystem, network).
5. If the behavior requires external dependencies, mock them at the boundary.
6. Use **behavior-based naming** — the test name should describe what the system does, not how.
7. Use **one logical assertion** per test (multiple asserts on the same logical outcome are acceptable).
8. The test must be **independent** — it must not depend on other tests or shared mutable state.
9. The test MUST **fail** when run (there is no implementation yet).
10. Follow the language and test framework conventions from the plan context below.

## Output Format

Output the complete test file content that should be written. Include:
- The file path as a comment on the first line (e.g., `# tests/test_calculator.py`)
- All necessary imports
- The single test function/method
- Any test-specific setup (fixtures, mocks at boundaries)

Do NOT include implementation code. Do NOT include explanations outside of code comments.

## Behavior Under Test

Behavior B003: The briefing email renders correctly on mobile devices with clear hierarchy and no horizontal scrolling
Linked tasks: T023

## Public Interfaces (from interfaces.md)

# Public Interfaces

## Source Configuration Loader (`src/ingestion/config.py`)

**Purpose**: Parses the sources.yaml configuration file and returns validated, typed Source objects for the ingestion pipeline.

**Public methods**:
- `load_sources(config_path: str)` → return: List of Source objects with fields (id, name, type, url, category, active, priority). Filters to active sources only. Raises validation error on missing required fields or duplicate IDs. Logs warnings for unknown source types.

**Exercised by**: B023, B024, B025, B027

---

## Global Configuration Loader (`src/shared/config.py`)

**Purpose**: Loads all configuration files (sources.yaml, settings.yaml, context-prompt.txt) and provides typed access to pipeline settings.

**Public methods**:
- `load_settings(config_dir: str)` → return: Settings object with fields (schedule, relevance_threshold, max_briefing_items, budget_caps, recipients, retention_days)
- `load_context_prompt(config_dir: str)` → return: String containing the relevance scoring context prompt text
- `load_sources(config_dir: str)` → return: List of Source objects (delegates to ingestion config loader)

**Exercised by**: B020, B026

---

## Shared Data Models (`src/shared/models.py`)

**Purpose**: Defines all domain entities used across pipeline stages as data classes / structured records.

**Public classes**:
- `Source` — fields: id, name, type (rss/web/x/youtube/podcast), url, category, active, priority
- `ContentItem` — fields: id, title, source_id, source_name, published_date, full_text, original_url, content_format (text/audio/video), transcript_status (pending/completed/failed/not_needed)
- `ScoredItem` — fields: content_item_id, relevance_score (0-100), urgency (informational/worth_discussing/action_needed), relevance_tag, executive_summary, scoring_reasoning, is_duplicate, duplicate_of
- `Briefing` — fields: date, items (list of ScoredItem), delivery_status, recipient_list
- `Recipient` — fields: name, email, timezone
- `PipelineRun` — fields: run_date, started_at, completed_at, sources_attempted, sources_succeeded, sources_failed, items_ingested, items_scored, items_above_threshold, items_in_briefing, transcription_jobs, estimated_cost_usd, delivery_status

**Exercised by**: B001–B036 (used throughout all behaviors as the shared data contract)

---

## S3 Helpers (`src/shared/s3.py`)

**Purpose**: Provides read/write operations for JSON and text objects in S3 with date-prefixed key patterns.

**Public methods**:
- `put_json(bucket: str, key: str, data: dict)` → return: None. Writes JSON-serialized data to S3.
- `get_json(bucket: str, key: str)` → return: dict. Reads and deserializes JSON from S3.
- `put_text(bucket: str, key: str, text: str)` → return: None. Writes plain text to S3.
- `get_text(bucket: str, key: str)` → return: str. Reads plain text from S3.
- `list_keys(bucket: str, prefix: str)` → return: List of S3 key strings matching the prefix.

**Exercised by**: B001, B006, B007–B012, B019, B031, B036

---

## RSS/Atom Ingestion (`src/ingestion/sources/rss.py`)

**Purpose**: Retrieves new entries from RSS/Atom feeds published within a given time window.

**Public methods**:
- `ingest(source: Source, since: datetime)` → return: List of ContentItem objects. Uses feedparser to retrieve entries published after `since`. Extracts title, URL, published date, and full text from each entry.

**Exercised by**: B007

---

## Web Page Ingestion (`src/ingestion/sources/web.py`)

**Purpose**: Scrapes web pages and extracts article text content.

**Public methods**:
- `ingest(source: Source, since: datetime)` → return: List of ContentItem objects. Fetches the page via HTTP, extracts article body using beautifulsoup4, returns items whose publication date is after `since`.

**Exercised by**: B007

---

## X (Twitter) API Ingestion (`src/ingestion/sources/x_api.py`)

**Purpose**: Retrieves recent tweets from configured accounts or search queries via the X API.

**Public methods**:
- `ingest(source: Source, since: datetime)` → return: List of ContentItem objects. Uses tweepy to query X API for tweets published after `since`. Handles rate limits with backoff, logs rate limit events, returns empty list if daily limit exhausted.

**Exercised by**: B008, B014

---

## YouTube Ingestion (`src/ingestion/sources/youtube.py`)

**Purpose**: Retrieves recent video metadata from YouTube channels or search queries.

**Public methods**:
- `ingest(source: Source, since: datetime)` → return: List of ContentItem objects with content_format=video. Uses YouTube Data API v3. Tracks quota units consumed, stops queries when approaching daily quota limit.

**Exercised by**: B009, B015

---

## Podcast Ingestion (`src/ingestion/sources/podcast.py`)

**Purpose**: Parses podcast RSS feeds and identifies new episodes for transcription.

**Public methods**:
- `ingest(source: Source, since: datetime)` → return: List of ContentItem objects with content_format=audio. Parses podcast RSS feed, extracts enclosure URLs for episodes published after `since`.

**Exercised by**: B010

---

## Ingestion Handler (`src/ingestion/handler.py`)

**Purpose**: Lambda entry point that orchestrates ingestion across all source types, writes results to S3, and enqueues transcription work.

**Public methods**:
- `handler(event: dict, context: object)` → return: dict with status, counts (sources_attempted, sources_succeeded, items_ingested, transcriptions_queued). Loads sources sorted by priority, invokes the appropriate source-type ingestion module for each, wraps each in error isolation (log + skip on failure), writes ContentItems to S3 at `raw/{date}/{source_id}/{item_id}.json`, enqueues audio/video items to SQS, writes manifest with pending transcription count, initializes PipelineRun record.

**Exercised by**: B001, B006, B007–B010, B013, B018

---

## Transcription Handler (`src/transcription/handler.py`)

**Purpose**: Lambda entry point that processes SQS transcription messages, retrieves or generates transcripts, and writes results to S3.

**Public methods**:
- `handler(event: dict, context: object)` → return: dict with status, transcript_status (completed/failed). For YouTube: tries yt-dlp subtitle download first, falls back to audio extraction + AWS Transcribe. For podcasts: downloads audio, checks duration against budget cap, sends to AWS Transcribe. Writes transcripts to S3 at `transcripts/{date}/{item_id}.txt`. Updates manifest pending count. Triggers scoring when all transcriptions complete. Sets transcript_status=failed on failure (item remains in pipeline with "transcript unavailable" flag).

**Exercised by**: B011, B012, B016, B017

---

## Deduplication (`src/scoring/deduplication.py`)

**Purpose**: Detects and collapses duplicate content items that cover the same development across sources.

**Public methods**:
- `deduplicate_by_url(items: list of ContentItem)` → return: List of ContentItem with exact URL duplicates removed (keeps earliest ingested). ⚠️ The spec says "highest-relevance version" for dedup, but URL dedup runs before scoring — this stage uses earliest-ingested as the tiebreaker; semantic dedup after scoring uses relevance.
- `deduplicate_by_semantics(scored_items: list of ScoredItem)` → return: List of ScoredItem with is_duplicate and duplicate_of fields populated. Items covering the same core development are flagged, retaining the highest-relevance version as primary. Items with genuinely different angles are preserved as distinct.

**Exercised by**: B028, B029, B030

---

## Scoring Handler (`src/scoring/handler.py`)

**Purpose**: Lambda entry point that scores content items for relevance, classifies urgency, generates summaries, and applies deduplication.

**Public methods**:
- `handler(event: dict, context: object)` → return: dict with status, counts (items_scored, items_above_threshold, duplicates_removed). Loads ContentItems + transcripts from S3 for the day. Runs URL deduplication. Loads context-prompt.txt (fresh each run, not cached). Calls Bedrock/Claude (temperature=0) for each item with the structured scoring prompt requesting JSON output (score, urgency, relevance_tag, summary, reasoning). Validates urgency classification (defaults to informational if ambiguous). Filters by configurable relevance threshold. Runs semantic deduplication. Writes ScoredItems to S3 at `scored/{date}/{item_id}.json`.

**Exercised by**: B019, B020, B021, B022, B026, B028, B029

---

## Briefing Handler (`src/briefing/handler.py`)

**Purpose**: Lambda entry point that assembles the daily briefing from scored items and delivers it via email.

**Public methods**:
- `handler(event: dict, context: object)` → return: dict with status, delivery_status, items_included. Loads ScoredItems above threshold (excluding duplicates). Sorts by urgency group (action_needed → worth_discussing → informational), then by score descending within group. Caps at max_briefing_items. Renders Jinja2 email template. Sends via SES to all recipients. If no items pass threshold, sends "no significant developments" variant. On pipeline failure, sends fallback error notification. Writes briefing metadata to S3 at `briefings/{date}/briefing.json`. Updates PipelineRun record with final delivery status.

**Exercised by**: B001, B002, B004, B005

---

## Email Template (`src/briefing/templates/briefing.html`)

**Purpose**: Jinja2 HTML template that renders the briefing email with mobile-friendly layout.

**Template contract**:
- Input context: list of scored items (each with title, source_name, summary, relevance_tag, urgency, original_url), briefing date, pipeline stats
- Renders: table-based layout, 600px max width, inline CSS, urgency-grouped sections with colored borders, item blocks with all required fields, pipeline stats footer
- Variants: standard briefing (5-10 items), "no significant developments" (confirmation message), fallback error (error summary with timestamp)

**Exercised by**: B002, B003, B004, B005

---

## Monitoring Handler (`src/monitoring/handler.py`)

**Purpose**: Lambda entry point that aggregates pipeline metrics, calculates costs, publishes CloudWatch metrics, and sends cost alerts.

**Public methods**:
- `handler(event: dict, context: object)` → return: dict with status, estimated_cost_usd, alert_sent. Calculates estimated costs (Bedrock token usage, Transcribe minutes). Publishes custom metrics to CloudWatch namespace "AgenticSDLCIntel" (sources_scanned, sources_failed, items_ingested, items_above_threshold, transcription_jobs, estimated_cost, delivery_latency_minutes, briefing_item_count). Compares daily cost against budget threshold from settings.yaml. Sends cost alert email via SES if threshold exceeded.

**Exercised by**: B031, B032, B033, B035

---

## Consecutive Source Failure Tracker (within `src/ingestion/handler.py`)

**Purpose**: Tracks per-source failure counts across pipeline runs to detect persistently failing sources.

**Public methods**:
- `track_source_failure(source_id: str, run_date: str, succeeded: bool)` → return: int (consecutive failure count). Reads/writes failure state from S3. Increments on failure, resets on success. Returns current consecutive count.
- `get_failing_sources(threshold: int)` → return: List of (source_id, consecutive_failure_count) tuples where count >= threshold.

**Exercised by**: B034

---

## CDK Pipeline Stack (`infra/stacks/pipeline_stack.py`)

**Purpose**: Defines all AWS infrastructure: S3 bucket with 30-day lifecycle, SQS queue, EventBridge cron rule, Lambda functions, and IAM roles.

**Key resources**:
- S3 bucket with lifecycle policy expiring objects after 30 days across all prefixes
- SQS transcription queue
- EventBridge rule triggering daily pipeline
- Lambda functions for ingestion, transcription, scoring, briefing, monitoring
- IAM roles with least-privilege access to S3, SQS, Transcribe, Bedrock, SES

**Exercised by**: B001, B036

---

## CDK Monitoring Stack (`infra/stacks/monitoring_stack.py`)

**Purpose**: Defines CloudWatch dashboard, log groups, and alarms for pipeline observability.

**Key resources**:
- CloudWatch dashboard with daily metrics graphs
- Alarms: delivery failure, cost threshold exceeded, >3 consecutive source failures

**Exercised by**: B033, B035

---

# Constitution Validation

The constitution provided contains only template placeholders with no specific principles defined. The following standard validations apply:

1. **Vertical slicing**: Each behavior tests a single observable outcome. Behaviors are ordered to respect task dependencies (shared models → ingestion → transcription → scoring → briefing → monitoring).
2. **Public interface only**: All behaviors are defined against public handler entry points, public module functions, and observable outputs (emails, S3 objects, CloudWatch metrics). No behavior requires accessing internal implementation details.
3. **Test-driven ordering**: Behaviors are sequenced so that foundational behaviors (B007–B010: individual source ingestion) precede composed behaviors (B001: end-to-end delivery), allowing incremental red-green-refactor progression.
4. **Guardrail compliance**: "Read Before Writing" and "Test Before Commit" guardrails are compatible with the behavior queue — each behavior defines what to test before the corresponding task is committed.

⚠️ **Flag**: `deduplicate_by_url` in B028 runs before scoring but the spec (US5.S1) says "only the highest-relevance version appears" — URL dedup cannot use relevance scores. The interface definition notes this: URL dedup uses earliest-ingested as tiebreaker; semantic dedup after scoring uses relevance. Tests should validate both stages separately.

## Existing Tests (for context — do not duplicate)

(No existing tests found)

## Plan Context (language, framework, project structure)

# Implementation Plan: Agentic SDLC Daily Intelligence Briefing Agent

**Branch**: `001-agentic-sdlc-intelligence` | **Date**: 2026-03-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-agentic-sdlc-intelligence/spec.md`

## Summary

Build an automated daily intelligence pipeline that ingests content from RSS, web, X, YouTube, and podcasts — transcribing audio/video where necessary — scores each item for relevance against the company's agentic SDLC transformation goals using an LLM, generates executive summaries, and delivers a curated email briefing each morning. The system runs as a serverless pipeline on AWS using Lambda, S3, SQS, Transcribe, Bedrock (Claude), SES, and EventBridge.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: boto3 (AWS SDK), feedparser (RSS), yt-dlp (YouTube audio), tweepy (X API), beautifulsoup4 (web scraping), jinja2 (email templates)
**Storage**: Amazon S3 (raw content, transcripts, scored items, briefings — 30-day retention with lifecycle policy)
**Testing**: pytest, moto (AWS mocking), pytest-cov
**Target Platform**: AWS Lambda (serverless), single-region deployment
**Project Type**: Serverless pipeline / scheduled automation
**Performance Goals**: Full pipeline completes within 2 hours under normal conditions (completeness-first: delivery waits for all processing)
**Constraints**: Daily operational budget ~$5-15/day ($150-450/month); must handle 50-200 content items per daily run; 30-day data retention
**Scale/Scope**: 3-4 recipients, 20-50 configured sources, 5-10 briefing items per day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution has not been customized (still contains template placeholders). No specific gates are defined to evaluate against. Proceeding with standard engineering best practices:

- **Simplicity**: Single-purpose Lambda functions for each pipeline stage, no over-abstraction
- **Testability**: Each pipeline stage independently testable with mocked AWS services
- **Observability**: CloudWatch metrics and structured logging throughout
- **IaC**: All infrastructure defined in CDK (Python) — no manual resource creation

**Post-Phase 1 re-check**: Design adheres to the above principles. No violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/001-agentic-sdlc-intelligence/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── briefing-email.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── ingestion/
│   ├── __init__.py
│   ├── handler.py           # Lambda handler: orchestrates source ingestion
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── rss.py           # RSS/Atom feed ingestion
│   │   ├── web.py           # Web page scraping
│   │   ├── x_api.py         # X (Twitter) API ingestion
│   │   ├── youtube.py       # YouTube API + transcript retrieval
│   │   └── podcast.py       # Podcast RSS + audio download
│   └── config.py            # Source configuration loader
├── transcription/
│   ├── __init__.py
│   └── handler.py           # Lambda handler: AWS Transcribe worker
├── scoring/
│   ├── __init__.py
│   ├── handler.py           # Lambda handler: relevance scoring via Bedrock
│   ├── deduplication.py     # Content deduplication logic
│   └── prompts/
│       └── relevance.txt    # Configurable scoring context prompt
├── briefing/
│   ├── __init__.py
│   ├── handler.py           # Lambda handler: briefing assembly + SES delivery
│   └── templates/
│       └── briefing.html    # Jinja2 email template (mobile-friendly)
├── monitoring/
│   ├── __init__.py
│   └── handler.py           # Lambda handler: cost aggregation + alerting
└── shared/
    ├── __init__.py
    ├── models.py            # Shared data models (Source, ContentItem, ScoredItem, etc.)
    ├── s3.py                # S3 read/write helpers
    └── config.py            # Global configuration loader

config/
├── sources.yaml             # Source list (add/remove without code changes)
├── context-prompt.txt       # Relevance scoring context (editable without code changes)
└── settings.yaml            # Thresholds, budget caps, recipient list, schedule

infra/
├── app.py                   # CDK app entry point
├── stacks/
│   ├── pipeline_stack.py    # Main pipeline stack (Lambdas, S3, SQS, EventBridge)
│   ├── delivery_stack.py    # SES configuration
│   └── monitoring_stack.py  # CloudWatch dashboards, alarms, cost alerts
└── requirements.txt         # CDK dependencies

tests/
├── unit/
│   ├── test_rss.py
│   ├── test_web.py
│   ├── test_x_api.py
│   ├── test_youtube.py
│   ├── test_podcast.py
│   ├── test_scoring.py
│   ├── test_deduplication.py
│   ├── test_briefing.py
│   └── test_monitoring.py
├── integration/
│   ├── test_ingestion_pipeline.py
│   ├── test_transcription_pipeline.py
│   ├── test_scoring_pipeline.py
│   └── test_end_to_end.py
└── fixtures/
    ├── sample_rss.xml
    ├── sample_content.json
    └── sample_scored.json
```

**Structure Decision**: Single-project serverless pipeline. Each pipeline stage is a separate Lambda function with its own handler module, sharing common models and utilities via `src/shared/`. Infrastructure is defined in CDK stacks under `infra/`. Configuration files under `config/` are editable without code changes. This keeps the codebase flat and navigable while maintaining clear separation of pipeline stages.

## Guardrails (lessons from previous failures — follow these)

### Sign: Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Read the file first
- **Added after**: Core principle


### Sign: Test Before Commit
- **Trigger**: Before committing changes
- **Instruction**: Run required tests and verify outputs
- **Added after**: Core principle
