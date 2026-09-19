from datetime import datetime, date as date_type, time as time_type, timedelta
from db.config import get_connection

WORK_START = time_type(9, 0)
LAST_SLOT_START = time_type(16, 30)  # last bookable slot, ends exactly at 17:00
MAX_BOOKING_WINDOW_DAYS = 30


def find_matching_doctors(doctor_identifier: str) -> list[dict]:
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    if doctor_identifier.isdigit():
        cursor.execute(
            "SELECT id, full_name, specialization FROM doctors WHERE id = %s",
            (int(doctor_identifier),)
        )
        matches = cursor.fetchall()
    else:
        words = [w for w in doctor_identifier.strip().split() if w.lower() not in ("dr", "dr.")]

        if not words:
            matches = []
        else:
            conditions = " AND ".join(["full_name LIKE %s"] * len(words))
            params = tuple(f"%{word}%" for word in words)
            cursor.execute(
                f"SELECT id, full_name, specialization FROM doctors WHERE {conditions}",
                params
            )
            matches = cursor.fetchall()

    cursor.close()
    connection.close()
    return matches


def format_doctor_options(doctors: list[dict]) -> str:
    """Formats a list of same-named doctors into a readable disambiguation message."""
    lines = [
        f"- ID {doc['id']}: {doc['full_name']} ({doc['specialization']})"
        for doc in doctors
    ]
    return "\n".join(lines)


def is_valid_appointment_date(date_str: str) -> bool:
    """
    Checks that the date is a real calendar date, not in the past,
    and not further than MAX_BOOKING_WINDOW_DAYS in the future.
    """
    try:
        requested_date = date_type.fromisoformat(date_str)
    except ValueError:
        return False

    today = date_type.today()
    max_date = today + timedelta(days=MAX_BOOKING_WINDOW_DAYS)

    return today <= requested_date <= max_date


def is_valid_appointment_time(time_str: str) -> bool:
    """
    Checks that the time is well-formed, falls on a valid 30-minute boundary
    (HH:00 or HH:30), and lies within working hours (09:00 to 16:30 inclusive).
    """
    try:
        requested_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return False

    if requested_time.minute not in (0, 30):
        return False

    return WORK_START <= requested_time <= LAST_SLOT_START


def has_conflicting_appointment(doctor_id: int, date_str: str, time_str: str) -> bool:
    """
    Checks whether the given doctor already has a confirmed appointment
    at this exact date and time slot.
    """
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

    cursor.execute(
        """SELECT id FROM appointments
        WHERE doctor_id = %s AND status = 'confirmed' AND start_time = %s""",
        (doctor_id, start_dt)
    )
    conflict = cursor.fetchone()

    cursor.close()
    connection.close()

    return conflict is not None

