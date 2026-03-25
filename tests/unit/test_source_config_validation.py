# tests/unit/test_source_config_validation.py
#
# Behavior B027: Source configuration is validated — duplicate IDs rejected.
#
# Tests the public interface load_sources(config_path) in src/ingestion/config.py.
# When two source entries share the same ID, load_sources() must raise a
# ValueError so that misconfigured configs are caught before ingestion runs.
import textwrap

import pytest

from src.ingestion.config import load_sources


def test_load_sources_raises_when_config_contains_duplicate_source_ids(tmp_path):
    """
    Given a sources.yaml that contains two entries with the same id,
    when load_sources() is called, it raises a ValueError — preventing
    ambiguous pipeline runs where the same source ID would write to the
    same S3 paths and produce non-deterministic results.
    """
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-duplicate-id
            name: First Source
            type: rss
            url: https://first.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-duplicate-id
            name: Second Source With Same ID
            type: web
            url: https://second.example.com/articles
            category: research
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)

    with pytest.raises(ValueError, match="duplicate"):
        load_sources(str(config_file))
