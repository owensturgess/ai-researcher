Test passes.

```
FILE: src/shared/models.py
FILE: src/scoring/deduplication.py
```

**Changes made:**
- `ScoredItem`: added `also_reported_by: list = field(default_factory=list)`
- `deduplicate_by_semantics`: appends each duplicate's `content_item_id` to the primary's `also_reported_by` list when flagging it
