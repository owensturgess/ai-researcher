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
