"""Core flight booking agent implementation."""

from __future__ import annotations

import json
import asyncio
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from browser_use.agent.prompts import (
    ERROR_RECOVERY_PROMPT,
    STEP_INSTRUCTION_TEMPLATE,
    SYSTEM_PROMPT,
)
from browser_use.browser.browser import Browser
from browser_use.controller.service import Controller
from browser_use.models.booking_data import BookingRequest


class FlightBookingAgent:
    """Specialized agent for automated flight bookings."""

    def __init__(
        self,
        booking_request: BookingRequest | Dict[str, Any],
        openai_model: str = "gpt-4o",
        temperature: float = 0.0,
        max_steps: int = 50,
        search_engine: str = "skyscanner",
        auto_accept_cookies: bool = True,
        cookie_strategy: str = "accept_all",
    ) -> None:
        try:
            if isinstance(booking_request, BookingRequest):
                self.booking_data = booking_request
            else:
                self.booking_data = BookingRequest(**booking_request)
        except ValidationError as exc:
            raise ValueError(f"Invalid booking request: {exc}") from exc

        self.llm = ChatOpenAI(
            model=openai_model,
            temperature=temperature,
            max_tokens=4000,
            request_timeout=60,
            model_kwargs={"response_format": {"type": "json_object"}}
        )

        self.browser = Browser(
            config={
                "headless": False,
                "disable_security": False,
            }
        )

        self.controller = Controller()
        self._register_flight_tools()

        self.max_steps = max_steps
        self.current_step = 0
        self.history: List[Dict[str, str]] = []
        self.search_engine = search_engine

        self.last_actions: List[str] = []
        self.last_page_states: List[str] = []

        self.should_stop = False
        self.stop_reason: Optional[str] = None

        self.auto_accept_cookies = auto_accept_cookies
        self.cookie_strategy = cookie_strategy
        self.cookie_handled = False

    def _register_flight_tools(self) -> None:
        from browser_use.tools.flight_tools import (
            fill_passenger_form,
            freeze_at_payment,
            handle_cookie_consent,
            verify_booking_summary,
        )

        self.controller.register_tool(handle_cookie_consent)
        self.controller.register_tool(fill_passenger_form)
        self.controller.register_tool(verify_booking_summary)
        self.controller.register_tool(freeze_at_payment)

    async def _auto_handle_cookies(self) -> bool:
        """Automatically handle cookie consent popups if enabled."""
        if not self.auto_accept_cookies or self.cookie_handled:
            return False

        try:
            page = self.browser.page
            if not page:
                return False

            # Wait a bit for popup to appear
            await asyncio.sleep(1)

            # Common cookie consent selectors
            cookie_selectors = {
                "accept_all": [
                    "button:has-text('Accept all')",
                    "button:has-text('Accept All')",
                    "button:has-text('Accept cookies')",
                    "button[id*='accept']",
                    "button[class*='accept-all']",
                    "#onetrust-accept-btn-handler",
                    ".cookie-accept-all",
                ],
                "accept_essential": [
                    "button:has-text('Accept essential')",
                    "button:has-text('Essential only')",
                    "button:has-text('Reject all')",
                    "button[class*='essential']",
                ],
            }

            # Get appropriate selectors based on strategy
            selectors = cookie_selectors.get(self.cookie_strategy, cookie_selectors["accept_all"])

            # Try each selector
            for selector in selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        await button.click()
                        print(f"✓ Automatically accepted cookies using: {selector}")
                        self.cookie_handled = True
                        await asyncio.sleep(1)  # Wait for popup to close
                        return True
                except Exception:
                    continue

            return False

        except Exception as exc:
            print(f"Cookie auto-handler failed: {exc}")
            return False

    async def run(self) -> Dict[str, Any]:
        try:
            await self._initialize()

            if self.auto_accept_cookies:
                await self._auto_handle_cookies()

            while self.current_step < self.max_steps and not self.should_stop:
                self.current_step += 1
                print(f"\n--- Step {self.current_step} ---")  # ADD THIS

                page_state = await self._get_page_state()

                if self.auto_accept_cookies and not self.cookie_handled:
                    await self._auto_handle_cookies()

                if self._is_looping():
                    await self._handle_loop_detection()

                messages = self._build_messages(page_state)

                try:
                    print("Calling LLM...")  # ADD THIS
                    response = await self.llm.ainvoke(messages)
                    print(f"LLM Response: {response.content[:200]}")  # ADD THIS

                    action = self._parse_llm_response(response)
                    print(f"Parsed action: {action}")  # ADD THIS
                except Exception as exc:
                    print(f"ERROR: {exc}")  # ADD THIS
                    raise

                if self._should_stop_execution(action):
                    break

                result = await self.controller.execute(action, self.browser)

                if isinstance(result, str) and "STOP_EXECUTION" in result:
                    self.should_stop = True
                    self.stop_reason = "Payment page reached - manual completion required"

                self._update_history(action, result, page_state)

                self.last_actions.append(str(action))
                self.last_actions = self.last_actions[-3:]
                self.last_page_states.append(page_state["url"])
                self.last_page_states = self.last_page_states[-3:]

            return self._generate_result()

        except Exception:
            raise
        finally:
            page = self.browser.page
            if page is not None:
                print("\n" + "=" * 60)
                print("BROWSER LEFT OPEN FOR INSPECTION")
                print(f"Current URL: {page.url}")
                print("=" * 60 + "\n")

                if not self.should_stop:
                    print("Press Ctrl+C to close browser...")
                    await self.browser.keep_alive()

    async def _initialize(self) -> None:
        await self.browser.start()
        start_url = self._resolve_start_url(self.search_engine)
        await self.browser.goto(start_url)
        self.history.append({
            "role": "assistant",
            "content": f"Initialized session at {start_url}",
        })

    @staticmethod
    def _resolve_start_url(identifier: str) -> str:
        mapping = {
            "skyscanner": "https://www.skyscanner.net/",
            "google_flights": "https://www.google.com/travel/flights",
            "kayak": "https://www.kayak.com/flights",
        }
        if identifier.startswith("http://") or identifier.startswith("https://"):
            return identifier
        return mapping.get(identifier.lower(), "https://www.skyscanner.net/")

    async def _get_page_state(self) -> Dict[str, Any]:
        page = await self.browser.start()

        url = page.url or "about:blank"
        try:
            title = await page.title()
        except Exception:
            title = ""

        try:
            element_count = await page.evaluate("document.querySelectorAll('*').length")
        except Exception:
            element_count = 0

        screenshot = await self.browser.screenshot_base64()

        return {
            "url": url,
            "title": title,
            "element_count": element_count,
            "screenshot": screenshot,
        }

    def _is_looping(self) -> bool:
        if len(self.last_actions) < 3:
            return False
        if len(set(self.last_actions)) == 1:
            return True
        if len(set(self.last_page_states)) == 1:
            return True
        return False

    async def _handle_loop_detection(self) -> None:
        error_message = ERROR_RECOVERY_PROMPT.format(failed_action=self.last_actions[-1])
        self.history.append({"role": "system", "content": error_message})
        self.last_actions.clear()
        self.last_page_states.clear()

    def _should_stop_execution(self, action: Any) -> bool:
        if isinstance(action, dict):
            action_type = action.get("type", "").lower()
            if action_type == "stop":
                self.should_stop = True
                self.stop_reason = action.get("reason") or "Stop requested by model"
                return True

        if isinstance(action, str):
            upper = action.upper()
            if "STOP_EXECUTION" in upper or "PAYMENT_PAGE_REACHED" in upper:
                self.should_stop = True
                self.stop_reason = "Payment page reached - manual completion required"
                return True
            if "VALIDATION_ERROR" in upper:
                self.should_stop = True
                self.stop_reason = "Data validation failed"
                return True

        return False

    def _build_messages(self, page_state: Dict[str, Any]) -> List[Any]:
        messages: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]

        booking_context = HumanMessage(
            content=(
                "BOOKING REQUEST:\n"
                f"Origin: {self.booking_data.search.origin}\n"
                f"Destination: {self.booking_data.search.destination}\n"
                f"Departure: {self.booking_data.search.departure_date}\n"
                f"Return: {self.booking_data.search.return_date or 'One-way'}\n"
                f"Passengers: {self.booking_data.search.num_passengers}\n\n"
                "PASSENGER DATA:\n"
                f"{self._format_passenger_data()}\n\n"
                "CONTACT:\n"
                f"Email: {self.booking_data.contact.email}\n"
                f"Phone: {self.booking_data.contact.phone}"
            )
        )
        messages.append(booking_context)

        recent_history = self.history[-5:]
        for item in recent_history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "system":
                messages.append(SystemMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        current_state_text = STEP_INSTRUCTION_TEMPLATE.format(
            task_description=self._get_current_task_description(),
            booking_data="[See above]",
            current_url=page_state["url"],
            page_title=page_state["title"],
            element_count=page_state["element_count"],
            recent_history=self._format_recent_history(),
        )
        messages.append(HumanMessage(content=current_state_text))

        screenshot = page_state.get("screenshot")
        if screenshot:
            messages.append(
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Current page screenshot:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screenshot}"},
                        },
                    ]
                )
            )

        return messages

    def _parse_llm_response(self, response: Any) -> Dict[str, Any]:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            content = "\n".join(text_parts)

        if not isinstance(content, str):
            raise ValueError("LLM response content must be a string.")

        content = content.strip()
        if not content:
            raise ValueError("LLM response was empty.")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM response must be JSON-formatted. Received: {content}") from exc

    def _update_history(self, action: Dict[str, Any], result: Any, page_state: Dict[str, Any]) -> None:
        summary = (
            f"Action: {json.dumps(action)}\n"
            f"Result: {result}\n"
            f"URL: {page_state['url']}"
        )
        self.history.append({"role": "assistant", "content": summary})

    def _format_passenger_data(self) -> str:
        lines: List[str] = []
        for index, passenger in enumerate(self.booking_data.passengers, start=1):
            lines.append(f"Passenger {index}:")
            lines.append(f"  Name: {passenger.first_name} {passenger.last_name}")
            lines.append(f"  DOB: {passenger.date_of_birth}")
            lines.append(f"  Gender: {passenger.gender}")
            lines.append(f"  Nationality: {passenger.nationality}")
            if passenger.passport_number:
                lines.append(f"  Passport: {passenger.passport_number}")
        return "\n".join(lines)

    def _get_current_task_description(self) -> str:
        if self.current_step <= 3:
            return "Navigate to flight search website and handle popups"
        if self.current_step <= 10:
            return "Fill search form and find flights"
        if self.current_step <= 20:
            return "Select cheapest flight and proceed to booking"
        if self.current_step <= 35:
            return "Fill passenger and contact information"
        return "Review booking and proceed to payment"

    def _format_recent_history(self) -> str:
        recent = self.history[-3:]
        return "\n".join(
            f"- {item.get('role', 'assistant')}: {item.get('content', '')}" for item in recent
        )

    async def _keep_browser_alive(self) -> None:
        await self.browser.keep_alive()

    def _generate_result(self) -> Dict[str, Any]:
        page = self.browser.page
        final_url = page.url if page else None
        return {
            "success": self.should_stop and self.stop_reason == "Payment page reached - manual completion required",
            "stop_reason": self.stop_reason,
            "steps_completed": self.current_step,
            "final_url": final_url,
            "booking_summary": {
                "origin": self.booking_data.search.origin,
                "destination": self.booking_data.search.destination,
                "passengers": len(self.booking_data.passengers),
            },
        }
