from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from playwright.async_api import Page

from browser_use.controller.service import Tool


class CookieConsentOptions(BaseModel):
    """Configuration options for handling cookie consent dialogs."""

    preferred_actions: List[str] = Field(
        default_factory=lambda: ["accept_all", "accept", "agree"]
    )
    custom_selectors: Dict[str, List[str]] = Field(default_factory=dict)
    custom_text_matches: Dict[str, List[str]] = Field(default_factory=dict)
    timeout_ms: int = 2000


DEFAULT_SELECTOR_MAP: Dict[str, List[str]] = {
    "accept_all": [
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("Accept All Cookies")',
        'button:has-text("Accept all cookies")',
        'button:has-text("Accept and close")',
        'button[data-testid*="accept-all"]',
        'button[aria-label*="Accept all"]',
        'button[id*="accept-all"]',
        'button[id*="accept"]',
        'button[class*="accept-all"]',
        'button[class*="accept"]',
        '#onetrust-accept-btn-handler',
        '.cookie-accept',
        '[data-testid="cookie-accept"]',
    ],
    "accept": [
        'button:has-text("Accept")',
        'button:has-text("Allow")',
        'button:has-text("Allow all")',
        'button:has-text("Yes, accept")',
        'button:has-text("I accept")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
    ],
    "agree": [
        'button:has-text("Agree")',
        'button:has-text("Agree and continue")',
    ],
}


DEFAULT_TEXT_MATCHES: Dict[str, List[str]] = {
    "accept_all": [
        r"accept all",
        r"accept all cookies",
        r"allow all",
    ],
    "accept": [
        r"accept",
        r"allow",
        r"yes,? accept",
        r"i accept",
        r"i agree",
    ],
    "agree": [
        r"agree",
        r"consent",
    ],
}


async def _click_selectors(page: Page, selectors: List[str], timeout: int) -> Optional[str]:
    for selector in selectors:
        try:
            await page.click(selector, timeout=timeout)
            return selector
        except Exception:
            continue
    return None


async def _click_by_text(page: Page, patterns: List[str], timeout: int) -> Optional[str]:
    for pattern in patterns:
        try:
            await page.get_by_role("button", name=re.compile(pattern, re.IGNORECASE)).click(
                timeout=timeout
            )
            return f"role=button[name~/{pattern}/i]"
        except Exception:
            continue
    return None


@Tool()
async def handle_cookie_consent(
    page: Page, options: Optional[CookieConsentOptions | Dict[str, Any]] = None
) -> str:
    """Automatically handle cookie consent popups with configurable options."""

    if options is None:
        options_model = CookieConsentOptions()
    elif isinstance(options, CookieConsentOptions):
        options_model = options
    elif isinstance(options, dict):
        options_model = CookieConsentOptions(**options)
    else:  # pragma: no cover - defensive branch
        raise TypeError("options must be a CookieConsentOptions or mapping")

    for action in options_model.preferred_actions:
        selectors = list(DEFAULT_SELECTOR_MAP.get(action, []))
        selectors.extend(options_model.custom_selectors.get(action, []))

        clicked_selector = await _click_selectors(
            page, selectors, timeout=options_model.timeout_ms
        )
        if clicked_selector:
            return f"✓ Cookie consent handled via '{action}': {clicked_selector}"

        text_patterns = list(DEFAULT_TEXT_MATCHES.get(action, []))
        text_patterns.extend(options_model.custom_text_matches.get(action, []))

        clicked_text = await _click_by_text(
            page, text_patterns, timeout=options_model.timeout_ms
        )
        if clicked_text:
            return f"✓ Cookie consent handled via '{action}': {clicked_text}"

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
