import re
from db.config import get_connection
from calendar.calendar_tools import update_event_attendee_email, get_service


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    """Basic format check for an email address."""
    return bool(EMAIL_PATTERN.match(email.strip()))


def set_client_email(identifier: str, email: str) -> bool:
    """
    Saves (creates or updates) a client's email address.
    Returns True if a matching client was found and updated, False otherwise.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE clients SET email = %s WHERE whatsapp_number = %s OR telegram_id = %s",
        (email, identifier, identifier)
    )
    connection.commit()

    updated = cursor.rowcount > 0

    cursor.close()
    connection.close()
    return updated


def update_attendee_email_in_appointments(client_id: int, new_email: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """SELECT google_event_id FROM appointments
        WHERE client_id = %s AND status = 'confirmed' AND google_event_id IS NOT NULL""",
        (client_id,)
    )
    rows = cursor.fetchall()
    event_ids = [row[0] for row in rows]

    cursor.close()
    connection.close()

    service = get_service()

    for event_id in event_ids:
        try:
            update_event_attendee_email(service=service, event_id=event_id, new_email=new_email)
        except Exception as e:
            print(f"Failed to update attendee email for event {event_id}: {e}")

