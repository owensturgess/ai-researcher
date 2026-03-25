Test fails as expected (RED). The handler publishes no metrics at all into the `AgenticSDLCIntel` namespace currently — it doesn't aggregate 7-day rolling delivery reliability or average cost per run.

```
FILE: tests/unit/test_delivery_reliability_metrics.py
```
