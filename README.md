# Browser Agent

This repository provides an automated flight booking agent powered by Playwright. It showcases how to combine browser automation with structured reasoning to accomplish multi-step tasks such as searching for flights, selecting itineraries, and finalizing bookings.

## Features
- Headless browser automation using Playwright.
- Typed data models with Pydantic for task inputs and outputs.
- Integration-ready scaffold for LLM-powered decision making.

## Development
Set up the project with [uv](https://github.com/astral-sh/uv):

```bash
uv venv --python 3.11
source .venv/bin/activate
uv sync
```

Run the demo script after configuring the necessary environment variables:

```bash
uv run flight_booking_demo.py
```
