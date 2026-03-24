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

The write requires your permission. Here's the complete test file to create at `tests/unit/test_briefing_mobile.py`:

```python
# tests/unit/test_briefing_mobile.py
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader


def test_briefing_email_constrains_width_to_prevent_horizontal_scrolling():
    """The briefing email template renders with a max-width of 600px so mobile clients
    display it without horizontal scrolling."""
    template_dir = os.path.join(
        os.path.dirname(__file__), "../../src/briefing/templates"
    )
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("briefing.html")

    items = [
        {
            "title": "LLMs in Production: Lessons from Scale",
            "source_name": "The Pragmatic Engineer",
            "summary": (
                "This article explores operational challenges of running LLMs at "
                "scale in production environments. It covers cost management, latency "
                "budgets, and graceful degradation patterns."
            ),
            "relevance_tag": "AI Engineering",
            "urgency": "worth_discussing",
            "original_url": "https://example.com/llms-production",
        }
    ]

    html = template.render(
        items=items,
        briefing_date="2026-03-24",
        pipeline_stats={"sources_scanned": 15, "items_ingested": 42},
    )

    # The outer container must declare max-width: 600px (with or without spaces)
    # so email clients do not render a layout wider than a mobile viewport.
    assert re.search(r"max-width\s*:\s*600px", html), (
        "Expected 'max-width: 600px' in rendered HTML to prevent horizontal "
        "scrolling on mobile devices"
    )

    # No element may declare a fixed pixel width wider than 600px, which would
    # force horizontal scrolling regardless of the container constraint.
    fixed_widths = re.findall(r"width\s*:\s*(\d+)px", html)
    oversized = [int(w) for w in fixed_widths if int(w) > 600]
    assert not oversized, (
        f"Found fixed pixel widths exceeding 600px: {oversized}. "
        "These will cause horizontal scrolling on mobile."
    )
```

**Why this test fails (RED)**: `src/briefing/templates/briefing.html` does not exist yet, so `env.get_template("briefing.html")` raises `TemplateNotFound`.

**What it tests (observable behavior)**:
- Renders the real Jinja2 template through its documented public contract (input: items list, briefing_date, pipeline_stats)
- Asserts `max-width: 600px` is present — the standard email-safe constraint that prevents horizontal scrolling on mobile viewports
- Asserts no inline `width: Npx` values exceed 600px — catches table columns or images that would overflow regardless of container constraints

**No mocks needed** — the template is a local file (no system boundary to mock), and Jinja2 rendering is pure in-process.

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
