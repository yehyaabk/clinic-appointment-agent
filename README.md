## Google Calendar Integration

This project uses the **Google Calendar API v3** to manage appointments programmatically — creating, retrieving, and listing events on a dedicated calendar. Authentication is handled via OAuth 2.0 (or a service account for production/headless use), and all date-time values follow the **RFC 3339** standard with explicit timezone handling to remain safe across Daylight Saving Time changes.

### 1. Getting the Calendar service

```python
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)
```

The returned `service` object is a `googleapiclient.discovery.Resource` instance — the entry point for every subsequent Calendar API call.

### 2. Creating an event and inviting an attendee

```python
def get_calendar_timezone(service, calendar_id='primary'):
    calendar = service.calendars().get(calendarId=calendar_id).execute()
    return calendar['timeZone']

def book_appointment(service, summary, start_iso, end_iso, attendee_email, calendar_id='primary'):
    my_timezone = get_calendar_timezone(service, calendar_id)

    event = {
        'summary': summary,
        'start': {'dateTime': start_iso, 'timeZone': my_timezone},
        'end':   {'dateTime': end_iso, 'timeZone': my_timezone},
        'attendees': [{'email': attendee_email}],
    }

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates='all'   # notifies the attendee by email
    ).execute()

    return created_event['id']  # store this ID for future lookups/updates/cancellations
```

### 3. Retrieving an event by its ID

```python
def get_event_by_id(service, event_id, calendar_id='primary'):
    return service.events().get(
        calendarId=calendar_id,
        eventId=event_id
    ).execute()
```

### 4. Listing the next upcoming events

```python
import datetime

def get_next_events(service, calendar_id='primary', max_results=10):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])
```

### Notes

- All timestamps must be RFC 3339-compliant (e.g. `2026-09-10T15:00:00+02:00`); pairing `dateTime` with a named `timeZone` (e.g. `Europe/Paris`) is preferred over a raw offset, since it remains correct across DST transitions.
- `event_id`, returned on creation, is the sole reference needed to later retrieve, update, or cancel a specific appointment — it should be persisted alongside the corresponding record in the application's database.
- `sendUpdates='all'` triggers an automatic email invitation to any listed attendees; use `'none'` to create events silently.