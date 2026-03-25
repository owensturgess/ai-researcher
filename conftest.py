# conftest.py
import sys
import os
from types import ModuleType

sys.path.insert(0, os.path.dirname(__file__))

# Stub third-party libraries that may not be installed in the test environment.
# Each stub is a minimal module object; tests that need specific behaviour patch
# at the usage site (e.g. src.ingestion.sources.x_api.tweepy.Client).
def _stub_module(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod

if "tweepy" not in sys.modules:
    tweepy_stub = _stub_module("tweepy")
    tweepy_stub.Client = None  # replaced by patch() in individual tests

    # errors sub-module with TooManyRequests exception
    tweepy_errors_stub = _stub_module("tweepy.errors")

    class TooManyRequests(Exception):
        def __init__(self, response=None):
            self.response = response

    tweepy_errors_stub.TooManyRequests = TooManyRequests
    tweepy_stub.errors = tweepy_errors_stub

if "yt_dlp" not in sys.modules:
    yt_dlp_stub = _stub_module("yt_dlp")
    yt_dlp_stub.YoutubeDL = None  # replaced by patch() in individual tests
