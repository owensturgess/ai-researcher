The write requires your permission. Here's the complete test file to create at `tests/unit/test_briefing_mobile.py`:

```python
# tests/unit/test_briefing_mobile.py
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader


def test_briefing_email_constrains_width_to_prevent_horizontal_scrolling():
    """The briefing email template renders with a max-width of 600px so mobile clients
    display it without horizontal scrolling."""
    template_dir = os.path.join(
        os.path.dirname(__file__), "../../src/briefing/templates"
    )
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("briefing.html")

    items = [
        {
            "title": "LLMs in Production: Lessons from Scale",
            "source_name": "The Pragmatic Engineer",
            "summary": (
                "This article explores operational challenges of running LLMs at "
                "scale in production environments. It covers cost management, latency "
                "budgets, and graceful degradation patterns."
            ),
            "relevance_tag": "AI Engineering",
            "urgency": "worth_discussing",
            "original_url": "https://example.com/llms-production",
        }
    ]

    html = template.render(
        items=items,
        briefing_date="2026-03-24",
        pipeline_stats={"sources_scanned": 15, "items_ingested": 42},
    )

    # The outer container must declare max-width: 600px (with or without spaces)
    # so email clients do not render a layout wider than a mobile viewport.
    assert re.search(r"max-width\s*:\s*600px", html), (
        "Expected 'max-width: 600px' in rendered HTML to prevent horizontal "
        "scrolling on mobile devices"
    )

    # No element may declare a fixed pixel width wider than 600px, which would
    # force horizontal scrolling regardless of the container constraint.
    fixed_widths = re.findall(r"width\s*:\s*(\d+)px", html)
    oversized = [int(w) for w in fixed_widths if int(w) > 600]
    assert not oversized, (
        f"Found fixed pixel widths exceeding 600px: {oversized}. "
        "These will cause horizontal scrolling on mobile."
    )
```

**Why this test fails (RED)**: `src/briefing/templates/briefing.html` does not exist yet, so `env.get_template("briefing.html")` raises `TemplateNotFound`.

**What it tests (observable behavior)**:
- Renders the real Jinja2 template through its documented public contract (input: items list, briefing_date, pipeline_stats)
- Asserts `max-width: 600px` is present — the standard email-safe constraint that prevents horizontal scrolling on mobile viewports
- Asserts no inline `width: Npx` values exceed 600px — catches table columns or images that would overflow regardless of container constraints

**No mocks needed** — the template is a local file (no system boundary to mock), and Jinja2 rendering is pure in-process.
