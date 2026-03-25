# infra/stacks/pipeline_stack.py
import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from constructs import Construct


class PipelineStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        s3.Bucket(
            self,
            "PipelineBucket",
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(30),
                    enabled=True,
                )
            ],
        )
