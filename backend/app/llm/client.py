import structlog
from anthropic import AsyncAnthropic

from app.config import settings

log = structlog.get_logger()


def get_anthropic_client() -> AsyncAnthropic:
    """Return a configured AsyncAnthropic client.

    max_retries=5: SDK automatically retries 429 and 5xx with exponential backoff.
    Default is 2; we raise to 5 so bursts that briefly exceed rate limits self-heal.
    """
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=5)


async def call_tool_use(
    client: AsyncAnthropic,
    model: str,
    system_prompt: str,
    user_message: str,
    tool_schema: dict,
    max_tokens: int = 4096,
) -> dict:
    """
    Make a Claude API call using tool_use for structured output.

    Returns the tool input dict. Logs token usage with structlog.
    Raises on API error or if no tool_use block is returned.
    """
    tool_name = tool_schema["name"]
    bound_log = log.bind(model=model, tool=tool_name)
    bound_log.info("llm.call.start")

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_message}],
    )

    bound_log.info(
        "llm.call.complete",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        bound_log.error("llm.call.no_tool_use", stop_reason=response.stop_reason)
        raise ValueError(f"No tool_use block returned by model for tool '{tool_name}'")

    return tool_use_block.input
