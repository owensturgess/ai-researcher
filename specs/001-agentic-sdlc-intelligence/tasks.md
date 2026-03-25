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

- [x] T013 [US1] Implement source configuration loader in src/ingestion/config.py — parse sources.yaml, filter active sources, return typed Source objects
- [x] T014 [P] [US1] Implement RSS/Atom feed ingestion in src/ingestion/sources/rss.py — use feedparser to retrieve entries published in last 24 hours, extract title, URL, published date, full text, return list of ContentItem
- [x] T015 [P] [US1] Implement web page scraping in src/ingestion/sources/web.py — use requests + beautifulsoup4 to fetch and extract article text, handle HTML cleanup, return ContentItem
- [x] T016 [P] [US1] Implement X (Twitter) API ingestion in src/ingestion/sources/x_api.py — use tweepy to retrieve recent tweets from configured accounts/searches (last 24 hours), handle rate limits, return list of ContentItem
- [x] T017 [P] [US1] Implement YouTube ingestion in src/ingestion/sources/youtube.py — use YouTube Data API v3 for channel/search queries (last 24 hours), retrieve video metadata, return list of ContentItem with content_format=video
- [x] T018 [P] [US1] Implement podcast feed ingestion in src/ingestion/sources/podcast.py — parse podcast RSS feeds for new episodes (last 24 hours), extract enclosure URLs for audio download, return list of ContentItem with content_format=audio
- [x] T019 [US1] Implement ingestion Lambda handler in src/ingestion/handler.py — orchestrate all source types, write ContentItems to S3 (raw/{date}/{source_id}/{item_id}.json), enqueue audio/video items to SQS transcription queue, write manifest to S3 with pending transcription count, handle per-source failures gracefully (log and continue)
- [x] T020 [US1] Implement transcription Lambda handler in src/transcription/handler.py — process SQS messages, for YouTube items try transcript retrieval via yt-dlp subtitles first then fall back to AWS Transcribe, for podcasts download audio and send to AWS Transcribe, write transcripts to S3 (transcripts/{date}/{item_id}.txt), update manifest pending count, trigger scoring when all transcriptions complete
- [x] T021 [US1] Implement relevance scoring in src/scoring/handler.py — load all ContentItems + transcripts from S3 for the day, load context-prompt.txt, call Bedrock/Claude for each item with structured JSON output (score, urgency, relevance_tag, summary), write ScoredItems to S3 (scored/{date}/{item_id}.json), filter by relevance threshold from settings.yaml
- [x] T022 [US1] Implement briefing assembly and email delivery in src/briefing/handler.py — load ScoredItems above threshold, sort by urgency group (action_needed → worth_discussing → informational) then by score descending within group, cap at max_briefing_items, render Jinja2 email template, send via SES to all recipients, write briefing metadata to S3 (briefings/{date}/briefing.json)
- [x] T023 [US1] Create mobile-friendly HTML email template in src/briefing/templates/briefing.html — table-based layout per contracts/briefing-email.md, inline CSS, 600px max width, urgency-grouped sections with colored borders, item blocks with title/source/summary/relevance-tag/link, pipeline stats footer
- [x] T024 [US1] Implement "no significant developments" email variant in src/briefing/handler.py — when no items pass threshold, send confirmation email per contracts/briefing-email.md empty variant
- [x] T025 [US1] Implement fallback error notification in src/briefing/handler.py — if pipeline fails, send error notification email per contracts/briefing-email.md fallback variant with error summary, failed stage, and timestamp
- [x] T026 [US1] Wire Lambda functions in infra/stacks/pipeline_stack.py — create Lambda functions for ingestion, transcription, scoring, and briefing handlers; connect EventBridge cron → ingestion, SQS → transcription, S3 manifest event → scoring, scoring completion → briefing; set IAM roles for S3, SQS, Transcribe, Bedrock, SES access
- [x] T027 [US1] Write PipelineRun record in src/ingestion/handler.py and src/briefing/handler.py — track started_at, completed_at, sources_attempted/succeeded, items_ingested/scored/above_threshold/in_briefing, transcription_jobs, delivery_status, write to S3 (runs/{date}/run.json)

**Checkpoint**: End-to-end pipeline functional — daily briefing delivered via email with multi-format ingestion, transcription, scoring, and assembly. This is the MVP.

---

## Phase 4: User Story 2 — Multi-Format Source Ingestion Hardening (Priority: P1)

**Goal**: Harden ingestion across all five source types with robust error handling, rate limit management, and source failure isolation.

**Independent Test**: Configure sources across all five format types, induce failures in individual sources, verify pipeline continues and logs failures without blocking.

### Implementation for User Story 2

- [x] T028 [P] [US2] Add rate limit handling to src/ingestion/sources/x_api.py — implement backoff on 429 responses, respect X-Rate-Limit headers, log rate limit events, skip remaining X queries if daily limit exhausted
- [x] T029 [P] [US2] Add rate limit handling to src/ingestion/sources/youtube.py — track YouTube API quota units consumed, stop YouTube queries when approaching daily quota (10,000 units), log quota usage
- [x] T030 [US2] Implement source priority-based ingestion ordering in src/ingestion/handler.py — sort sources by priority field (highest first) so highest-value sources are processed first when rate limits constrain volume (FR-018)
- [x] T031 [US2] Add per-source error isolation in src/ingestion/handler.py — wrap each source ingestion in try/except, log source_id + error details, continue to next source, include failed sources in PipelineRun.sources_failed list
- [x] T032 [US2] Add YouTube transcript fallback chain in src/transcription/handler.py — try yt-dlp subtitle download first (auto-generated or manual captions), if unavailable extract audio via yt-dlp and send to AWS Transcribe, log which method succeeded, handle transcription failure gracefully (set transcript_status=failed, include item with "transcript unavailable" flag)
- [x] T033 [US2] Add podcast audio download and transcription in src/transcription/handler.py — download audio from RSS enclosure URL, handle large files (>2 hours: log cost warning, check against daily transcription budget cap from settings.yaml, skip if would exceed budget), send to AWS Transcribe, poll for completion

**Checkpoint**: All five source types robust with graceful failure handling, rate limit management, and transcription fallbacks.

---

## Phase 5: User Story 3 — Context-Aware Relevance Scoring (Priority: P2)

**Goal**: Ensure scoring produces consistent, well-calibrated relevance scores with clear urgency classification and chain-of-thought reasoning.

**Independent Test**: Provide a set of sample content items (some highly relevant, some irrelevant), verify scoring correctly ranks relevant items higher with ±10 point consistency and appropriate urgency classifications.

### Implementation for User Story 3

- [x] T034 [US3] Build structured scoring prompt in src/scoring/prompts/relevance.txt — chain-of-thought format requiring the LLM to (1) identify topic area, (2) assess relevance to transformation goals, (3) evaluate novelty/recency, (4) assign score 0-100, (5) classify urgency, (6) write relevance tag, (7) write 2-3 sentence summary; include 5-10 few-shot examples as score anchors; require JSON output format
- [x] T035 [US3] Implement scoring consistency measures in src/scoring/handler.py — use temperature=0 for Bedrock/Claude calls, include few-shot examples in every prompt, log chain-of-thought reasoning in ScoredItem.scoring_reasoning field for auditability
- [x] T036 [US3] Implement urgency classification logic in src/scoring/handler.py — map LLM output to enum (informational/worth_discussing/action_needed), validate classification is present and valid, default to informational if ambiguous
- [x] T037 [US3] Add configurable relevance threshold in src/scoring/handler.py — read threshold from settings.yaml (default: 60), filter ScoredItems, log count of items above/below threshold per run

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
