# PLAN Step: Extract Behaviors and Define Interfaces

You are the TDD Planner. Your job is to analyze SpecKit artifacts and produce two outputs:
1. A **behavior queue** — ordered list of testable behaviors extracted from acceptance scenarios
2. A **public interfaces** definition — language-agnostic description of public APIs for blind validation

## Input Artifacts

### Specification (spec.md)
# Feature Specification: Agentic SDLC Daily Intelligence Briefing Agent

**Feature Branch**: `001-agentic-sdlc-intelligence`
**Created**: 2026-03-24
**Status**: Draft
**Input**: User description: "./prds/prd-agentic-sdlc-research-agent.md"

## Clarifications

### Session 2026-03-24

- Q: What is the data retention policy for ingested content, transcripts, and past briefings? → A: 30-day retention — retain raw content, transcripts, scored items, and briefings for 30 days, then auto-delete.
- Q: When the pipeline is running long, should it prioritize the 7 AM deadline or complete all processing? → A: Completeness-first — delay delivery until all processing (including transcriptions) finishes, even if it arrives after 7 AM.
- Q: What scoring consistency tolerance is acceptable when the same content is scored on consecutive days? → A: Moderate — ±10 points on the 0-100 scale.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Morning Briefing Delivery (Priority: P1)

As a CTO leading an agentic SDLC transformation, I want to receive a curated email briefing of the top 5-10 agentic software development developments by 7 AM each morning, so I can start my day informed without manually scanning dozens of sources.

**Why this priority**: This is the core value proposition — the single daily touchpoint that replaces 5-10 hours/week of manual scanning. Without reliable delivery, the entire system has no value.

**Independent Test**: Can be fully tested by configuring a source list, running the pipeline, and verifying that a well-formatted email with ranked, summarized items arrives in the recipient's inbox before the delivery deadline.

**Acceptance Scenarios**:

1. **Given** the pipeline is configured with at least one active source, **When** the daily scheduled run executes, **Then** an email briefing arrives in each configured recipient's inbox by 7:00 AM local time.
2. **Given** the briefing contains 5-10 items, **When** a recipient opens the email, **Then** each item displays a title, source name, 2-3 sentence executive summary, relevance tag (why it matters), urgency indicator (Informational / Worth Discussing / Action Needed), and a clickable source link.
3. **Given** the briefing is delivered, **When** a recipient reads it on a mobile device, **Then** the content renders correctly with clear hierarchy and is fully readable without horizontal scrolling.
4. **Given** the pipeline encounters a failure that prevents briefing generation, **When** the delivery deadline approaches, **Then** a fallback notification email is sent to all recipients explaining the delay and expected resolution.

---

### User Story 2 - Multi-Format Source Ingestion (Priority: P1)

As a CTO, I want the agent to ingest content from web pages, RSS feeds, X (Twitter), YouTube, and podcasts, so I don't miss critical developments published in any format.

**Why this priority**: The value of the briefing depends directly on source coverage. If the agent only reads blogs but misses a critical YouTube talk or podcast discussion, the CTO makes decisions on incomplete information. This is co-P1 because briefing delivery without broad ingestion delivers low-quality output.

**Independent Test**: Can be fully tested by configuring sources across all five format types, running the ingestion pipeline, and verifying that new content from the last 24 hours is captured from each source type with full text available for scoring.

**Acceptance Scenarios**:

1. **Given** a configured source list with entries across RSS/web, X, YouTube, podcasts, and Substack, **When** the daily ingestion runs, **Then** new content published in the last 24 hours is retrieved from each source type.
2. **Given** a YouTube video was published in the last 24 hours on a monitored channel, **When** the ingestion pipeline processes it, **Then** the full transcript is available — retrieved via the YouTube transcript first, with audio transcription as a fallback.
3. **Given** a podcast episode was published in the last 24 hours on a monitored feed, **When** the ingestion pipeline processes it, **Then** the episode audio is transcribed and the full text is available for scoring.
4. **Given** one source in the list is temporarily unavailable (HTTP error, rate limit), **When** the ingestion pipeline runs, **Then** the failure is logged, the unavailable source is skipped, and all other sources are processed normally.

---

### User Story 3 - Context-Aware Relevance Scoring (Priority: P2)

As a CTO leading an agentic SDLC transformation, I want each content item scored for relevance against my company's specific transformation goals and priorities, so the briefing contains signal, not noise.

**Why this priority**: Without relevance scoring, the briefing is just an unfiltered feed. Scoring is what transforms raw content into actionable intelligence. It's P2 because a manually curated source list provides baseline relevance even without scoring, but scaling depends on this.

**Independent Test**: Can be fully tested by providing a set of sample content items (some highly relevant, some irrelevant) and verifying the scoring system correctly ranks relevant items higher, with scores and urgency classifications that match human judgment.

**Acceptance Scenarios**:

1. **Given** a batch of ingested content items, **When** the scoring pipeline runs, **Then** each item receives a relevance score (0-100) based on the configured company context.
2. **Given** the relevance threshold is set to 60 (default), **When** items are scored, **Then** only items scoring above 60 appear in the final briefing.
3. **Given** a scored item, **When** it passes the relevance threshold, **Then** it is classified with an urgency level: Informational, Worth Discussing, or Action Needed.
4. **Given** the same content item is processed on two consecutive days, **When** scores are compared, **Then** the scores are consistent within ±10 points on the 0-100 scale, demonstrating scoring reliability.

---

### User Story 4 - Configurable Source Management (Priority: P2)

As a CTO, I want to add or remove sources from the agent's scan list without modifying code, so I can tune coverage as the landscape evolves.

**Why this priority**: The agentic development landscape is fast-moving. New blogs, podcasts, and channels emerge frequently. If adding a source requires a code change and deployment, the system becomes stale quickly.

**Independent Test**: Can be fully tested by editing the source configuration file to add a new source, then verifying the next pipeline run ingests content from the newly added source.

**Acceptance Scenarios**:

1. **Given** a source configuration file exists, **When** a user adds a new source entry with name, type, URL, and optional category, **Then** the new source is included in the next daily pipeline run.
2. **Given** a source is removed from the configuration file, **When** the next daily run executes, **Then** content from that source is no longer ingested.
3. **Given** the source configuration file, **When** a user reviews it, **Then** the seed list contains at least 20 sources spanning all supported format types (RSS/web, X, YouTube, podcasts, Substack).

---

### User Story 5 - Content Deduplication (Priority: P3)

As a CTO, I want the agent to detect and merge duplicate content that appears across multiple sources, so the briefing doesn't waste my time with repetitive items.

**Why this priority**: Major developments often appear across multiple blogs, X accounts, and YouTube channels simultaneously. Without deduplication, the briefing would contain 3-4 summaries of the same announcement, reducing its value and inflating item count.

**Independent Test**: Can be fully tested by feeding the scoring pipeline with two articles covering the same announcement from different sources, and verifying only one representative item (the highest-quality or earliest source) appears in the briefing.

**Acceptance Scenarios**:

1. **Given** two content items from different sources cover the same development, **When** the deduplication step runs, **Then** only the highest-relevance version appears in the briefing.
2. **Given** two items have similar topics but genuinely different angles or insights, **When** the deduplication step runs, **Then** both items are retained as distinct entries.

---

### User Story 6 - Pipeline Health and Cost Monitoring (Priority: P3)

As a CTO, I want visibility into the agent's operational health and daily costs, so I can ensure reliability and manage expenses.

**Why this priority**: The system runs autonomously every day. Without monitoring, failures could go unnoticed and costs could escalate silently, especially transcription costs for long-form audio/video content.

**Independent Test**: Can be fully tested by running the pipeline, then checking that operational metrics (source success/failure counts, transcription costs, total items processed, delivery status) are logged and accessible.

**Acceptance Scenarios**:

1. **Given** the daily pipeline completes, **When** an operator reviews the logs, **Then** they can see: number of sources scanned, items ingested, items scored above threshold, transcription jobs run, and total estimated cost.
2. **Given** daily costs exceed a configurable threshold, **When** the pipeline completes, **Then** a cost alert notification is sent to the configured recipients.
3. **Given** the pipeline has run for 7 consecutive days, **When** an operator reviews metrics, **Then** they can see delivery reliability (% of on-time deliveries) and average cost per run.

---

### Edge Cases

- What happens when no relevant content is found in the last 24 hours? The system sends a brief "no significant developments" email confirming it ran successfully, rather than sending nothing.
- What happens when a podcast episode exceeds 2 hours in length? The system transcribes it within budget constraints, logging the cost; if it would exceed the daily transcription budget cap, it is flagged as "transcript unavailable" with the link still included.
- What happens when the X API rate limit is hit mid-ingestion? The system logs the rate limit event, processes the sources already retrieved, and continues with other source types.
- What happens when a source consistently fails for multiple consecutive days? The system logs a warning after 3 consecutive failures for the same source, included in the operator metrics.
- What happens when the same development is announced across 5+ sources simultaneously? The deduplication step selects the single best representative item, with other source links optionally listed as "also reported by."
- What happens when a YouTube video has no transcript and transcription fails? The item is included in the briefing with a "transcript unavailable" flag; the title, source, and link are still provided so the recipient can manually review if interested.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest content from at least five source types: RSS/Atom feeds, web pages, X (Twitter) accounts/searches, YouTube channels/searches, and podcast RSS feeds.
- **FR-002**: System MUST retrieve only content published within the last 24 hours on each daily run.
- **FR-003**: System MUST transcribe audio content (podcasts) and video content (YouTube) into full text, using existing platform transcripts where available and falling back to a transcription service.
- **FR-004**: System MUST score each content item for relevance (0-100) against a configurable company context prompt that encodes transformation goals, target topic areas, audience roles, and recency weighting.
- **FR-005**: System MUST filter items using a configurable relevance threshold (default: 60) and include only items above the threshold in the briefing.
- **FR-006**: System MUST classify each qualifying item with an urgency indicator: Informational, Worth Discussing, or Action Needed.
- **FR-007**: System MUST generate a 2-3 sentence executive summary for each qualifying item, written for a CTO audience.
- **FR-008**: System MUST assemble qualifying items into an email briefing with: title, source name, summary, relevance tag, urgency indicator, and source link for each item.
- **FR-009**: System MUST deliver the briefing email to all configured recipients by 7:00 AM local time, 7 days per week, under normal conditions. If processing requires additional time, the system MUST complete all ingestion, transcription, and scoring before delivering — even if this delays delivery past 7 AM.
- **FR-010**: System MUST render the email briefing correctly on mobile email clients, with clear hierarchy and no horizontal scrolling required.
- **FR-011**: System MUST allow sources to be added or removed via a configuration file (without code changes), with changes taking effect on the next daily run.
- **FR-012**: System MUST deduplicate content items that cover the same development across multiple sources, retaining the highest-relevance version.
- **FR-013**: System MUST handle individual source failures gracefully — logging the failure and continuing to process remaining sources without blocking the pipeline.
- **FR-014**: System MUST send a fallback notification email if the pipeline fails to generate a briefing before the delivery deadline.
- **FR-015**: System MUST send a "no significant developments" email when no items pass the relevance threshold, confirming the system is operational.
- **FR-016**: System MUST log daily operational metrics including: sources scanned, items ingested, items above threshold, transcription jobs run, and estimated daily cost.
- **FR-017**: System MUST alert recipients when daily operational costs exceed a configurable budget threshold.
- **FR-018**: System MUST respect rate limits for third-party services, prioritizing highest-value sources when limits constrain ingestion volume.
- **FR-021**: System MUST retain all raw ingested content, transcripts, scored items, and generated briefings for 30 days from creation, then automatically delete them.
- **FR-019**: System MUST allow the relevance scoring context prompt to be updated without code changes.
- **FR-020**: System MUST include a seed source list of at least 20 high-quality sources spanning all supported format types.

### Key Entities

- **Source**: A content channel monitored by the agent. Attributes: name, type (RSS/X/YouTube/podcast/web), URL or identifier, category tag, active status.
- **Content Item**: A single piece of ingested content. Attributes: title, source reference, publication date, full text (or transcript), original URL, content format (text/audio/video).
- **Scored Item**: A content item with relevance assessment. Attributes: relevance score, urgency classification, relevance tag (why it matters), executive summary.
- **Briefing**: The assembled daily output delivered to recipients. Attributes: date, list of scored items (ranked), delivery status, recipient list.
- **Recipient**: A person who receives the daily briefing. Attributes: name, email address, time zone.
- **Pipeline Run**: A single execution of the daily pipeline. Attributes: run date, start/end time, sources attempted, sources succeeded, items ingested, items scored, items included, transcription count, estimated cost, delivery status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Recipients open and read (>50% scroll depth) more than 80% of briefings within 24 hours of delivery, after the first 2 weeks of operation.
- **SC-002**: Recipients self-report a reduction in weekly manual source scanning time from 5-10 hours/week to less than 1 hour/week within 30 days of launch.
- **SC-003**: More than 70% of briefing items are rated as "relevant" or "highly relevant" by recipients when surveyed.
- **SC-004**: Fewer than 1 significant agentic SDLC development per week is discovered through other means that the agent missed (coverage/recall target).
- **SC-005**: More than 50% of briefings lead to at least one downstream action: shared with team, influenced a decision, or triggered deeper research.
- **SC-006**: Each daily briefing is readable in under 15 minutes.
- **SC-007**: Fewer than 20% of briefing items are rated as irrelevant by recipients (false positive guardrail).
- **SC-008**: The briefing arrives by 7:00 AM local time on at least 95% of days (delivery reliability target). On days when processing runs long, completeness takes priority over the deadline — delivery may be late but must always include fully processed content.

## Assumptions

- All recipients are in the same time zone (or close enough that a single 7 AM delivery time serves the group). Per-recipient scheduling is a post-MVP enhancement.
- Recipients have standard corporate email clients (iOS Mail, Gmail, Outlook) that support basic HTML email rendering.
- The company has existing cloud infrastructure accounts with the necessary services provisioned (compute, storage, email delivery, transcription, and LLM access).
- The CTO will provide an initial curated seed list of at least 20 sources across all format types within the first week.
- Audio/video content averaging under 60 minutes per episode is the norm; episodes over 2 hours are rare edge cases.
- The daily briefing format (5-10 items, uniform summary depth) is sufficient for MVP. A two-tier format with "deep dive" sections is a post-MVP enhancement.
- Paywalled content will be handled by summarizing from the available preview/excerpt text. Purchasing subscriptions for key sources is a future consideration.
- The target monthly operational budget for the agent (transcription, LLM calls, API access) is under $500/month, with daily cost logging to track actuals.
- This is strictly an external intelligence agent. Internal company content (Slack, internal docs, retros) is out of scope for MVP.
- All recipients receive the same briefing. Per-user relevance profiles are a post-MVP enhancement.

### Implementation Plan (plan.md)
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

### Task Breakdown (tasks.md)
# Tasks: Agentic SDLC Daily Intelligence Briefing Agent

**Input**: Design documents from `/specs/001-agentic-sdlc-intelligence/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, and base project structure

- [ ] T001 Create project directory structure per plan.md (src/ingestion/, src/transcription/, src/scoring/, src/briefing/, src/monitoring/, src/shared/, config/, infra/, tests/)
- [ ] T002 Initialize Python project with pyproject.toml — declare dependencies: boto3, feedparser, yt-dlp, tweepy, beautifulsoup4, jinja2, requests
- [ ] T003 [P] Create dev dependencies: pytest, moto, pytest-cov, ruff (linting), black (formatting)
- [ ] T004 [P] Create config/sources.yaml with seed source list of 20+ sources across RSS, web, X, YouTube, and podcast types
- [ ] T005 [P] Create config/settings.yaml with default settings: schedule, scoring threshold (60), max briefing items (10), budget caps, recipient list, retention (30 days)
- [ ] T006 [P] Create config/context-prompt.txt with the relevance scoring context prompt encoding agentic SDLC transformation goals, topic areas (agentic tools, SDLC processes, governance/safety), and audience roles (CTO, VP Eng)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models, utilities, and AWS infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Implement shared data models (Source, ContentItem, ScoredItem, Briefing, Recipient, PipelineRun) in src/shared/models.py per data-model.md
- [ ] T008 [P] Implement S3 read/write helpers in src/shared/s3.py — put_json, get_json, put_text, get_text, list_keys with date-prefixed key patterns (raw/{date}/, scored/{date}/, briefings/{date}/, runs/{date}/)
- [ ] T009 [P] Implement global configuration loader in src/shared/config.py — load sources.yaml, settings.yaml, and context-prompt.txt from config/ directory
- [ ] T010 [P] Create CDK app entry point in infra/app.py and base pipeline stack in infra/stacks/pipeline_stack.py — define S3 bucket with 30-day lifecycle policy, SQS transcription queue, EventBridge daily cron rule
- [ ] T011 [P] Create SES delivery stack in infra/stacks/delivery_stack.py — configure SES sender identity with DKIM/SPF
- [ ] T012 [P] Create monitoring stack in infra/stacks/monitoring_stack.py — CloudWatch log groups, custom metrics namespace "AgenticSDLCIntel", cost alert alarm

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Daily Morning Briefing Delivery (Priority: P1) MVP

**Goal**: Deliver a curated email briefing of 5-10 items to recipients each morning — the core end-to-end pipeline.

**Independent Test**: Configure a source list, run the full pipeline, verify a well-formatted email with ranked, summarized items arrives in the recipient's inbox.

### Implementation for User Story 1

- [ ] T013 [US1] Implement source configuration loader in src/ingestion/config.py — parse sources.yaml, filter active sources, return typed Source objects
- [ ] T014 [P] [US1] Implement RSS/Atom feed ingestion in src/ingestion/sources/rss.py — use feedparser to retrieve entries published in last 24 hours, extract title, URL, published date, full text, return list of ContentItem
- [ ] T015 [P] [US1] Implement web page scraping in src/ingestion/sources/web.py — use requests + beautifulsoup4 to fetch and extract article text, handle HTML cleanup, return ContentItem
- [ ] T016 [P] [US1] Implement X (Twitter) API ingestion in src/ingestion/sources/x_api.py — use tweepy to retrieve recent tweets from configured accounts/searches (last 24 hours), handle rate limits, return list of ContentItem
- [ ] T017 [P] [US1] Implement YouTube ingestion in src/ingestion/sources/youtube.py — use YouTube Data API v3 for channel/search queries (last 24 hours), retrieve video metadata, return list of ContentItem with content_format=video
- [ ] T018 [P] [US1] Implement podcast feed ingestion in src/ingestion/sources/podcast.py — parse podcast RSS feeds for new episodes (last 24 hours), extract enclosure URLs for audio download, return list of ContentItem with content_format=audio
- [ ] T019 [US1] Implement ingestion Lambda handler in src/ingestion/handler.py — orchestrate all source types, write ContentItems to S3 (raw/{date}/{source_id}/{item_id}.json), enqueue audio/video items to SQS transcription queue, write manifest to S3 with pending transcription count, handle per-source failures gracefully (log and continue)
- [ ] T020 [US1] Implement transcription Lambda handler in src/transcription/handler.py — process SQS messages, for YouTube items try transcript retrieval via yt-dlp subtitles first then fall back to AWS Transcribe, for podcasts download audio and send to AWS Transcribe, write transcripts to S3 (transcripts/{date}/{item_id}.txt), update manifest pending count, trigger scoring when all transcriptions complete
- [ ] T021 [US1] Implement relevance scoring in src/scoring/handler.py — load all ContentItems + transcripts from S3 for the day, load context-prompt.txt, call Bedrock/Claude for each item with structured JSON output (score, urgency, relevance_tag, summary), write ScoredItems to S3 (scored/{date}/{item_id}.json), filter by relevance threshold from settings.yaml
- [ ] T022 [US1] Implement briefing assembly and email delivery in src/briefing/handler.py — load ScoredItems above threshold, sort by urgency group (action_needed → worth_discussing → informational) then by score descending within group, cap at max_briefing_items, render Jinja2 email template, send via SES to all recipients, write briefing metadata to S3 (briefings/{date}/briefing.json)
- [ ] T023 [US1] Create mobile-friendly HTML email template in src/briefing/templates/briefing.html — table-based layout per contracts/briefing-email.md, inline CSS, 600px max width, urgency-grouped sections with colored borders, item blocks with title/source/summary/relevance-tag/link, pipeline stats footer
- [ ] T024 [US1] Implement "no significant developments" email variant in src/briefing/handler.py — when no items pass threshold, send confirmation email per contracts/briefing-email.md empty variant
- [ ] T025 [US1] Implement fallback error notification in src/briefing/handler.py — if pipeline fails, send error notification email per contracts/briefing-email.md fallback variant with error summary, failed stage, and timestamp
- [ ] T026 [US1] Wire Lambda functions in infra/stacks/pipeline_stack.py — create Lambda functions for ingestion, transcription, scoring, and briefing handlers; connect EventBridge cron → ingestion, SQS → transcription, S3 manifest event → scoring, scoring completion → briefing; set IAM roles for S3, SQS, Transcribe, Bedrock, SES access
- [ ] T027 [US1] Write PipelineRun record in src/ingestion/handler.py and src/briefing/handler.py — track started_at, completed_at, sources_attempted/succeeded, items_ingested/scored/above_threshold/in_briefing, transcription_jobs, delivery_status, write to S3 (runs/{date}/run.json)

**Checkpoint**: End-to-end pipeline functional — daily briefing delivered via email with multi-format ingestion, transcription, scoring, and assembly. This is the MVP.

---

## Phase 4: User Story 2 — Multi-Format Source Ingestion Hardening (Priority: P1)

**Goal**: Harden ingestion across all five source types with robust error handling, rate limit management, and source failure isolation.

**Independent Test**: Configure sources across all five format types, induce failures in individual sources, verify pipeline continues and logs failures without blocking.

### Implementation for User Story 2

- [ ] T028 [P] [US2] Add rate limit handling to src/ingestion/sources/x_api.py — implement backoff on 429 responses, respect X-Rate-Limit headers, log rate limit events, skip remaining X queries if daily limit exhausted
- [ ] T029 [P] [US2] Add rate limit handling to src/ingestion/sources/youtube.py — track YouTube API quota units consumed, stop YouTube queries when approaching daily quota (10,000 units), log quota usage
- [ ] T030 [US2] Implement source priority-based ingestion ordering in src/ingestion/handler.py — sort sources by priority field (highest first) so highest-value sources are processed first when rate limits constrain volume (FR-018)
- [ ] T031 [US2] Add per-source error isolation in src/ingestion/handler.py — wrap each source ingestion in try/except, log source_id + error details, continue to next source, include failed sources in PipelineRun.sources_failed list
- [ ] T032 [US2] Add YouTube transcript fallback chain in src/transcription/handler.py — try yt-dlp subtitle download first (auto-generated or manual captions), if unavailable extract audio via yt-dlp and send to AWS Transcribe, log which method succeeded, handle transcription failure gracefully (set transcript_status=failed, include item with "transcript unavailable" flag)
- [ ] T033 [US2] Add podcast audio download and transcription in src/transcription/handler.py — download audio from RSS enclosure URL, handle large files (>2 hours: log cost warning, check against daily transcription budget cap from settings.yaml, skip if would exceed budget), send to AWS Transcribe, poll for completion

**Checkpoint**: All five source types robust with graceful failure handling, rate limit management, and transcription fallbacks.

---

## Phase 5: User Story 3 — Context-Aware Relevance Scoring (Priority: P2)

**Goal**: Ensure scoring produces consistent, well-calibrated relevance scores with clear urgency classification and chain-of-thought reasoning.

**Independent Test**: Provide a set of sample content items (some highly relevant, some irrelevant), verify scoring correctly ranks relevant items higher with ±10 point consistency and appropriate urgency classifications.

### Implementation for User Story 3

- [ ] T034 [US3] Build structured scoring prompt in src/scoring/prompts/relevance.txt — chain-of-thought format requiring the LLM to (1) identify topic area, (2) assess relevance to transformation goals, (3) evaluate novelty/recency, (4) assign score 0-100, (5) classify urgency, (6) write relevance tag, (7) write 2-3 sentence summary; include 5-10 few-shot examples as score anchors; require JSON output format
- [ ] T035 [US3] Implement scoring consistency measures in src/scoring/handler.py — use temperature=0 for Bedrock/Claude calls, include few-shot examples in every prompt, log chain-of-thought reasoning in ScoredItem.scoring_reasoning field for auditability
- [ ] T036 [US3] Implement urgency classification logic in src/scoring/handler.py — map LLM output to enum (informational/worth_discussing/action_needed), validate classification is present and valid, default to informational if ambiguous
- [ ] T037 [US3] Add configurable relevance threshold in src/scoring/handler.py — read threshold from settings.yaml (default: 60), filter ScoredItems, log count of items above/below threshold per run

**Checkpoint**: Scoring pipeline produces consistent, well-calibrated results with chain-of-thought reasoning and configurable thresholds.

---

## Phase 6: User Story 4 — Configurable Source Management (Priority: P2)

**Goal**: Allow sources to be added or removed via configuration file without code changes.

**Independent Test**: Edit sources.yaml to add a new source, run the pipeline, verify the new source is ingested on the next run.

### Implementation for User Story 4

- [ ] T038 [US4] Implement source configuration validation in src/ingestion/config.py — validate sources.yaml schema (required fields: id, name, type, url; optional: category, active, priority), reject duplicates by id, warn on unknown source types, log validation results
- [ ] T039 [US4] Implement hot-reload of context prompt in src/scoring/handler.py — read config/context-prompt.txt at the start of each pipeline run (not cached across runs), allowing CTO to update scoring criteria without code changes (FR-019)
- [ ] T040 [US4] Create seed source list in config/sources.yaml — populate with 20+ high-quality sources: 5+ RSS/blog feeds (Simon Willison, The Pragmatic Engineer, etc.), 3+ Substack feeds, 3+ X accounts (AI/SDLC thought leaders), 3+ YouTube channels (AI engineering talks), 3+ podcast feeds (Latent Space, Practical AI, etc.), 3+ web sources; include category tags and priority rankings

**Checkpoint**: Source management is fully configuration-driven. Adding a source is a YAML edit.

---

## Phase 7: User Story 5 — Content Deduplication (Priority: P3)

**Goal**: Detect and merge duplicate content across multiple sources so the briefing doesn't contain repetitive items.

**Independent Test**: Feed two articles covering the same announcement from different sources, verify only one appears in the briefing.

### Implementation for User Story 5

- [ ] T041 [US5] Implement URL-based exact deduplication in src/scoring/deduplication.py — hash URLs, collapse identical URLs across sources at ingestion time, keep earliest ingested version
- [ ] T042 [US5] Implement LLM-based semantic deduplication in src/scoring/deduplication.py — during scoring, include instruction in the prompt to flag items that cover the same core development as a previously scored item, set is_duplicate=true and duplicate_of=primary_item_id on ScoredItem
- [ ] T043 [US5] Integrate deduplication into scoring pipeline in src/scoring/handler.py — run URL dedup before scoring, run semantic dedup during scoring, filter out duplicates before passing to briefing assembly, optionally include "also reported by" source list on primary item

**Checkpoint**: Briefing contains only unique developments, with duplicates collapsed to the highest-relevance version.

---

## Phase 8: User Story 6 — Pipeline Health and Cost Monitoring (Priority: P3)

**Goal**: Provide visibility into pipeline operational health and daily costs.

**Independent Test**: Run the pipeline, verify operational metrics are logged and accessible, trigger a cost alert by setting a low threshold.

### Implementation for User Story 6

- [ ] T044 [US6] Implement cost tracking in src/monitoring/handler.py — calculate estimated costs per run: Bedrock token usage (input + output tokens × rate), Transcribe minutes × rate, track X API monthly spend; write to PipelineRun.estimated_cost_usd
- [ ] T045 [US6] Implement cost alerting in src/monitoring/handler.py — compare daily cost against settings.yaml threshold, send alert email via SES if exceeded (FR-017)
- [ ] T046 [US6] Implement structured logging across all Lambda handlers — log source scan results, transcription job outcomes, scoring statistics (items scored, above threshold, duplicates removed), delivery status; use CloudWatch structured JSON logging format
- [ ] T047 [US6] Add CloudWatch custom metrics in src/monitoring/handler.py — publish to "AgenticSDLCIntel" namespace: sources_scanned, sources_failed, items_ingested, items_above_threshold, transcription_jobs, estimated_cost, delivery_latency_minutes, briefing_item_count
- [ ] T048 [US6] Configure CloudWatch dashboard and alarms in infra/stacks/monitoring_stack.py — dashboard with daily metrics graphs, alarms for: delivery failure, cost threshold exceeded, >3 consecutive source failures

**Checkpoint**: Full operational visibility with cost tracking, alerting, and CloudWatch dashboard.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T049 [P] Validate end-to-end pipeline with real sources — run full pipeline against production source list, verify email quality, scoring calibration, transcription accuracy
- [ ] T050 [P] Test email rendering across target clients — verify briefing HTML renders correctly on iOS Mail, Gmail (web + mobile), Outlook (desktop + web) per contracts/briefing-email.md
- [ ] T051 Add 30-day S3 lifecycle policy validation — verify lifecycle rules are applied to all prefixes (raw/, transcripts/, scored/, briefings/, runs/), test that objects are expired after 30 days
- [ ] T052 [P] Add consecutive source failure tracking in src/ingestion/handler.py — track per-source failure count across runs (store in S3), log warning after 3 consecutive failures for the same source per edge case spec
- [ ] T053 Run quickstart.md validation — follow quickstart.md step by step on a clean environment to verify setup instructions are complete and accurate
- [ ] T054 Security review — verify API keys and credentials are stored in AWS Secrets Manager or environment variables (not in config files), verify SES sender is properly authenticated, verify Lambda IAM roles follow least-privilege principle

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — this is the MVP
- **User Story 2 (Phase 4)**: Depends on User Story 1 (hardens ingestion built in US1)
- **User Story 3 (Phase 5)**: Depends on Foundational — can run in parallel with US1 if scoring handler is stubbed
- **User Story 4 (Phase 6)**: Depends on Foundational — can run in parallel with US1
- **User Story 5 (Phase 7)**: Depends on US1 + US3 (needs scoring pipeline to exist)
- **User Story 6 (Phase 8)**: Depends on US1 (needs pipeline to monitor)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational
    ↓
Phase 3: US1 — Daily Briefing (MVP) ←──────────────────┐
    ↓                                                    │
Phase 4: US2 — Ingestion Hardening (extends US1)        │
    ↓                                                    │
Phase 5: US3 — Relevance Scoring (can parallel US1/US2) │
    ↓                                                    │
Phase 6: US4 — Source Management (can parallel US1)      │
    ↓                                                    │
Phase 7: US5 — Deduplication (needs US1 + US3)           │
    ↓                                                    │
Phase 8: US6 — Monitoring (needs US1) ──────────────────┘
    ↓
Phase 9: Polish
```

### Recommended Sequential Path (solo developer)

Setup → Foundational → US1 (MVP) → US2 → US3 → US4 → US5 → US6 → Polish

### Parallel Opportunities

- Within Phase 1: T003, T004, T005, T006 can all run in parallel
- Within Phase 2: T008, T009, T010, T011, T012 can all run in parallel (after T007)
- Within US1: T014, T015, T016, T017, T018 can all run in parallel (source ingestion modules)
- Within US2: T028, T029 can run in parallel
- US3 + US4 can run in parallel with each other (both depend only on Foundational)
- Within US6: T044, T045, T046, T047 can run in parallel
- Within Polish: T049, T050, T053 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all source ingestion modules together (different files, no dependencies):
Task: "T014 [P] [US1] Implement RSS/Atom feed ingestion in src/ingestion/sources/rss.py"
Task: "T015 [P] [US1] Implement web page scraping in src/ingestion/sources/web.py"
Task: "T016 [P] [US1] Implement X API ingestion in src/ingestion/sources/x_api.py"
Task: "T017 [P] [US1] Implement YouTube ingestion in src/ingestion/sources/youtube.py"
Task: "T018 [P] [US1] Implement podcast feed ingestion in src/ingestion/sources/podcast.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (end-to-end pipeline)
4. **STOP and VALIDATE**: Run pipeline with real sources, verify email delivery and quality
5. Deploy and begin daily delivery to Owen only

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test end-to-end → Deploy (MVP — daily briefing works)
3. Add US2 → Harden ingestion → Redeploy (robust multi-format coverage)
4. Add US3 → Tune scoring → Redeploy (better signal-to-noise)
5. Add US4 → Populate seed list → Redeploy (easy source management)
6. Add US5 → Deduplicate → Redeploy (cleaner briefings)
7. Add US6 → Monitor → Redeploy (operational visibility)
8. Polish → Validate → Expand to full leadership group

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

### Constitution
# [PROJECT_NAME] Constitution
<!-- Example: Spec Constitution, TaskFlow Constitution, etc. -->

## Core Principles

### [PRINCIPLE_1_NAME]
<!-- Example: I. Library-First -->
[PRINCIPLE_1_DESCRIPTION]
<!-- Example: Every feature starts as a standalone library; Libraries must be self-contained, independently testable, documented; Clear purpose required - no organizational-only libraries -->

### [PRINCIPLE_2_NAME]
<!-- Example: II. CLI Interface -->
[PRINCIPLE_2_DESCRIPTION]
<!-- Example: Every library exposes functionality via CLI; Text in/out protocol: stdin/args → stdout, errors → stderr; Support JSON + human-readable formats -->

### [PRINCIPLE_3_NAME]
<!-- Example: III. Test-First (NON-NEGOTIABLE) -->
[PRINCIPLE_3_DESCRIPTION]
<!-- Example: TDD mandatory: Tests written → User approved → Tests fail → Then implement; Red-Green-Refactor cycle strictly enforced -->

### [PRINCIPLE_4_NAME]
<!-- Example: IV. Integration Testing -->
[PRINCIPLE_4_DESCRIPTION]
<!-- Example: Focus areas requiring integration tests: New library contract tests, Contract changes, Inter-service communication, Shared schemas -->

### [PRINCIPLE_5_NAME]
<!-- Example: V. Observability, VI. Versioning & Breaking Changes, VII. Simplicity -->
[PRINCIPLE_5_DESCRIPTION]
<!-- Example: Text I/O ensures debuggability; Structured logging required; Or: MAJOR.MINOR.BUILD format; Or: Start simple, YAGNI principles -->

## [SECTION_2_NAME]
<!-- Example: Additional Constraints, Security Requirements, Performance Standards, etc. -->

[SECTION_2_CONTENT]
<!-- Example: Technology stack requirements, compliance standards, deployment policies, etc. -->

## [SECTION_3_NAME]
<!-- Example: Development Workflow, Review Process, Quality Gates, etc. -->

[SECTION_3_CONTENT]
<!-- Example: Code review requirements, testing gates, deployment approval process, etc. -->

## Governance
<!-- Example: Constitution supersedes all other practices; Amendments require documentation, approval, migration plan -->

[GOVERNANCE_RULES]
<!-- Example: All PRs/reviews must verify compliance; Complexity must be justified; Use [GUIDANCE_FILE] for runtime development guidance -->

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Example: Version: 2.1.1 | Ratified: 2025-06-13 | Last Amended: 2025-07-16 -->

## Guardrails
### Sign: Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Read the file first
- **Added after**: Core principle


### Sign: Test Before Commit
- **Trigger**: Before committing changes
- **Instruction**: Run required tests and verify outputs
- **Added after**: Core principle

## Instructions

### Behavior Extraction

1. Read each user story's acceptance scenarios in spec.md.
2. For each scenario, extract one or more testable behaviors. A behavior is a single observable outcome through a public interface.
3. Map each behavior to the task ID(s) in tasks.md that will implement it.
4. Order behaviors to respect task dependency ordering from tasks.md.
5. Group behaviors by user story.
6. If a scenario is ambiguous, flag it with `⚠️` in the description.

### Interface Definition

1. From plan.md project structure and spec.md requirements, identify all public modules/classes/functions.
2. Describe each public method with: name, parameters, return type/description, and which behaviors exercise it.
3. Use language-agnostic prose — do NOT write code. The blind validator will use this to judge whether tests exercise public interfaces only.

### Constitution Validation

If a constitution is provided, validate that:
- The behavior queue respects vertical slicing (one behavior at a time)
- No behavior requires accessing internal implementation details
- Test-driven design principles are preserved in the ordering

Flag any violations.

## Output Format

You MUST produce output in exactly this format:

```
# Behavior Queue

## User Story N: [Title]

| ID   | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B001 | [behavior description] | US1.S1 | T001 | queued |
| B002 | [behavior description] | US1.S2 | T002 | queued |

# Public Interfaces

## [Module/Class Name]

**Purpose**: [what this module does]

**Public methods**:
- `method_name(params)` → return: [description]

**Exercised by**: B001, B002
```

Important:
- Every behavior MUST have status `queued`
- Every behavior MUST link to at least one task ID from tasks.md
- Scenario references use format `USn.Sn` (User Story number, Scenario number)
- The `# Behavior Queue` and `# Public Interfaces` headings are required section markers
