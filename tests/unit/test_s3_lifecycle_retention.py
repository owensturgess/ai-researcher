# tests/unit/test_s3_lifecycle_retention.py
#
# Behavior B036: Raw content, transcripts, scored items, and briefings older
# than 30 days are automatically deleted.
#
# Tests the CDK Pipeline Stack (infra/stacks/pipeline_stack.py).
# The S3 bucket must have an S3 lifecycle policy that expires objects after
# 30 days across all data prefixes (raw/, transcripts/, scored/, briefings/)
# so that storage costs remain bounded and data is purged automatically without
# operator intervention.
#
# This test FAILS (RED) because infra/stacks/pipeline_stack.py does not exist yet.

import aws_cdk as cdk
from aws_cdk import assertions

from infra.stacks.pipeline_stack import PipelineStack


def test_pipeline_stack_s3_bucket_has_30_day_lifecycle_expiration_across_all_prefixes():
    """
    Given the CDK PipelineStack is synthesized, when the CloudFormation template
    is inspected, the pipeline S3 bucket has at least one S3 lifecycle rule that
    expires objects after 30 days — automatically deleting raw content, transcripts,
    scored items, and briefings older than 30 days without manual operator action.
    """
    app = cdk.App()
    stack = PipelineStack(app, "TestPipelineStack")
    template = assertions.Template.from_stack(stack)

    # The pipeline bucket must have a lifecycle configuration with a 30-day expiration rule.
    # AWS CDK emits this as an AWS::S3::Bucket resource with LifecycleConfiguration.Rules
    # containing at least one rule with ExpirationInDays=30 and Status=Enabled.
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "LifecycleConfiguration": {
                "Rules": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "ExpirationInDays": 30,
                        "Status": "Enabled",
                    })
                ])
            }
        },
    )
