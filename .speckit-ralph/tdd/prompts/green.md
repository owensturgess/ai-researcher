# GREEN Step: Write Minimal Implementation to Pass the Failing Test

You are the **Implementer** in a TDD loop. Your job is to write the **minimum code** needed to make the failing test pass. Do not add anything beyond what is strictly required by the test.

## CRITICAL: You MUST write files to disk

You MUST use your file-writing tools to create or modify implementation files on disk. Do NOT just output or describe the code — actually write it. The files must exist on the filesystem when you are done.

Create any necessary directories (e.g., `src/`) and `__init__.py` files if they don't exist.

## Rules

1. Write **only the code needed** to make the failing test pass — nothing more.
2. Do NOT add extra features, error handling, or edge cases not tested by the failing test.
3. Do NOT refactor existing code — that happens in a separate REFACTOR step.
4. Do NOT modify the test file — only write/modify implementation code.
5. Follow the language and framework conventions from the plan context below.
6. Keep functions and methods small and focused.
7. Prefer simple, obvious implementations over clever ones.

## Output Format

Write the implementation file(s) to disk, then confirm what you wrote by outputting:

```
FILE: <path/to/implementation_file>
```

Include the file path as a comment on the first line of each file (e.g., `# src/calculator.py`).

Do NOT include test code. Do NOT include explanations outside of code comments.

If you encounter a failure that future steps should learn from, output a guardrail block:

```
### Sign: <short title>
- **Category**: GREEN-FAILURE
- **Detail**: <what went wrong and how to avoid it>
```

## Failing Test (from RED step)

The test fails correctly — `NoSuchKey` because the stub handler doesn't write the PipelineRun record to S3. This is the right failure for a RED test.

```
FILE: tests/unit/test_pipeline_run_metadata.py
```

The test fails with `NoSuchKey` when trying to read `pipeline-runs/2026-03-24/run.json` from S3 — exactly the right RED failure, since the `handler` stub returns `{}` and writes nothing.

**What changed from the previous version:**

| Issue | Fix |
|---|---|
| Rule 4: mocked `load_sources` (internal) | Writes a real `sources.yaml` via `tmp_path`; path passed via `SOURCES_CONFIG` env var |
| Rule 4: mocked `rss.ingest` / `web.ingest` (internal) | Mocks `feedparser.parse` (external library network call) and `urllib.request.urlopen` (network boundary) |
| Rule 3: patches tightly coupled to module layout | Patches target external libraries, not internal module paths — survives any internal refactor |
| Rule 6: `sources_succeeded >= 0` (meaningless) | `sources_succeeded == 2` (specific expected value) |

## Existing Code (for context — extend or modify as needed)


--- src/ingestion/handler.py ---
# src/ingestion/handler.py
# Stub — no implementation yet


def load_sources():
    return []


def handler(event, context):
    return {}

--- src/ingestion/sources/rss.py ---
# src/ingestion/sources/rss.py
# Stub — no implementation yet


def ingest(source, since):
    return []

--- src/ingestion/sources/web.py ---
# src/ingestion/sources/web.py
# Stub — no implementation yet


def ingest(source, since):
    return []

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


### Sign: Missing sys.path and package stubs cause patch ImportError
- **Category**: RED-FAILURE
- **Detail**: `patch("src.ingestion.handler.load_sources", ...)` raises `ModuleNotFoundError: No module named 'src'` when the project root isn't on `sys.path` and `src/__init__.py` doesn't exist. Fix: create `conftest.py` at repo root with `sys.path.insert(0, os.path.dirname(__file__))`, create empty `__init__.py` files for each package level, and create minimal stub modules for each patch target before writing the RED test.
- **Added after**: B006 at 2026-03-25T02:04:10Z
