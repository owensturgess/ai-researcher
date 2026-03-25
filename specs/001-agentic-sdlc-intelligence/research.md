# Research: Agentic SDLC Daily Intelligence Briefing Agent

**Branch**: `001-agentic-sdlc-intelligence` | **Date**: 2026-03-24

## R1: Language & Runtime Choice

**Decision**: Python 3.12 on AWS Lambda

**Rationale**: Python has the strongest ecosystem for the core tasks in this pipeline: RSS parsing (feedparser), web scraping (beautifulsoup4, requests), YouTube interaction (yt-dlp, google-api-python-client), X API (tweepy), and AWS SDK (boto3). Lambda's Python runtime is mature with excellent cold-start performance for I/O-bound workloads. The team is building this as an internal tool where Python's rapid development speed outweighs raw performance needs.

**Alternatives considered**:
- **Node.js/TypeScript**: Strong AWS Lambda support but weaker ecosystem for RSS parsing and audio processing. Would require more third-party dependencies for equivalent functionality.
- **Go**: Faster cold starts but significantly more boilerplate for HTTP scraping, RSS parsing, and template rendering. Over-optimized for this use case.

## R2: Infrastructure as Code

**Decision**: AWS CDK (Python)

**Rationale**: CDK in Python keeps the infrastructure code in the same language as the application code, reducing context-switching. CDK provides higher-level constructs for Lambda, S3, SQS, and EventBridge that reduce boilerplate compared to raw CloudFormation. The team can define, test, and deploy infrastructure alongside application code.

**Alternatives considered**:
- **Terraform**: More widely adopted, cloud-agnostic. But this project is AWS-only and the Python CDK aligns better with the Python application code.
- **SAM (Serverless Application Model)**: Simpler for pure Lambda deployments, but less flexible for the multi-service orchestration this pipeline requires (SQS, Transcribe callbacks, SES, CloudWatch alarms).

## R3: YouTube Transcript Retrieval Strategy

**Decision**: YouTube Data API v3 for metadata + youtube-transcript-api (or yt-dlp) for captions, falling back to AWS Transcribe for audio extraction and transcription.

**Rationale**: Most YouTube videos have auto-generated or manual captions available. Retrieving these is free (no transcription cost) and fast (<1 second vs. minutes for Transcribe). The fallback to AWS Transcribe handles the ~10-15% of videos without captions. yt-dlp can extract audio for Transcribe input and also retrieve available subtitles.

**Alternatives considered**:
- **Always use AWS Transcribe**: Simpler code path but unnecessarily expensive ($0.024/min). A 30-minute video costs $0.72 to transcribe vs. ~$0 for caption retrieval.
- **YouTube transcript API only (no fallback)**: Cheaper but loses coverage on videos without captions, which may include critical conference talks or live recordings.

## R4: X (Twitter) API Access Strategy

**Decision**: X API Free/Basic tier for initial deployment, with web scraping via Nitter-like proxies or RSS bridges as a fallback if API access is insufficient.

**Rationale**: The X API Free tier allows 1,500 tweets/month read access — potentially insufficient for monitoring 10-20 accounts daily. The Basic tier ($100/month) provides 10,000 tweets/month which should suffice. However, X API pricing and access terms have been volatile. Building a scraping fallback ensures the pipeline isn't blocked by API access issues. RSS bridge services (e.g., RSSHub) can convert X accounts to RSS feeds, which the pipeline already handles.

**Alternatives considered**:
- **X API Pro tier**: $5,000/month — vastly overpriced for this use case.
- **Web scraping only (no API)**: Fragile, against ToS, and harder to maintain. Acceptable as a fallback but not primary.
- **Skip X entirely for MVP**: Viable but would miss significant signal — many agentic SDLC developments are first announced or discussed on X.

## R5: Content Deduplication Approach

**Decision**: Two-pass deduplication: (1) exact URL deduplication, then (2) LLM-based semantic similarity check during the scoring phase.

**Rationale**: URL deduplication catches the obvious case (same article shared across aggregators). Semantic deduplication catches the harder case (three different blog posts all covering the same announcement). Since the pipeline already sends content to the LLM for scoring, adding a deduplication instruction to the scoring prompt is cost-efficient — it doesn't require a separate LLM call. The scoring prompt can include: "If this content covers the same core development as another item, flag it as a duplicate with a reference to the primary item."

**Alternatives considered**:
- **Embedding-based similarity (cosine distance)**: More deterministic but requires an embedding model, vector store, and similarity threshold tuning. Over-engineered for 50-200 items/day.
- **Title/keyword matching**: Too brittle — misses paraphrased duplicates and creates false positives for articles with similar titles but different content.

## R6: Email Delivery & Formatting

**Decision**: Amazon SES with DKIM/SPF, using Jinja2 HTML templates with inline CSS for mobile compatibility.

**Rationale**: SES is the natural choice within the AWS ecosystem — no additional vendor relationship, simple integration via boto3, and cost-effective ($0.10 per 1,000 emails). Email HTML must use inline CSS and table-based layout for reliable rendering across email clients (Outlook, Gmail, iOS Mail). Jinja2 provides clean template separation from Python code.

**Alternatives considered**:
- **SendGrid/Mailgun**: More features (analytics, A/B testing) but adds an external dependency and vendor relationship for what is essentially a single daily email to 3-4 people.
- **Plain text email**: Simpler but loses formatting hierarchy that makes the briefing scannable. A well-structured HTML email with clear headings and urgency indicators is worth the template complexity.

## R7: Pipeline Orchestration Pattern

**Decision**: EventBridge cron → Ingestion Lambda → S3 (raw content) + SQS (transcription jobs) → Transcription Lambda (triggered by SQS) → Scoring Lambda (triggered after ingestion + transcription complete) → Briefing Lambda → SES delivery.

**Rationale**: Event-driven with SQS decoupling keeps each Lambda single-purpose and independently scalable. The transcription queue allows parallel processing of multiple audio/video items. A Step Functions orchestration was considered but adds complexity for a linear pipeline with one branching point (transcription).

**Orchestration detail**: The Ingestion Lambda writes all text content to S3 and enqueues audio/video items to SQS. It also writes a manifest file to S3 listing all items (with a "pending transcription" count). The Transcription Lambda processes SQS messages, writes transcripts to S3, and decrements the pending count. When pending reaches zero (or a timeout), the Scoring Lambda is triggered via S3 event notification on the manifest file update.

**Alternatives considered**:
- **AWS Step Functions**: More explicit workflow orchestration, better for complex branching. But adds cost ($0.025 per 1,000 state transitions) and complexity for a pipeline that is essentially sequential with one parallel branch.
- **Single monolithic Lambda**: Simpler deployment but risks Lambda timeout (15 min max) with large transcription workloads. Violates single-responsibility and makes debugging harder.

## R8: Data Retention Implementation

**Decision**: S3 lifecycle policies with 30-day expiration on all pipeline output prefixes.

**Rationale**: S3 lifecycle policies are native, zero-code, and reliable. By organizing content into date-prefixed keys (e.g., `raw/2026-03-24/`, `transcripts/2026-03-24/`, `briefings/2026-03-24/`), a single lifecycle rule can expire all objects older than 30 days. No custom cleanup Lambda needed.

**Alternatives considered**:
- **DynamoDB with TTL**: Better for structured queries but adds a database dependency for what is essentially a write-heavy, read-rarely pattern. S3 is simpler and cheaper for blob storage.
- **Custom cleanup Lambda on a schedule**: Works but unnecessary when S3 lifecycle policies handle this natively.

## R9: Scoring Prompt Architecture

**Decision**: Structured scoring prompt with chain-of-thought reasoning, few-shot examples, and JSON output format. Context prompt stored as a separate editable text file.

**Rationale**: The scoring prompt is the core intelligence of the system. It must produce consistent, well-calibrated scores (±10 point tolerance). Chain-of-thought reduces score variance by forcing the LLM to reason before scoring. Few-shot examples (5-10 pre-scored items) anchor the score distribution. Structured JSON output (`{"score": 75, "urgency": "Worth Discussing", "relevance_tag": "...", "summary": "..."}`) enables reliable parsing. Separating the context prompt into `config/context-prompt.txt` allows the CTO to tune scoring criteria without code changes.

**Alternatives considered**:
- **Simple numeric prompt ("Rate 0-100")**: Fast but high variance — scores drift without anchoring examples.
- **Classification only (relevant/not relevant)**: Loses the granularity needed for ranking and threshold tuning.
- **Multiple LLM calls per item (score + summarize separately)**: More expensive, slower, and the combined prompt produces equally good results since the model already "understands" the content during scoring.

## R10: Cost Estimation

**Decision**: Target daily cost of $5-15/day (~$150-450/month), well within the $500/month budget assumption.

**Cost breakdown (estimated per daily run)**:
- **LLM scoring + summarization (Bedrock/Claude)**: ~100 items × ~2,000 input tokens × $0.003/1K tokens = ~$0.60 input + ~100 items × ~500 output tokens × $0.015/1K tokens = ~$0.75 output = **~$1.35/day**
- **AWS Transcribe**: ~5 audio items/day × 30 min avg × $0.024/min = **~$3.60/day**
- **Lambda compute**: Minimal — well within free tier for this volume
- **S3 storage**: Minimal — ~100MB/day × 30 days = ~3GB, negligible cost
- **SES**: $0.10/1,000 emails — effectively free at 3-4 emails/day
- **X API (Basic tier)**: $100/month = **~$3.33/day**
- **YouTube Data API**: Free tier (10,000 quota units/day) should suffice

**Total estimated**: ~$8-10/day typical, with spikes to $15 on heavy transcription days.
