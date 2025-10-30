"""Action controller and tool registry for the flight booking agent."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from browser_use.browser.browser import Browser


@dataclass
class ToolSpec:
    """Metadata for a registered tool."""

    name: str
    description: str
    coroutine: Callable[..., Awaitable[str]]


class Tool:
    """Decorator used to register reusable async tools."""

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None) -> None:
        self._name = name
        self._description = description

    def __call__(self, func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        tool_name = self._name or func.__name__
        tool_description = self._description or (inspect.getdoc(func) or "")
        setattr(func, "__tool_spec__", ToolSpec(tool_name, tool_description, func))
        return func


class Controller:
    """Executes actions requested by the language model."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register_tool(self, func: Callable[..., Awaitable[str]]) -> None:
        """Register a decorated tool callable."""

        spec: Optional[ToolSpec] = getattr(func, "__tool_spec__", None)
        if not spec:
            raise ValueError("Tool functions must be decorated with @Tool().")
        self._tools[spec.name] = spec

    async def execute(self, action: Dict[str, Any], browser: Browser) -> str:
        """Execute an action dictionary produced by the LLM."""

        if not isinstance(action, dict):
            raise ValueError("Controller.execute expects an action dictionary.")

        action_type = action.get("type")
        if not action_type:
            raise ValueError("Action missing 'type' field.")

        page = await browser.start()

        if action_type == "navigate":
            url = action.get("url")
            if not url:
                raise ValueError("Navigate action requires 'url'.")
            await browser.goto(url)
            return f"Navigated to {url}"

        if action_type == "click":
            selector = action.get("selector")
            if not selector:
                raise ValueError("Click action requires 'selector'.")
            await page.click(selector, timeout=action.get("timeout", 5000))
            return f"Clicked {selector}"

        if action_type == "fill":
            selector = action.get("selector")
            value = action.get("value")
            if not selector or value is None:
                raise ValueError("Fill action requires 'selector' and 'value'.")
            await page.fill(selector, str(value), timeout=action.get("timeout", 5000))
            return f"Filled {selector}"

        if action_type == "press":
            key = action.get("key")
            if not key:
                raise ValueError("Press action requires 'key'.")
            await page.keyboard.press(key)
            return f"Pressed {key}"

        if action_type == "wait_for_selector":
            selector = action.get("selector")
            if not selector:
                raise ValueError("wait_for_selector action requires 'selector'.")
            await page.wait_for_selector(selector, timeout=action.get("timeout", 5000))
            return f"Waited for {selector}"

        if action_type == "tool":
            tool_name = action.get("name")
            args = action.get("args", {})
            if not tool_name:
                raise ValueError("Tool action requires 'name'.")

            tool = self._tools.get(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' is not registered.")

            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be provided as a dictionary.")

            return await tool.coroutine(page, **args)

        if action_type == "evaluate":
            expression = action.get("expression")
            if not expression:
                raise ValueError("Evaluate action requires 'expression'.")
            result = await page.evaluate(expression)
            return f"Evaluated expression -> {result}"

        if action_type == "stop":
            return "STOP_EXECUTION:REQUESTED"

        raise ValueError(f"Unsupported action type: {action_type}")

    def get_tool_names(self) -> Dict[str, str]:
        """Return mapping of tool names to descriptions."""

        return {name: spec.description for name, spec in self._tools.items()}
