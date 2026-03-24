# Quickstart: Agentic SDLC Daily Intelligence Briefing Agent

**Branch**: `001-agentic-sdlc-intelligence` | **Date**: 2026-03-24

## Prerequisites

- Python 3.12+
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- An AWS account with access to: Lambda, S3, SQS, Transcribe, Bedrock (Claude), SES, EventBridge, CloudWatch
- SES verified sender email address (or sandbox mode for testing)
- X API Basic tier developer account (optional — can be disabled in config)
- YouTube Data API v3 key

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/owensturgess/ai-researcher.git
cd ai-researcher
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure sources

Edit `config/sources.yaml` to define the sources to monitor:

```yaml
sources:
  - id: simon-willison-blog
    name: "Simon Willison's Weblog"
    type: rss
    url: "https://simonwillison.net/atom/everything/"
    category: agentic-tools
    active: true
    priority: 8

  - id: latent-space-podcast
    name: "Latent Space Podcast"
    type: podcast
    url: "https://api.substack.com/feed/podcast/1084089.rss"
    category: agentic-sdlc
    active: true
    priority: 7
```

### 3. Configure settings

Edit `config/settings.yaml`:

```yaml
schedule:
  cron: "0 5 * * ? *"  # 5 AM UTC daily (adjust for timezone)
  timezone: "America/New_York"

scoring:
  relevance_threshold: 60
  max_briefing_items: 10

budget:
  daily_cost_alert_threshold_usd: 20.00
  monthly_budget_usd: 500.00

recipients:
  - name: "Owen Sturgess"
    email: "owen@example.com"
    timezone: "America/New_York"

retention:
  days: 30
```

### 4. Customize the relevance scoring context

Edit `config/context-prompt.txt` to encode your company's transformation goals, target topic areas, and audience roles. This is the prompt that guides the LLM's relevance scoring.

### 5. Deploy infrastructure

```bash
cd infra
pip install -r requirements.txt
cdk bootstrap  # first time only
cdk deploy --all
```

### 6. Run a test invocation

```bash
# Trigger the pipeline manually (outside of schedule)
aws lambda invoke \
  --function-name agentic-sdlc-intel-ingestion \
  --payload '{}' \
  /dev/stdout
```

### 7. Verify delivery

Check the configured recipient email inbox for the test briefing. Review CloudWatch logs for pipeline metrics.

## Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires AWS credentials)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=src --cov-report=term-missing
```

## Key Configuration Files

| File                       | Purpose                                    | Editable without code change |
|----------------------------|--------------------------------------------|-----------------------------|
| `config/sources.yaml`     | Source list (add/remove monitored channels) | Yes                         |
| `config/context-prompt.txt` | Relevance scoring context for the LLM    | Yes                         |
| `config/settings.yaml`    | Thresholds, recipients, budget, schedule   | Yes                         |

## Operational Notes

- **Logs**: CloudWatch Log Groups, one per Lambda function
- **Metrics**: CloudWatch custom metrics under `AgenticSDLCIntel` namespace
- **Cost alerts**: CloudWatch Alarm triggers when daily cost exceeds threshold
- **Data retention**: S3 lifecycle policy auto-deletes content older than 30 days
