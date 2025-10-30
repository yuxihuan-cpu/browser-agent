"""Simple entry point for the flight booking automation demo."""
from dotenv import load_dotenv

load_dotenv()

import asyncio
from datetime import date

from browser_use.agent.service import FlightBookingAgent
from browser_use.models.booking_data import (
    BookingRequest,
    ContactInfo,
    FlightSearchCriteria,
    PassengerInfo,
)


async def main() -> None:
    booking_request = BookingRequest(
        search=FlightSearchCriteria(
            origin="London",
            destination="Beijing",
            departure_date=date(2025, 12, 15),
            return_date=None,
            num_passengers=1,
            cabin_class="economy",
        ),
        passengers=[
            PassengerInfo(
                first_name="John",
                last_name="Doe",
                date_of_birth=date(1990, 1, 1),
                passport_number="AB1234567",
                nationality="British",
                gender="M",
            )
        ],
        contact=ContactInfo(
            email="john.doe@example.com",
            phone="+447700900000",
        ),
    )

    agent = FlightBookingAgent(
        booking_request=booking_request,
        openai_model="gpt-4o",
        max_steps=50,
        search_engine="skyscanner",
    )

    print("Starting flight booking automation...")
    print(f"Search: {booking_request.search.origin} → {booking_request.search.destination}")
    print(f"Date: {booking_request.search.departure_date}")
    print(f"Passengers: {len(booking_request.passengers)}")
    print("\n" + "=" * 60 + "\n")

    try:
        result = await agent.run()
    except ValueError as exc:
        print(f"❌ Validation Error: {exc}")
        return

    print("\n" + "=" * 60)
    print("BOOKING AUTOMATION COMPLETE")
    print(f"Success: {result['success']}")
    print(f"Reason: {result['stop_reason']}")
    print(f"Steps: {result['steps_completed']}")
    print(f"Final URL: {result['final_url']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
