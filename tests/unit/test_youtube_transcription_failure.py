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
