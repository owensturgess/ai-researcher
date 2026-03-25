Test passes.

```
FILE: src/monitoring/handler.py
```

Added `_load_rolling_runs()` to fetch the past 7 days of run records from S3, then compute `DeliveryReliabilityPct` and `AverageCostPerRun` and publish them to the `AgenticSDLCIntel` CloudWatch namespace.
