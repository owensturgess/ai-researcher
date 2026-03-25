I need write permission to create the test file. Please approve the write to `tests/integration/test_briefing_pipeline.py` — the directory doesn't exist yet either, so the Write tool will need to create both.

Here's a summary of what the test does and why it satisfies all the validation checks:

**Addresses all prior failures:**

1. **Check 4 (mocks internal collaborator)** — Fixed. `load_settings` is not patched anywhere. Instead, settings are written directly to S3 at `config/settings.json` before the handler is called. The handler reads them through its normal S3 codepath.

2. **Check 2 (undocumented return field)** — Fixed. Assertions only touch the three documented fields: `status`, `delivery_status`, `items_included`. No `recipients_delivered`.

3. **Dead code** — Fixed. SES send count is verified via `ses.get_send_statistics()` with `DeliveryAttempts` summed across all DataPoints, asserted equal to `len(TEST_RECIPIENTS)`.

**Test structure:**
- `@mock_aws` intercepts all AWS calls (S3 + SES)
- S3 is seeded with: `config/settings.json` (recipients, threshold, sender), `scored/{date}/item-001.json` (score=80, above threshold=50), `raw/{date}/…/item-001.json` (content body)
- SES identities are verified at the boundary before the call
- Handler is imported and invoked; the test fails immediately with `ModuleNotFoundError` since `src/briefing/handler.py` does not exist yet — which is the correct RED state
