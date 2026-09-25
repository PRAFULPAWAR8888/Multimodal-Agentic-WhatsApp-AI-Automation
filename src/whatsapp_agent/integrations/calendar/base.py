"""
Calendar Provider Base Interface.

Defines the contract for interacting with calendar systems 
(Google Calendar, Outlook, Mock).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CalendarProvider(ABC):
    """Abstract base class for all calendar providers."""

    @abstractmethod
    async def get_availability(self, date_str: str) -> list[str]:
        """
        Get available time slots for a specific date.
        
        Args:
            date_str: Date string in YYYY-MM-DD format.
            
        Returns:
            List of available time slot strings (e.g., ["10:00 AM", "2:00 PM"]).
        """
        pass

    @abstractmethod
    async def book_appointment(
        self, date_str: str, time_str: str, name: str, phone: str, **kwargs: Any
    ) -> bool:
        """
        Book an appointment on the calendar.
        
        Args:
            date_str: Date string in YYYY-MM-DD format.
            time_str: Time string (e.g., "10:00 AM").
            name: Customer's name.
            phone: Customer's phone number.
            
        Returns:
            True if booking was successful, False otherwise.
        """
        pass
