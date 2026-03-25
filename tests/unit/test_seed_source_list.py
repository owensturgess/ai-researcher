# tests/unit/test_seed_source_list.py
#
# Behavior B025: The seed source list contains at least 20 sources spanning
# all supported format types (rss, web, x, youtube, podcast, substack).
#
# Tests the actual config/sources.yaml at the repository root — no mocking,
# because the observable behavior IS the contents of the seed file itself.
import os
import pathlib

import pytest

from src.ingestion.config import load_sources

# Canonical path for the seed source list, relative to the repository root
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SEED_CONFIG = _REPO_ROOT / "config" / "sources.yaml"

REQUIRED_TYPES = {"rss", "web", "x", "youtube", "podcast", "substack"}
MIN_SOURCE_COUNT = 20


def test_seed_source_list_has_at_least_20_sources_spanning_all_format_types():
    """
    Given the seed sources.yaml at config/sources.yaml, when load_sources() is
    called on it, the result contains at least 20 active sources and all
    supported format types (rss, web, x, youtube, podcast, substack) are
    represented by at least one source each.
    """
    assert _SEED_CONFIG.exists(), (
        f"Seed source config not found at {_SEED_CONFIG}. "
        "Create config/sources.yaml with at least 20 sources covering all format types."
    )

    sources = load_sources(str(_SEED_CONFIG))

    assert len(sources) >= MIN_SOURCE_COUNT, (
        f"Seed source list has only {len(sources)} active sources; "
        f"need at least {MIN_SOURCE_COUNT}."
    )

    present_types = {s.type for s in sources}
    missing_types = REQUIRED_TYPES - present_types
    assert not missing_types, (
        f"Seed source list is missing format types: {missing_types}. "
        f"Present types: {present_types}. "
        "Add at least one source of each type to config/sources.yaml."
    )
