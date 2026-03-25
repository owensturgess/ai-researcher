```
FILE: src/scoring/handler.py
```

Added `"temperature": 0` to the Bedrock request body in `_score_item` (line 17). The mock returns a stable score of 75 on both days when `temperature=0` is present, so the ±10 assertion will pass.
