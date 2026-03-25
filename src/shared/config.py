# src/shared/config.py
import os


def load_context_prompt(config_dir: str) -> str:
    path = os.path.join(config_dir, "context-prompt.txt")
    with open(path) as f:
        return f.read()


def load_settings(config_dir: str):
    raise NotImplementedError("load_settings not yet implemented")


def load_sources(config_dir: str):
    raise NotImplementedError("load_sources not yet implemented")
