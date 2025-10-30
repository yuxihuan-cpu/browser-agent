"""Flight booking automation package."""

from .agent.service import FlightBookingAgent
from .models.booking_data import (
    BookingRequest,
    ContactInfo,
    FlightSearchCriteria,
    PassengerInfo,
)

__all__ = [
    "FlightBookingAgent",
    "BookingRequest",
    "ContactInfo",
    "FlightSearchCriteria",
    "PassengerInfo",
]
