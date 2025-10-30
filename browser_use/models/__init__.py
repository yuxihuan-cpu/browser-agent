"""Data models used by the flight booking agent."""

from .booking_data import BookingRequest, ContactInfo, FlightSearchCriteria, PassengerInfo

__all__ = [
    "BookingRequest",
    "ContactInfo",
    "FlightSearchCriteria",
    "PassengerInfo",
]
