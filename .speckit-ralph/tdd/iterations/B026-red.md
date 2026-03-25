The test fails correctly at runtime (not import time). 

```
FILE: tests/unit/test_context_prompt_hot_reload.py
```

The test fails with `NotImplementedError` because `src/shared/config.py` has no implementation. It tests the public `load_context_prompt(config_dir)` interface: given a config directory containing `context-prompt.txt`, two consecutive calls must return the current file contents — proving the function reads from disk fresh each time (no caching), so an operator can update the file and the change takes effect on the next pipeline run without any code deployment.
