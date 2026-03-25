# tests/unit/test_context_prompt_hot_reload.py
#
# Behavior B026: The relevance scoring context prompt can be updated without
# code changes, taking effect on the next pipeline run.
#
# Tests the public interface load_context_prompt(config_dir) in
# src/shared/config.py. Each call must read the file fresh from disk so that
# an operator can edit context-prompt.txt and the change takes effect on the
# next pipeline run without redeploying code.
from src.shared.config import load_context_prompt


def test_updated_context_prompt_file_is_returned_on_next_call_without_code_changes(
    tmp_path,
):
    """
    Given config/context-prompt.txt is updated on disk between two calls to
    load_context_prompt(), when the second call is made (no code changes), it
    returns the new prompt text — confirming the function reads the file fresh
    each time rather than caching the result.
    """
    config_dir = str(tmp_path)
    prompt_file = tmp_path / "context-prompt.txt"

    # Write initial prompt and read it
    prompt_file.write_text("PROMPT_VERSION_ONE: Focus on agentic SDLC tooling.")
    first_result = load_context_prompt(config_dir)

    assert "PROMPT_VERSION_ONE" in first_result, (
        f"load_context_prompt did not return the initial prompt text; got: {first_result!r}"
    )

    # Update the prompt on disk — no code changes, no restart
    prompt_file.write_text("PROMPT_VERSION_TWO: Focus on autonomous agent orchestration.")
    second_result = load_context_prompt(config_dir)

    # The second call must reflect the updated file content
    assert "PROMPT_VERSION_TWO" in second_result, (
        "load_context_prompt returned stale content after the file was updated — "
        "it appears to be caching the prompt rather than reading from disk each call. "
        f"Got: {second_result!r}"
    )
    assert "PROMPT_VERSION_ONE" not in second_result, (
        "load_context_prompt still returned old prompt text after the file was updated."
    )
