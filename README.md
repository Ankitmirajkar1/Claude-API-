# Claude Tools Demo

A small, heavily-commented Python project that demonstrates, end to end, how
the **Anthropic Claude Messages API** works — the request/response shape,
the two-role conversation model, and a complete **agentic tool-use loop**
(including parallel tool calls). It's built to be read alongside the code:
every concept below has a matching comment in [`main.py`](main.py),
[`tools/definitions.py`](tools/definitions.py), or
[`tools/handlers.py`](tools/handlers.py).

This README covers two things:

1. **This project** — what it does, how to run it, how to extend it.
2. **The general Claude API / tool-use concepts** it demonstrates — useful as
   a standalone reference even outside this repo.

---

## Table of contents

- [What this project does](#what-this-project-does)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Run](#run)
- [Configuration](#configuration)
- [Tools included](#tools-included)
- [Extending the project](#extending-the-project)
- [Claude API fundamentals](#claude-api-fundamentals)
  - [The Messages endpoint](#the-messages-endpoint)
  - [Only two roles: `user` and `assistant`](#only-two-roles-user-and-assistant)
  - [The API is stateless](#the-api-is-stateless)
  - [`stop_reason`](#stop_reason)
- [Tool use in depth](#tool-use-in-depth)
  - [Defining a tool](#defining-a-tool)
  - [`tool_choice`](#tool_choice)
  - [How a tool call actually flows](#how-a-tool-call-actually-flows)
  - [`tool_use` content blocks](#tool_use-content-blocks)
  - [`tool_result` content blocks](#tool_result-content-blocks)
  - [Parallel tool use](#parallel-tool-use)
  - [Error handling in tool results](#error-handling-in-tool-results)
- [The agentic loop](#the-agentic-loop)
- [Other ways to build with Claude](#other-ways-to-build-with-claude)
- [Troubleshooting](#troubleshooting)
- [Further reading](#further-reading)

---

## What this project does

`main.py` sends three demo prompts through a single `run_conversation()`
function and prints, in color-coded detail, everything that happens at each
step of the API round trip:

1. **`SYSTEM_PROMPT`** — logged once, showing it is a top-level parameter,
   never a message.
2. **The exact JSON `messages` array sent on every single API call** —
   proving the API has no memory of its own; your code carries the entire
   conversation, every time.
3. **The raw response fields** (`id`, `stop_reason`, `usage`, `content`)
   exactly as Claude's API returns them, before any of the demo's own
   formatting touches them.
4. **Tool calls and tool results** as they're issued and executed.
5. **The final natural-language answer**, once the loop terminates.

The three demo prompts are chosen to exercise three distinct paths:

| Prompt | Demonstrates |
|---|---|
| "What's the weather like in Paris right now?" | A single tool call (`get_weather`) |
| "If I borrow $350,000 at 6.5% for 30 years..." | A single tool call (`calculate_mortgage`) |
| "Compare the weather in Tokyo and London, and also work out the mortgage..." | **Parallel** tool use — three tool calls issued in one assistant turn |

## Project structure

```
claude_tools_demo/
├── .env.example        # Template for required/optional environment variables
├── .python-version
├── main.py             # Client setup, logging helpers, tool execution, agentic loop
├── pyproject.toml
├── requirements.txt
├── uv.lock
└── tools/
    ├── __init__.py
    ├── definitions.py  # Tool JSON Schemas + name -> handler mapping (TOOLS, TOOL_HANDLERS)
    └── handlers.py     # Plain Python functions the tools actually run (mocked data)
```

- **`main.py`** owns everything Anthropic-SDK-specific: constructing the
  client, calling `client.messages.create(...)`, reading `stop_reason`, and
  driving the loop that keeps calling the API until Claude is done.
- **`tools/definitions.py`** owns the tool *contracts* — the JSON Schema
  Claude sees, and the Python function each tool name maps to. It imports
  from `handlers.py` but has no Anthropic SDK dependency itself.
- **`tools/handlers.py`** owns the tool *implementations* — ordinary Python
  functions with no awareness of Claude, the SDK, or JSON Schema. They take
  typed arguments and return a string (here, JSON-encoded mock data).

This separation is deliberate: swapping a mock for a real API/database call
means editing only `handlers.py` — `main.py` and the schemas never change.

## Setup

Requires Python 3.12+ and an [Anthropic API key](https://console.anthropic.com/settings/keys).

```bash
cd claude_tools_demo
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

(This project also ships a `uv.lock` / `pyproject.toml`, so `uv sync` works
as an alternative to `pip install -r requirements.txt` if you use
[uv](https://docs.astral.sh/uv/).)

## Run

```bash
python main.py
```

This runs the three demo prompts listed above through the agentic loop and
prints the full request/response trace for each.

## Configuration

All configuration lives in `.env` (see [`.env.example`](.env.example)):

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key. The program exits with a clear message if it's missing. |
| `CLAUDE_MODEL` | No | Overrides the default model (`claude-sonnet-5`). |
| `ANTHROPIC_BASE_URL` | No | Routes requests through a custom endpoint (e.g. an internal gateway/relay) instead of `api.anthropic.com`. |

Other tunables live directly in `main.py` as module-level constants:

- `MAX_TOKENS` — cap on tokens Claude can generate per response.
- `SYSTEM_PROMPT` — the top-level system instruction.
- `TOOL_CHOICE` — how Claude is allowed/forced to use tools (see
  [`tool_choice`](#tool_choice) below).

> **Note on model IDs:** `claude-3-5-sonnet-latest` has been retired by
> Anthropic and is no longer a valid model ID. `claude-sonnet-5` is the
> current equivalent and is the default here. Always use the exact model ID
> string from Anthropic's current model list — don't guess or append date
> suffixes.

## Tools included

| Tool | Signature | Description |
|---|---|---|
| `get_weather` | `get_weather(city: str) -> str` | Returns mock current weather (condition + temperature) for a city, deterministic per city name. |
| `calculate_mortgage` | `calculate_mortgage(principal: float, rate: float, term_years: int) -> str` | Computes monthly payment, total paid, and total interest for a fixed-rate loan. |

Both are mock implementations in `tools/handlers.py` — no network calls, no
real weather or financial data. Swap in real API/database calls without
touching `main.py` or the tool schemas in `definitions.py`.

## Extending the project

- **Add a tool:**
  1. Write a plain Python function in `tools/handlers.py` that returns a
     string (JSON-encode structured results, as the existing tools do).
  2. Add its JSON Schema entry to `TOOLS` in `tools/definitions.py`.
  3. Register `"tool_name": handler_function` in `TOOL_HANDLERS` in the same
     file.
  4. No changes are needed in `main.py` — it looks up handlers generically
     by name.
- **Force a specific tool every turn:** set `TOOL_CHOICE` in `main.py` to
  `{"type": "tool", "name": "get_weather"}`.
- **Force *some* tool call every turn:** set `TOOL_CHOICE = {"type": "any"}`.
- **Disable tool use entirely for a turn:** `{"type": "none"}`.
- **See the raw wire format:** `log_context()` and `log_raw_response()` in
  `main.py` print the exact JSON sent and received — the best way to see
  precisely what changes when you edit a tool schema or prompt.

---

## Claude API fundamentals

Everything below is general knowledge about the Anthropic Claude API, using
this project's code as the running example.

### The Messages endpoint

Every request — with or without tools — goes through one endpoint:
`POST /v1/messages`, exposed by the SDK as `client.messages.create(...)`.
The request this project sends looks like:

```python
client.messages.create(
    model=MODEL,                # e.g. "claude-sonnet-5"
    max_tokens=MAX_TOKENS,       # cap on generated output tokens
    system=SYSTEM_PROMPT,        # top-level system prompt (see below)
    tools=TOOLS,                 # JSON Schema tool definitions
    tool_choice=TOOL_CHOICE,     # how tools may/must be used
    messages=messages,           # the full conversation so far
)
```

Key point: **the system prompt is a top-level parameter, not a message.**
It is never an item inside `messages`, and it doesn't take a "role" — it's
just a string (or, for advanced use, a list of content blocks) sent
alongside `messages` on every call.

### Only two roles: `user` and `assistant`

The Anthropic API's conversation model has exactly two roles:

- **`user`** — anything supplied *to* Claude: the human's question, and
  (importantly) the results of tool executions.
- **`assistant`** — anything produced *by* Claude: text, and/or requests to
  call a tool.

**There is no `"tool"` role.** This surprises people coming from APIs that
have one. When your code runs a tool and needs to hand the result back to
Claude, that result is packaged as a new **`user`** message containing a
`tool_result` block. From Claude's point of view, this reads as "the user
(or the environment acting on the user's behalf) supplied this data" — even
though no human typed anything. See [`tool_result` content
blocks](#tool_result-content-blocks) below.

### The API is stateless

Anthropic's API has no server-side memory of a conversation. Every single
call must carry the **entire** conversation history in `messages` — every
past user question, every past assistant reply, every past
`tool_use`/`tool_result` pair. In this project, that history lives in one
Python list (`messages` inside `run_conversation()`) that grows by one
entry per `messages.append(...)` call and is resent, in full, on every loop
iteration. `log_context()` in `main.py` prints this list before each
request specifically to make this concrete — watch it grow across
iterations when you run the demo.

If you don't resend history, Claude has no idea what happened before — this
is why chat apps built on this API must persist and replay the transcript
themselves (in a database, a session object, etc.).

### `stop_reason`

Every response carries a `stop_reason` telling you *why* generation
stopped. The ones relevant here:

| `stop_reason` | Meaning |
|---|---|
| `end_turn` | Claude finished its turn normally. Nothing more to do. |
| `tool_use` | Claude wants to call one or more tools before continuing. Your code must execute them and send results back. |
| `max_tokens` | Generation was cut off by the `max_tokens` cap. Consider raising it or handling truncation. |
| `refusal` | Claude declined to continue for a safety reason (only on some newer models). Always check `content` may be partial or absent. |

The agentic loop in this project is, at its core, just: *keep calling the
API and resolving tool calls until `stop_reason` is no longer `tool_use`.*

---

## Tool use in depth

### Defining a tool

A tool is described to Claude with a **name**, a **natural-language
description**, and an **`input_schema`** written as standard [JSON
Schema](https://json-schema.org/). Claude never runs anything itself — it
only ever decides *that* a tool should be called and *with what arguments*.
From `tools/definitions.py`:

```python
{
    "name": "get_weather",
    "description": (
        "Get the current weather for a given city. Use this whenever the "
        "user asks about weather, temperature, or conditions in a location."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, e.g. 'Paris' or 'San Francisco'.",
            }
        },
        "required": ["city"],
    },
}
```

The **description** matters as much as the schema — it's the only thing
Claude uses to decide *when* to reach for a tool versus answering directly.
Vague or missing descriptions are a common cause of tools being ignored or
misused.

### `tool_choice`

`tool_choice` controls how much freedom Claude has to decide whether to use
a tool at all:

| Value | Behavior |
|---|---|
| `{"type": "auto"}` | Claude decides per turn whether a tool call is warranted. **Default in this project.** |
| `{"type": "any"}` | Claude must call *some* tool this turn (can't just reply with text). |
| `{"type": "tool", "name": "get_weather"}` | Claude must call this specific tool this turn. |
| `{"type": "none"}` | Claude must not call any tool this turn, even if `tools` is provided. |

### How a tool call actually flows

This is the part that trips people up most, so it's worth spelling out as a
sequence:

1. You send a request with `tools` attached.
2. Claude replies as `assistant` with one or more `tool_use` content
   blocks (instead of, or alongside, text) — it does **not** execute
   anything.
3. **Your code** looks up the tool by name and runs the matching Python
   function (`execute_tool()` in `main.py`).
4. **Your code** packages the return value as a `tool_result` block and
   sends it back inside a **new `user` message**.
5. Claude reads the `tool_result` and continues the turn — either replying
   with text, or requesting another tool call.
6. Repeat from step 2 until `stop_reason` is no longer `tool_use`.

### `tool_use` content blocks

When Claude wants to call a tool, the `assistant` message's `content` list
contains a block shaped like:

```json
{
  "type": "tool_use",
  "id": "toolu_01A09q90qw90lq917835lq9",
  "name": "get_weather",
  "input": { "city": "Paris" }
}
```

- **`id`** is unique per tool call and must be echoed back in the matching
  `tool_result` (see below) — this is how Claude matches results to calls,
  especially when several are issued at once.
- **`input`** is already parsed JSON matching your `input_schema` — no need
  to re-parse a string.

`main.py`'s `execute_tool()` reads `block.name` and `block.input` directly
off this block and calls `TOOL_HANDLERS[block.name](**block.input)`.

### `tool_result` content blocks

The result goes back as a `user` message containing one block per tool
call:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
  "content": "{\"city\": \"Paris\", \"temperature_celsius\": 18, \"condition\": \"cloudy\"}",
  "is_error": false
}
```

- **`tool_use_id`** must match the `id` from the corresponding `tool_use`
  block exactly.
- **`content`** is typically a string (JSON-encoded, as both handlers in
  this project do, if the data is structured) — it can also be a list of
  content blocks (e.g. to return an image), but a plain string covers most
  cases.
- **`is_error`** (optional, default `false`) tells Claude the tool
  execution failed — see [error handling](#error-handling-in-tool-results).

### Parallel tool use

Claude may request **multiple tools in a single assistant turn** — for
example, the third demo prompt in this project triggers two `get_weather`
calls and one `calculate_mortgage` call at once. When this happens:

- All of the resulting `tool_result` blocks **must** be returned together
  in a **single** `user` message — never split across multiple messages.
- Execute them however makes sense for your code (sequentially is fine for
  a demo; concurrently is common in production for I/O-bound tools).

`main.py` handles this generically: it collects *every* `tool_use` block
from `response.content` into `tool_use_blocks`, executes each one, and
appends all the resulting `tool_result` blocks into one `messages.append()`
call. Splitting results across separate messages is not just wrong — it
actively discourages Claude from batching calls in future turns, since it
looks like the batching didn't work.

### Error handling in tool results

If a tool handler raises an exception, **don't drop the tool call or crash
the loop** — tell Claude it failed and let it decide what to do next (retry
with different arguments, try a different tool, or explain the failure to
the user). This project's `execute_tool()` demonstrates the pattern:

```python
def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Error: unknown tool '{name}'", True
    try:
        return handler(**tool_input), False
    except Exception as exc:
        return f"Error running '{name}': {exc}", True
```

The returned `(content, is_error)` tuple maps directly onto the
`tool_result` block's `content` and `is_error` fields.

---

## The agentic loop

Putting it all together, `run_conversation()` in `main.py` implements the
minimal form of an agentic loop:

```python
messages = [{"role": "user", "content": user_message}]

while True:
    response = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
        tools=TOOLS, tool_choice=TOOL_CHOICE, messages=messages,
    )

    # The assistant's turn becomes history exactly as Claude produced it.
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason != "tool_use":
        break  # end_turn (or another terminal reason) - done.

    # Execute every requested tool, collect all results...
    tool_result_blocks = [...]

    # ...and send them all back as ONE new user message.
    messages.append({"role": "user", "content": tool_result_blocks})

final_text = next((b.text for b in response.content if b.type == "text"), "")
```

Two details worth internalizing:

- **The assistant's message is appended verbatim.** Never edit or trim
  `response.content` before storing it — Claude's own tool-use blocks are
  part of the conversation it needs to see again to stay consistent.
- **The loop terminates on `stop_reason`, not on the presence/absence of
  text.** Claude can legitimately reply with only `tool_use` blocks and no
  text in a given turn.

This hand-written loop is intentionally minimal so the mechanics are
visible. For production code, the Anthropic SDKs also ship a **Tool
Runner** helper (`client.beta.messages.tool_runner(...)` in Python) that
automates this exact loop — request → execute → repeat — while still giving
you per-turn hooks for approval gates, retries, and logging. This project
deliberately writes the loop by hand instead, since the goal is to make the
underlying request/response mechanics explicit.

## Other ways to build with Claude

This project uses the lowest-level building block — the Messages API with
a manual tool-use loop. For context, the broader surface area:

| Approach | What you write | Who hosts it | Use when |
|---|---|---|---|
| **Claude API — manual loop** (this project) | The loop itself | You | You want full visibility into every request/response |
| **Claude API — Tool Runner** | Just the tool functions | You | Same idea, without hand-writing the loop |
| **Managed Agents** | Agent config + tool results | Anthropic | You want a server-managed agent with a hosted sandbox (bash, files, code exec) |
| **Claude Agent SDK** | A prompt + options | You | You want the full Claude Code harness (built-in file/bash tools) on your own infra |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Missing ANTHROPIC_API_KEY` at startup | `.env` wasn't created from `.env.example`, or the key wasn't set. |
| `401`/authentication error from the API | Invalid or revoked API key. |
| `400 invalid_request_error` mentioning the model | The model ID is wrong or retired (e.g. `claude-3-5-sonnet-latest`) — use a current ID such as `claude-sonnet-5`. |
| Claude never calls a tool you expect | Check the tool's `description` is specific enough, and that `TOOL_CHOICE` is `"auto"` (not `"none"`). |
| Response cut off mid-sentence | `stop_reason == "max_tokens"` — raise `MAX_TOKENS` in `main.py`. |
| Tool result seems ignored | Confirm `tool_use_id` in your `tool_result` block exactly matches the originating `tool_use` block's `id`. |

## Further reading

- Anthropic API docs: https://docs.anthropic.com
- Get an API key: https://console.anthropic.com/settings/keys
- JSON Schema reference (for `input_schema`): https://json-schema.org
