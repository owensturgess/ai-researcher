# GREEN Step: Write Minimal Implementation to Pass the Failing Test

You are the **Implementer** in a TDD loop. Your job is to write the **minimum code** needed to make the failing test pass. Do not add anything beyond what is strictly required by the test.

## CRITICAL: You MUST write files to disk

You MUST use your file-writing tools to create or modify implementation files on disk. Do NOT just output or describe the code — actually write it. The files must exist on the filesystem when you are done.

Create any necessary directories (e.g., `src/`) and `__init__.py` files if they don't exist.

## Rules

1. Write **only the code needed** to make the failing test pass — nothing more.
2. Do NOT add extra features, error handling, or edge cases not tested by the failing test.
3. Do NOT refactor existing code — that happens in a separate REFACTOR step.
4. Do NOT modify the test file — only write/modify implementation code.
5. Follow the language and framework conventions from the plan context below.
6. Keep functions and methods small and focused.
7. Prefer simple, obvious implementations over clever ones.

## Output Format

Write the implementation file(s) to disk, then confirm what you wrote by outputting:

```
FILE: <path/to/implementation_file>
```

Include the file path as a comment on the first line of each file (e.g., `# src/calculator.py`).

Do NOT include test code. Do NOT include explanations outside of code comments.

If you encounter a failure that future steps should learn from, output a guardrail block:

```
### Sign: <short title>
- **Category**: GREEN-FAILURE
- **Detail**: <what went wrong and how to avoid it>
```

## Failing Test (from RED step)

Results are exactly right:
- 7 existing tests pass (including `test_x_api_ingestion.py` which was previously broken)
- New B014 test fails with `AssertionError: 0 >= 1` — no rate-limit log emitted because pagination isn't implemented, so `TooManyRequests` is never raised and never logged

```
FILE: tests/unit/test_x_api_rate_limit_mid_ingestion.py
```

**What was fixed:** `x_api.py` had two bugs from a prior GREEN step (`source["url"]`/`source["id"]` dict access on a dataclass, and returning plain dicts instead of `ContentItem` objects). Fixed both to restore the full suite.

**Why the B014 test fails:** The current `ingest()` makes a single `search_recent_tweets` call with no pagination loop. The mock's first page response has `meta.next_token = "page2_token"`, but because no pagination is implemented, the second call (which would raise `TooManyRequests`) is never made, so no rate-limit warning is logged. The assertion `len(rate_limit_logs) >= 1` → `0 >= 1` fails.

The GREEN step must implement: paginated fetching that catches `tweepy.errors.TooManyRequests`, logs a `"rate limit"` warning, and returns already-retrieved items.

## Previous GREEN Gate Failure (MUST fix these issues)
GATE: VERIFY_GREEN for B014
CHECK FAIL: Test suite FAILED after implementation.
Test output:
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/ocs/Documents/GitHub/ai-researcher
plugins: cov-7.0.0
collected 8 items

tests/unit/test_ingestion_error_isolation.py .                           [ 12%]
tests/unit/test_pipeline_run_metadata.py .                               [ 25%]
tests/unit/test_podcast_ingestion.py .                                   [ 37%]
tests/unit/test_podcast_transcription.py .                               [ 50%]
tests/unit/test_x_api_ingestion.py F                                     [ 62%]
tests/unit/test_x_api_rate_limit_mid_ingestion.py .                      [ 75%]
tests/unit/test_youtube_ingestion.py .                                   [ 87%]
tests/unit/test_youtube_transcription.py .                               [100%]

=================================== FAILURES ===================================
_________ test_x_api_ingestion_returns_content_items_for_recent_tweets _________

    def test_x_api_ingestion_returns_content_items_for_recent_tweets():
        """
        Given an X source and a since datetime, when ingest() is called,
        it returns ContentItem objects for tweets published after `since`,
        each with source_id, title, published_date, original_url, and full_text
        populated from the tweet data.
        """
        source = Source(
            id="x-source-1",
            name="Test X Account",
            type="x",
            url="https://twitter.com/testaccount",
            category="ai",
            active=True,
            priority=1,
        )
        since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
    
        tweet_id = "1234567890"
        tweet_text = "Exciting AI development announced today! #AI"
        tweet_created_at = datetime(2026, 3, 24, 9, 0, 0, tzinfo=timezone.utc)
    
        mock_tweet = MagicMock()
        mock_tweet.id = tweet_id
        mock_tweet.text = tweet_text
        mock_tweet.created_at = tweet_created_at
    
        mock_response = MagicMock()
        mock_response.data = [mock_tweet]
    
        mock_client_instance = MagicMock()
        mock_client_instance.search_recent_tweets.return_value = mock_response
    
        with patch("src.ingestion.sources.x_api.tweepy.Client", return_value=mock_client_instance):
>           results = ingest(source, since)
                      ^^^^^^^^^^^^^^^^^^^^^

tests/unit/test_x_api_ingestion.py:45: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

source = Source(id='x-source-1', name='Test X Account', type='x', url='https://twitter.com/testaccount', category='ai', active=True, priority=1)
since = datetime.datetime(2026, 3, 23, 0, 0, tzinfo=datetime.timezone.utc)

    def ingest(source, since):
        client = tweepy.Client()
>       username = source["url"].rstrip("/").split("/")[-1]
                   ^^^^^^^^^^^^^
E       TypeError: 'Source' object is not subscriptable

src/ingestion/sources/x_api.py:7: TypeError
=========================== short test summary info ============================
FAILED tests/unit/test_x_api_ingestion.py::test_x_api_ingestion_returns_content_items_for_recent_tweets
========================= 1 failed, 7 passed in 1.49s ==========================
RESULT: FAIL

## Existing Code (for context — extend or modify as needed)


--- src/ingestion/handler.py ---
# src/ingestion/handler.py
import json
import os

import boto3
import yaml

from src.ingestion.sources import rss, web, x_api


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return [s for s in config.get("sources", []) if s.get("active", True)]


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    ingesters = {"rss": rss.ingest, "web": web.ingest, "x": x_api.ingest}

    for source in sources:
        source_type = source.get("type")
        ingest_fn = ingesters.get(source_type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
            for i, item in enumerate(items):
                item_key = f"raw/{run_date}/{source['id']}/{i}.json"
                s3.put_object(
                    Bucket=bucket,
                    Key=item_key,
                    Body=json.dumps(item),
                    ContentType="application/json",
                )
            all_items.extend(items)
            sources_succeeded += 1
        except Exception:
            pass

    run_record = {
        "sources_attempted": sources_attempted,
        "sources_succeeded": sources_succeeded,
        "items_ingested": len(all_items),
        "transcription_jobs": 0,
        "delivery_status": "pending",
    }

    s3.put_object(
        Bucket=bucket,
        Key=f"pipeline-runs/{run_date}/run.json",
        Body=json.dumps(run_record),
        ContentType="application/json",
    )

    return run_record

--- src/ingestion/sources/rss.py ---
# src/ingestion/sources/rss.py
import feedparser


def ingest(source, since):
    feed = feedparser.parse(source["url"])
    if feed.bozo:
        return []
    return [
        {
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", ""),
            "source_id": source["id"],
        }
        for entry in feed.entries
    ]

--- src/ingestion/sources/web.py ---
# src/ingestion/sources/web.py
import urllib.request
from bs4 import BeautifulSoup


def ingest(source, since):
    with urllib.request.urlopen(source["url"]) as response:
        html = response.read()
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for article in soup.find_all("article"):
        title_tag = article.find(["h1", "h2", "h3"])
        title = title_tag.get_text(strip=True) if title_tag else ""
        p_tag = article.find("p")
        summary = p_tag.get_text(strip=True) if p_tag else ""
        items.append({
            "title": title,
            "url": source["url"],
            "summary": summary,
            "source_id": source["id"],
        })
    return items

--- src/ingestion/sources/x_api.py ---
# src/ingestion/sources/x_api.py
import tweepy

from src.shared.models import ContentItem


def ingest(source, since):
    client = tweepy.Client()
    username = source.url.rstrip("/").split("/")[-1]
    query = f"from:{username}"
    response = client.search_recent_tweets(
        query=query,
        start_time=since,
        tweet_fields=["created_at", "text"],
    )
    items = []
    if not response.data:
        return items
    for tweet in response.data:
        items.append(ContentItem(
            id=str(tweet.id),
            title=tweet.text,
            source_id=source.id,
            source_name=source.name,
            published_date=tweet.created_at,
            full_text=tweet.text,
            original_url=f"https://twitter.com/i/web/status/{tweet.id}",
        ))
    return items

--- src/ingestion/sources/youtube.py ---
# src/ingestion/sources/youtube.py
from datetime import datetime, timezone

from googleapiclient.discovery import build

from src.shared.models import ContentItem


def ingest(source, since):
    channel_id = source.url.rstrip("/").split("/")[-1]
    youtube = build("youtube", "v3", developerKey=None)
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        publishedAfter=since.isoformat() if since else None,
        type="video",
        maxResults=50,
    )
    response = request.execute()
    items = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        published_at = snippet["publishedAt"]
        published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        items.append(ContentItem(
            id=video_id,
            title=snippet["title"],
            source_id=source.id,
            source_name=source.name,
            published_date=published_date,
            full_text="",
            original_url=f"https://www.youtube.com/watch?v={video_id}",
            content_format="video",
        ))
    return items

--- src/ingestion/sources/podcast.py ---
# src/ingestion/sources/podcast.py
from datetime import datetime, timezone

import feedparser

from src.shared.models import ContentItem


def ingest(source, since):
    feed = feedparser.parse(source.url)
    if feed.bozo:
        return []
    items = []
    for entry in feed.entries:
        published_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if since and published_date < since:
            continue
        enclosures = getattr(entry, "enclosures", [])
        if not enclosures:
            continue
        enclosure_url = enclosures[0].href
        items.append(ContentItem(
            id=enclosure_url,
            title=entry.title,
            source_id=source.id,
            source_name=source.name,
            published_date=published_date,
            full_text="",
            original_url=enclosure_url,
            content_format="audio",
        ))
    return items

--- src/transcription/handler.py ---
# src/transcription/handler.py
import json
import os
import time
import urllib.parse
import urllib.request

import boto3
import yt_dlp


def _upload_audio(s3, bucket, original_url, audio_key):
    with urllib.request.urlopen(original_url) as response:
        audio_bytes = response.read()
    s3.put_object(Bucket=bucket, Key=audio_key, Body=audio_bytes)


def _poll_transcription_job(transcribe, job_name):
    while True:
        resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        job = resp["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]
        if status == "COMPLETED":
            return job["Transcript"]["TranscriptFileUri"]
        if status == "FAILED":
            return None
        time.sleep(5)


def _fetch_transcript_text(s3, transcript_uri):
    parsed = urllib.parse.urlparse(transcript_uri)
    path_parts = parsed.path.lstrip("/").split("/", 1)
    obj = s3.get_object(Bucket=path_parts[0], Key=path_parts[1])
    transcript_data = json.loads(obj["Body"].read())
    transcripts = transcript_data.get("results", {}).get("transcripts", [])
    return transcripts[0]["transcript"] if transcripts else ""


def _transcribe_audio(s3, bucket, item_id, original_url, run_date):
    audio_key = f"audio/{run_date}/{item_id}.mp3"
    _upload_audio(s3, bucket, original_url, audio_key)

    transcribe = boto3.client("transcribe")
    job_name = f"transcribe-{run_date}-{item_id}".replace("/", "-")
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{bucket}/{audio_key}"},
        MediaFormat="mp3",
        LanguageCode="en-US",
        OutputBucketName=bucket,
        OutputKey=f"transcribe-output/{run_date}/{item_id}.json",
    )

    transcript_uri = _poll_transcription_job(transcribe, job_name)
    if transcript_uri is None:
        return ""
    return _fetch_transcript_text(s3, transcript_uri)


def _extract_youtube_transcript(original_url):
    ydl_opts = {"writesubtitles": True, "subtitleslangs": ["en"], "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(original_url, download=False)

    requested = info.get("requested_subtitles") or {}
    for sub in requested.values():
        data = sub.get("data", "")
        if data:
            return data
    return ""


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")

    for record in event["Records"]:
        body = json.loads(record["body"])
        item_id = body["item_id"]
        original_url = body["original_url"]
        run_date = body["run_date"]
        content_format = body.get("content_format", "video")

        if content_format == "audio":
            transcript_text = _transcribe_audio(s3, bucket, item_id, original_url, run_date)
        else:
            transcript_text = _extract_youtube_transcript(original_url)

        s3.put_object(
            Bucket=bucket,
            Key=f"transcripts/{run_date}/{item_id}.txt",
            Body=transcript_text.encode("utf-8"),
            ContentType="text/plain",
        )

    return {"transcript_status": "completed"}

--- src/shared/models.py ---
# src/shared/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Source:
    id: str
    name: str
    type: str  # rss / web / x / youtube / podcast
    url: str
    category: str
    active: bool = True
    priority: int = 1


@dataclass
class ContentItem:
    id: str
    title: str
    source_id: str
    source_name: str
    published_date: datetime
    full_text: str
    original_url: str
    content_format: str = "text"  # text / audio / video
    transcript_status: str = "not_needed"  # pending / completed / failed / not_needed

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


### Sign: Missing sys.path and package stubs cause patch ImportError
- **Category**: RED-FAILURE
- **Detail**: `patch("src.ingestion.handler.load_sources", ...)` raises `ModuleNotFoundError: No module named 'src'` when the project root isn't on `sys.path` and `src/__init__.py` doesn't exist. Fix: create `conftest.py` at repo root with `sys.path.insert(0, os.path.dirname(__file__))`, create empty `__init__.py` files for each package level, and create minimal stub modules for each patch target before writing the RED test.
- **Added after**: B006 at 2026-03-25T02:04:10Z


### Sign: pip shim broken for older Python, use python3 -m pip
- **Category**: GREEN-FAILURE
- **Detail**: `/usr/local/bin/pip` pointed to a removed Python 3.9 interpreter. Use `python3 -m pip install <pkg>` to target the active interpreter. Always install packages via `python3 -m pip` rather than bare `pip` in this environment.
- **Added after**: B009 at 2026-03-25T02:58:00Z
