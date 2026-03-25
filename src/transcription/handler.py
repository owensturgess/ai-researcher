# src/transcription/handler.py
import json
import os

import boto3
import yt_dlp


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")

    for record in event["Records"]:
        body = json.loads(record["body"])
        item_id = body["item_id"]
        source_id = body["source_id"]
        original_url = body["original_url"]
        run_date = body["run_date"]

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
