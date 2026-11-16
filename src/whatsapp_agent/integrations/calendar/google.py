"""
Google Calendar Provider.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.integrations.calendar.base import CalendarProvider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# Scopes needed for Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = "google_calendar_token.json"


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar API Integration."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.creds = self._get_credentials()

    def _get_credentials(self) -> Credentials | None:
        """Load credentials from local token file."""
        creds = None
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                logger.error("failed_to_load_google_token", error=str(e))
                return None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error("failed_to_refresh_google_token", error=str(e))
                return None
        return creds

    async def get_availability(self, date_str: str) -> list[str]:
        """
        Get available time slots for a specific date (Mocked implementation returning 9-5).
        In a real app, this would use FreeBusy query.
        """
        if not self.creds:
            logger.warning("google_calendar_not_authenticated")
            return ["10:00 AM", "02:00 PM"] # fallback
            
        try:
            service = build("calendar", "v3", credentials=self.creds)
            # Basic fallback for MVP: Just return fixed slots
            # Ideal: Use service.freebusy().query(...) to get actual free slots
            return ["09:00 AM", "11:00 AM", "02:00 PM", "04:00 PM"]
        except Exception as e:
            logger.error("get_availability_failed", error=str(e))
            return []

    async def book_appointment(
        self, date_str: str, time_str: str, name: str, phone: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Book an appointment by creating an event with a Google Meet link."""
        if not self.creds:
            logger.error("google_calendar_not_authenticated_cannot_book")
            return {"success": False, "error": "Not authenticated"}

        try:
            service = build("calendar", "v3", credentials=self.creds)

            # Parse date_str (YYYY-MM-DD) and time_str (e.g., 10:00 AM)
            dt_str = f"{date_str} {time_str}"
            start_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
            end_dt = start_dt + datetime.timedelta(hours=1) # 1 hour duration
            tz = "Asia/Kolkata"

            event = {
                "summary": f"Meeting with {name}",
                "description": f"Phone: {phone}\n{kwargs.get('notes', '')}",
                "start": {
                    "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": tz,
                },
                "end": {
                    "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": tz,
                },
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"{phone}-{int(datetime.datetime.now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"}
                    }
                }
            }

            event = service.events().insert(
                calendarId="primary", 
                body=event, 
                conferenceDataVersion=1
            ).execute()
            
            meet_link = event.get("hangoutLink")
            if not meet_link:
                entry_points = event.get("conferenceData", {}).get("entryPoints", [])
                for ep in entry_points:
                    if ep.get("entryPointType") == "video" or "meet.google.com" in ep.get("uri", ""):
                        meet_link = ep.get("uri")
                        break

            logger.info("appointment_booked", event_id=event.get("id"), link=event.get("htmlLink"), meet_link=meet_link)
            return {"success": True, "meet_link": meet_link or event.get("htmlLink")}
        except Exception as e:
            logger.error("book_appointment_failed", error=str(e))
            return {"success": False, "error": str(e)}
