# REFACTOR Step — Code Quality Improvement

You are a refactoring agent for a TDD-driven project. Your job is to improve code quality without changing behavior.

## CRITICAL: You MUST modify files on disk

You MUST use your file-writing tools to edit implementation files directly on disk. Do NOT just output or describe changes — actually apply them. The refactored files must be updated on the filesystem when you are done.

## Rules

1. **All tests must still pass** after your changes. Do not break any existing tests.
2. **Do not change behavior** — refactoring is structural improvement only.
3. **Do not modify test files** — tests define the expected behavior and must remain unchanged.
4. **Do not add new features** — only improve existing code.
5. **Preserve the public interface** described in the interfaces section.

## What to look for

- Duplicated code that can be extracted into shared helpers
- Long functions that can be broken into smaller, focused functions
- Unclear naming that can be improved for readability
- Dead code or unused imports that can be removed
- Overly complex conditionals that can be simplified
- Missing error handling at system boundaries
- Performance improvements that don't change behavior

## Current Implementation


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
from datetime import date, datetime, timedelta, timezone

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


def _delivery_latency_minutes(run):
    started = run.get("started_at", "")
    completed = run.get("completed_at", "")
    if not started or not completed:
        return 0.0
    try:
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(completed)
        return (t1 - t0).total_seconds() / 60.0
    except Exception:
        return 0.0


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{run_date}/run.json")
    run = json.loads(obj["Body"].read())

    sources_succeeded = run.get("sources_succeeded", 0)
    sources_failed = run.get("sources_failed", 0)
    items_ingested = run.get("items_ingested", 0)
    items_above_threshold = run.get("items_above_threshold", 0)
    items_in_briefing = run.get("items_in_briefing", 0)
    transcription_jobs = run.get("transcription_jobs", 0)
    estimated_cost_usd = run.get("estimated_cost_usd", 0.0)
    delivery_latency = _delivery_latency_minutes(run)

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
        Namespace="AgenticSDLCIntel",
        MetricData=[
            {"MetricName": "SourcesScanned", "Value": sources_succeeded, "Unit": "Count"},
            {"MetricName": "SourcesFailed", "Value": sources_failed, "Unit": "Count"},
            {"MetricName": "ItemsIngested", "Value": items_ingested, "Unit": "Count"},
            {"MetricName": "ItemsAboveThreshold", "Value": items_above_threshold, "Unit": "Count"},
            {"MetricName": "TranscriptionJobs", "Value": transcription_jobs, "Unit": "Count"},
            {"MetricName": "EstimatedCostUSD", "Value": estimated_cost_usd, "Unit": "None"},
            {"MetricName": "DeliveryLatencyMinutes", "Value": delivery_latency, "Unit": "None"},
            {"MetricName": "BriefingItemCount", "Value": items_in_briefing, "Unit": "Count"},
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

## Current Tests


--- tests/unit/test_youtube_quota_limit.py ---
# tests/unit/test_youtube_quota_limit.py
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from src.ingestion.sources.youtube import ingest
from src.shared.models import Source


def test_youtube_quota_exceeded_stops_queries_and_returns_partial_results(caplog):
    """
    Given a YouTube source where the first API page succeeds but a subsequent
    query raises an HttpError with status 403 (quotaExceeded), when ingest()
    is called, it returns the ContentItems already retrieved and does not raise
    an exception — the caller (pipeline) can continue with other source types.
    """
    source = Source(
        id="yt-source-quota",
        name="AI Channel",
        type="youtube",
        url="https://www.youtube.com/channel/UC_quota_test_channel",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    # First page returns one video successfully
    first_page_response = {
        "items": [
            {
                "id": {"videoId": "video-before-quota"},
                "snippet": {
                    "title": "Video Retrieved Before Quota Hit",
                    "publishedAt": "2026-03-24T08:00:00Z",
                    "channelTitle": "AI Channel",
                },
            }
        ],
        "nextPageToken": "page2token",
    }

    # Second page raises quota exceeded error (403 quotaExceeded)
    quota_error_content = json.dumps({
        "error": {
            "code": 403,
            "errors": [{"reason": "quotaExceeded", "domain": "youtube.quota"}],
            "message": "The request cannot be completed because you have exceeded your quota.",
        }
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = 403
    quota_error = HttpError(resp=mock_resp, content=quota_error_content)

    call_count = 0

    def execute_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_page_response
        raise quota_error

    mock_list_request = MagicMock()
    mock_list_request.execute.side_effect = execute_side_effect

    mock_search = MagicMock()
    mock_search.list.return_value = mock_list_request

    mock_youtube_client = MagicMock()
    mock_youtube_client.search.return_value = mock_search

    with patch("src.ingestion.sources.youtube.build", return_value=mock_youtube_client):
        with caplog.at_level(logging.WARNING):
            results = ingest(source, since)

    # Must return items collected before quota was hit — not raise or return nothing
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0].source_id == "yt-source-quota"
    assert results[0].content_format == "video"

    # Must log a quota-related warning so the operator knows queries stopped early
    quota_logs = [
        r for r in caplog.records
        if "quota" in r.message.lower()
    ]
    assert len(quota_logs) >= 1

--- tests/unit/test_ingestion_error_isolation.py ---
# tests/unit/test_ingestion_error_isolation.py
import textwrap
from urllib.error import HTTPError
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_failing_source_is_skipped_and_other_sources_process_normally(
    monkeypatch, tmp_path
):
    """
    Given two RSS sources where one raises an HTTP 429 (rate limit) during
    ingestion, when the handler runs, the failing source is skipped and the
    other source's items are ingested normally — sources_attempted == 2 and
    sources_succeeded == 1 in the returned counts.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-rss-failing
            name: Failing Feed
            type: rss
            url: https://failing.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-rss-ok
            name: Healthy Feed
            type: rss
            url: https://healthy.example.com/feed.xml
            category: ai
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    # Healthy feed returns one recent entry
    fake_healthy_feed = MagicMock()
    fake_healthy_feed.bozo = False
    fake_healthy_feed.entries = [
        MagicMock(
            title="AI Update from Healthy Source",
            link="https://healthy.example.com/article-1",
            published_parsed=(2026, 3, 24, 10, 0, 0, 0, 0, 0),
            summary="A healthy AI update.",
        )
    ]

    # feedparser.parse raises HTTPError for the failing source URL
    def parse_side_effect(url, *args, **kwargs):
        if "failing" in url:
            raise HTTPError(url, 429, "Too Many Requests", {}, None)
        return fake_healthy_feed

    with patch("feedparser.parse", side_effect=parse_side_effect):
        result = handler({}, None)

    # Both sources were attempted; only the healthy one succeeded
    assert result["sources_attempted"] == 2
    assert result["sources_succeeded"] == 1

    # Items from the healthy source were written to S3 despite the other failure
    objects = s3.list_objects_v2(
        Bucket="test-pipeline-bucket", Prefix="raw/2026-03-24/src-rss-ok/"
    )
    assert objects.get("KeyCount", 0) >= 1

--- tests/unit/test_youtube_transcription.py ---
# tests/unit/test_youtube_transcription.py
import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from src.transcription.handler import handler


@mock_aws
def test_youtube_transcript_retrieved_via_ytdlp_subtitles_and_written_to_s3(
    monkeypatch, tmp_path
):
    """
    Given a YouTube video item on the transcription queue, when the handler
    processes it and yt-dlp can download subtitles, the transcript text is
    written to S3 at transcripts/{date}/{item_id}.txt and transcript_status
    is 'completed' — without falling back to audio extraction.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item_id = "yt-item-001"
    source_id = "yt-source-1"
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    subtitle_text = "This is the full transcript of the YouTube video."

    # Write the raw ContentItem to S3 (the handler reads it to get item details)
    content_item = {
        "id": item_id,
        "title": "AI Developments Explained",
        "source_id": source_id,
        "source_name": "AI Channel",
        "published_date": "2026-03-24T10:00:00+00:00",
        "full_text": "",
        "original_url": video_url,
        "content_format": "video",
        "transcript_status": "pending",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{source_id}/{item_id}.json",
        Body=json.dumps(content_item),
    )

    # SQS event payload — yt-dlp subtitle path is the primary transcript source
    sqs_message_body = json.dumps(
        {
            "item_id": item_id,
            "source_id": source_id,
            "content_format": "video",
            "original_url": video_url,
            "run_date": "2026-03-24",
        }
    )
    event = {"Records": [{"body": sqs_message_body}]}

    # Mock yt-dlp at the external boundary — subtitles available, no audio fallback
    mock_ydl_instance = MagicMock()
    mock_ydl_instance.__enter__ = lambda s: s
    mock_ydl_instance.__exit__ = MagicMock(return_value=False)
    mock_ydl_instance.extract_info.return_value = {
        "id": "dQw4w9WgXcQ",
        "title": "AI Developments Explained",
        "subtitles": {"en": [{"ext": "vtt", "data": subtitle_text}]},
        "requested_subtitles": {"en": {"ext": "vtt", "data": subtitle_text}},
    }

    mock_ydl_class = MagicMock(return_value=mock_ydl_instance)

    with patch("src.transcription.handler.yt_dlp.YoutubeDL", mock_ydl_class):
        result = handler(event, None)

    # Transcript must be written to S3 at the canonical path
    transcript_key = f"transcripts/2026-03-24/{item_id}.txt"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=transcript_key)
    stored_transcript = response["Body"].read().decode("utf-8")

    assert subtitle_text in stored_transcript
    assert result["transcript_status"] == "completed"

--- tests/unit/test_source_removal_stops_ingestion.py ---
# tests/unit/test_source_removal_stops_ingestion.py
#
# Behavior B024: Given a source is removed from the configuration file,
# content from that source is no longer ingested on the next run.
#
# This test verifies that the pipeline run record written to S3 contains an
# explicit list of source IDs that were attempted (source_ids_attempted), and
# that the removed source's ID is absent from that list while the remaining
# source's ID is present.  The handler currently writes only counts
# (sources_attempted, sources_succeeded) — not an ID list — so this test fails
# until source_ids_attempted is added to the run record.
import json
import textwrap
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_removed_source_id_is_absent_from_run_record_source_id_list(
    monkeypatch, tmp_path
):
    """
    Given a config file that contains only src-remaining-001 (src-removed-002
    was previously active but has been removed from the YAML), when the
    ingestion handler runs, the pipeline run record written to S3 includes a
    source_ids_attempted list that contains src-remaining-001 and does NOT
    contain src-removed-002 — giving operators an explicit record of which
    sources participated in each run.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Config after removal: only src-remaining-001 is present
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-remaining-001
            name: Remaining AI Feed
            type: rss
            url: https://remaining.example.com/feed.xml
            category: ai
            active: true
            priority: 1
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.entries = []

    with patch("feedparser.parse", return_value=fake_feed):
        handler({}, None)

    # Read the pipeline run record written to S3
    response = s3.get_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
    )
    run_data = json.loads(response["Body"].read())

    # The run record must include an explicit list of source IDs attempted
    assert "source_ids_attempted" in run_data, (
        "pipeline run record missing 'source_ids_attempted' field — "
        "operators cannot verify which sources ran vs. which were removed"
    )

    source_ids = run_data["source_ids_attempted"]
    assert "src-remaining-001" in source_ids, (
        f"src-remaining-001 should be in source_ids_attempted but got: {source_ids}"
    )
    assert "src-removed-002" not in source_ids, (
        f"src-removed-002 must not appear in source_ids_attempted after removal, got: {source_ids}"
    )

--- tests/unit/test_semantic_deduplication.py ---
# tests/unit/test_semantic_deduplication.py
#
# Behavior B028: Given two content items from different sources cover the same
# development, only the highest-relevance version appears in the briefing.
#
# Tests the public interface deduplicate_by_semantics(scored_items) in
# src/scoring/deduplication.py. When two ScoredItems cover the same core
# development, the lower-relevance item must be flagged with is_duplicate=True
# and duplicate_of pointing to the higher-relevance item's content_item_id.
import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_lower_relevance_item_flagged_as_duplicate_when_two_sources_cover_same_development():
    """
    Given two ScoredItems from different sources covering the same Claude 4
    release (score 85 and score 60), when deduplicate_by_semantics() runs,
    the lower-relevance item has is_duplicate=True and duplicate_of set to
    the higher-relevance item's content_item_id, while the higher-relevance
    item remains is_duplicate=False.
    """
    item_primary = ScoredItem(
        content_item_id="item-claude4-techcrunch",
        relevance_score=85,
        urgency="worth_discussing",
        relevance_tag="AI Tools",
        executive_summary=(
            "Anthropic releases Claude 4 with major agentic software development "
            "capabilities, enabling autonomous multi-step coding workflows."
        ),
        scoring_reasoning="Directly relevant to agentic SDLC transformation goals.",
        is_duplicate=False,
        duplicate_of=None,
    )

    item_duplicate = ScoredItem(
        content_item_id="item-claude4-verge",
        relevance_score=60,
        urgency="informational",
        relevance_tag="AI Tools",
        executive_summary=(
            "Claude 4 AI assistant launched by Anthropic with new coding and "
            "agentic features announced today."
        ),
        scoring_reasoning="Same Claude 4 release covered from a consumer angle.",
        is_duplicate=False,
        duplicate_of=None,
    )

    # Mock Bedrock at the AWS service boundary — LLM identifies the pair as duplicates
    # and nominates item-claude4-techcrunch (higher score) as the primary version.
    llm_response = json.dumps({"is_duplicate": True})
    mock_stream = MagicMock()
    mock_stream.read.return_value = json.dumps(
        {"content": [{"text": llm_response}]}
    ).encode("utf-8")

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = {"body": mock_stream}

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics([item_primary, item_duplicate])

    by_id = {item.content_item_id: item for item in result}

    # Higher-relevance item must remain primary — not flagged as duplicate
    assert by_id["item-claude4-techcrunch"].is_duplicate is False, (
        "The highest-relevance item must not be flagged as a duplicate."
    )
    assert by_id["item-claude4-techcrunch"].duplicate_of is None

    # Lower-relevance item must be flagged as a duplicate of the primary
    assert by_id["item-claude4-verge"].is_duplicate is True, (
        "The lower-relevance item covering the same development must be flagged "
        "is_duplicate=True so it is excluded from the briefing."
    )
    assert by_id["item-claude4-verge"].duplicate_of == "item-claude4-techcrunch", (
        f"duplicate_of must point to the primary item id, "
        f"got: {by_id['item-claude4-verge'].duplicate_of!r}"
    )

--- tests/unit/test_scoring_reliability.py ---
# tests/unit/test_scoring_reliability.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler

# The scoring handler must call Bedrock with temperature=0 so that the same
# content item receives consistent scores across consecutive daily runs.
# Without temperature=0, LLM outputs are non-deterministic and scores can vary
# wildly between runs — violating the ±10 point reliability requirement.


@mock_aws
def test_same_content_item_scores_consistently_across_two_consecutive_days(
    monkeypatch, tmp_path
):
    """
    Given the same content item is ingested and scored on two consecutive days,
    when the scoring handler runs each day, the two resulting relevance scores
    differ by no more than ±10 points — confirmed by the handler passing
    temperature=0 to Bedrock so the LLM produces deterministic output.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0")  # score all items

    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(
        "Score content for relevance to agentic SDLC transformation goals."
    )
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # The same item ingested on two consecutive days
    item = {
        "id": "item-reliability-001",
        "title": "Claude 4 Released with Agentic Capabilities",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "Anthropic released Claude 4 with major agentic improvements.",
        "original_url": "https://example.com/claude-4",
        "content_format": "text",
        "transcript_status": "not_needed",
    }

    for run_date in ("2026-03-24", "2026-03-25"):
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"raw/{run_date}/{item['source_id']}/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Bedrock mock: when temperature=0 is present both calls return 75 (consistent).
    # When temperature is absent or non-zero the mock alternates between 30 and 75
    # on successive calls, simulating the non-determinism that arises without
    # temperature pinning. This makes the test fail (RED) until the handler passes
    # temperature=0 so the same score is produced across consecutive daily runs.
    call_counter = {"n": 0}
    non_deterministic_scores = [30, 75]  # differ by 45 — exceeds ±10 threshold

    def bedrock_invoke_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        uses_zero_temp = request.get("temperature", None) == 0
        if uses_zero_temp:
            score = 75  # deterministic when temperature=0
        else:
            # Alternate scores to simulate non-determinism without temperature pinning
            score = non_deterministic_scores[call_counter["n"] % len(non_deterministic_scores)]
            call_counter["n"] += 1
        response_body = json.dumps({
            "score": score,
            "urgency": "worth_discussing",
            "relevance_tag": "AI Tools",
            "summary": "Agentic AI release.",
            "reasoning": "Directly relevant to agentic SDLC goals.",
        })
        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps({
            "content": [{"text": response_body}]
        }).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = bedrock_invoke_side_effect

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service in ("bedrock-runtime", "bedrock"):
            return mock_bedrock
        return moto_boto3_client(service, **kw)

    scores = []
    for run_date in ("2026-03-24", "2026-03-25"):
        monkeypatch.setenv("RUN_DATE", run_date)
        with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
            handler({}, None)

        key = f"scored/{run_date}/{item['id']}.json"
        response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
        scored = json.loads(response["Body"].read())
        scores.append(scored["relevance_score"])

    # Both daily scores must be within ±10 points of each other
    score_day1, score_day2 = scores
    assert abs(score_day1 - score_day2) <= 10, (
        f"Scores differ by {abs(score_day1 - score_day2)} points "
        f"(day1={score_day1}, day2={score_day2}) — exceeds ±10 reliability threshold. "
        "Ensure the scoring handler passes temperature=0 to Bedrock."
    )

--- tests/unit/test_pipeline_run_metadata.py ---
# tests/unit/test_pipeline_run_metadata.py
import json
import textwrap
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_ingestion_handler_writes_pipeline_run_record_with_source_and_item_counts(
    monkeypatch, tmp_path
):
    """
    After the ingestion handler runs with two active sources (RSS and web),
    a PipelineRun record is written to S3 at pipeline-runs/{date}/run.json
    containing sources_attempted == 2, sources_succeeded == 2,
    items_ingested, transcription_jobs, and delivery_status.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Write a real sources.yaml at the filesystem boundary (not mocking load_sources)
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-rss-1
            name: AI News RSS
            type: rss
            url: https://example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-web-1
            name: Tech Blog
            type: web
            url: https://example.com/blog
            category: ai
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    # Set up AWS services at the AWS boundary
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    # Mock feedparser.parse at the external library / network boundary (RSS)
    fake_rss_feed = MagicMock()
    fake_rss_feed.bozo = False
    fake_rss_feed.entries = [
        MagicMock(
            title="AI Breakthrough",
            link="https://example.com/article-1",
            published_parsed=(2026, 3, 24, 10, 0, 0, 0, 0, 0),
            summary="An AI breakthrough was announced.",
        ),
        MagicMock(
            title="LLM Update",
            link="https://example.com/article-2",
            published_parsed=(2026, 3, 24, 11, 0, 0, 0, 0, 0),
            summary="A new LLM update was released.",
        ),
    ]

    # Mock urllib.request.urlopen at the network boundary (web page fetching)
    fake_web_html = b"""<html><body>
      <article>
        <h1>Tech Post</h1>
        <time datetime="2026-03-24">March 24, 2026</time>
        <p>AI developments continue.</p>
      </article>
    </body></html>"""
    fake_http_response = MagicMock()
    fake_http_response.read.return_value = fake_web_html
    fake_http_response.__enter__ = lambda s: s
    fake_http_response.__exit__ = MagicMock(return_value=False)

    with (
        patch("feedparser.parse", return_value=fake_rss_feed),
        patch("urllib.request.urlopen", return_value=fake_http_response),
    ):
        handler({}, None)

    # PipelineRun record must be written to S3 with correct metadata fields
    run_key = "pipeline-runs/2026-03-24/run.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=run_key)
    run_data = json.loads(response["Body"].read())

    assert run_data["sources_attempted"] == 2
    assert run_data["sources_succeeded"] == 2
    assert "items_ingested" in run_data
    assert "transcription_jobs" in run_data
    assert "delivery_status" in run_data

--- tests/unit/test_briefing_threshold_filtering.py ---
# tests/unit/test_briefing_threshold_filtering.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.briefing.handler import handler


@mock_aws
def test_only_items_above_relevance_threshold_appear_in_final_briefing(
    monkeypatch, tmp_path
):
    """
    Given the relevance threshold is set to 60 (default) and scored items in S3
    where one item has score 75 (above threshold) and one has score 40 (below
    threshold), when the briefing handler runs, only the item scoring above 60
    appears in the briefing — items_included == 1.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "60")
    monkeypatch.setenv("SES_SENDER", "briefing@example.com")
    monkeypatch.setenv("RECIPIENTS", "user@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Item above threshold (score 75) — should appear in briefing
    item_above = {
        "id": "item-above",
        "title": "Claude 4 Released with Agentic Capabilities",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "Anthropic released Claude 4.",
        "original_url": "https://example.com/claude-4",
        "content_format": "text",
        "transcript_status": "not_needed",
        "relevance_score": 75,
        "urgency": "worth_discussing",
        "relevance_tag": "AI Tools",
        "executive_summary": "Major agentic AI release.",
        "scoring_reasoning": "Highly relevant to agentic SDLC goals.",
        "is_duplicate": False,
        "duplicate_of": None,
    }

    # Item below threshold (score 40) — must NOT appear in briefing
    item_below = {
        "id": "item-below",
        "title": "Local Weather Forecast for March",
        "source_id": "src-rss-2",
        "source_name": "Weather Feed",
        "published_date": "2026-03-24T07:00:00+00:00",
        "full_text": "Expect sunny skies.",
        "original_url": "https://example.com/weather",
        "content_format": "text",
        "transcript_status": "not_needed",
        "relevance_score": 40,
        "urgency": "informational",
        "relevance_tag": "Other",
        "executive_summary": "Local weather update.",
        "scoring_reasoning": "Not relevant to agentic SDLC goals.",
        "is_duplicate": False,
        "duplicate_of": None,
    }

    for item in [item_above, item_below]:
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"scored/2026-03-24/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Mock SES at the AWS service boundary — we only care about item filtering
    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "msg-001"}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.briefing.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Only the item above the 60-point threshold must appear in the briefing
    assert result["items_included"] == 1

--- tests/unit/test_podcast_budget_cap.py ---
# tests/unit/test_podcast_budget_cap.py
#
# Behavior B017: When a podcast episode would exceed the daily transcription
# budget cap, it is flagged as "transcript unavailable" (transcript_status='failed')
# with the link still preserved in S3.
#
# Approach: DAILY_TRANSCRIPTION_BUDGET_MINUTES=0 exhausts the budget cap so any
# episode duration triggers the failure. No internal duration-detection library is
# mocked — only system boundaries (network, AWS) are patched.
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.transcription.handler import handler

# Load the minimal real MP3 fixture (one MPEG1/Layer3 frame at 44100 Hz, ~26 ms)
# stored in tests/fixtures/ so duration detection uses real library logic.
_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "short_podcast.mp3"
_MP3_BYTES = _FIXTURE_PATH.read_bytes()


@mock_aws
def test_podcast_episode_exceeding_budget_cap_is_flagged_transcript_unavailable(
    monkeypatch,
):
    """
    Given a podcast episode on the transcription queue and a daily transcription
    budget cap of 0 minutes (already exhausted), when the handler processes it,
    the episode is NOT transcribed; transcript_status is set to 'failed' and the
    ContentItem in S3 retains its title, source_name, and original_url.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    # Budget cap is 0: any episode that would consume transcription minutes is rejected.
    monkeypatch.setenv("DAILY_TRANSCRIPTION_BUDGET_MINUTES", "0")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item_id = "podcast-item-budget-cap"
    source_id = "podcast-source-1"
    audio_url = "https://example.com/podcast/long-episode.mp3"
    item_title = "Episode 99: A Very Long Deep Dive"
    source_name = "AI Podcast"

    content_item = {
        "id": item_id,
        "title": item_title,
        "source_id": source_id,
        "source_name": source_name,
        "published_date": "2026-03-24T09:00:00+00:00",
        "full_text": "",
        "original_url": audio_url,
        "content_format": "audio",
        "transcript_status": "pending",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{source_id}/{item_id}.json",
        Body=json.dumps(content_item),
    )

    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "item_id": item_id,
                        "source_id": source_id,
                        "content_format": "audio",
                        "original_url": audio_url,
                        "run_date": "2026-03-24",
                    }
                )
            }
        ]
    }

    # Pre-populate the Transcribe output object in S3 so that the baseline code path
    # (without a budget-cap check) would complete successfully and return
    # transcript_status='completed'.  This ensures the test fails (RED) because the
    # budget-cap guard is absent, not because of an unrelated S3 look-up error.
    transcribe_output_key = f"transcribe-output/2026-03-24/{item_id}.json"
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=transcribe_output_key,
        Body=json.dumps({"results": {"transcripts": [{"transcript": "some text"}]}}),
    )

    # Mock the network boundary: audio download returns the real MP3 fixture bytes.
    # No mutagen or duration-detection library is patched — the fixture is a genuine
    # MPEG1 Layer3 frame so any library can parse it if needed.
    mock_http_response = MagicMock()
    mock_http_response.read.return_value = _MP3_BYTES
    mock_http_response.__enter__ = lambda s: s
    mock_http_response.__exit__ = MagicMock(return_value=False)

    # Mock the AWS Transcribe boundary so the test isolates the budget-cap behaviour.
    transcript_output_uri = (
        f"https://s3.amazonaws.com/test-pipeline-bucket/{transcribe_output_key}"
    )
    mock_transcribe = MagicMock()
    mock_transcribe.start_transcription_job.return_value = {}
    mock_transcribe.get_transcription_job.return_value = {
        "TranscriptionJob": {
            "TranscriptionJobStatus": "COMPLETED",
            "Transcript": {"TranscriptFileUri": transcript_output_uri},
        }
    }

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "transcribe":
            return mock_transcribe
        return moto_boto3_client(service, **kw)

    with (
        patch("urllib.request.urlopen", return_value=mock_http_response),
        patch("src.transcription.handler.boto3.client", side_effect=client_factory),
    ):
        result = handler(event, None)

    # Handler must signal budget-cap failure via transcript_status.
    assert result["transcript_status"] == "failed"

    # ContentItem in S3 must be preserved: title, source_name, original_url intact
    # and transcript_status updated to 'failed' (the "transcript unavailable" flag).
    item_key = f"raw/2026-03-24/{source_id}/{item_id}.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=item_key)
    updated_item = json.loads(response["Body"].read())

    assert updated_item["title"] == item_title
    assert updated_item["source_name"] == source_name
    assert updated_item["original_url"] == audio_url
    assert updated_item["transcript_status"] == "failed"

--- tests/unit/test_podcast_ingestion.py ---
# tests/unit/test_podcast_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.ingestion.sources.podcast import ingest
from src.shared.models import Source


def test_podcast_ingestion_returns_audio_content_items_for_recent_episodes():
    """
    Given a podcast source and a since datetime, when ingest() is called,
    it returns ContentItem objects with content_format=audio for episodes
    published after `since`, each with source_id, title, published_date,
    and original_url set to the enclosure (audio file) URL.
    """
    source = Source(
        id="podcast-source-1",
        name="AI Podcast",
        type="podcast",
        url="https://example.com/podcast/feed.xml",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    episode_title = "Episode 42: The Future of Agentic AI"
    episode_enclosure_url = "https://example.com/podcast/ep42.mp3"

    mock_entry = MagicMock()
    mock_entry.title = episode_title
    mock_entry.published_parsed = (2026, 3, 24, 9, 0, 0, 0, 0, 0)
    mock_entry.enclosures = [
        MagicMock(href=episode_enclosure_url, type="audio/mpeg")
    ]

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_feed):
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "podcast-source-1"
    assert item.title == episode_title
    assert item.content_format == "audio"
    assert item.original_url == episode_enclosure_url
    assert item.published_date >= since

--- tests/unit/test_s3_lifecycle_retention.py ---
# tests/unit/test_s3_lifecycle_retention.py
#
# Behavior B036: Raw content, transcripts, scored items, and briefings older
# than 30 days are automatically deleted.
#
# Tests the CDK Pipeline Stack (infra/stacks/pipeline_stack.py).
# The S3 bucket must have an S3 lifecycle policy that expires objects after
# 30 days across all data prefixes (raw/, transcripts/, scored/, briefings/)
# so that storage costs remain bounded and data is purged automatically without
# operator intervention.
#
# This test FAILS (RED) because infra/stacks/pipeline_stack.py does not exist yet.

import aws_cdk as cdk
from aws_cdk import assertions

from infra.stacks.pipeline_stack import PipelineStack


def test_pipeline_stack_s3_bucket_has_30_day_lifecycle_expiration_across_all_prefixes():
    """
    Given the CDK PipelineStack is synthesized, when the CloudFormation template
    is inspected, the pipeline S3 bucket has at least one S3 lifecycle rule that
    expires objects after 30 days — automatically deleting raw content, transcripts,
    scored items, and briefings older than 30 days without manual operator action.
    """
    app = cdk.App()
    stack = PipelineStack(app, "TestPipelineStack")
    template = assertions.Template.from_stack(stack)

    # The pipeline bucket must have a lifecycle configuration with a 30-day expiration rule.
    # AWS CDK emits this as an AWS::S3::Bucket resource with LifecycleConfiguration.Rules
    # containing at least one rule with ExpirationInDays=30 and Status=Enabled.
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "LifecycleConfiguration": {
                "Rules": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "ExpirationInDays": 30,
                        "Status": "Enabled",
                    })
                ])
            }
        },
    )

--- tests/unit/test_x_api_ingestion.py ---
# tests/unit/test_x_api_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.sources.x_api import ingest
from src.shared.models import Source


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
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "x-source-1"
    assert tweet_text in item.title or tweet_text in item.full_text
    assert item.published_date == tweet_created_at
    assert tweet_id in item.original_url

--- tests/unit/test_pipeline_completion_logging.py ---
# tests/unit/test_pipeline_completion_logging.py
#
# Behavior B031: When the daily pipeline completes, logs show: sources scanned,
# items ingested, items scored above threshold, transcription jobs run, and
# total estimated cost.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# After a completed pipeline run record exists in S3, the monitoring handler must
# emit a log entry containing all five required pipeline completion metrics.
import json
import logging
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_pipeline_completion_logs_sources_items_scored_transcriptions_and_cost(
    monkeypatch, caplog
):
    """
    Given a completed PipelineRun record in S3 with known metrics (11 sources
    scanned, 47 items ingested, 8 items above threshold, 3 transcription jobs,
    $2.47 estimated cost), when the monitoring handler runs, the log output
    contains all five values — confirming operators can verify pipeline health
    from logs alone without consulting the S3 run record directly.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "10.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write a completed PipelineRun record to S3 with known metric values
    pipeline_run = {
        "run_date": "2026-03-24",
        "started_at": "2026-03-24T06:00:00+00:00",
        "completed_at": "2026-03-24T07:30:00+00:00",
        "sources_attempted": 12,
        "sources_succeeded": 11,
        "sources_failed": 1,
        "items_ingested": 47,
        "items_scored": 47,
        "items_above_threshold": 8,
        "items_in_briefing": 8,
        "transcription_jobs": 3,
        "estimated_cost_usd": 2.47,
        "delivery_status": "delivered",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
        Body=json.dumps(pipeline_run),
    )

    # Mock CloudWatch at the AWS service boundary — cost is below threshold
    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}

    # Mock SES at the AWS service boundary — no alert expected (cost < threshold)
    mock_ses = MagicMock()

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        with caplog.at_level(logging.INFO):
            result = handler({}, None)

    assert result["status"] == "ok"

    # Collect all log text for inspection
    all_log_messages = " ".join(r.message for r in caplog.records)

    # 1. Sources scanned (sources_succeeded=11)
    assert "11" in all_log_messages, (
        f"Logs must include sources scanned count (11). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 2. Items ingested (items_ingested=47)
    assert "47" in all_log_messages, (
        f"Logs must include items ingested count (47). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 3. Items scored above threshold (items_above_threshold=8)
    assert "8" in all_log_messages, (
        f"Logs must include items above threshold count (8). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 4. Transcription jobs run (transcription_jobs=3)
    assert "3" in all_log_messages, (
        f"Logs must include transcription jobs count (3). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 5. Total estimated cost ($2.47)
    assert "2.47" in all_log_messages, (
        f"Logs must include estimated cost (2.47). "
        f"Got log messages: {all_log_messages!r}"
    )

--- tests/unit/test_priority_ordered_ingestion.py ---
# tests/unit/test_priority_ordered_ingestion.py
import textwrap
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_sources_ingested_in_priority_order_regardless_of_yaml_declaration_order(
    monkeypatch, tmp_path
):
    """
    Given three RSS sources declared in YAML with priorities 3, 1, 2 (non-sorted),
    when the handler runs, it invokes each source ingestion in ascending priority
    order (priority 1 first, then 2, then 3) — ensuring highest-value sources
    are processed first when rate limits may constrain total volume.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Sources declared in non-priority order: 3, 1, 2
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-priority-3
            name: Low Priority Feed
            type: rss
            url: https://low-priority.example.com/feed.xml
            category: ai
            active: true
            priority: 3
          - id: src-priority-1
            name: High Priority Feed
            type: rss
            url: https://high-priority.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-priority-2
            name: Medium Priority Feed
            type: rss
            url: https://medium-priority.example.com/feed.xml
            category: ai
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    # Track the URL order that feedparser.parse is called with
    call_order = []

    def parse_side_effect(url, *args, **kwargs):
        call_order.append(url)
        feed = MagicMock()
        feed.bozo = False
        feed.entries = []
        return feed

    with patch("feedparser.parse", side_effect=parse_side_effect):
        handler({}, None)

    # All three sources must be attempted
    assert len(call_order) == 3

    # Priority=1 (high-priority) must be ingested first
    assert "high-priority" in call_order[0], (
        f"Expected priority=1 source first, got: {call_order}"
    )
    # Priority=2 (medium-priority) must be ingested second
    assert "medium-priority" in call_order[1], (
        f"Expected priority=2 source second, got: {call_order}"
    )
    # Priority=3 (low-priority) must be ingested last
    assert "low-priority" in call_order[2], (
        f"Expected priority=3 source last, got: {call_order}"
    )

--- tests/unit/test_cost_alert_notification.py ---
# tests/unit/test_cost_alert_notification.py
#
# Behavior B032: When daily costs exceed a configurable threshold, a cost alert
# notification is sent to configured recipients.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# When estimated_cost_usd in the PipelineRun record exceeds COST_ALERT_THRESHOLD_USD,
# the handler must send a cost alert email via SES and return alert_sent=True.
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_cost_alert_sent_to_recipients_when_daily_cost_exceeds_threshold(
    monkeypatch,
):
    """
    Given a completed PipelineRun record with estimated_cost_usd=18.75 and a
    cost alert threshold of $10.00, when the monitoring handler runs, it sends
    a cost alert email via SES to the configured alert recipient and returns
    alert_sent=True — notifying operators that the daily budget was exceeded.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "10.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Pipeline run with cost ($18.75) exceeding the threshold ($10.00)
    pipeline_run = {
        "run_date": "2026-03-24",
        "started_at": "2026-03-24T06:00:00+00:00",
        "completed_at": "2026-03-24T07:30:00+00:00",
        "sources_attempted": 12,
        "sources_succeeded": 12,
        "sources_failed": 0,
        "items_ingested": 120,
        "items_scored": 120,
        "items_above_threshold": 10,
        "items_in_briefing": 10,
        "transcription_jobs": 15,
        "estimated_cost_usd": 18.75,
        "delivery_status": "delivered",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
        Body=json.dumps(pipeline_run),
    )

    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}

    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "alert-msg-001"}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Handler must report that an alert was sent
    assert result.get("alert_sent") is True, (
        f"Expected alert_sent=True when cost $18.75 exceeds threshold $10.00, "
        f"got: {result.get('alert_sent')!r}"
    )

    # SES send_email must have been called at least once (the cost alert)
    assert mock_ses.send_email.called, (
        "SES send_email was never called — cost alert was not sent despite "
        "estimated_cost_usd ($18.75) exceeding COST_ALERT_THRESHOLD_USD ($10.00)."
    )

    # The alert must be addressed to the configured recipient
    call_kwargs = mock_ses.send_email.call_args
    # Support both positional and keyword argument styles
    call_args_flat = str(call_kwargs)
    assert "admin@example.com" in call_args_flat, (
        f"Cost alert email must be sent to ALERT_RECIPIENT 'admin@example.com'. "
        f"SES call args: {call_kwargs}"
    )

--- tests/unit/test_context_prompt_hot_reload.py ---
# tests/unit/test_context_prompt_hot_reload.py
#
# Behavior B026: The relevance scoring context prompt can be updated without
# code changes, taking effect on the next pipeline run.
#
# Tests the public interface load_context_prompt(config_dir) in
# src/shared/config.py. Each call must read the file fresh from disk so that
# an operator can edit context-prompt.txt and the change takes effect on the
# next pipeline run without redeploying code.
from src.shared.config import load_context_prompt


def test_updated_context_prompt_file_is_returned_on_next_call_without_code_changes(
    tmp_path,
):
    """
    Given config/context-prompt.txt is updated on disk between two calls to
    load_context_prompt(), when the second call is made (no code changes), it
    returns the new prompt text — confirming the function reads the file fresh
    each time rather than caching the result.
    """
    config_dir = str(tmp_path)
    prompt_file = tmp_path / "context-prompt.txt"

    # Write initial prompt and read it
    prompt_file.write_text("PROMPT_VERSION_ONE: Focus on agentic SDLC tooling.")
    first_result = load_context_prompt(config_dir)

    assert "PROMPT_VERSION_ONE" in first_result, (
        f"load_context_prompt did not return the initial prompt text; got: {first_result!r}"
    )

    # Update the prompt on disk — no code changes, no restart
    prompt_file.write_text("PROMPT_VERSION_TWO: Focus on autonomous agent orchestration.")
    second_result = load_context_prompt(config_dir)

    # The second call must reflect the updated file content
    assert "PROMPT_VERSION_TWO" in second_result, (
        "load_context_prompt returned stale content after the file was updated — "
        "it appears to be caching the prompt rather than reading from disk each call. "
        f"Got: {second_result!r}"
    )
    assert "PROMPT_VERSION_ONE" not in second_result, (
        "load_context_prompt still returned old prompt text after the file was updated."
    )

--- tests/unit/test_youtube_ingestion.py ---
# tests/unit/test_youtube_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.ingestion.sources.youtube import ingest
from src.shared.models import Source


def test_youtube_ingestion_returns_video_content_items_for_recent_videos():
    """
    Given a YouTube source and a since datetime, when ingest() is called,
    it returns ContentItem objects with content_format=video for videos
    published after `since`, each with source_id, title, published_date,
    and original_url populated from the YouTube API response.
    """
    source = Source(
        id="yt-source-1",
        name="AI Channel",
        type="youtube",
        url="https://www.youtube.com/channel/UC_test_channel_id",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    video_id = "dQw4w9WgXcQ"
    video_title = "Latest AI Developments Explained"
    published_at = "2026-03-24T10:00:00Z"

    mock_search_response = {
        "items": [
            {
                "id": {"videoId": video_id},
                "snippet": {
                    "title": video_title,
                    "publishedAt": published_at,
                    "channelTitle": "AI Channel",
                },
            }
        ]
    }

    mock_list_request = MagicMock()
    mock_list_request.execute.return_value = mock_search_response

    mock_search = MagicMock()
    mock_search.list.return_value = mock_list_request

    mock_youtube_client = MagicMock()
    mock_youtube_client.search.return_value = mock_search

    with patch(
        "src.ingestion.sources.youtube.build",
        return_value=mock_youtube_client,
    ):
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "yt-source-1"
    assert item.title == video_title
    assert item.content_format == "video"
    assert video_id in item.original_url
    assert item.published_date == datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)

--- tests/unit/test_x_api_rate_limit_mid_ingestion.py ---
# tests/unit/test_x_api_rate_limit_mid_ingestion.py
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import tweepy

from src.ingestion.sources.x_api import ingest
from src.shared.models import Source


def test_x_api_rate_limit_mid_ingestion_returns_partial_results_and_logs_event(caplog):
    """
    Given an X source being ingested across multiple pages, when the X API
    raises TooManyRequests on the second page (rate limit hit mid-ingestion),
    ingest() returns the ContentItems already retrieved from the first page
    and emits a warning log containing "rate limit".
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

    # First page: one tweet retrieved successfully, meta indicates more pages exist
    mock_tweet = MagicMock()
    mock_tweet.id = "tweet-page1-001"
    mock_tweet.text = "First page tweet about AI developments"
    mock_tweet.created_at = datetime(2026, 3, 24, 9, 0, 0, tzinfo=timezone.utc)

    first_page_meta = MagicMock()
    first_page_meta.next_token = "page2_token"

    first_page_response = MagicMock()
    first_page_response.data = [mock_tweet]
    first_page_response.meta = first_page_meta

    # Construct a tweepy TooManyRequests exception for the second page
    mock_rate_limit_response = MagicMock()
    mock_rate_limit_response.status_code = 429
    mock_rate_limit_response.headers = {}
    mock_rate_limit_response.json.return_value = {}
    mock_rate_limit_response.text = "Too Many Requests"

    call_count = 0

    def search_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_page_response
        raise tweepy.errors.TooManyRequests(mock_rate_limit_response)

    mock_client = MagicMock()
    mock_client.search_recent_tweets.side_effect = search_side_effect

    with patch("src.ingestion.sources.x_api.tweepy.Client", return_value=mock_client):
        with caplog.at_level(logging.WARNING):
            results = ingest(source, since)

    # Items from the first page must be returned despite the rate limit
    assert len(results) == 1
    assert results[0].source_id == "x-source-1"

    # A rate-limit-specific warning must be logged
    rate_limit_logs = [r for r in caplog.records if "rate limit" in r.message.lower()]
    assert len(rate_limit_logs) >= 1

--- tests/unit/test_source_config_validation.py ---
# tests/unit/test_source_config_validation.py
#
# Behavior B027: Source configuration is validated — duplicate IDs rejected.
#
# Tests the public interface load_sources(config_path) in src/ingestion/config.py.
# When two source entries share the same ID, load_sources() must raise a
# ValueError so that misconfigured configs are caught before ingestion runs.
import textwrap

import pytest

from src.ingestion.config import load_sources


def test_load_sources_raises_when_config_contains_duplicate_source_ids(tmp_path):
    """
    Given a sources.yaml that contains two entries with the same id,
    when load_sources() is called, it raises a ValueError — preventing
    ambiguous pipeline runs where the same source ID would write to the
    same S3 paths and produce non-deterministic results.
    """
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-duplicate-id
            name: First Source
            type: rss
            url: https://first.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-duplicate-id
            name: Second Source With Same ID
            type: web
            url: https://second.example.com/articles
            category: research
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)

    with pytest.raises(ValueError, match="duplicate"):
        load_sources(str(config_file))

--- tests/unit/test_scoring_relevance.py ---
# tests/unit/test_scoring_relevance.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler


@mock_aws
def test_each_content_item_receives_relevance_score_between_0_and_100(
    monkeypatch, tmp_path
):
    """
    Given a batch of ingested ContentItems in S3 and a configured company context
    prompt, when the scoring handler runs, each item is scored by the LLM and a
    ScoredItem is written to S3 at scored/{date}/{item_id}.json with a
    relevance_score between 0 and 100 inclusive.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Write context-prompt.txt at the filesystem boundary
    context_prompt = (
        "Score content for relevance to agentic SDLC transformation goals."
    )
    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(context_prompt)
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write two ContentItems to S3 at the raw path
    items = [
        {
            "id": "item-001",
            "title": "Claude 4 Released with Agentic Capabilities",
            "source_id": "src-rss-1",
            "source_name": "AI News",
            "published_date": "2026-03-24T08:00:00+00:00",
            "full_text": "Anthropic released Claude 4 with major agentic improvements.",
            "original_url": "https://example.com/claude-4",
            "content_format": "text",
            "transcript_status": "not_needed",
        },
        {
            "id": "item-002",
            "title": "Local Weather Forecast for March",
            "source_id": "src-rss-2",
            "source_name": "Weather Feed",
            "published_date": "2026-03-24T07:00:00+00:00",
            "full_text": "Expect sunny skies with a high of 72 degrees.",
            "original_url": "https://example.com/weather",
            "content_format": "text",
            "transcript_status": "not_needed",
        },
    ]
    for item in items:
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"raw/2026-03-24/{item['source_id']}/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Mock Bedrock at the AWS service boundary — returns structured JSON scores
    def bedrock_invoke_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        # Return a different score per item based on content to simulate LLM scoring
        title = ""
        for msg in request.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str):
                title = content
                break
        score = 85 if "Claude" in title or "claude" in title.lower() else 12
        response_body = json.dumps({
            "score": score,
            "urgency": "worth_discussing",
            "relevance_tag": "AI Tools",
            "summary": "Summary of the item.",
            "reasoning": "Scored based on relevance to agentic SDLC.",
        })
        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps({
            "content": [{"text": response_body}]
        }).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = bedrock_invoke_side_effect

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service in ("bedrock-runtime", "bedrock"):
            return mock_bedrock
        return moto_boto3_client(service, **kw)

    with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Handler must report all items scored
    assert result["items_scored"] == 2

    # Each item must have a ScoredItem written to S3 with relevance_score in [0, 100]
    for item in items:
        key = f"scored/2026-03-24/{item['id']}.json"
        response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
        scored = json.loads(response["Body"].read())

        assert "relevance_score" in scored, f"relevance_score missing for {item['id']}"
        score = scored["relevance_score"]
        assert isinstance(score, (int, float)), (
            f"relevance_score must be numeric, got {type(score)} for {item['id']}"
        )
        assert 0 <= score <= 100, (
            f"relevance_score {score} out of [0,100] range for {item['id']}"
        )

--- tests/unit/test_cloudwatch_metrics_namespace.py ---
# tests/unit/test_cloudwatch_metrics_namespace.py
#
# Behavior B035: CloudWatch custom metrics are published to the
# "AgenticSDLCIntel" namespace with dashboard and alarms.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# All per-run pipeline metrics must be published to "AgenticSDLCIntel" — not an
# alternative namespace — so that the CDK-defined dashboard and alarms can
# reference the same namespace and display / trigger without manual reconfiguration.
#
# This test FAILS (RED) because the handler currently publishes per-run metrics
# to "AiResearcher/Pipeline" rather than "AgenticSDLCIntel", and is missing
# required metric names: sources_failed, delivery_latency_minutes, briefing_item_count.
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler

REQUIRED_METRICS = {
    "SourcesScanned",
    "SourcesFailed",
    "ItemsIngested",
    "ItemsAboveThreshold",
    "TranscriptionJobs",
    "EstimatedCostUSD",
    "DeliveryLatencyMinutes",
    "BriefingItemCount",
}


@mock_aws
def test_monitoring_handler_publishes_all_per_run_metrics_to_agentic_sdlc_intel_namespace(
    monkeypatch,
):
    """
    Given a completed PipelineRun record in S3 with all standard fields,
    when the monitoring handler runs, it publishes all eight per-run metrics
    (SourcesScanned, SourcesFailed, ItemsIngested, ItemsAboveThreshold,
    TranscriptionJobs, EstimatedCostUSD, DeliveryLatencyMinutes,
    BriefingItemCount) to the CloudWatch namespace "AgenticSDLCIntel" —
    the same namespace referenced by the CDK dashboard and alarms — so that
    operators can monitor pipeline health through the AWS Console without
    namespace mismatch errors.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "100.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    pipeline_run = {
        "run_date": "2026-03-24",
        "started_at": "2026-03-24T06:00:00+00:00",
        "completed_at": "2026-03-24T07:30:00+00:00",
        "sources_attempted": 12,
        "sources_succeeded": 11,
        "sources_failed": 1,
        "items_ingested": 47,
        "items_scored": 47,
        "items_above_threshold": 8,
        "items_in_briefing": 8,
        "transcription_jobs": 3,
        "estimated_cost_usd": 2.47,
        "delivery_status": "delivered",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
        Body=json.dumps(pipeline_run),
    )

    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}
    mock_ses = MagicMock()

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    assert result["status"] == "ok"

    # Collect all metrics published per namespace across all put_metric_data calls
    metrics_by_namespace: dict[str, set] = {}
    for call in mock_cloudwatch.put_metric_data.call_args_list:
        kw = call.kwargs or {}
        namespace = kw.get("Namespace", "")
        metric_data = kw.get("MetricData", [])
        names = {m.get("MetricName", "") for m in metric_data}
        metrics_by_namespace.setdefault(namespace, set()).update(names)

    # All required per-run metrics must be published to "AgenticSDLCIntel"
    published_in_target = metrics_by_namespace.get("AgenticSDLCIntel", set())

    missing = REQUIRED_METRICS - published_in_target
    assert not missing, (
        f"The following metrics were not published to 'AgenticSDLCIntel' namespace: "
        f"{sorted(missing)}. "
        f"Metrics found in 'AgenticSDLCIntel': {sorted(published_in_target)}. "
        f"All namespaces published to: {list(metrics_by_namespace.keys())}. "
        "All per-run metrics must use 'AgenticSDLCIntel' so the CDK-defined "
        "dashboard and alarms can reference them without namespace mismatch."
    )

--- tests/unit/test_source_config_new_entry.py ---
# tests/unit/test_source_config_new_entry.py
import textwrap

import pytest

from src.ingestion.config import load_sources


def test_new_source_entry_in_config_file_is_included_in_loaded_sources(tmp_path):
    """
    Given a sources.yaml with an existing source and a newly added source entry
    (name, type, URL, and optional category), when load_sources() is called,
    the new source is present in the returned list — confirming it would be
    included in the next daily pipeline run.
    """
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-existing-001
            name: Existing AI News
            type: rss
            url: https://existing.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-new-002
            name: New Source Added by User
            type: web
            url: https://new-source.example.com/articles
            category: research
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)

    sources = load_sources(str(config_file))

    source_ids = [s.id for s in sources]
    assert "src-new-002" in source_ids, (
        "Newly added source 'src-new-002' was not returned by load_sources()"
    )

    new_source = next(s for s in sources if s.id == "src-new-002")
    assert new_source.name == "New Source Added by User"
    assert new_source.type == "web"
    assert new_source.url == "https://new-source.example.com/articles"
    assert new_source.category == "research"

--- tests/unit/test_deduplication_five_sources.py ---
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

--- tests/unit/test_youtube_transcription_failure.py ---
# tests/unit/test_youtube_transcription_failure.py
import json
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.transcription.handler import handler


@mock_aws
def test_youtube_no_transcript_and_transcription_failure_item_preserved_with_unavailable_flag(
    monkeypatch,
):
    """
    Given a YouTube video with no subtitles where both yt-dlp subtitle download
    and audio transcription fail, when the handler processes the item, it returns
    transcript_status='failed' and the ContentItem in S3 retains its title,
    source_name, and original_url — the item is not dropped from the pipeline.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item_id = "yt-item-no-transcript"
    source_id = "yt-source-1"
    video_url = "https://www.youtube.com/watch?v=noTranscriptVideoId"
    item_title = "AI Summit Keynote: No Captions Available"
    source_name = "AI Conference Channel"

    # Write the raw ContentItem to S3
    content_item = {
        "id": item_id,
        "title": item_title,
        "source_id": source_id,
        "source_name": source_name,
        "published_date": "2026-03-24T10:00:00+00:00",
        "full_text": "",
        "original_url": video_url,
        "content_format": "video",
        "transcript_status": "pending",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{source_id}/{item_id}.json",
        Body=json.dumps(content_item),
    )

    # SQS event for the YouTube video
    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "item_id": item_id,
                        "source_id": source_id,
                        "content_format": "video",
                        "original_url": video_url,
                        "run_date": "2026-03-24",
                    }
                )
            }
        ]
    }

    # yt-dlp raises an exception — no subtitles and audio extraction fails
    mock_ydl_instance = MagicMock()
    mock_ydl_instance.__enter__ = lambda s: s
    mock_ydl_instance.__exit__ = MagicMock(return_value=False)
    mock_ydl_instance.extract_info.side_effect = Exception(
        "No subtitles available and audio download failed"
    )

    mock_ydl_class = MagicMock(return_value=mock_ydl_instance)

    with patch("src.transcription.handler.yt_dlp.YoutubeDL", mock_ydl_class):
        result = handler(event, None)

    # Handler must report transcript_status=failed — not raise or swallow the failure silently
    assert result["transcript_status"] == "failed"

    # The ContentItem in S3 must still preserve title, source_name, and original_url
    updated_item_key = f"raw/2026-03-24/{source_id}/{item_id}.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=updated_item_key)
    updated_item = json.loads(response["Body"].read())

    assert updated_item["title"] == item_title
    assert updated_item["source_name"] == source_name
    assert updated_item["original_url"] == video_url
    # transcript_status must be 'failed' (the "transcript unavailable" flag)
    assert updated_item["transcript_status"] == "failed"

--- tests/unit/test_delivery_reliability_metrics.py ---
# tests/unit/test_delivery_reliability_metrics.py
#
# Behavior B033: After 7 consecutive days, an operator can see delivery reliability
# (% on-time) and average cost per run.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# After 7 pipeline run records exist in S3, the monitoring handler must publish
# DeliveryReliabilityPct and AverageCostPerRun metrics to CloudWatch namespace
# "AgenticSDLCIntel" so operators have a 7-day rolling view without querying S3.
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_after_seven_days_monitoring_handler_publishes_delivery_reliability_and_average_cost(
    monkeypatch,
):
    """
    Given 7 consecutive pipeline run records in S3 (6 with delivery_status='delivered'
    and 1 with delivery_status='failed'), when the monitoring handler runs on day 7,
    CloudWatch put_metric_data is called with 'DeliveryReliabilityPct' (~85.7%) and
    'AverageCostPerRun' metrics in the 'AgenticSDLCIntel' namespace — giving operators
    a 7-day rolling view of pipeline reliability and cost without consulting S3 directly.

    This test FAILS (RED) because the monitoring handler currently only publishes
    per-run metrics for the current day — it does not aggregate across 7 days to
    compute rolling delivery reliability or average cost per run.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "100.00")  # high so no alert fires
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write 7 consecutive pipeline run records to S3.
    # 6 delivered on-time, 1 failed → reliability = 6/7 ≈ 85.71%
    # Costs: 2.00, 2.50, 3.00, 3.50, 4.00, 4.50, 5.00 → avg = 3.50
    base_date = date(2026, 3, 18)  # 7 days ending on RUN_DATE 2026-03-24
    for i in range(7):
        run_date = (base_date + timedelta(days=i)).isoformat()
        cost = 2.0 + i * 0.5
        delivery_status = "failed" if i == 3 else "delivered"
        pipeline_run = {
            "run_date": run_date,
            "started_at": f"{run_date}T06:00:00+00:00",
            "completed_at": f"{run_date}T07:30:00+00:00",
            "sources_attempted": 12,
            "sources_succeeded": 12,
            "sources_failed": 0,
            "items_ingested": 50,
            "items_scored": 50,
            "items_above_threshold": 8,
            "items_in_briefing": 8,
            "transcription_jobs": 3,
            "estimated_cost_usd": cost,
            "delivery_status": delivery_status,
        }
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"pipeline-runs/{run_date}/run.json",
            Body=json.dumps(pipeline_run),
        )

    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}
    mock_ses = MagicMock()

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    assert result["status"] == "ok"

    # Collect all metric names published to the AgenticSDLCIntel namespace
    published_metrics = {}
    for call_args in mock_cloudwatch.put_metric_data.call_args_list:
        kwargs = call_args.kwargs or {}
        positional = call_args.args or ()
        namespace = kwargs.get("Namespace") or (positional[0] if positional else "")
        metric_data = kwargs.get("MetricData") or (positional[1] if len(positional) > 1 else [])
        if "AgenticSDLCIntel" in str(namespace):
            for metric in metric_data:
                name = metric.get("MetricName", "")
                published_metrics[name] = metric.get("Value")

    # --- Assertion 1: delivery reliability metric must be published ---
    reliability_metric = next(
        (name for name in published_metrics if "reliability" in name.lower()),
        None,
    )
    assert reliability_metric is not None, (
        f"No delivery reliability metric found in CloudWatch 'AgenticSDLCIntel' namespace. "
        f"Published metrics: {list(published_metrics.keys())}. "
        "After 7 consecutive days the monitoring handler must publish a "
        "'DeliveryReliabilityPct' (or similar) metric so operators can track "
        "the % of on-time deliveries over the rolling 7-day window."
    )

    # Value must be close to 85.71% (6 delivered / 7 total × 100)
    reliability_value = published_metrics[reliability_metric]
    assert abs(reliability_value - (6 / 7 * 100)) < 1.0, (
        f"DeliveryReliabilityPct should be ~85.71% (6/7 runs delivered), "
        f"got {reliability_value:.2f}%."
    )

    # --- Assertion 2: average cost per run metric must be published ---
    avg_cost_metric = next(
        (
            name for name in published_metrics
            if "average" in name.lower() and "cost" in name.lower()
        ),
        None,
    )
    assert avg_cost_metric is not None, (
        f"No average cost per run metric found in CloudWatch 'AgenticSDLCIntel' namespace. "
        f"Published metrics: {list(published_metrics.keys())}. "
        "After 7 consecutive days the monitoring handler must publish an "
        "'AverageCostPerRun' (or similar) metric so operators can track "
        "the rolling 7-day average pipeline cost."
    )

    # Value must be close to $3.50 (sum of 2.00..5.00 / 7)
    avg_cost_value = published_metrics[avg_cost_metric]
    assert abs(avg_cost_value - 3.50) < 0.01, (
        f"AverageCostPerRun should be $3.50 (avg of 7 runs), got ${avg_cost_value:.2f}."
    )

--- tests/unit/test_scoring_urgency_classification.py ---
# tests/unit/test_scoring_urgency_classification.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler

VALID_URGENCY_LEVELS = {"informational", "worth_discussing", "action_needed"}


@mock_aws
def test_scored_item_above_threshold_is_classified_with_valid_urgency_level(
    monkeypatch, tmp_path
):
    """
    Given a ContentItem that scores above the relevance threshold, when the
    scoring handler runs and the LLM returns urgency='action_needed', the
    ScoredItem written to S3 has urgency set to one of the three valid levels:
    informational, worth_discussing, or action_needed.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "60")

    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(
        "Score content for relevance to agentic SDLC transformation goals."
    )
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item = {
        "id": "item-urgency-001",
        "title": "Critical: GPT-5 Threatens Competitive Position",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "OpenAI released GPT-5 with capabilities far exceeding current models.",
        "original_url": "https://example.com/gpt5-release",
        "content_format": "text",
        "transcript_status": "not_needed",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{item['source_id']}/{item['id']}.json",
        Body=json.dumps(item),
    )

    # Bedrock returns score=90 (above threshold=60) with urgency='action_needed'
    llm_response_body = json.dumps({
        "score": 90,
        "urgency": "action_needed",
        "relevance_tag": "Competitive Intelligence",
        "summary": "GPT-5 release poses direct competitive threat to agentic SDLC goals.",
        "reasoning": "High-relevance competitive development requiring immediate attention.",
    })
    mock_stream = MagicMock()
    mock_stream.read.return_value = json.dumps({
        "content": [{"text": llm_response_body}]
    }).encode("utf-8")

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = {"body": mock_stream}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service in ("bedrock-runtime", "bedrock"):
            return mock_bedrock
        return moto_boto3_client(service, **kw)

    with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
        handler({}, None)

    # ScoredItem must be written with a valid urgency classification
    key = f"scored/2026-03-24/{item['id']}.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
    scored = json.loads(response["Body"].read())

    assert "urgency" in scored, "ScoredItem missing urgency field"
    assert scored["urgency"] in VALID_URGENCY_LEVELS, (
        f"urgency '{scored['urgency']}' is not one of {VALID_URGENCY_LEVELS}"
    )
    assert scored["urgency"] == "action_needed", (
        f"Expected 'action_needed' from LLM response, got '{scored['urgency']}'"
    )

--- tests/unit/test_semantic_deduplication_different_angles.py ---
# tests/unit/test_semantic_deduplication_different_angles.py
#
# Behavior B029: Given two items have similar topics but genuinely different
# angles or insights, both items are retained as distinct entries.
#
# The current _are_duplicates prompt sends only executive_summary to the LLM.
# Without scoring_reasoning, the LLM lacks context to distinguish "same core
# development reported twice" from "same topic covered from a genuinely
# different angle." This test will FAIL (RED) until scoring_reasoning is
# included in the deduplication prompt, enabling proper angle differentiation.

import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_items_with_different_angle_reasoning_are_both_retained_when_reasoning_informs_dedup():
    """
    Given two ScoredItems with similar executive_summaries (same GPT-5 release)
    but scoring_reasoning that explicitly documents different angles — one scored
    from a developer-tools perspective, one from a business-strategy perspective —
    when deduplicate_by_semantics() is called, both items are retained as distinct
    entries (is_duplicate=False, duplicate_of=None for both).

    The Bedrock mock returns is_duplicate=false ONLY when the prompt contains
    the scoring_reasoning text, simulating a real LLM that correctly identifies
    different angles once given full context. With the current implementation
    (prompt contains only executive_summary), the mock returns is_duplicate=true
    and the test FAILS — confirming that scoring_reasoning must be included in
    the deduplication prompt to detect genuinely different angles.
    """
    item_developer = ScoredItem(
        content_item_id="item-gpt5-developer-tools",
        relevance_score=85,
        urgency="worth_discussing",
        relevance_tag="AI Tools",
        executive_summary=(
            "OpenAI releases GPT-5 with advanced coding and agentic capabilities, "
            "signalling a major shift in AI-assisted development workflows."
        ),
        scoring_reasoning=(
            "Scored from a developer-tools angle: GPT-5 directly competes with our "
            "agentic SDLC toolchain choices and may alter which LLM we recommend "
            "for code generation tasks."
        ),
        is_duplicate=False,
        duplicate_of=None,
    )

    item_business = ScoredItem(
        content_item_id="item-gpt5-business-strategy",
        relevance_score=70,
        urgency="worth_discussing",
        relevance_tag="Market Intelligence",
        executive_summary=(
            "GPT-5 launched by OpenAI; analysts expect significant market impact "
            "across enterprise AI adoption."
        ),
        scoring_reasoning=(
            "Scored from a business-strategy angle: this launch reshapes the "
            "competitive landscape for enterprise AI adoption and may influence "
            "budget allocation decisions for agentic SDLC initiatives."
        ),
        is_duplicate=False,
        duplicate_of=None,
    )

    # Bedrock mock: returns is_duplicate=false only when scoring_reasoning text
    # is present in the prompt — simulating a well-informed LLM that recognises
    # the developer-tools and business-strategy angles as genuinely distinct.
    # Without reasoning in the prompt the mock returns is_duplicate=true, which
    # causes the test to fail (RED) for the current implementation.
    def invoke_model_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        prompt_text = ""
        for msg in request.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt_text += content

        reasoning_present = (
            "developer-tools angle" in prompt_text
            or "business-strategy angle" in prompt_text
        )
        result = {"is_duplicate": not reasoning_present}

        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps(
            {"content": [{"text": json.dumps(result)}]}
        ).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = invoke_model_side_effect

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics([item_developer, item_business])

    by_id = {item.content_item_id: item for item in result}

    # Both items must be retained as distinct entries — neither flagged as duplicate
    assert by_id["item-gpt5-developer-tools"].is_duplicate is False, (
        "The developer-tools-angle item must not be flagged as a duplicate."
    )
    assert by_id["item-gpt5-business-strategy"].is_duplicate is False, (
        "The business-strategy-angle item must not be flagged as a duplicate — "
        "it covers the same topic as the other item but from a genuinely different "
        "angle. The dedup prompt must include scoring_reasoning so the LLM can "
        "distinguish angle coverage from same-development duplication."
    )
    assert by_id["item-gpt5-business-strategy"].duplicate_of is None, (
        "duplicate_of must be None for an item retained as a distinct entry."
    )

--- tests/unit/test_seed_source_list.py ---
# tests/unit/test_seed_source_list.py
#
# Behavior B025: The seed source list contains at least 20 sources spanning
# all supported format types (rss, web, x, youtube, podcast, substack).
#
# Tests the actual config/sources.yaml at the repository root — no mocking,
# because the observable behavior IS the contents of the seed file itself.
import os
import pathlib

import pytest

from src.ingestion.config import load_sources

# Canonical path for the seed source list, relative to the repository root
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SEED_CONFIG = _REPO_ROOT / "config" / "sources.yaml"

REQUIRED_TYPES = {"rss", "web", "x", "youtube", "podcast", "substack"}
MIN_SOURCE_COUNT = 20


def test_seed_source_list_has_at_least_20_sources_spanning_all_format_types():
    """
    Given the seed sources.yaml at config/sources.yaml, when load_sources() is
    called on it, the result contains at least 20 active sources and all
    supported format types (rss, web, x, youtube, podcast, substack) are
    represented by at least one source each.
    """
    assert _SEED_CONFIG.exists(), (
        f"Seed source config not found at {_SEED_CONFIG}. "
        "Create config/sources.yaml with at least 20 sources covering all format types."
    )

    sources = load_sources(str(_SEED_CONFIG))

    assert len(sources) >= MIN_SOURCE_COUNT, (
        f"Seed source list has only {len(sources)} active sources; "
        f"need at least {MIN_SOURCE_COUNT}."
    )

    present_types = {s.type for s in sources}
    missing_types = REQUIRED_TYPES - present_types
    assert not missing_types, (
        f"Seed source list is missing format types: {missing_types}. "
        f"Present types: {present_types}. "
        "Add at least one source of each type to config/sources.yaml."
    )

--- tests/unit/test_podcast_transcription.py ---
# tests/unit/test_podcast_transcription.py
import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from src.transcription.handler import handler


@mock_aws
def test_podcast_episode_audio_transcribed_via_aws_transcribe_and_written_to_s3(
    monkeypatch,
):
    """
    Given a podcast episode item on the transcription queue (content_format=audio),
    when the handler processes it, the audio is downloaded, sent to AWS Transcribe,
    and the resulting transcript text is written to S3 at
    transcripts/{date}/{item_id}.txt with transcript_status 'completed'.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item_id = "podcast-item-001"
    source_id = "podcast-source-1"
    audio_url = "https://example.com/podcast/ep42.mp3"
    transcript_text = "Welcome to episode 42 about the future of agentic AI systems."

    # Write the raw ContentItem to S3 (the handler reads it to get item details)
    content_item = {
        "id": item_id,
        "title": "Episode 42: The Future of Agentic AI",
        "source_id": source_id,
        "source_name": "AI Podcast",
        "published_date": "2026-03-24T09:00:00+00:00",
        "full_text": "",
        "original_url": audio_url,
        "content_format": "audio",
        "transcript_status": "pending",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{source_id}/{item_id}.json",
        Body=json.dumps(content_item),
    )

    # Write the Transcribe output JSON to S3 — simulates what AWS Transcribe
    # deposits at its output S3 location once the job completes.
    transcribe_output = {
        "results": {
            "transcripts": [{"transcript": transcript_text}]
        }
    }
    transcribe_output_key = f"transcribe-output/2026-03-24/{item_id}.json"
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=transcribe_output_key,
        Body=json.dumps(transcribe_output),
    )

    # SQS event payload for a podcast audio item
    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "item_id": item_id,
                        "source_id": source_id,
                        "content_format": "audio",
                        "original_url": audio_url,
                        "run_date": "2026-03-24",
                    }
                )
            }
        ]
    }

    # Mock audio download at the network boundary
    fake_audio_bytes = b"FAKE_MP3_AUDIO_DATA"
    mock_http_response = MagicMock()
    mock_http_response.read.return_value = fake_audio_bytes
    mock_http_response.__enter__ = lambda s: s
    mock_http_response.__exit__ = MagicMock(return_value=False)

    # Mock AWS Transcribe at the service boundary: job starts and immediately
    # returns COMPLETED with a pointer to the transcript output in S3.
    transcript_output_uri = (
        f"https://s3.amazonaws.com/test-pipeline-bucket/{transcribe_output_key}"
    )
    mock_transcribe = MagicMock()
    mock_transcribe.start_transcription_job.return_value = {}
    mock_transcribe.get_transcription_job.return_value = {
        "TranscriptionJob": {
            "TranscriptionJobStatus": "COMPLETED",
            "Transcript": {"TranscriptFileUri": transcript_output_uri},
        }
    }

    # Capture the moto-patched boto3.client so we can delegate S3 calls to it
    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "transcribe":
            return mock_transcribe
        return moto_boto3_client(service, **kw)

    with (
        patch("urllib.request.urlopen", return_value=mock_http_response),
        patch("src.transcription.handler.boto3.client", side_effect=client_factory),
    ):
        result = handler(event, None)

    # Transcript must be written to S3 at the canonical path
    transcript_key = f"transcripts/2026-03-24/{item_id}.txt"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=transcript_key)
    stored_transcript = response["Body"].read().decode("utf-8")

    assert transcript_text in stored_transcript
    assert result["transcript_status"] == "completed"

--- tests/unit/test_consecutive_source_failure_tracking.py ---
# tests/unit/test_consecutive_source_failure_tracking.py
#
# Behavior B034: A source that fails for 3 consecutive days triggers a warning
# in operator metrics.
#
# Tests the public interfaces track_source_failure() and get_failing_sources()
# in src/ingestion/handler.py. After recording 3 consecutive daily failures for
# a source, get_failing_sources(threshold=3) must return that source so the
# monitoring handler can surface it in operator metrics and CloudWatch alarms.
import boto3
from moto import mock_aws

from src.ingestion.handler import get_failing_sources, track_source_failure


@mock_aws
def test_source_failing_three_consecutive_days_appears_in_get_failing_sources(
    monkeypatch,
):
    """
    Given a source whose ingestion has failed on 3 consecutive days (tracked
    via track_source_failure()), when get_failing_sources(threshold=3) is
    called, the source appears in the result with a consecutive failure count
    of 3 — enabling the monitoring handler to surface a warning in operator
    metrics and trigger CloudWatch alarms for persistently failing sources.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    source_id = "src-persistently-failing"

    # Record 3 consecutive daily failures for the same source
    track_source_failure(source_id, "2026-03-22", succeeded=False)
    track_source_failure(source_id, "2026-03-23", succeeded=False)
    track_source_failure(source_id, "2026-03-24", succeeded=False)

    # A source with a different ID that succeeds on day 3 must NOT appear
    other_id = "src-recovered"
    track_source_failure(other_id, "2026-03-22", succeeded=False)
    track_source_failure(other_id, "2026-03-23", succeeded=False)
    track_source_failure(other_id, "2026-03-24", succeeded=True)  # reset on success

    failing = get_failing_sources(threshold=3)

    failing_ids = [src_id for src_id, _count in failing]
    assert source_id in failing_ids, (
        f"Source '{source_id}' with 3 consecutive failures must appear in "
        f"get_failing_sources(threshold=3). Got: {failing}"
    )

    count_for_source = next(
        count for src_id, count in failing if src_id == source_id
    )
    assert count_for_source == 3, (
        f"Consecutive failure count must be 3, got {count_for_source}"
    )

    assert other_id not in failing_ids, (
        f"Source '{other_id}' recovered on day 3 (succeeded=True resets count) "
        f"and must not appear in get_failing_sources(threshold=3). Got: {failing}"
    )

## Public Interfaces (DO NOT change signatures)

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

## Guardrails

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


### Sign: aws_cdk not installed — CDK infra tests fail at collection
- **Category**: RED-FAILURE
- **Detail**: `import aws_cdk` raises `ModuleNotFoundError` because `aws_cdk` is not in the test environment. The GREEN phase must install `aws_cdk` and `aws-cdk-lib` (e.g., `python3 -m pip install aws-cdk-lib constructs`) before the CDK assertions can run. The `infra/` package also needs `__init__.py` files at each level so Python treats it as a package.
- **Added after**: B036 at 2026-03-25T04:59:18Z

## Output Format

Edit the files on disk, then confirm what you changed by outputting:

```
REFACTORED: <file_path>
```

for each file modified. If no refactoring is needed, output:

```
# No Refactoring Needed

The code is clean and well-structured. No changes recommended.
```

If you encounter a failure that future steps should learn from, output a guardrail block:

```
### Sign: <short title>
- **Category**: REFACTOR-FAILURE
- **Detail**: <what went wrong and how to avoid it>
```
