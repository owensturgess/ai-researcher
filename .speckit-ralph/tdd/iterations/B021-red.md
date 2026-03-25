```
FILE: tests/unit/test_scoring_urgency_classification.py
```

The test puts a single `ContentItem` in S3, mocks Bedrock to return `score=90` with `urgency="action_needed"` (well above the threshold of 60), calls the scoring handler, then asserts:

1. The `urgency` field is present in the written `ScoredItem`
2. It is one of the three valid classifications (`informational`, `worth_discussing`, `action_needed`)
3. It matches the LLM's returned value (`action_needed`)

This will fail RED because the scoring handler does not yet validate and persist the urgency classification field.
