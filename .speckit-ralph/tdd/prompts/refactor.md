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
