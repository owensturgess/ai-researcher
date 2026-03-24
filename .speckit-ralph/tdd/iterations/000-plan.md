# Behavior Queue

## User Story 1: Daily Morning Briefing Delivery

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B001 | When the daily scheduled run executes with at least one active source configured, an email briefing is delivered to each configured recipient's inbox | US1.S1 | T019, T022, T026 | queued |
| B002 | Each briefing item displays a title, source name, 2-3 sentence executive summary, relevance tag, urgency indicator (Informational / Worth Discussing / Action Needed), and a clickable source link | US1.S2 | T021, T022, T023 | queued |
| B003 | The briefing email renders correctly on mobile devices with clear hierarchy and no horizontal scrolling | US1.S3 | T023 | queued |
| B004 | When the pipeline fails before the delivery deadline, a fallback notification email is sent to all recipients explaining the delay and expected resolution | US1.S4 | T025 | queued |
| B005 | When no items pass the relevance threshold, a "no significant developments" confirmation email is sent instead of an empty or missing briefing | Edge Case | T024 | queued |
| B006 | Pipeline run metadata is recorded including sources attempted/succeeded, items ingested/scored/included, transcription jobs, and delivery status | US1.S1 | T027 | queued |

## User Story 2: Multi-Format Source Ingestion

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B007 | Given a configured source list with RSS/web entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from RSS/web sources | US2.S1 | T014, T015, T019 | queued |
| B008 | Given a configured source list with X (Twitter) entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from X sources | US2.S1 | T016, T019 | queued |
| B009 | Given a configured source list with YouTube entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from YouTube sources | US2.S1 | T017, T019 | queued |
| B010 | Given a configured source list with podcast entries, when daily ingestion runs, new episodes published in the last 24 hours are retrieved from podcast feeds | US2.S1 | T018, T019 | queued |
| B011 | Given a YouTube video published in the last 24 hours, the full transcript is available — retrieved via YouTube transcript first, with audio transcription as fallback | US2.S2 | T020, T032 | queued |
| B012 | Given a podcast episode published in the last 24 hours, the episode audio is transcribed and full text is available for scoring | US2.S3 | T020, T033 | queued |
| B013 | Given one source is temporarily unavailable (HTTP error, rate limit), the failure is logged, the source is skipped, and all other sources process normally | US2.S4 | T031 | queued |
| B014 | When the X API rate limit is hit mid-ingestion, the system logs the event, processes already-retrieved sources, and continues with other source types | Edge Case | T028 | queued |
| B015 | When the YouTube API quota approaches its daily limit, YouTube queries stop and the pipeline continues with other source types | Edge Case | T029 | queued |
| B016 | When a YouTube video has no transcript and transcription fails, the item is included with a "transcript unavailable" flag; title, source, and link are still provided | Edge Case | T032 | queued |
| B017 | When a podcast episode exceeds 2 hours and would exceed the daily transcription budget cap, it is flagged as "transcript unavailable" with the link still included | Edge Case | T033 | queued |
| B018 | Sources are processed in priority order so highest-value sources are ingested first when rate limits constrain volume | FR-018 | T030 | queued |

## User Story 3: Context-Aware Relevance Scoring

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B019 | Given a batch of ingested content items, each item receives a relevance score (0-100) based on the configured company context | US3.S1 | T021, T034, T035 | queued |
| B020 | Given the relevance threshold is set to 60 (default), only items scoring above 60 appear in the final briefing | US3.S2 | T037 | queued |
| B021 | Given a scored item passes the relevance threshold, it is classified with an urgency level: Informational, Worth Discussing, or Action Needed | US3.S3 | T036 | queued |
| B022 | Given the same content item is processed on two consecutive days, the scores are consistent within ±10 points (scoring reliability) | US3.S4 | T035 | queued |

## User Story 4: Configurable Source Management

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B023 | Given a source configuration file, when a user adds a new source entry with name, type, URL, and optional category, the new source is included in the next daily pipeline run | US4.S1 | T013, T038 | queued |
| B024 | Given a source is removed from the configuration file, content from that source is no longer ingested on the next run | US4.S2 | T013, T038 | queued |
| B025 | The seed source list contains at least 20 sources spanning all supported format types (RSS/web, X, YouTube, podcasts, Substack) | US4.S3 | T040 | queued |
| B026 | The relevance scoring context prompt can be updated without code changes, taking effect on the next pipeline run | FR-019 | T039 | queued |
| B027 | Source configuration is validated: required fields enforced, duplicates rejected, unknown types warned | US4.S1 | T038 | queued |

## User Story 5: Content Deduplication

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B028 | Given two content items from different sources cover the same development, only the highest-relevance version appears in the briefing | US5.S1 | T041, T042, T043 | queued |
| B029 | Given two items have similar topics but genuinely different angles or insights, both items are retained as distinct entries | US5.S2 | T042, T043 | queued |
| B030 | When the same development is announced across 5+ sources, the deduplication step selects the single best representative item, with other source links optionally listed as "also reported by" | Edge Case | T042, T043 | queued |

## User Story 6: Pipeline Health and Cost Monitoring

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B031 | When the daily pipeline completes, logs show: sources scanned, items ingested, items scored above threshold, transcription jobs run, and total estimated cost | US6.S1 | T044, T046 | queued |
| B032 | When daily costs exceed a configurable threshold, a cost alert notification is sent to configured recipients | US6.S2 | T045 | queued |
| B033 | After 7 consecutive days, an operator can see delivery reliability (% on-time) and average cost per run | US6.S3 | T047, T048 | queued |
| B034 | A source that fails for 3 consecutive days triggers a warning in operator metrics | Edge Case | T052 | queued |
| B035 | CloudWatch custom metrics are published to the "AgenticSDLCIntel" namespace with dashboard and alarms | US6.S1 | T047, T048 | queued |

## Cross-Cutting: Data Retention

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B036 | Raw content, transcripts, scored items, and briefings older than 30 days are automatically deleted | FR-021 | T010, T051 | queued |

---

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
