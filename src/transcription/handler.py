# src/transcription/handler.py
import json
import os
import time
import urllib.parse
import urllib.request

import boto3
import yt_dlp


def _transcribe_audio(s3, bucket, item_id, original_url, run_date):
    with urllib.request.urlopen(original_url) as response:
        audio_bytes = response.read()

    audio_key = f"audio/{run_date}/{item_id}.mp3"
    s3.put_object(Bucket=bucket, Key=audio_key, Body=audio_bytes)

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

    while True:
        resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        job = resp["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]
        if status == "COMPLETED":
            transcript_uri = job["Transcript"]["TranscriptFileUri"]
            break
        elif status == "FAILED":
            return ""
        time.sleep(5)

    parsed = urllib.parse.urlparse(transcript_uri)
    path_parts = parsed.path.lstrip("/").split("/", 1)
    transcript_bucket = path_parts[0]
    transcript_key = path_parts[1]

    obj = s3.get_object(Bucket=transcript_bucket, Key=transcript_key)
    transcript_data = json.loads(obj["Body"].read())
    transcripts = transcript_data.get("results", {}).get("transcripts", [])
    return transcripts[0]["transcript"] if transcripts else ""


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")

    for record in event["Records"]:
        body = json.loads(record["body"])
        item_id = body["item_id"]
        source_id = body["source_id"]
        original_url = body["original_url"]
        run_date = body["run_date"]
        content_format = body.get("content_format", "video")

        if content_format == "audio":
            transcript_text = _transcribe_audio(s3, bucket, item_id, original_url, run_date)
        else:
            ydl_opts = {"writesubtitles": True, "subtitleslangs": ["en"], "skip_download": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(original_url, download=False)

            transcript_text = ""
            requested = info.get("requested_subtitles") or {}
            for lang, sub in requested.items():
                data = sub.get("data", "")
                if data:
                    transcript_text = data
                    break

        s3.put_object(
            Bucket=bucket,
            Key=f"transcripts/{run_date}/{item_id}.txt",
            Body=transcript_text.encode("utf-8"),
            ContentType="text/plain",
        )

    return {"transcript_status": "completed"}
