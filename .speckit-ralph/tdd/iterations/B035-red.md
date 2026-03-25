Test fails as expected with a clear error message.

```
FILE: tests/unit/test_cloudwatch_metrics_namespace.py
```

The test fails because the handler currently:
1. Publishes per-run metrics to `"AiResearcher/Pipeline"` instead of `"AgenticSDLCIntel"`
2. Is missing 3 required metrics: `SourcesFailed`, `DeliveryLatencyMinutes`, `BriefingItemCount`

The GREEN phase will need to move all per-run `put_metric_data` calls to the `"AgenticSDLCIntel"` namespace and add the three missing metrics.
