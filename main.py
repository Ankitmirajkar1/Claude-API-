"""Anthropic Claude Messages API fundamentals: roles, tool use, and the
agentic loop.

Key mental model (this is the whole point of this file):

  * There are only two conversational roles: "user" and "assistant".
    There is NO "tool" role in the Anthropic API.
  * The system prompt is a single top-level `system` parameter on every
    request - it is never an item inside `messages`.
  * When Claude wants to call a tool, it replies with role "assistant" and
    one or more `tool_use` content blocks (no plain text may accompany them
    if the tool call is all it wants to do this turn).
  * We execute those tools locally, then send the results back as a new
    "user" message containing `tool_result` blocks. From Claude's point of
    view, "the user handed me the tool's answer" - even though a human typed
    nothing. This is why tool results live under role "user".
  * The full message history (including every past tool_use/tool_result
    pair) must be resent on every request - the API is stateless.

Run with: python main.py
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

from tools.definitions import TOOL_HANDLERS, TOOLS

load_dotenv()

# claude-3-5-sonnet-latest (sometimes assumed as a "default" model id) has
# been retired. claude-sonnet-5 is the current Sonnet-tier model; override
# via CLAUDE_MODEL in your .env if you want a different one.
DEFAULT_MODEL = "claude-sonnet-5"
MODEL = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools for checking weather "
    "and calculating mortgage payments. Use a tool whenever it would give "
    "the user a more accurate answer than you reasoning alone. When you are "
    "done using tools, summarize the result for the user in plain language."
)

# Set to {"type": "any"} to force Claude to call some tool every turn, or
# {"type": "tool", "name": "get_weather"} to force one specific tool.
TOOL_CHOICE = {"type": "auto"}


# --------------------------------------------------------------------------
# Terminal logging
# --------------------------------------------------------------------------

_COLORS = {
    "system": "\033[35m",  # magenta
    "user": "\033[36m",  # cyan
    "assistant": "\033[32m",  # green
    "tool": "\033[33m",  # yellow
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def _supports_color() -> bool:
    return sys.stdout.isatty()


def log_role(role: str, label: str) -> None:
    """Print a distinct, styled header for the active role/turn."""
    color = _COLORS.get(role, "")
    reset = _COLORS["reset"] if _supports_color() else ""
    bold = _COLORS["bold"] if _supports_color() else ""
    color = color if _supports_color() else ""
    print(f"\n{bold}{color}[{label}]{reset}")


def log_text(text: str) -> None:
    print(text)


def log_tool_use(name: str, tool_input: dict, tool_use_id: str) -> None:
    color = _COLORS["tool"] if _supports_color() else ""
    reset = _COLORS["reset"] if _supports_color() else ""
    print(f"{color}-> tool_use  {name}({json.dumps(tool_input)})  id={tool_use_id}{reset}")


def log_tool_result(tool_use_id: str, result: str, is_error: bool = False) -> None:
    color = _COLORS["tool"] if _supports_color() else ""
    reset = _COLORS["reset"] if _supports_color() else ""
    status = "ERROR" if is_error else "result"
    print(f"{color}<- tool_{status}  id={tool_use_id}  {result}{reset}")


def _json_safe(obj):
    """Best-effort JSON serialization for SDK objects (TextBlock, ToolUseBlock, ...)."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


def log_context(messages: list[dict]) -> None:
    """Print the exact conversation history ("context") being sent THIS call.

    This is the whole point of "stateless": the API has no memory of its
    own. Every request must carry the FULL conversation so far - system
    prompt is passed separately (see SYSTEM_PROMPT), but everything else
    (every past user question, every past assistant reply, every past
    tool_use/tool_result pair) lives in this one `messages` list and is
    resent, in full, on every single call. This Python list is the ONLY
    place "memory" exists in this whole program - there is no database,
    no server-side session, nothing. It grows by one entry each time we
    call messages.append(...) below, and shrinks back to nothing the
    moment the program exits.
    """
    color = _COLORS["tool"] if _supports_color() else ""
    reset = _COLORS["reset"] if _supports_color() else ""
    print(f"{color}>>> CONTEXT SENT THIS CALL - {len(messages)} message(s) in history{reset}")
    print(json.dumps(messages, indent=2, default=_json_safe))
    print(f"{color}>>> END CONTEXT{reset}")


def log_raw_response(response) -> None:
    """Print the raw fields Claude's API actually returned, unfiltered.

    Everything main.py does afterwards (log_role/log_text/log_tool_use,
    the stop_reason check, etc.) is just reading pieces OFF of this same
    object - this print shows you the whole thing at once.
    """
    color = _COLORS["assistant"] if _supports_color() else ""
    reset = _COLORS["reset"] if _supports_color() else ""
    print(f"{color}<<< RAW API RESPONSE{reset}")
    print(f"    id:                {response.id}")
    print(f"    stop_reason:       {response.stop_reason}")
    print(
        f"    usage:             input_tokens={response.usage.input_tokens}, "
        f"output_tokens={response.usage.output_tokens}"
    )
    print(f"    content (blocks):  {[_json_safe(b) for b in response.content]}")
    print(f"{color}<<< END RAW RESPONSE{reset}")


# --------------------------------------------------------------------------
# Tool execution
# --------------------------------------------------------------------------


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Look up and run a tool handler by name.

    Returns (content, is_error) so the caller can set `is_error` on the
    tool_result block without raising and losing the tool_use_id.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Error: unknown tool '{name}'", True

    try:
        return handler(**tool_input), False
    except Exception as exc:  # noqa: BLE001 - surface any handler failure to Claude
        return f"Error running '{name}': {exc}", True


# --------------------------------------------------------------------------
# Agentic loop
# --------------------------------------------------------------------------


def run_conversation(client: anthropic.Anthropic, user_message: str) -> str:
    """Run one user turn to completion, including any tool-use round trips."""
    messages: list[dict] = [{"role": "user", "content": user_message}]

    log_role("system", "SYSTEM")
    log_text(SYSTEM_PROMPT)

    log_role("user", "USER")
    log_text(user_message)

    while True:
        # `messages` is "the context" for this call - see log_context's
        # docstring. It is passed fresh, in full, every single iteration.
        log_context(messages)

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            tool_choice=TOOL_CHOICE,
            messages=messages,
        )

        log_raw_response(response)

        log_role("assistant", "ASSISTANT")
        for block in response.content:
            if block.type == "text":
                log_text(block.text)
            elif block.type == "tool_use":
                log_tool_use(block.name, block.input, block.id)

        # The assistant's turn (text + any tool_use blocks) becomes part of
        # history exactly as Claude produced it - never edited or trimmed.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # end_turn (or another terminal reason) - the loop is done.
            break

        # Claude may request multiple tools in one turn (parallel tool use).
        # All of their results must go back together in a single "user"
        # message - splitting them across separate messages is invalid and
        # will discourage Claude from batching calls in the future.
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_result_blocks = []

        for block in tool_use_blocks:
            result, is_error = execute_tool(block.name, block.input)
            log_tool_result(block.id, result, is_error)
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                }
            )

        # Tool results are fed back as role "user" - there is no "tool"
        # role in the Anthropic API. Claude reads this as "the user (or the
        # environment acting on the user's behalf) supplied this data."
        log_role("user", "USER (tool_result)")
        for trb in tool_result_blocks:
            log_tool_result(trb["tool_use_id"], trb["content"], trb["is_error"])
        messages.append({"role": "user", "content": tool_result_blocks})

    final_text = next(
        (b.text for b in response.content if b.type == "text"), ""
    )
    return final_text


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Missing ANTHROPIC_API_KEY. Copy .env.example to .env and add your key."
        )
        sys.exit(1)

    # Optional: route requests through a custom endpoint (e.g. an internal
    # gateway/relay) instead of api.anthropic.com. Leave BASE_URL unset in
    # .env to use Anthropic's endpoint directly.
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    demo_prompts = [
        "What's the weather like in Paris right now?",
        "If I borrow $350,000 at 6.5% for 30 years, what's my monthly payment?",
        "Compare the weather in Tokyo and London, and also work out the "
        "mortgage payment for a $500,000 loan at 5.9% over 15 years.",
    ]

    for prompt in demo_prompts:
        print("\n" + "=" * 70)
        final_answer = run_conversation(client, prompt)
        log_role("assistant", "FINAL ANSWER")
        log_text(final_answer)


if __name__ == "__main__":
    main()
