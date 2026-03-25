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

Test fails as expected with a clear error message.

```
FILE: tests/unit/test_cloudwatch_metrics_namespace.py
```

The test fails because the handler currently:
1. Publishes per-run metrics to `"AiResearcher/Pipeline"` instead of `"AgenticSDLCIntel"`
2. Is missing 3 required metrics: `SourcesFailed`, `DeliveryLatencyMinutes`, `BriefingItemCount`

The GREEN phase will need to move all per-run `put_metric_data` calls to the `"AgenticSDLCIntel"` namespace and add the three missing metrics.

## Existing Code (for context — extend or modify as needed)


--- src/ingestion/config.py ---
# src/ingestion/config.py
import yaml

from src.shared.models import Source


def load_sources(config_path):
    with open(config_path) as f:
        config = yaml.safe_load(f)
    raw = config.get("sources", [])
    seen = set()
    for s in raw:
        if s["id"] in seen:
            raise ValueError(f"duplicate source id: {s['id']}")
        seen.add(s["id"])
    return [
        Source(
            id=s["id"],
            name=s["name"],
            type=s["type"],
            url=s["url"],
            category=s.get("category", ""),
            active=s.get("active", True),
            priority=s.get("priority", 1),
        )
        for s in raw
        if s.get("active", True)
    ]

--- src/ingestion/handler.py ---
# src/ingestion/handler.py
import json
import logging
import os

import boto3

from src.ingestion.config import load_sources as _load_sources
from src.ingestion.sources import rss, web, x_api

logger = logging.getLogger(__name__)

_INGESTERS = {"rss": rss.ingest, "web": web.ingest, "x": x_api.ingest}

_FAILURE_PREFIX = "source-failures/"


def _failure_key(source_id):
    return f"{_FAILURE_PREFIX}{source_id}.json"


def track_source_failure(source_id, date, succeeded):
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")
    key = _failure_key(source_id)

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
    except Exception:
        data = {"consecutive_failures": 0}

    if succeeded:
        data["consecutive_failures"] = 0
    else:
        data["consecutive_failures"] = data.get("consecutive_failures", 0) + 1

    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(data), ContentType="application/json")


def get_failing_sources(threshold=3):
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    result = []
    for page in paginator.paginate(Bucket=bucket, Prefix=_FAILURE_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            source_id = key[len(_FAILURE_PREFIX):].removesuffix(".json")
            data = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
            count = data.get("consecutive_failures", 0)
            if count >= threshold:
                result.append((source_id, count))
    return result


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    return sorted(_load_sources(config_path), key=lambda s: s.priority)


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    for source in sources:
        ingest_fn = _INGESTERS.get(source.type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
            for i, item in enumerate(items):
                item_key = f"raw/{run_date}/{source.id}/{i}.json"
                s3.put_object(
                    Bucket=bucket,
                    Key=item_key,
                    Body=json.dumps(item),
                    ContentType="application/json",
                )
            all_items.extend(items)
            sources_succeeded += 1
        except Exception:
            logger.warning("ingestion failed for source %s", source.id, exc_info=True)

    run_record = {
        "sources_attempted": sources_attempted,
        "sources_succeeded": sources_succeeded,
        "source_ids_attempted": [s.id for s in sources],
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
    feed = feedparser.parse(source.url)
    if feed.bozo:
        return []
    return [
        {
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", ""),
            "source_id": source.id,
        }
        for entry in feed.entries
    ]

--- src/ingestion/sources/web.py ---
# src/ingestion/sources/web.py
import urllib.request
from bs4 import BeautifulSoup


def ingest(source, since):
    with urllib.request.urlopen(source.url) as response:
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
            "url": source.url,
            "summary": summary,
            "source_id": source.id,
        })
    return items

--- src/ingestion/sources/x_api.py ---
# src/ingestion/sources/x_api.py
import logging

import tweepy

from src.shared.models import ContentItem

logger = logging.getLogger(__name__)


def ingest(source, since):
    client = tweepy.Client()
    username = source.url.rstrip("/").split("/")[-1]
    query = f"from:{username}"
    items = []
    next_token = None

    while True:
        kwargs = dict(
            query=query,
            start_time=since,
            tweet_fields=["created_at", "text"],
        )
        if next_token:
            kwargs["next_token"] = next_token

        try:
            response = client.search_recent_tweets(**kwargs)
        except tweepy.errors.TooManyRequests:
            logger.warning("rate limit hit mid-ingestion for source %s; returning partial results", source.id)
            break

        if response.data:
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

        # next_token must be a real string to continue pagination
        meta = getattr(response, "meta", None)
        token = getattr(meta, "next_token", None) if meta is not None else None
        if not isinstance(token, str) or not token:
            break
        next_token = token

    return items

--- src/ingestion/sources/youtube.py ---
# src/ingestion/sources/youtube.py
import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.shared.models import ContentItem

logger = logging.getLogger(__name__)


def ingest(source, since):
    channel_id = source.url.rstrip("/").split("/")[-1]
    youtube = build("youtube", "v3", developerKey=None)
    items = []
    page_token = None

    while True:
        kwargs = dict(
            part="snippet",
            channelId=channel_id,
            publishedAfter=since.isoformat() if since else None,
            type="video",
            maxResults=50,
        )
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            response = youtube.search().list(**kwargs).execute()
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(
                    "YouTube quota exceeded for source %s; returning partial results", source.id
                )
                break
            raise

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

        page_token = response.get("nextPageToken")
        if not page_token:
            break

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


def _mark_transcript_failed(s3, bucket, run_date, source_id, item_id):
    item_key = f"raw/{run_date}/{source_id}/{item_id}.json"
    obj = s3.get_object(Bucket=bucket, Key=item_key)
    item_data = json.loads(obj["Body"].read())
    item_data["transcript_status"] = "failed"
    s3.put_object(
        Bucket=bucket,
        Key=item_key,
        Body=json.dumps(item_data),
        ContentType="application/json",
    )


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")
    any_failed = False

    for record in event["Records"]:
        body = json.loads(record["body"])
        item_id = body["item_id"]
        original_url = body["original_url"]
        run_date = body["run_date"]
        content_format = body.get("content_format", "video")
        source_id = body.get("source_id", "")

        try:
            if content_format == "audio":
                budget = int(os.environ.get("DAILY_TRANSCRIPTION_BUDGET_MINUTES", "999999"))
                if budget <= 0:
                    raise RuntimeError("Daily transcription budget exhausted")
                transcript_text = _transcribe_audio(s3, bucket, item_id, original_url, run_date)
            else:
                transcript_text = _extract_youtube_transcript(original_url)

            s3.put_object(
                Bucket=bucket,
                Key=f"transcripts/{run_date}/{item_id}.txt",
                Body=transcript_text.encode("utf-8"),
                ContentType="text/plain",
            )
        except Exception:
            any_failed = True
            _mark_transcript_failed(s3, bucket, run_date, source_id, item_id)

    if any_failed:
        return {"transcript_status": "failed"}
    return {"transcript_status": "completed"}

--- src/shared/config.py ---
# src/shared/config.py
import os


def load_context_prompt(config_dir: str) -> str:
    path = os.path.join(config_dir, "context-prompt.txt")
    with open(path) as f:
        return f.read()


def load_settings(config_dir: str):
    raise NotImplementedError("load_settings not yet implemented")


def load_sources(config_dir: str):
    raise NotImplementedError("load_sources not yet implemented")

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


@dataclass
class ScoredItem:
    content_item_id: str
    relevance_score: int
    urgency: str
    relevance_tag: str
    executive_summary: str
    scoring_reasoning: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    also_reported_by: list = field(default_factory=list)

--- src/briefing/handler.py ---
# src/briefing/handler.py
import json
import os

import boto3


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    threshold = int(os.environ.get("RELEVANCE_THRESHOLD", "60"))

    s3 = boto3.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=f"scored/{run_date}/")

    included_items = []
    for page in pages:
        for obj in page.get("Contents", []):
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            item = json.loads(body)
            if item.get("relevance_score", 0) >= threshold:
                included_items.append(item)

    return {"items_included": len(included_items)}

--- src/scoring/handler.py ---
# src/scoring/handler.py
import json
import os

import boto3


def _score_item(bedrock, context_prompt, item):
    user_text = (
        f"Title: {item.get('title', '')}\n"
        f"Content: {item.get('full_text', '')}\n\n"
        "Respond with JSON containing a 'score' field (integer 0-100)."
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "temperature": 0,
        "system": context_prompt,
        "messages": [{"role": "user", "content": user_text}],
    })

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=request_body,
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    text = response_body["content"][0]["text"]
    parsed = json.loads(text)
    urgency = parsed.get("urgency", "informational")
    return parsed["score"], urgency


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    context_prompt_path = os.environ.get("CONTEXT_PROMPT_PATH", "config/context-prompt.txt")

    with open(context_prompt_path) as f:
        context_prompt = f.read().strip()

    s3 = boto3.client("s3")
    bedrock = boto3.client("bedrock-runtime")

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=f"raw/{run_date}/")

    threshold = int(os.environ.get("RELEVANCE_THRESHOLD", "60"))
    items_scored = 0
    items_above_threshold = 0
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            item = json.loads(body)

            score, urgency = _score_item(bedrock, context_prompt, item)

            item_id = item["id"]
            scored = dict(item)
            scored["relevance_score"] = score
            scored["urgency"] = urgency
            items_scored += 1

            s3.put_object(
                Bucket=bucket,
                Key=f"scored/{run_date}/{item_id}.json",
                Body=json.dumps(scored),
                ContentType="application/json",
            )
            if score >= threshold:
                items_above_threshold += 1

    return {"items_scored": items_scored, "items_above_threshold": items_above_threshold}

--- src/scoring/deduplication.py ---
# src/scoring/deduplication.py
import json

import boto3


def _are_duplicates(bedrock, item_a, item_b):
    prompt = (
        f"Item A summary: {item_a.executive_summary}\n"
        f"Item A reasoning: {item_a.scoring_reasoning}\n"
        f"Item B summary: {item_b.executive_summary}\n"
        f"Item B reasoning: {item_b.scoring_reasoning}\n\n"
        "Do these items cover the same core development? "
        "Respond with JSON: {\"is_duplicate\": true} or {\"is_duplicate\": false}."
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 64,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    text = json.loads(response["body"].read())["content"][0]["text"]
    return json.loads(text).get("is_duplicate", False)


def deduplicate_by_semantics(scored_items):
    bedrock = boto3.client("bedrock-runtime")
    items = sorted(scored_items, key=lambda x: x.relevance_score, reverse=True)

    for i in range(len(items)):
        if items[i].is_duplicate:
            continue
        for j in range(i + 1, len(items)):
            if items[j].is_duplicate:
                continue
            if _are_duplicates(bedrock, items[i], items[j]):
                items[j].is_duplicate = True
                items[j].duplicate_of = items[i].content_item_id
                items[i].also_reported_by.append(items[j].content_item_id)

    return items

--- src/monitoring/handler.py ---
# src/monitoring/handler.py
import json
import logging
import os
from datetime import date, timedelta

import boto3

logger = logging.getLogger(__name__)


def _load_rolling_runs(s3, bucket, run_date_str, days=7):
    """Load up to `days` pipeline run records ending on run_date_str (inclusive)."""
    end = date.fromisoformat(run_date_str)
    runs = []
    for i in range(days):
        d = (end - timedelta(days=days - 1 - i)).isoformat()
        try:
            obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{d}/run.json")
            runs.append(json.loads(obj["Body"].read()))
        except Exception:
            pass
    return runs


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{run_date}/run.json")
    run = json.loads(obj["Body"].read())

    sources_succeeded = run.get("sources_succeeded", 0)
    items_ingested = run.get("items_ingested", 0)
    items_above_threshold = run.get("items_above_threshold", 0)
    transcription_jobs = run.get("transcription_jobs", 0)
    estimated_cost_usd = run.get("estimated_cost_usd", 0.0)

    logger.info(
        "Pipeline run complete: sources_scanned=%s items_ingested=%s "
        "items_above_threshold=%s transcription_jobs=%s estimated_cost_usd=%s",
        sources_succeeded,
        items_ingested,
        items_above_threshold,
        transcription_jobs,
        estimated_cost_usd,
    )

    cloudwatch = boto3.client("cloudwatch")
    cloudwatch.put_metric_data(
        Namespace="AiResearcher/Pipeline",
        MetricData=[
            {"MetricName": "SourcesScanned", "Value": sources_succeeded, "Unit": "Count"},
            {"MetricName": "ItemsIngested", "Value": items_ingested, "Unit": "Count"},
            {"MetricName": "ItemsAboveThreshold", "Value": items_above_threshold, "Unit": "Count"},
            {"MetricName": "TranscriptionJobs", "Value": transcription_jobs, "Unit": "Count"},
            {"MetricName": "EstimatedCostUSD", "Value": estimated_cost_usd, "Unit": "None"},
        ],
    )

    rolling_runs = _load_rolling_runs(s3, bucket, run_date)
    if rolling_runs:
        delivered = sum(1 for r in rolling_runs if r.get("delivery_status") == "delivered")
        reliability_pct = delivered / len(rolling_runs) * 100
        avg_cost = sum(r.get("estimated_cost_usd", 0.0) for r in rolling_runs) / len(rolling_runs)
        cloudwatch.put_metric_data(
            Namespace="AgenticSDLCIntel",
            MetricData=[
                {"MetricName": "DeliveryReliabilityPct", "Value": reliability_pct, "Unit": "Percent"},
                {"MetricName": "AverageCostPerRun", "Value": avg_cost, "Unit": "None"},
            ],
        )

    threshold = float(os.environ.get("COST_ALERT_THRESHOLD_USD", "10.00"))
    alert_sent = False
    if estimated_cost_usd > threshold:
        ses = boto3.client("ses")
        ses.send_email(
            Source=os.environ.get("SES_SENDER", ""),
            Destination={"ToAddresses": [os.environ.get("ALERT_RECIPIENT", "")]},
            Message={
                "Subject": {"Data": "AI Researcher: Cost Alert"},
                "Body": {"Text": {"Data": f"Estimated cost ${estimated_cost_usd:.2f} exceeds threshold ${threshold:.2f}"}},
            },
        )
        alert_sent = True

    return {"status": "ok", "alert_sent": alert_sent}

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


### Sign: B024 behavior A already implemented — RED phase produces GREEN test
- **Category**: RED-FAILURE
- **Detail**: The source-removal behavior (B024 Behavior A) is already covered by the existing `handler.py` implementation: `load_sources()` reads only from the active `SOURCES_CONFIG` file, so any source absent from YAML is never attempted. The corrected single-assertion RED test (`sources_attempted == 1`, no S3 keys under `src-removed-002/`, at least one key under `src-remaining-001/`) passes immediately without new implementation. When a behavior is already implemented by prior GREEN phases, the RED test will be green from the start — treat this as "behavior pre-implemented" and advance directly to VALIDATE.
- **Added after**: B024 at 2026-03-25T04:22:49Z


### Sign: B029 behavior pre-implemented — RED phase produces GREEN test
- **Category**: RED-FAILURE
- **Detail**: The "different angles → both retained" path (B029) is automatically satisfied by the B028 implementation in `deduplicate_by_semantics`. When `_are_duplicates()` returns `False`, the function simply skips flagging — no additional code path needed. The RED test passes immediately. Per the established guardrail pattern (see B024), advance directly to VALIDATE.
- **Added after**: B029 at 2026-03-25T04:38:24Z
