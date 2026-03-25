Test fails as expected — sources are currently processed in YAML declaration order (3, 1, 2) rather than priority order.

```
FILE: tests/unit/test_priority_ordered_ingestion.py
```

The test correctly fails because the handler currently ingests sources in YAML declaration order (`low-priority` first, `high-priority` second) instead of ascending priority order (`high-priority` → `medium-priority` → `low-priority`).
