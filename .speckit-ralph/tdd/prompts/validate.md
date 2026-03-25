# VALIDATE Step: Blind Test Quality Review

You are the **Blind Validator** in a TDD loop. Your job is to review a test for quality WITHOUT seeing the implementation source code. You receive only the test file, the public interface definitions, and the TDD quality checklist.

**IMPORTANT: You do NOT have access to implementation source code. You MUST NOT request or assume knowledge of implementation details.**

## TDD Quality Checklist

Review the test against EVERY item below. A test MUST pass ALL checks to be approved.

1. **Behavior-based naming**: Test name describes WHAT the system does (observable behavior), not HOW it does it.
2. **Public interface only**: Test interacts ONLY with public methods/functions described in the interfaces section below. No access to private/internal methods, attributes, or implementation details.
3. **Survives refactor**: Test would still pass if the implementation were completely rewritten but the public interface contract was preserved.
4. **Mocks only at system boundaries**: Test ONLY mocks external dependencies (APIs, databases, filesystem, network). REJECTS if test mocks internal collaborators (classes/functions within the project).
5. **No unmocked external deps**: Test DOES NOT call real external services. REJECTS if test hits a real API, database, or network endpoint without mocking.
6. **One logical assertion**: Test has one logical assertion (multiple asserts on the same outcome are acceptable, but testing multiple independent behaviors is not).
7. **Independence**: Test does not depend on other tests, shared mutable state, or execution order.
8. **Meaningful failure**: If the test were to fail, the failure message would clearly indicate what behavior broke.

## Output Format

You MUST output your review in this exact format:

```
VALIDATION_RESULT: PASS
```

or

```
VALIDATION_RESULT: FAIL
FEEDBACK: <specific, actionable feedback explaining which checks failed and how to fix them>
```

If FAIL, the FEEDBACK section MUST:
- State which checklist item(s) failed
- Quote the specific line(s) that violate the rule
- Describe exactly what to change

Do NOT include general advice. Be specific and actionable.

## Test File Under Review

# tests/unit/test_deduplication_five_sources.py
# tests/unit/test_deduplication_five_sources.py
#
# Behavior B030: When the same development is announced across 5+ sources,
# the deduplication step selects the single best representative item, with
# other source links optionally listed as "also reported by".
#
# Tests the public interface deduplicate_by_semantics(scored_items) in
# src/scoring/deduplication.py. When 5 ScoredItems all cover the same core
# development, the highest-relevance item must be retained as primary and all
# four others flagged as duplicates. The primary item must expose an
# also_reported_by attribute listing the content_item_ids of the other
# sources — enabling the briefing template to surface "also covered by 4
# other sources" without cluttering the main item list.
#
# This test fails (RED) because ScoredItem has no also_reported_by field and
# deduplicate_by_semantics does not populate it.
import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_five_sources_same_development_best_item_retained_with_also_reported_by():
    """
    Given five ScoredItems from different sources all covering the same GPT-5
    release (scores 90, 75, 65, 55, 45), when deduplicate_by_semantics() runs:

    1. Exactly one item has is_duplicate=False (the score-90 primary).
    2. All four remaining items have is_duplicate=True and duplicate_of equal
       to the primary item's content_item_id.
    3. The primary item has an also_reported_by attribute that is a list
       containing the content_item_ids of all four duplicate items — so the
       briefing renderer can append "also reported by: source-b, source-c, …"
       without re-querying the full scored list.
    """
    items = [
        ScoredItem(
            content_item_id="item-gpt5-source-a",
            relevance_score=90,
            urgency="action_needed",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "OpenAI releases GPT-5 with reasoning and agentic capabilities "
                "that set a new industry benchmark for AI-assisted software development."
            ),
            scoring_reasoning="Primary source with deepest technical analysis.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-b",
            relevance_score=75,
            urgency="worth_discussing",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "GPT-5 announced by OpenAI; industry observers note significant "
                "improvements over GPT-4 in coding benchmarks."
            ),
            scoring_reasoning="Same GPT-5 release from a different outlet.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-c",
            relevance_score=65,
            urgency="worth_discussing",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "OpenAI's GPT-5 model launched today with multimodal and agentic features."
            ),
            scoring_reasoning="Same release, shorter coverage.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-d",
            relevance_score=55,
            urgency="informational",
            relevance_tag="AI Tools",
            executive_summary=(
                "GPT-5 is here: OpenAI drops its most powerful model yet."
            ),
            scoring_reasoning="Consumer-angle reporting on the same release.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-e",
            relevance_score=45,
            urgency="informational",
            relevance_tag="AI Tools",
            executive_summary=(
                "OpenAI announces GPT-5 availability for ChatGPT Plus users."
            ),
            scoring_reasoning="Brief product-availability notice for the same release.",
            is_duplicate=False,
            duplicate_of=None,
        ),
    ]

    # All five items cover the same GPT-5 release — LLM returns is_duplicate=true
    # for every pairwise comparison initiated by the implementation.
    def invoke_model_side_effect(modelId, body, **kwargs):
        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps(
            {"content": [{"text": json.dumps({"is_duplicate": True})}]}
        ).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = invoke_model_side_effect

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics(items)

    by_id = {item.content_item_id: item for item in result}

    # --- Assertion 1: exactly one non-duplicate (the highest-scoring primary) ---
    non_duplicates = [item for item in result if not item.is_duplicate]
    assert len(non_duplicates) == 1, (
        f"Expected exactly 1 non-duplicate item, got {len(non_duplicates)}: "
        f"{[i.content_item_id for i in non_duplicates]}"
    )
    primary = non_duplicates[0]
    assert primary.content_item_id == "item-gpt5-source-a", (
        f"The highest-relevance item (score 90) must be the primary; "
        f"got: {primary.content_item_id}"
    )

    # --- Assertion 2: all four remaining items flagged as duplicates of the primary ---
    duplicate_ids = {"item-gpt5-source-b", "item-gpt5-source-c",
                     "item-gpt5-source-d", "item-gpt5-source-e"}
    for item_id in duplicate_ids:
        item = by_id[item_id]
        assert item.is_duplicate is True, (
            f"{item_id} must be flagged is_duplicate=True when 5 sources cover "
            "the same development and it is not the highest-relevance item."
        )
        assert item.duplicate_of == "item-gpt5-source-a", (
            f"{item_id}.duplicate_of must point to the primary item "
            f"'item-gpt5-source-a', got: {item.duplicate_of!r}"
        )

    # --- Assertion 3: primary item exposes also_reported_by list of duplicate IDs ---
    # This will FAIL (RED) because ScoredItem has no also_reported_by field and
    # deduplicate_by_semantics does not populate it.
    assert hasattr(primary, "also_reported_by"), (
        "The primary ScoredItem must have an 'also_reported_by' attribute so that "
        "the briefing renderer can append 'also reported by: …' without re-scanning "
        "the full scored list. Add also_reported_by to ScoredItem and populate it "
        "in deduplicate_by_semantics()."
    )
    also_reported = set(primary.also_reported_by)
    assert also_reported == duplicate_ids, (
        f"primary.also_reported_by must contain the ids of all 4 duplicate items. "
        f"Expected: {duplicate_ids}, got: {also_reported}"
    )

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
- `deduplicate_by_url(items: list of ContentItem)` → return: List of ContentItem with exact URL duplicates removed (keeps earliest ingested). ⚠️ The spec says "highest-relevance version" for dedup, but URL dedup runs before scoring — this stage uses earliest-ingested as tiebreaker; semantic dedup after scoring uses relevance.
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

The constitution contains only template placeholders with no specific principles defined. Standard validations applied:

1. **Vertical slicing**: Each behavior tests a single observable outcome. Behaviors are ordered to respect task dependencies (shared models -> ingestion -> transcription -> scoring -> briefing -> monitoring).
2. **Public interface only**: All behaviors are defined against public handler entry points, public module functions, and observable outputs (emails, S3 objects, CloudWatch metrics). No behavior requires accessing internal implementation details.
3. **Test-driven ordering**: Behaviors are sequenced so that foundational behaviors (B001-B005: briefing delivery) precede source-specific behaviors (B007-B010), which precede hardening behaviors (B013-B018).
4. **Guardrail compliance**: "Read Before Writing" and "Test Before Commit" guardrails are compatible with the behavior queue.

⚠️ **Flag**: `deduplicate_by_url` in B028 runs before scoring but the spec (US5.S1) says "only the highest-relevance version appears" — URL dedup cannot use relevance scores. The interface definition notes this: URL dedup uses earliest-ingested as tiebreaker; semantic dedup after scoring uses relevance. Tests should validate both stages separately.

---

**Current progress**: B001-B005 complete, B006 in RED phase. Next behavior to implement: B006 (pipeline run metadata recording). The behavior queue and public interfaces are stable and consistent with all spec artifacts.

## Guardrails (lessons from previous failures — follow these)

### Sign: Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Read the file first
- **Added after**: Core principle


### Sign: Test Before Commit
- **Trigger**: Before committing changes
- **Instruction**: Run required tests and verify outputs
- **Added after**: Core principle


### Sign: Missing sys.path and package stubs cause patch ImportError
- **Category**: RED-FAILURE
- **Detail**: `patch("src.ingestion.handler.load_sources", ...)` raises `ModuleNotFoundError: No module named 'src'` when the project root isn't on `sys.path` and `src/__init__.py` doesn't exist. Fix: create `conftest.py` at repo root with `sys.path.insert(0, os.path.dirname(__file__))`, create empty `__init__.py` files for each package level, and create minimal stub modules for each patch target before writing the RED test.
- **Added after**: B006 at 2026-03-25T02:04:10Z


### Sign: pip shim broken for older Python, use python3 -m pip
- **Category**: GREEN-FAILURE
- **Detail**: `/usr/local/bin/pip` pointed to a removed Python 3.9 interpreter. Use `python3 -m pip install <pkg>` to target the active interpreter. Always install packages via `python3 -m pip` rather than bare `pip` in this environment.
- **Added after**: B009 at 2026-03-25T02:58:00Z


### Sign: B024 behavior A already implemented — RED phase produces GREEN test
- **Category**: RED-FAILURE
- **Detail**: The source-removal behavior (B024 Behavior A) is already covered by the existing `handler.py` implementation: `load_sources()` reads only from the active `SOURCES_CONFIG` file, so any source absent from YAML is never attempted. The corrected single-assertion RED test (`sources_attempted == 1`, no S3 keys under `src-removed-002/`, at least one key under `src-remaining-001/`) passes immediately without new implementation. When a behavior is already implemented by prior GREEN phases, the RED test will be green from the start — treat this as "behavior pre-implemented" and advance directly to VALIDATE.
- **Added after**: B024 at 2026-03-25T04:22:49Z


### Sign: B029 behavior pre-implemented — RED phase produces GREEN test
- **Category**: RED-FAILURE
- **Detail**: The "different angles → both retained" path (B029) is automatically satisfied by the B028 implementation in `deduplicate_by_semantics`. When `_are_duplicates()` returns `False`, the function simply skips flagging — no additional code path needed. The RED test passes immediately. Per the established guardrail pattern (see B024), advance directly to VALIDATE.
- **Added after**: B029 at 2026-03-25T04:38:24Z
