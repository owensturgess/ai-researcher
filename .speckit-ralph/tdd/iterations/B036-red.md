The test fails at collection because `aws_cdk` is not installed and `infra/stacks/pipeline_stack.py` doesn't exist — both are valid RED states confirming there is no implementation.

```
FILE: tests/unit/test_s3_lifecycle_retention.py
```

The test imports `PipelineStack` from the not-yet-created `infra/stacks/pipeline_stack.py` and uses `aws_cdk.assertions.Template` to verify the synthesized CloudFormation template contains an S3 bucket with a lifecycle rule of `ExpirationInDays=30` and `Status=Enabled`. It fails with `ModuleNotFoundError` for `aws_cdk` (not installed) and would then fail for the missing `infra` package — both confirming no implementation exists.

### Sign: aws_cdk not installed — CDK infra tests fail at collection
- **Category**: RED-FAILURE
- **Detail**: `import aws_cdk` raises `ModuleNotFoundError` because `aws_cdk` is not in the test environment. The GREEN phase must install `aws_cdk` and `aws-cdk-lib` (e.g., `python3 -m pip install aws-cdk-lib constructs`) before the CDK assertions can run. The `infra/` package also needs `__init__.py` files at each level so Python treats it as a package.
