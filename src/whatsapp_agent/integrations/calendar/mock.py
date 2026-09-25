"""
Mock Calendar Provider for testing and development.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime
import asyncio

from whatsapp_agent.integrations.calendar.base import CalendarProvider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class MockCalendarProvider(CalendarProvider):
    """A mock implementation of CalendarProvider."""

    def __init__(self) -> None:
        # In-memory "database" of bookings
        # format: {"YYYY-MM-DD": ["10:00 AM", ...]}
        self.bookings: dict[str, list[str]] = {}
        
        # Standard business hours available
        self.standard_slots = [
            "09:00 AM", "10:00 AM", "11:00 AM",
            "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM"
        ]

    async def get_availability(self, date_str: str) -> list[str]:
        """Return hardcoded available slots for a given date."""
        logger.info("mock_calendar_get_availability", date=date_str)
        
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        # Validate date format roughly
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return []

        # Find booked slots for this date
        booked_slots = self.bookings.get(date_str, [])
        
        # Return slots that aren't booked
        available = [slot for slot in self.standard_slots if slot not in booked_slots]
        return available

    async def book_appointment(
        self, date_str: str, time_str: str, name: str, phone: str, **kwargs: Any
    ) -> bool:
        """Mock booking an appointment."""
        logger.info(
            "mock_calendar_book_appointment", 
            date=date_str, 
            time=time_str, 
            name=name, 
            phone=phone
        )
        
        # Simulate network latency
        await asyncio.sleep(1.0)
        
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False
            
        if time_str not in self.standard_slots:
            return False

        if date_str not in self.bookings:
            self.bookings[date_str] = []
            
        if time_str in self.bookings[date_str]:
            # Already booked
            return False
            
        # Successfully book
        self.bookings[date_str].append(time_str)
        
        return True
