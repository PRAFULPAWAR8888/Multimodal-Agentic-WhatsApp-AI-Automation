import asyncio
import sys
sys.stdout.reconfigure(encoding="utf-8")
from whatsapp_agent.integrations.calendar.google import GoogleCalendarProvider

async def main():
    provider = GoogleCalendarProvider()
    print("========================================")
    print("   Google Calendar & Meet Test Suite   ")
    print("========================================")
    
    print("\n1. Checking Google OAuth Credentials...")
    if not provider.creds:
        print("[FAIL] Credentials missing, expired, or revoked.")
        print("Please authenticate by visiting:")
        print("   http://localhost:8000/api/v1/calendar/google/login")
        return
        
    print("[PASS] Credentials loaded successfully!")
    print(f"   Token valid: {provider.creds.valid}")
    
    print("\n2. Checking Availability on Google Calendar...")
    test_date = "2026-10-15"
    slots = await provider.get_availability(test_date)
    print(f"[PASS] Available slots for {test_date}: {slots}")
    
    print("\n3. Testing Google Calendar Event & Meet Link Creation...")
    booking = await provider.book_appointment(
        date_str=test_date,
        time_str="03:00 PM",
        name="Praful Pawar Test",
        phone="+919876543210",
        notes="Automated test for Google Calendar & Google Meet API"
    )
    
    if booking.get("success"):
        print("[SUCCESS] Event created successfully on Google Calendar!")
        print(f"   Google Meet Link: {booking.get('meet_link')}")
    else:
        print(f"[FAIL] Booking failed: {booking.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
