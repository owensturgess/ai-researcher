Test passes.

```
FILE: src/monitoring/handler.py
```

Added `alert_sent = False` before the threshold check, set it to `True` after sending the SES email, and included it in the return dict.
