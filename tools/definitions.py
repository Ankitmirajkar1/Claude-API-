"""Tool JSON Schemas and the name -> handler mapping.

Anthropic's Messages API takes tool schemas under the top-level `tools`
parameter using standard JSON Schema for `input_schema`. Claude never
executes anything itself - it only ever returns a `tool_use` content block
naming a tool and its arguments; the calling code (main.py) is responsible
for looking up and invoking the matching handler below.
"""

from typing import Any, Callable, Dict, List

from tools.handlers import calculate_mortgage, get_weather

TOOLS: List[Dict[str, Any]] = [
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
    },
    {
        "name": "calculate_mortgage",
        "description": (
            "Calculate the monthly payment, total amount paid, and total "
            "interest for a fixed-rate mortgage loan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Loan amount in dollars, e.g. 300000.",
                },
                "rate": {
                    "type": "number",
                    "description": "Annual interest rate as a percentage, e.g. 6.5.",
                },
                "term_years": {
                    "type": "integer",
                    "description": "Loan term in years, e.g. 30.",
                },
            },
            "required": ["principal", "rate", "term_years"],
        },
    },
]

# Maps each tool's `name` to the Python function that actually executes it.
# main.py looks up tool_use.name here to know what to call.
TOOL_HANDLERS: Dict[str, Callable[..., str]] = {
    "get_weather": get_weather,
    "calculate_mortgage": calculate_mortgage,
}
