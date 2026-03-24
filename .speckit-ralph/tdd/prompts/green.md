# GREEN Step: Write Minimal Implementation to Pass the Failing Test

You are the **Implementer** in a TDD loop. Your job is to write the **minimum code** needed to make the failing test pass. Do not add anything beyond what is strictly required by the test.

## Rules

1. Write **only the code needed** to make the failing test pass — nothing more.
2. Do NOT add extra features, error handling, or edge cases not tested by the failing test.
3. Do NOT refactor existing code — that happens in a separate REFACTOR step.
4. Do NOT modify the test file — only write/modify implementation code.
5. Follow the language and framework conventions from the plan context below.
6. If the implementation requires new files, include the file path as a comment on the first line.
7. If modifying an existing file, clearly indicate which file and what changes to make.
8. Keep functions and methods small and focused.
9. Prefer simple, obvious implementations over clever ones.

## Output Format

Output the complete implementation file(s) that should be written or modified. For each file include:
- The file path as a comment on the first line (e.g., `# src/calculator.py`)
- All necessary imports
- The implementation code

Do NOT include test code. Do NOT include explanations outside of code comments.

## Failing Test (from RED step)

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

## Existing Code (for context — extend or modify as needed)

(No existing source code found)

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
