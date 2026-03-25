# src/shared/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Source:
    id: str
    name: str
    type: str  # rss / web / x / youtube / podcast
    url: str
    category: str
    active: bool = True
    priority: int = 1


@dataclass
class ContentItem:
    id: str
    title: str
    source_id: str
    source_name: str
    published_date: datetime
    full_text: str
    original_url: str
    content_format: str = "text"  # text / audio / video
    transcript_status: str = "not_needed"  # pending / completed / failed / not_needed


@dataclass
class ScoredItem:
    content_item_id: str
    relevance_score: int
    urgency: str
    relevance_tag: str
    executive_summary: str
    scoring_reasoning: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    also_reported_by: list = field(default_factory=list)
