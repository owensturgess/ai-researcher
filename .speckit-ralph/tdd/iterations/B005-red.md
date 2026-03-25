It seems write permission to `tests/unit/test_briefing.py` hasn't been granted. Here's the complete test file content to write at `tests/unit/test_briefing.py`:

```python
# tests/unit/test_briefing.py
import os
import json
import pytest
from datetime import date
from unittest.mock import MagicMock, patch, call


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
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
    (d / "sources.yaml").write_text("sources: []\n")
    (d / "context-prompt.txt").write_text("Evaluate relevance.\n")
    return str(d)


def test_sends_no_significant_developments_email_when_no_items_pass_threshold(config_dir):
    """When no scored items exceed the relevance threshold, a 'no significant developments' confirmation email is sent."""
    bucket = "test-pipeline-bucket"
    sender = "briefing@example.com"
    run_date = date.today().isoformat()

    # Boundary mock: S3 returns no scored items for today's run
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {"Contents": [], "KeyCount": 0}
    mock_s3.put_object.return_value = {}

    # Boundary mock: SES — capture outbound email content
    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "test-msg-001"}

    def boto3_client_factory(service_name, **kwargs):
        if service_name == "s3":
            return mock_s3
        if service_name == "ses":
            return mock_ses
        return MagicMock()

    with patch("boto3.client", side_effect=boto3_client_factory), \
         patch.dict(os.environ, {
             "S3_BUCKET": bucket,
             "SES_SENDER": sender,
             "CONFIG_DIR": config_dir,
             "RUN_DATE": run_date,
             "AWS_DEFAULT_REGION": "us-east-1",
         }):
        from src.briefing.handler import handler
        result = handler({}, None)

    # No items should have been included
    assert result["items_included"] == 0

    # Email must have been delivered — not silently skipped
    assert result["delivery_status"] == "delivered"

    # The email must be the "no significant developments" variant, not an empty or missing briefing
    assert mock_ses.send_email.called, "Expected SES send_email to be called when no items pass threshold"

    send_kwargs = mock_ses.send_email.call_args[1]
    body = send_kwargs.get("Message", {}).get("Body", {})
    html_body = body.get("Html", {}).get("Data", "")
    text_body = body.get("Text", {}).get("Data", "")
    combined = (html_body + text_body).lower()

    assert "no significant developments" in combined, (
        f"Expected 'no significant developments' in email body; "
        f"got preview: {combined[:300]!r}"
    )
```

**Design decisions:**

- **Mocked at boundaries only**: `boto3.client` is intercepted to return fakes for S3 (empty scored items) and SES (captures send calls). Config files are written to a real `tmp_path` filesystem — that's the boundary, not mocked.
- **Three logical assertions on one outcome** — all verify the same observable behavior: a "no significant developments" email was sent (not skipped, not empty):
  1. `items_included == 0` — confirms the threshold filter ran
  2. `delivery_status == "delivered"` — confirms no silent skip
  3. `"no significant developments" in email body` — confirms the correct variant was rendered and sent
- **Will fail immediately**: `src/briefing/handler.py` doesn't exist yet, so the import raises `ModuleNotFoundError`.
