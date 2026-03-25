All 18 tests pass. Here's what I changed:

**Eliminated duplicate config loading** — `handler.py` had its own `load_sources()` that duplicated YAML parsing and active-source filtering from `config.py`. Replaced it with a thin wrapper that delegates to `config.py`'s `load_sources()` and adds priority sorting. This removed the `yaml` import from `handler.py`.

**Unified source access pattern** — `rss.py` and `web.py` used dict access (`source["url"]`, `source["id"]`) while `x_api.py`, `youtube.py`, and `podcast.py` used attribute access (`source.url`, `source.id`). Now all ingesters consistently use attribute access on `Source` dataclass objects.

```
REFACTORED: src/ingestion/handler.py
REFACTORED: src/ingestion/sources/rss.py
REFACTORED: src/ingestion/sources/web.py
```
