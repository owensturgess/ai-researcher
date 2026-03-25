# Contract: Briefing Email Format

**Date**: 2026-03-24

## Overview

The daily briefing email is the primary user-facing output of the pipeline. It must be scannable in under 15 minutes, render correctly on mobile email clients, and provide clear information hierarchy.

## Email Structure

```
Subject: "Agentic SDLC Intelligence — {date} ({item_count} items)"

Body:
┌──────────────────────────────────────────────┐
│  Agentic SDLC Intelligence Briefing          │
│  {date} • {item_count} items                 │
├──────────────────────────────────────────────┤
│                                              │
│  🔴 ACTION NEEDED (if any)                   │
│  ─────────────────────────────               │
│  [{item.title}]({item.url})                  │
│  {item.source_name}                          │
│  {item.summary}                              │
│  Why it matters: {item.relevance_tag}        │
│                                              │
│  🟡 WORTH DISCUSSING (if any)                │
│  ─────────────────────────────               │
│  [{item.title}]({item.url})                  │
│  {item.source_name}                          │
│  {item.summary}                              │
│  Why it matters: {item.relevance_tag}        │
│                                              │
│  🔵 INFORMATIONAL                            │
│  ─────────────────────────────               │
│  [{item.title}]({item.url})                  │
│  {item.source_name}                          │
│  {item.summary}                              │
│  Why it matters: {item.relevance_tag}        │
│                                              │
├──────────────────────────────────────────────┤
│  Pipeline: {sources_scanned} sources |       │
│  {items_ingested} items scanned |            │
│  Est. cost: ${estimated_cost}                │
└──────────────────────────────────────────────┘
```

## Ordering Rules

1. Items are grouped by urgency: Action Needed → Worth Discussing → Informational
2. Within each urgency group, items are ordered by relevance score (descending)
3. Maximum 10 items total; minimum 0 (triggers "no significant developments" variant)

## "No Significant Developments" Variant

```
Subject: "Agentic SDLC Intelligence — {date} (No significant developments)"

Body:
┌──────────────────────────────────────────────┐
│  Agentic SDLC Intelligence Briefing          │
│  {date}                                      │
├──────────────────────────────────────────────┤
│                                              │
│  No significant developments in the last     │
│  24 hours met the relevance threshold.       │
│                                              │
│  The pipeline scanned {sources_scanned}      │
│  sources and evaluated {items_ingested}      │
│  items. All scored below the threshold       │
│  of {threshold}.                             │
│                                              │
│  This confirms the system is operational.    │
│                                              │
├──────────────────────────────────────────────┤
│  Pipeline: {sources_scanned} sources |       │
│  {items_ingested} items scanned |            │
│  Est. cost: ${estimated_cost}                │
└──────────────────────────────────────────────┘
```

## Fallback Notification Variant

```
Subject: "⚠️ Agentic SDLC Intelligence — {date} (Delivery Delayed)"

Body:
The daily briefing pipeline encountered an error and could not
generate today's briefing on schedule.

Error: {error_summary}
Pipeline stage: {failed_stage}
Time: {failure_time}

The team has been notified. A delayed briefing may follow if
the issue is resolved today.
```

## Rendering Requirements

- HTML email with inline CSS (no external stylesheets)
- Table-based layout for Outlook compatibility
- Maximum width: 600px (standard email width)
- Font: system default sans-serif stack
- No images required — text and color indicators only
- Urgency indicators use colored text/borders (not emoji in production — emoji shown above for illustration)
- All links must be absolute URLs
- Tested against: iOS Mail, Gmail (web + mobile), Outlook (desktop + web)
