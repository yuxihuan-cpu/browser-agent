from typing import Any, Dict

from playwright.async_api import Page

from browser_use.controller.service import Tool


@Tool()
async def handle_cookie_consent(page: Page) -> str:
    """Automatically handle cookie consent popups on flight booking sites."""

    selectors = [
        'button:has-text("Accept")',
        'button:has-text("Accept all")',
        'button:has-text("Agree")',
        'button[id*="accept"]',
        'button[class*="accept"]',
        '#onetrust-accept-btn-handler',
        '.cookie-accept',
        '[data-testid="cookie-accept"]',
    ]

    for selector in selectors:
        try:
            await page.click(selector, timeout=2000)
            return f"✓ Cookie consent handled: {selector}"
        except Exception:
            continue

    return "No cookie popup found or already handled"


@Tool()
async def fill_passenger_form(page: Page, passenger_index: int, passenger_data: Dict[str, Any]) -> str:
    """Fill passenger information form with validation."""

    required_fields = ["first_name", "last_name"]
    for field in required_fields:
        if not passenger_data.get(field):
            raise ValueError(f"Required field '{field}' is missing for passenger {passenger_index}")

    fields = {
        "first_name": [
            f'input[name*="firstName"][name*="{passenger_index}"]',
            f'input[name="passengers[{passenger_index}].firstName"]',
            'input[placeholder*="First name"]',
        ],
        "last_name": [
            f'input[name*="lastName"][name*="{passenger_index}"]',
            f'input[name="passengers[{passenger_index}].lastName"]',
            'input[placeholder*="Last name"]',
        ],
        "date_of_birth": [
            f'input[name*="dateOfBirth"][name*="{passenger_index}"]',
            f'input[type="date"][name*="{passenger_index}"]',
        ],
        "passport_number": [
            f'input[name*="passport"][name*="{passenger_index}"]',
            'input[placeholder*="Passport"]',
        ],
        "nationality": [
            f'select[name*="nationality"][name*="{passenger_index}"]',
            'select[placeholder*="Nationality"]',
        ],
    }

    filled_fields = []
    missing_fields = []

    for field_name, selectors in fields.items():
        value = passenger_data.get(field_name)
        if not value:
            continue

        field_filled = False
        for selector in selectors:
            try:
                await page.fill(selector, str(value), timeout=1000)
                filled_fields.append(field_name)
                field_filled = True
                break
            except Exception:
                continue

        if not field_filled:
            missing_fields.append(field_name)

    result = f"Passenger {passenger_index}: Filled {len(filled_fields)} fields"
    if missing_fields:
        result += f" | Could not fill: {', '.join(missing_fields)}"

    return result


@Tool()
async def verify_booking_summary(page: Page, expected_data: Dict[str, Any]) -> str:
    """Verify booking summary page shows correct information before proceeding."""

    try:
        text = (await page.inner_text("body")).lower()
    except Exception as exc:  # pragma: no cover - fallback path
        return f"Verification failed: {exc}"

    checks = {
        "origin": expected_data.get("origin", "").lower() in text,
        "destination": expected_data.get("destination", "").lower() in text,
        "passenger_name": expected_data.get("passenger_name", "").lower() in text,
        "email": expected_data.get("email", "").lower() in text,
    }

    passed = [key for key, ok in checks.items() if ok]
    failed = [key for key, ok in checks.items() if not ok]

    if failed:
        return f"⚠️ Verification incomplete. Missing: {', '.join(failed)}"

    return f"✓ Booking summary verified: {', '.join(passed)}"


@Tool()
async def freeze_at_payment(page: Page) -> str:
    """Detect payment page and freeze browser for manual completion."""

    indicators = [
        "payment",
        "credit card",
        "card number",
        "cvv",
        "expiry",
        "billing",
        "checkout",
        "pay now",
    ]

    url = page.url.lower()
    try:
        text = (await page.inner_text("body")).lower()
    except Exception:
        text = ""

    is_payment = any(indicator in url or indicator in text for indicator in indicators)

    if is_payment:
        await page.screenshot(path="payment_page.png")
        return "STOP_EXECUTION:PAYMENT_PAGE_REACHED"

    return "Not on payment page yet"
