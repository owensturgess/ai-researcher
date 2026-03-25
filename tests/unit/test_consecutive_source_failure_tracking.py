# tests/unit/test_consecutive_source_failure_tracking.py
#
# Behavior B034: A source that fails for 3 consecutive days triggers a warning
# in operator metrics.
#
# Tests the public interfaces track_source_failure() and get_failing_sources()
# in src/ingestion/handler.py. After recording 3 consecutive daily failures for
# a source, get_failing_sources(threshold=3) must return that source so the
# monitoring handler can surface it in operator metrics and CloudWatch alarms.
import boto3
from moto import mock_aws

from src.ingestion.handler import get_failing_sources, track_source_failure


@mock_aws
def test_source_failing_three_consecutive_days_appears_in_get_failing_sources(
    monkeypatch,
):
    """
    Given a source whose ingestion has failed on 3 consecutive days (tracked
    via track_source_failure()), when get_failing_sources(threshold=3) is
    called, the source appears in the result with a consecutive failure count
    of 3 — enabling the monitoring handler to surface a warning in operator
    metrics and trigger CloudWatch alarms for persistently failing sources.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    source_id = "src-persistently-failing"

    # Record 3 consecutive daily failures for the same source
    track_source_failure(source_id, "2026-03-22", succeeded=False)
    track_source_failure(source_id, "2026-03-23", succeeded=False)
    track_source_failure(source_id, "2026-03-24", succeeded=False)

    # A source with a different ID that succeeds on day 3 must NOT appear
    other_id = "src-recovered"
    track_source_failure(other_id, "2026-03-22", succeeded=False)
    track_source_failure(other_id, "2026-03-23", succeeded=False)
    track_source_failure(other_id, "2026-03-24", succeeded=True)  # reset on success

    failing = get_failing_sources(threshold=3)

    failing_ids = [src_id for src_id, _count in failing]
    assert source_id in failing_ids, (
        f"Source '{source_id}' with 3 consecutive failures must appear in "
        f"get_failing_sources(threshold=3). Got: {failing}"
    )

    count_for_source = next(
        count for src_id, count in failing if src_id == source_id
    )
    assert count_for_source == 3, (
        f"Consecutive failure count must be 3, got {count_for_source}"
    )

    assert other_id not in failing_ids, (
        f"Source '{other_id}' recovered on day 3 (succeeded=True resets count) "
        f"and must not appear in get_failing_sources(threshold=3). Got: {failing}"
    )
