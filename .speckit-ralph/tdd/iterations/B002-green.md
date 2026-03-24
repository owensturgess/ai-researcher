Please grant permission to write new files. Once approved, I'll create:

1. `tests/__init__.py` — empty
2. `tests/briefing/__init__.py` — empty
3. `tests/briefing/test_template.py` — the failing test
4. `src/briefing/templates/briefing.html` — minimal Jinja2 template that maps `urgency` snake_case to human-readable labels and renders all 6 required fields

The key non-trivial part of the template will be a mapping like:
```html
{% set urgency_labels = {"action_needed": "Action Needed", "monitor": "Monitor", "fyi": "FYI"} %}
```
