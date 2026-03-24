It looks like write permissions haven't been granted for `src/`. Could you approve the file write permission for the `src/` directory? Once granted, I'll create:

- `src/briefing/__init__.py`
- `src/briefing/handler.py` — the minimal `handler()` that reads `config_dir` from the event, loads `settings.yaml`, and sends one fallback SES email per recipient
- `src/shared/__init__.py`
