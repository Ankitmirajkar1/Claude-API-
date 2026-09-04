"""Mock tool implementations.

These are plain Python functions with no relationship to the Anthropic SDK -
the API only ever sees their JSON Schema description (definitions.py) and
their string return values. Swap these bodies for real API/database calls
without touching any of the message-handling code in main.py.
"""

import json
import random


def get_weather(city: str) -> str:
    """Return a mock current-weather reading for a city."""
    # Deterministic-looking but fake data, seeded by city name so repeated
    # calls for the same city return the same "reading" within a run.
    rng = random.Random(city.lower())
    condition = rng.choice(["sunny", "cloudy", "rainy", "windy", "snowy"])
    temp_c = rng.randint(-5, 35)
    return json.dumps(
        {
            "city": city,
            "temperature_celsius": temp_c,
            "condition": condition,
        }
    )


def calculate_mortgage(principal: float, rate: float, term_years: int) -> str:
    """Compute a fixed-rate monthly mortgage payment.

    Args:
        principal: Loan amount, e.g. 300000.
        rate: Annual interest rate as a percentage, e.g. 6.5 for 6.5%.
        term_years: Loan term in years, e.g. 30.
    """
    monthly_rate = (rate / 100) / 12
    num_payments = term_years * 12

    if monthly_rate == 0:
        monthly_payment = principal / num_payments
    else:
        monthly_payment = (
            principal
            * (monthly_rate * (1 + monthly_rate) ** num_payments)
            / ((1 + monthly_rate) ** num_payments - 1)
        )

    total_paid = monthly_payment * num_payments
    total_interest = total_paid - principal

    return json.dumps(
        {
            "monthly_payment": round(monthly_payment, 2),
            "total_paid": round(total_paid, 2),
            "total_interest": round(total_interest, 2),
        }
    )
