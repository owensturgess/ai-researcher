The tool is awaiting your permission to write the file. Here's the complete test I've designed for B006:

---

**File**: `tests/unit/test_pipeline_run_metadata.py`

```python
# tests/unit/test_pipeline_run_metadata.py
import json
import os
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    (d / "sources.yaml").write_text(
        "sources:\n"
        "  - id: rss-techcrunch\n"
        "    name: TechCrunch\n"
        "    type: rss\n"
        "    url: https://techcrunch.com/feed/\n"
        "    category: tech\n"
        "    active: true\n"
        "    priority: 1\n"
    )
    (d / "settings.yaml").write_text(
        "schedule: '0 7 * * *'\n"
        "relevance_threshold: 70\n"
        "max_briefing_items: 10\n"
        "budget_caps:\n"
        "  transcribe_minutes: 60\n"
        "  bedrock_tokens: 100000\n"
        "recipients:\n"
        "  - name: Alice\n"
        "    email: alice@example.com\n"
        "    timezone: UTC\n"
        "retention_days: 30\n"
    )
    (d / "context-prompt.txt").write_text("Evaluate relevance.\n")
    return str(d)


def test_ingestion_handler_writes_pipeline_run_record_with_required_metadata(config_dir):
    """After the ingestion handler completes, a PipelineRun record is persisted to S3
    containing sources_attempted, sources_succeeded, items_ingested,
    transcription_jobs, and delivery_status."""
    bucket = "test-pipeline-bucket"
    run_date = "2026-03-24"

    # Track all objects written to S3 at the boundary
    s3_objects = {}

    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = lambda Bucket, Key, Body, **kw: s3_objects.update({Key: Body})
    mock_s3.get_object.side_effect = KeyError  # no pre-existing objects
    mock_s3.list_objects_v2.return_value = {"Contents": [], "KeyCount": 0}

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-001"}

    # Mock feedparser at the network boundary so no real HTTP is made
    empty_feed = MagicMock()
    empty_feed.entries = []

    def boto3_client_factory(service_name, **kwargs):
        if service_name == "s3":
            return mock_s3
        if service_name == "sqs":
            return mock_sqs
        return MagicMock()

    with patch("boto3.client", side_effect=boto3_client_factory), \
         patch("feedparser.parse", return_value=empty_feed), \
         patch.dict(os.environ, {
             "S3_BUCKET": bucket,
             "CONFIG_DIR": config_dir,
             "RUN_DATE": run_date,
             "AWS_DEFAULT_REGION": "us-east-1",
         }):
        from src.ingestion.handler import handler
        handler({}, None)

    # A PipelineRun record must have been written to S3
    pipeline_run_keys = [k for k in s3_objects if "pipeline_run" in k]
    assert len(pipeline_run_keys) == 1, (
        f"Expected exactly one PipelineRun record written to S3; found keys: {list(s3_objects.keys())}"
    )

    run_record = json.loads(s3_objects[pipeline_run_keys[0]])
    required_fields = {
        "sources_attempted",
        "sources_succeeded",
        "items_ingested",
        "transcription_jobs",
        "delivery_status",
    }
    missing = required_fields - run_record.keys()
    assert not missing, (
        f"PipelineRun record missing required metadata fields: {missing}"
    )
```

---

**Design decisions:**

- **Boundary mocks only**: `boto3.client` is intercepted for S3 (captures `put_object` calls into `s3_objects`) and SQS. `feedparser.parse` is patched at the HTTP library layer (network boundary). Config files use real `tmp_path` files (filesystem boundary).
- **One logical assertion**: both `assert` statements verify the same outcome — a PipelineRun record is in S3 with all required metadata fields.
- **Will fail immediately**: `src/ingestion/handler.py` doesn't exist → `ModuleNotFoundError`.

Please grant write permission so I can save this to `.speckit-ralph/tdd/iterations/B006-red.md` and `tests/unit/test_pipeline_run_metadata.py`.
