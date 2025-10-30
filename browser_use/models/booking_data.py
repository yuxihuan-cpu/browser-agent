from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class PassengerInfo(BaseModel):
    """Passenger information - all fields required."""

    first_name: str = Field(..., min_length=1, description="Passenger first name")
    last_name: str = Field(..., min_length=1, description="Passenger last name")
    date_of_birth: date = Field(..., description="Date of birth (YYYY-MM-DD)")
    passport_number: Optional[str] = Field(None, description="Passport number (if required)")
    nationality: str = Field(..., description="Passenger nationality")
    gender: str = Field(..., pattern="^(M|F|Other)$", description="Gender: M, F, or Other")

    @validator("first_name", "last_name")
    def validate_name(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError("Name cannot be empty")
        return value.strip()


class ContactInfo(BaseModel):
    """Contact information - all fields required."""

    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}$")
    phone: str = Field(..., min_length=10, description="Phone number with country code")

    @validator("email")
    def validate_email(cls, value: str) -> str:
        if not value or "@" not in value:
            raise ValueError("Valid email required")
        return value.lower()


class FlightSearchCriteria(BaseModel):
    """Flight search parameters - all required except return date."""

    origin: str = Field(..., min_length=3, description="Origin airport/city code or name")
    destination: str = Field(..., min_length=3, description="Destination airport/city code or name")
    departure_date: date = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: Optional[date] = Field(None, description="Return date for round trip")
    num_passengers: int = Field(..., ge=1, le=9, description="Number of passengers (1-9)")
    cabin_class: str = Field(default="economy", pattern="^(economy|premium_economy|business|first)$")

    @validator("return_date")
    def validate_return_date(cls, value: Optional[date], values: dict) -> Optional[date]:
        departure_date: Optional[date] = values.get("departure_date")
        if value and departure_date and value < departure_date:
            raise ValueError("Return date must be after departure date")
        return value

    @property
    def is_round_trip(self) -> bool:
        return self.return_date is not None


class BookingRequest(BaseModel):
    """Complete booking request - validates all required data."""

    search: FlightSearchCriteria
    passengers: List[PassengerInfo] = Field(..., min_items=1)
    contact: ContactInfo

    @validator("passengers")
    def validate_passenger_count(cls, passengers: List[PassengerInfo], values: dict) -> List[PassengerInfo]:
        search: Optional[FlightSearchCriteria] = values.get("search")
        if search is not None:
            expected = search.num_passengers
            actual = len(passengers)
            if actual != expected:
                raise ValueError(f"Passenger count mismatch: expected {expected}, got {actual}")
        return passengers

    def to_dict(self) -> dict:
        """Convert to dictionary for agent context."""

        return {
            "search_criteria": self.search.dict(),
            "passengers": [passenger.dict() for passenger in self.passengers],
            "contact": self.contact.dict(),
        }
