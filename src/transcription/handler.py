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

    if any_failed:
        return {"transcript_status": "failed"}
    return {"transcript_status": "completed"}
