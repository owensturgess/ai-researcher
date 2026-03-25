14/14 passing. 

```
FILE: src/briefing/handler.py
```

The briefing handler lists all scored items from `scored/{run_date}/` in S3, filters to those with `relevance_score >= threshold` (default 60), and returns `{"items_included": count}`.
