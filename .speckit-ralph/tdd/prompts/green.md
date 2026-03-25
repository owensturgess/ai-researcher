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

Full suite: 1 failed (B020 RED, correct), 13 passed (all existing tests restored).

```
FILE: tests/unit/test_briefing_threshold_filtering.py
```

**Summary of changes made:**

1. **Restored `src/scoring/handler.py`** — the previous GREEN attempt incorrectly filtered items at the scoring stage (only writing above-threshold items to S3). This broke B019. Restored it to write ALL scored items to `scored/`, and only count `items_above_threshold` for reporting.

2. **Created `src/briefing/__init__.py`** and **`src/briefing/handler.py`** stubs — the briefing package didn't exist. The stub raises `NotImplementedError` so the test fails at runtime (not collection time).

3. **Written `tests/unit/test_briefing_threshold_filtering.py`** — B020's RED test targets the **briefing handler** (not the scoring handler), which is the correct interface: per the spec, the briefing handler "loads ScoredItems above threshold." The test pre-populates S3 with two scored items (scores 75 and 40), calls the briefing handler, and asserts `items_included == 1`.

## Previous GREEN Gate Failure (MUST fix these issues)
GATE: VERIFY_GREEN for B020
CHECK FAIL: Test suite FAILED after implementation.
Test output:
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/ocs/Documents/GitHub/ai-researcher
plugins: cov-7.0.0
collected 14 items

tests/unit/test_ingestion_error_isolation.py .                           [  7%]
tests/unit/test_pipeline_run_metadata.py .                               [ 14%]
tests/unit/test_podcast_budget_cap.py .                                  [ 21%]
tests/unit/test_podcast_ingestion.py .                                   [ 28%]
tests/unit/test_podcast_transcription.py .                               [ 35%]
tests/unit/test_priority_ordered_ingestion.py .                          [ 42%]
tests/unit/test_relevance_threshold_filtering.py .                       [ 50%]
tests/unit/test_scoring_relevance.py F                                   [ 57%]
tests/unit/test_x_api_ingestion.py .                                     [ 64%]
tests/unit/test_x_api_rate_limit_mid_ingestion.py .                      [ 71%]
tests/unit/test_youtube_ingestion.py .                                   [ 78%]
tests/unit/test_youtube_quota_limit.py .                                 [ 85%]
tests/unit/test_youtube_transcription.py .                               [ 92%]
tests/unit/test_youtube_transcription_failure.py .                       [100%]

=================================== FAILURES ===================================
______ test_each_content_item_receives_relevance_score_between_0_and_100 _______

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10e51d750>
tmp_path = PosixPath('/private/var/folders/lk/483m3nhs18ddr8n3cy5n6rl80000gn/T/pytest-of-ocs/pytest-82/test_each_content_item_receive0')

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
>           response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/unit/test_scoring_relevance.py:110: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/botocore/client.py:602: in _api_call
    return self._make_api_call(operation_name, kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/botocore/context.py:123: in wrapper
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <botocore.client.S3 object at 0x111269940>, operation_name = 'GetObject'
api_params = {'Bucket': 'test-pipeline-bucket', 'ChecksumMode': 'ENABLED', 'Key': 'scored/2026-03-24/item-002.json'}

    @with_current_context()
    def _make_api_call(self, operation_name, api_params):
        operation_model = self._service_model.operation_model(operation_name)
        service_name = self._service_model.service_name
        history_recorder.record(
            'API_CALL',
            {
                'service': service_name,
                'operation': operation_name,
                'params': api_params,
            },
        )
        if operation_model.deprecated:
            logger.debug(
                'Warning: %s.%s() is deprecated', service_name, operation_name
            )
        request_context = {
            'client_region': self.meta.region_name,
            'client_config': self.meta.config,
            'has_streaming_input': operation_model.has_streaming_input,
            'auth_type': operation_model.resolved_auth_type,
            'unsigned_payload': operation_model.unsigned_payload,
            'auth_options': self._service_model.metadata.get('auth'),
        }
    
        api_params = self._emit_api_params(
            api_params=api_params,
            operation_model=operation_model,
            context=request_context,
        )
        (
            endpoint_url,
            additional_headers,
            properties,
        ) = self._resolve_endpoint_ruleset(
            operation_model, api_params, request_context
        )
        if properties:
            # Pass arbitrary endpoint info with the Request
            # for use during construction.
            request_context['endpoint_properties'] = properties
        request_dict = self._convert_to_request_dict(
            api_params=api_params,
            operation_model=operation_model,
            endpoint_url=endpoint_url,
            context=request_context,
            headers=additional_headers,
        )
        resolve_checksum_context(request_dict, operation_model, api_params)
    
        service_id = self._service_model.service_id.hyphenize()
        handler, event_response = self.meta.events.emit_until_response(
            f'before-call.{service_id}.{operation_name}',
            model=operation_model,
            params=request_dict,
            request_signer=self._request_signer,
            context=request_context,
        )
    
        if event_response is not None:
            http, parsed_response = event_response
        else:
            maybe_compress_request(
                self.meta.config, request_dict, operation_model
            )
            apply_request_checksum(request_dict)
            http, parsed_response = self._make_request(
                operation_model, request_dict, request_context
            )
    
        self.meta.events.emit(
            f'after-call.{service_id}.{operation_name}',
            http_response=http,
            parsed=parsed_response,
            model=operation_model,
            context=request_context,
        )
    
        if http.status_code >= 300:
            error_info = parsed_response.get("Error", {})
            error_code = request_context.get(
                'error_code_override'
            ) or error_info.get("Code")
            error_class = self.exceptions.from_code(error_code)
>           raise error_class(parsed_response, operation_name)
E           botocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist.

/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/botocore/client.py:1078: NoSuchKey
=========================== short test summary info ============================
FAILED tests/unit/test_scoring_relevance.py::test_each_content_item_receives_relevance_score_between_0_and_100
========================= 1 failed, 13 passed in 3.14s =========================
RESULT: FAIL

## Existing Code (for context — extend or modify as needed)


--- src/ingestion/handler.py ---
# src/ingestion/handler.py
import json
import logging
import os

import boto3
import yaml

from src.ingestion.sources import rss, web, x_api

logger = logging.getLogger(__name__)

_INGESTERS = {"rss": rss.ingest, "web": web.ingest, "x": x_api.ingest}


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    sources = [s for s in config.get("sources", []) if s.get("active", True)]
    return sorted(sources, key=lambda s: s.get("priority", 1))


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    for source in sources:
        source_type = source.get("type")
        ingest_fn = _INGESTERS.get(source_type)
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
            logger.warning("ingestion failed for source %s", source.get("id", "unknown"), exc_info=True)

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

--- src/briefing/handler.py ---
# src/briefing/handler.py
import boto3


def handler(event, context):
    raise NotImplementedError("Briefing handler not yet implemented")

--- src/scoring/handler.py ---
# src/scoring/handler.py
import json
import os

import boto3


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    context_prompt_path = os.environ.get("CONTEXT_PROMPT_PATH", "config/context-prompt.txt")

    with open(context_prompt_path) as f:
        context_prompt = f.read().strip()

    s3 = boto3.client("s3")
    bedrock = boto3.client("bedrock-runtime")

    # List all raw items for this run date
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

            score = _score_item(bedrock, context_prompt, item)

            item_id = item["id"]
            scored = dict(item)
            scored["relevance_score"] = score
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


def _score_item(bedrock, context_prompt, item):
    user_text = (
        f"Title: {item.get('title', '')}\n"
        f"Content: {item.get('full_text', '')}\n\n"
        "Respond with JSON containing a 'score' field (integer 0-100)."
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
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
    return parsed["score"]

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
