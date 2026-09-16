import os
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")


def get_service() -> Resource:
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service


def get_calendar_timezone(service: Resource, calendar_id: str = "primary") -> str:
    calendar = service.calendars().get(calendarId=calendar_id).execute()
    return calendar["timeZone"]


def create_appointment_event(
    service: Resource,
    summary: str,
    date: str,
    time: str,
    attendee_email: str,
    duration_minutes: int = 30,
    calendar_id: str = "primary",
) -> str:
    """
    Creates a Google Calendar event for an appointment and invites the client
    by email — this is what triggers Google to send them the confirmation email.

    date: 'YYYY-MM-DD'
    time: 'HH:MM'
    Returns the created event's id (to be stored alongside the appointment row).
    """
    timezone = get_calendar_timezone(service, calendar_id)

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        "attendees": [{"email": attendee_email}],
    }

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates="all", 
    ).execute()

    return created_event["id"]


def delete_calendar_event(service: Resource, event_id: str, calendar_id: str = "primary") -> None:
    """Deletes a Google Calendar event by its id."""
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


if __name__ == "__main__":
    service = get_service()
    print("Calendar service created successfully:", service)