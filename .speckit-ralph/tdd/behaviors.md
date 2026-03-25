The behavior queue and public interfaces already exist and are well-defined. Let me verify them against the current spec artifacts and produce the updated PLAN output.

# Behavior Queue

## User Story 1: Daily Morning Briefing Delivery

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B001 | When the daily scheduled run executes with at least one active source configured, an email briefing is delivered to each configured recipient's inbox | US1.S1 | T019, T022, T026 | complete |
| B002 | Each briefing item displays a title, source name, 2-3 sentence executive summary, relevance tag, urgency indicator (Informational / Worth Discussing / Action Needed), and a clickable source link | US1.S2 | T021, T022, T023 | complete |
| B003 | The briefing email renders correctly on mobile devices with clear hierarchy and no horizontal scrolling | US1.S3 | T023 | complete |
| B004 | When the pipeline fails before the delivery deadline, a fallback notification email is sent to all recipients explaining the delay and expected resolution | US1.S4 | T025 | complete |
| B005 | When no items pass the relevance threshold, a "no significant developments" confirmation email is sent instead of an empty or missing briefing | Edge Case | T024 | complete |
| B006 | Pipeline run metadata is recorded including sources attempted/succeeded, items ingested/scored/included, transcription jobs, and delivery status | US1.S1 | T027 | complete |

## User Story 2: Multi-Format Source Ingestion

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B007 | Given a configured source list with RSS/web entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from RSS/web sources | US2.S1 | T014, T015, T019 | complete |
| B008 | Given a configured source list with X (Twitter) entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from X sources | US2.S1 | T016, T019 | complete |
| B009 | Given a configured source list with YouTube entries, when daily ingestion runs, new content published in the last 24 hours is retrieved from YouTube sources | US2.S1 | T017, T019 | complete |
| B010 | Given a configured source list with podcast entries, when daily ingestion runs, new episodes published in the last 24 hours are retrieved from podcast feeds | US2.S1 | T018, T019 | complete |
| B011 | Given a YouTube video published in the last 24 hours, the full transcript is available — retrieved via YouTube transcript first, with audio transcription as fallback | US2.S2 | T020, T032 | complete |
| B012 | Given a podcast episode published in the last 24 hours, the episode audio is transcribed and full text is available for scoring | US2.S3 | T020, T033 | complete |
| B013 | Given one source is temporarily unavailable (HTTP error, rate limit), the failure is logged, the source is skipped, and all other sources process normally | US2.S4 | T031 | complete |
| B014 | When the X API rate limit is hit mid-ingestion, the system logs the event, processes already-retrieved sources, and continues with other source types | Edge Case | T028 | complete |
| B015 | When the YouTube API quota approaches its daily limit, YouTube queries stop and the pipeline continues with other source types | Edge Case | T029 | complete |
| B016 | When a YouTube video has no transcript and transcription fails, the item is included with a "transcript unavailable" flag; title, source, and link are still provided | Edge Case | T032 | complete |
| B017 | When a podcast episode exceeds 2 hours and would exceed the daily transcription budget cap, it is flagged as "transcript unavailable" with the link still included | Edge Case | T033 | complete |
| B018 | Sources are processed in priority order so highest-value sources are ingested first when rate limits constrain volume | FR-018 | T030 | complete |

## User Story 3: Context-Aware Relevance Scoring

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B019 | Given a batch of ingested content items, each item receives a relevance score (0-100) based on the configured company context | US3.S1 | T021, T034, T035 | complete |
| B020 | Given the relevance threshold is set to 60 (default), only items scoring above 60 appear in the final briefing | US3.S2 | T037 | complete |
| B021 | Given a scored item passes the relevance threshold, it is classified with an urgency level: Informational, Worth Discussing, or Action Needed | US3.S3 | T036 | complete |
| B022 | Given the same content item is processed on two consecutive days, the scores are consistent within ±10 points (scoring reliability) | US3.S4 | T035 | complete |

## User Story 4: Configurable Source Management

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B023 | Given a source configuration file, when a user adds a new source entry with name, type, URL, and optional category, the new source is included in the next daily pipeline run | US4.S1 | T013, T038 | complete |
| B024 | Given a source is removed from the configuration file, content from that source is no longer ingested on the next run | US4.S2 | T013, T038 | complete |
| B025 | The seed source list contains at least 20 sources spanning all supported format types (RSS/web, X, YouTube, podcasts, Substack) | US4.S3 | T040 | complete |
| B026 | The relevance scoring context prompt can be updated without code changes, taking effect on the next pipeline run | FR-019 | T039 | complete |
| B027 | Source configuration is validated: required fields enforced, duplicates rejected, unknown types warned | US4.S1 | T038 | complete |

## User Story 5: Content Deduplication

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B028 | Given two content items from different sources cover the same development, only the highest-relevance version appears in the briefing | US5.S1 | T041, T042, T043 | complete |
| B029 | Given two items have similar topics but genuinely different angles or insights, both items are retained as distinct entries | US5.S2 | T042, T043 | complete |
| B030 | When the same development is announced across 5+ sources, the deduplication step selects the single best representative item, with other source links optionally listed as "also reported by" | Edge Case | T042, T043 | complete |

## User Story 6: Pipeline Health and Cost Monitoring

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B031 | When the daily pipeline completes, logs show: sources scanned, items ingested, items scored above threshold, transcription jobs run, and total estimated cost | US6.S1 | T044, T046 | complete |
| B032 | When daily costs exceed a configurable threshold, a cost alert notification is sent to configured recipients | US6.S2 | T045 | complete |
| B033 | After 7 consecutive days, an operator can see delivery reliability (% on-time) and average cost per run | US6.S3 | T047, T048 | complete |
| B034 | A source that fails for 3 consecutive days triggers a warning in operator metrics | Edge Case | T052 | complete |
| B035 | CloudWatch custom metrics are published to the "AgenticSDLCIntel" namespace with dashboard and alarms | US6.S1 | T047, T048 | complete |

## Cross-Cutting: Data Retention

| ID | Description | Scenario | Tasks | Status |
|------|-------------|----------|-------|--------|
| B036 | Raw content, transcripts, scored items, and briefings older than 30 days are automatically deleted | FR-021 | T010, T051 | queued |

