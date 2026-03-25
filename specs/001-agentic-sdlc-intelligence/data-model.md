# Data Model: Agentic SDLC Daily Intelligence Briefing Agent

**Branch**: `001-agentic-sdlc-intelligence` | **Date**: 2026-03-24

## Entities

### Source

A content channel monitored by the agent. Defined in `config/sources.yaml`.

| Field        | Type                                          | Required | Description                              |
|--------------|-----------------------------------------------|----------|------------------------------------------|
| id           | string (slug)                                 | yes      | Unique identifier, e.g., "simon-willison-blog" |
| name         | string                                        | yes      | Display name, e.g., "Simon Willison's Weblog" |
| type         | enum: rss, web, x, youtube, podcast           | yes      | Source format type                        |
| url          | string (URL or identifier)                    | yes      | Feed URL, account handle, channel ID, etc. |
| category     | string                                        | no       | Topic category tag, e.g., "agentic-tools" |
| active       | boolean                                       | no       | Default: true. Set false to disable without removing |
| priority     | integer (1-10)                                | no       | Default: 5. Used for rate-limit prioritization |

**Identity rule**: `id` must be unique across all sources.

### ContentItem

A single piece of ingested content. Stored in S3 as JSON at `raw/{date}/{source_id}/{item_id}.json`.

| Field            | Type                                      | Required | Description                              |
|------------------|-------------------------------------------|----------|------------------------------------------|
| item_id          | string (hash of url)                      | yes      | Unique identifier derived from source URL |
| source_id        | string                                    | yes      | Reference to Source.id                    |
| title            | string                                    | yes      | Content title                             |
| url              | string (URL)                              | yes      | Original content URL                      |
| published_at     | datetime (ISO 8601)                       | yes      | Publication timestamp                     |
| ingested_at      | datetime (ISO 8601)                       | yes      | When the pipeline retrieved this item     |
| content_format   | enum: text, audio, video                  | yes      | Original content format                   |
| full_text        | string                                    | conditional | Extracted text (for text items) or transcript (for audio/video). Null if transcription pending/failed |
| transcript_status | enum: not_needed, pending, completed, failed | yes   | Transcription status for audio/video items; "not_needed" for text |
| word_count       | integer                                   | no       | Word count of full_text, when available   |

**Identity rule**: `item_id` (hash of `url`) must be unique within a daily run. Duplicate URLs across sources are collapsed at ingestion.

**State transitions for transcript_status**:
```
text items:    not_needed (terminal)
audio/video:   pending → completed
               pending → failed
```

### ScoredItem

A content item with relevance assessment. Stored in S3 as JSON at `scored/{date}/{item_id}.json`.

| Field           | Type                                       | Required | Description                              |
|-----------------|--------------------------------------------|----------|------------------------------------------|
| item_id         | string                                     | yes      | Reference to ContentItem.item_id          |
| relevance_score | integer (0-100)                            | yes      | LLM-assigned relevance score              |
| urgency         | enum: informational, worth_discussing, action_needed | yes | Urgency classification            |
| relevance_tag   | string                                     | yes      | 1-sentence explanation of why this matters |
| summary         | string                                     | yes      | 2-3 sentence executive summary            |
| is_duplicate    | boolean                                    | yes      | Whether this is a duplicate of another item |
| duplicate_of    | string                                     | no       | item_id of the primary item (if duplicate) |
| scoring_reasoning | string                                   | no       | Chain-of-thought reasoning from the LLM   |

**Identity rule**: One ScoredItem per ContentItem per daily run.

### Briefing

The assembled daily output. Stored in S3 as JSON + HTML at `briefings/{date}/briefing.json` and `briefings/{date}/briefing.html`.

| Field           | Type                                       | Required | Description                              |
|-----------------|--------------------------------------------|----------|------------------------------------------|
| date            | date (ISO 8601)                            | yes      | Briefing date                             |
| generated_at    | datetime (ISO 8601)                        | yes      | When the briefing was assembled           |
| items           | list of ScoredItem references (ranked)     | yes      | Top 5-10 items by relevance score, deduplicated |
| item_count      | integer                                    | yes      | Number of items in the briefing           |
| delivery_status | enum: pending, sent, failed                | yes      | Email delivery status                     |
| delivered_at    | datetime (ISO 8601)                        | no       | When SES confirmed delivery               |
| is_empty        | boolean                                    | yes      | True if no items passed threshold ("no significant developments") |

**State transitions for delivery_status**:
```
pending → sent
pending → failed
```

### Recipient

A briefing recipient. Defined in `config/settings.yaml`.

| Field      | Type           | Required | Description                  |
|------------|----------------|----------|------------------------------|
| name       | string         | yes      | Display name                  |
| email      | string (email) | yes      | Delivery email address        |
| timezone   | string (IANA)  | yes      | e.g., "America/New_York"     |

### PipelineRun

Operational record for each daily execution. Stored in S3 at `runs/{date}/run.json`.

| Field                | Type              | Required | Description                              |
|----------------------|-------------------|----------|------------------------------------------|
| run_date             | date (ISO 8601)   | yes      | Date of the pipeline run                  |
| started_at           | datetime           | yes      | Pipeline start time                       |
| completed_at         | datetime           | no       | Pipeline completion time                  |
| sources_attempted    | integer            | yes      | Number of sources the pipeline tried to ingest |
| sources_succeeded    | integer            | yes      | Number of sources successfully ingested   |
| sources_failed       | list of {source_id, error} | yes | Failed sources with error details    |
| items_ingested       | integer            | yes      | Total content items retrieved             |
| items_scored         | integer            | yes      | Items that went through scoring           |
| items_above_threshold | integer           | yes      | Items scoring above the relevance threshold |
| items_in_briefing    | integer            | yes      | Items included after deduplication        |
| transcription_jobs   | integer            | yes      | Number of transcription jobs dispatched   |
| estimated_cost_usd   | float              | yes      | Estimated total cost for this run         |
| delivery_status      | enum: on_time, late, failed | yes | Whether briefing was delivered by target time |
| briefing_delivered_at | datetime          | no       | Actual delivery time                      |

## Relationships

```
Source (1) ──── (many) ContentItem
ContentItem (1) ──── (1) ScoredItem
Briefing (1) ──── (many) ScoredItem
Briefing (1) ──── (many) Recipient
PipelineRun (1) ──── (1) Briefing
```

## Storage Layout (S3)

```
s3://{bucket}/
├── raw/{date}/{source_id}/{item_id}.json          # ContentItem
├── transcripts/{date}/{item_id}.txt                # Raw transcript text
├── scored/{date}/{item_id}.json                    # ScoredItem
├── briefings/{date}/briefing.json                  # Briefing metadata
├── briefings/{date}/briefing.html                  # Rendered email HTML
├── runs/{date}/run.json                            # PipelineRun
└── config/                                          # Snapshot of config used for each run
    └── {date}/sources.yaml
```

All prefixes subject to 30-day S3 lifecycle expiration policy.
