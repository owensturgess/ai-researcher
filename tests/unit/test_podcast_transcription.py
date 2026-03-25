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
