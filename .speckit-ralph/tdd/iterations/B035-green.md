Test passes.

```
FILE: src/monitoring/handler.py
```

Changes made:
- Changed `"AiResearcher/Pipeline"` namespace to `"AgenticSDLCIntel"` for the per-run `put_metric_data` call
- Added `SourcesFailed` (from `run["sources_failed"]`)
- Added `DeliveryLatencyMinutes` (computed from `started_at`/`completed_at` ISO timestamps)
- Added `BriefingItemCount` (from `run["items_in_briefing"]`)
- Added `datetime` import for latency calculation
