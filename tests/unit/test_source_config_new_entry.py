# tests/unit/test_source_config_new_entry.py
import textwrap

import pytest

from src.ingestion.config import load_sources


def test_new_source_entry_in_config_file_is_included_in_loaded_sources(tmp_path):
    """
    Given a sources.yaml with an existing source and a newly added source entry
    (name, type, URL, and optional category), when load_sources() is called,
    the new source is present in the returned list — confirming it would be
    included in the next daily pipeline run.
    """
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-existing-001
            name: Existing AI News
            type: rss
            url: https://existing.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-new-002
            name: New Source Added by User
            type: web
            url: https://new-source.example.com/articles
            category: research
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)

    sources = load_sources(str(config_file))

    source_ids = [s.id for s in sources]
    assert "src-new-002" in source_ids, (
        "Newly added source 'src-new-002' was not returned by load_sources()"
    )

    new_source = next(s for s in sources if s.id == "src-new-002")
    assert new_source.name == "New Source Added by User"
    assert new_source.type == "web"
    assert new_source.url == "https://new-source.example.com/articles"
    assert new_source.category == "research"
