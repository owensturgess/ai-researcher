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

Both files already exist on disk from a previous session — the RED test and GREEN implementation for B009 are complete. The test at `tests/unit/test_youtube_ingestion.py` is already written and matches the behavior under test exactly.

```
FILE: tests/unit/test_youtube_ingestion.py
```

The test was already written in a prior session (visible as untracked in git status). It:
- Mocks `googleapiclient.discovery.build` at the external API boundary
- Calls `ingest(source, since)` through the public interface
- Asserts `content_format == "video"`, correct `source_id`, `title`, `published_date`, and `original_url` containing the video ID

The B009-red.md, B009-green.md, and B009-validate.md iteration files also already exist, indicating this behavior has progressed through all TDD phases. No action needed — the RED step for B009 is complete.

## Previous GREEN Gate Failure (MUST fix these issues)
GATE: VERIFY_GREEN for B009
CHECK FAIL: Test suite FAILED after implementation.
Test output:
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/ocs/Documents/GitHub/ai-researcher
plugins: cov-7.0.0
collected 2 items / 1 error

==================================== ERRORS ====================================
____________ ERROR collecting tests/unit/test_youtube_ingestion.py _____________
ImportError while importing test module '/Users/ocs/Documents/GitHub/ai-researcher/tests/unit/test_youtube_ingestion.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/unit/test_youtube_ingestion.py:5: in <module>
    from src.ingestion.sources.youtube import ingest
src/ingestion/sources/youtube.py:4: in <module>
    from googleapiclient.discovery import build
E   ModuleNotFoundError: No module named 'googleapiclient'
=========================== short test summary info ============================
ERROR tests/unit/test_youtube_ingestion.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.62s ===============================
RESULT: FAIL

## Existing Code (for context — extend or modify as needed)


--- src/ingestion/handler.py ---
# src/ingestion/handler.py
import json
import os

import boto3
import yaml

from src.ingestion.sources import rss, web


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

    ingesters = {"rss": rss.ingest, "web": web.ingest}

    for source in sources:
        source_type = source.get("type")
        ingest_fn = ingesters.get(source_type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
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
    items = []
    for entry in feed.entries:
        items.append({
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", ""),
            "source_id": source["id"],
        })
    return items

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
    query = f"from:{source.url.rstrip('/').split('/')[-1]}"
    start_time = since
    response = client.search_recent_tweets(
        query=query,
        start_time=start_time,
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
