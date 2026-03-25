# Guardrails (Signs)

> Lessons learned from failures. Read before acting.

## Core Signs

### Sign: Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Read the file first
- **Added after**: Core principle

### Sign: Test Before Commit
- **Trigger**: Before committing changes
- **Instruction**: Run required tests and verify outputs
- **Added after**: Core principle

---

## Learned Signs

<!-- Add project-specific signs below -->

### Sign: Missing sys.path and package stubs cause patch ImportError
- **Category**: RED-FAILURE
- **Detail**: `patch("src.ingestion.handler.load_sources", ...)` raises `ModuleNotFoundError: No module named 'src'` when the project root isn't on `sys.path` and `src/__init__.py` doesn't exist. Fix: create `conftest.py` at repo root with `sys.path.insert(0, os.path.dirname(__file__))`, create empty `__init__.py` files for each package level, and create minimal stub modules for each patch target before writing the RED test.
- **Added after**: B006 at 2026-03-25T02:04:10Z

### Sign: pip shim broken for older Python, use python3 -m pip
- **Category**: GREEN-FAILURE
- **Detail**: `/usr/local/bin/pip` pointed to a removed Python 3.9 interpreter. Use `python3 -m pip install <pkg>` to target the active interpreter. Always install packages via `python3 -m pip` rather than bare `pip` in this environment.
- **Added after**: B009 at 2026-03-25T02:58:00Z

### Sign: B024 behavior A already implemented — RED phase produces GREEN test
- **Category**: RED-FAILURE
- **Detail**: The source-removal behavior (B024 Behavior A) is already covered by the existing `handler.py` implementation: `load_sources()` reads only from the active `SOURCES_CONFIG` file, so any source absent from YAML is never attempted. The corrected single-assertion RED test (`sources_attempted == 1`, no S3 keys under `src-removed-002/`, at least one key under `src-remaining-001/`) passes immediately without new implementation. When a behavior is already implemented by prior GREEN phases, the RED test will be green from the start — treat this as "behavior pre-implemented" and advance directly to VALIDATE.
- **Added after**: B024 at 2026-03-25T04:22:49Z
