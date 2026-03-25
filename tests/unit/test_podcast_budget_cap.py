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
