from mcp.server.fastmcp import FastMCP
from db.config import get_connection
from helpers.groq_functions import match_doctors_to_symptoms
from helpers.emails import *
from helpers.formatter import format_doctors
from datetime import datetime, timedelta
from helpers.booking_checks import *
from helpers.clients import *
from calendar_service.calendar_tools import *
import os

import warnings

warnings.filterwarnings("ignore")

mcp = FastMCP("appointment-server")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CENTER_INFO_PATH = os.path.join(BASE_DIR, "center_info.txt")

@mcp.resource("info://medical-center")
def get_center_info() -> str:
    """
    Returns general information about the medical center (address, opening
    hours, appointment policy, specializations, etc.). Used to answer general
    questions when no specific tool matches the patient's request.
    """
    with open(CENTER_INFO_PATH, "r", encoding="utf-8") as f:
        return f.read()



@mcp.tool(name="search_doctors_by_symptoms")
def search_doctors_by_symptoms(symptom_description: str) -> str:
    """Find doctors whose specialization matches the patient's described symptoms."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT id, specialization, years_experience, description FROM doctors")
    doctors = cursor.fetchall()

    summary_list = [
        f"Specialization: {doc['specialization']}, Years of experience: {doc['years_experience']}, Description: {doc['description']}"
        for doc in doctors
    ]

    matching_positions = match_doctors_to_symptoms(
        symptom_description=symptom_description,
        doctors=summary_list
    )

    matching_ids = [doctors[i]["id"] for i in matching_positions]

    if not matching_ids:
        cursor.close()
        connection.close()
        return "No matching doctor for your case"

    placeholders = ", ".join(["%s"] * len(matching_ids))
    cursor.execute(
        f"SELECT id, full_name, specialization, years_experience, description FROM doctors WHERE id IN ({placeholders})",
        tuple(matching_ids)
    )
    matched_doctors = cursor.fetchall()

    cursor.close()
    connection.close()

    return format_doctors(matched_doctors)


@mcp.tool(name="book_appointment")
def book_appointment(identifier: str, doctor_identifier: str, date: str = None, time: str = None) -> str:
    """
    Books a 30-minute appointment for a client with a specific doctor.

    identifier: the client's telegram_id or whatsapp_number
    doctor_identifier: the doctor's full name, or their numeric id if the name is ambiguous
    date: appointment date, format 'YYYY-MM-DD'
    time: appointment start time, format 'HH:MM'
    """
    client = get_client_by_identifier(identifier)

    if client is None or not client.get("email"):
        return (
            "Please enter your email before booking an appointment — "
            "it's not possible to book without it first."
        )

    if date is None or time is None:
        return (
            "Please provide both a date and a time for your appointment. "
            "Working hours are 9:00 AM to 5:00 PM, with appointments starting "
            "on the hour or half-hour (e.g. 10:00, 10:30, 11:00)."
        )

    matching_doctors = find_matching_doctors(doctor_identifier)

    if len(matching_doctors) == 0:
        return f"We couldn't find a doctor matching '{doctor_identifier}'. Please check the name and try again."

    if len(matching_doctors) > 1:
        doctor_options = format_doctor_options(matching_doctors)
        return (
            "Several doctors share this name. Please resubmit your request using "
            f"the doctor's ID instead:\n{doctor_options}"
        )

    if not is_valid_appointment_date(date):
        return (
            f"'{date}' is not a valid date. Please choose a date from today "
            "up to one month ahead."
        )

    if not is_valid_appointment_time(time):
        return (
            "That time isn't valid. Appointments must start on the hour or "
            "half-hour (e.g. 15:00 or 15:30) between 9:00 AM and 4:30 PM."
        )

    doctor = matching_doctors[0]

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """SELECT id FROM appointments
           WHERE client_id = %s AND doctor_id = %s AND status = 'confirmed'""",
        (client["id"], doctor["id"])
    )
    already_booked = cursor.fetchone() is not None
    cursor.close()
    connection.close()

    if already_booked:
        return (
            f"You already have an appointment with {doctor['full_name']}. "
            "You can only have one appointment per doctor at a time — "
            "please reschedule or cancel the existing one first."
        )

    if has_conflicting_appointment(doctor["id"], date, time):
        return (
            f"{doctor['full_name']} already has an appointment at {time} on {date}. "
            "Please choose a different time."
        )

    client_email = client["email"]
    service = get_service()

    summary = f"Appointment: {client.get('full_name') or client_email} with {doctor['full_name']}"

    google_event_id = create_appointment_event(
        service=service,
        summary=summary,
        date=date,
        time=time,
        attendee_email=client_email,
    )

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO appointments (client_id, doctor_id, start_time, end_time, status, google_event_id)
        VALUES (%s, %s, %s, %s, 'confirmed', %s)""",
        (client["id"], doctor["id"], start_dt, end_dt, google_event_id)
    )
    connection.commit()
    cursor.close()
    connection.close()

    return (
        f"Your appointment is confirmed for {date} at {time} "
        f"with {doctor['full_name']} ({doctor['specialization']}). "
        f"A calendar invite has been sent to {client_email}."
    )


@mcp.tool(name="add_client_email")
def add_client_email(identifier: str, client_email: str) -> str:
    """
    Sets or updates a client's email address.

    identifier: the client's telegram_id or whatsapp_number
    client_email: the new email address to save
    """
    if not is_valid_email(client_email):
        return "That doesn't look like a valid email address. Please enter it again, e.g. name@example.com."

    client = get_client_by_identifier(identifier)

    if client is None:
        return "We couldn't find your client record yet. Please send a message first so we can register you."

    old_email = client.get("email")

    set_client_email(identifier, client_email)

    if old_email:
        update_attendee_email_in_appointments(client_id=client["id"], new_email=client_email)
        return f"Your email has been updated from {old_email} to {client_email}. Please check your new email to confirm your appointments."

    return f"Thanks! Your email ({client_email}) has been saved. You can now go ahead and submit your appointment request."



@mcp.tool(name="reschedule_appointment")
def reschedule_appointment(identifier: str, doctor_identifier: str, date: str = None, time: str = None) -> str:
    """
    Reschedules a client's existing confirmed appointment with a specific doctor
    to a new date/time.

    identifier: the client's telegram_id or whatsapp_number
    doctor_identifier: the doctor's full name, or their numeric id if the name is ambiguous
    date: new appointment date, format 'YYYY-MM-DD'
    time: new appointment start time, format 'HH:MM'
    """
    client = get_client_by_identifier(identifier)

    if client is None or not client.get("email"):
        return "Please enter your email before managing an appointment — it's not possible without it first."

    if date is None or time is None:
        return (
            "Please provide the new date and time for your appointment. "
            "Working hours are 9:00 AM to 5:00 PM, with appointments starting "
            "on the hour or half-hour (e.g. 10:00, 10:30, 11:00)."
        )

    matching_doctors = find_matching_doctors(doctor_identifier)

    if len(matching_doctors) == 0:
        return f"We couldn't find a doctor matching '{doctor_identifier}'. Please check the name and try again."

    if len(matching_doctors) > 1:
        doctor_options = format_doctor_options(matching_doctors)
        return (
            "Several doctors share this name. Please resubmit your request using "
            f"the doctor's ID instead:\n{doctor_options}"
        )

    if not is_valid_appointment_date(date):
        return f"'{date}' is not a valid date. Please choose a date from today up to one month ahead."

    if not is_valid_appointment_time(time):
        return (
            "That time isn't valid. Appointments must start on the hour or "
            "half-hour (e.g. 15:00 or 15:30) between 9:00 AM and 4:30 PM."
        )

    doctor = matching_doctors[0]
    doctor_id = doctor["id"]
    client_id = client["id"]

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """SELECT id, google_event_id FROM appointments
        WHERE client_id = %s AND doctor_id = %s AND status = 'confirmed'""",
        (client_id, doctor_id)
    )
    existing_appointment = cursor.fetchone()

    if existing_appointment is None:
        cursor.close()
        connection.close()
        return f"We couldn't find an existing appointment with {doctor['full_name']} to reschedule."

    if has_conflicting_appointment(doctor_id, date, time):
        cursor.close()
        connection.close()
        return f"{doctor['full_name']} already has an appointment at {time} on {date}. Please choose a different time."

    service = get_service()

    delete_calendar_event(service, existing_appointment["google_event_id"])

    summary = f"Appointment: {client.get('full_name') or client['email']} with {doctor['full_name']}"
    new_google_event_id = create_appointment_event(
        service=service,
        summary=summary,
        date=date,
        time=time,
        attendee_email=client["email"],
    )

    new_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    new_end = new_start + timedelta(minutes=30)

    cursor.execute(
        """UPDATE appointments
        SET start_time = %s, end_time = %s, google_event_id = %s
        WHERE id = %s""",
        (new_start, new_end, new_google_event_id, existing_appointment["id"])
    )
    connection.commit()

    cursor.close()
    connection.close()

    return (
        f"Your appointment with {doctor['full_name']} has been rescheduled "
        f"to {date} at {time}. An updated invite has been sent to {client['email']}."
    )


@mcp.tool(name="cancel_appointment")
def cancel_appointment(identifier: str, doctor_identifier: str) -> str:
    """
    Cancels a client's existing confirmed appointment with a specific doctor.

    identifier: the client's telegram_id or whatsapp_number
    doctor_identifier: the doctor's full name, or their numeric id if the name is ambiguous
    """
    client = get_client_by_identifier(identifier)

    if client is None:
        return "We couldn't find your client record yet. Please send a message first so we can register you."

    matching_doctors = find_matching_doctors(doctor_identifier)

    if len(matching_doctors) == 0:
        return f"We couldn't find a doctor matching '{doctor_identifier}'. Please check the name and try again."

    if len(matching_doctors) > 1:
        doctor_options = format_doctor_options(matching_doctors)
        return (
            "Several doctors share this name. Please resubmit your request using "
            f"the doctor's ID instead:\n{doctor_options}"
        )

    doctor = matching_doctors[0]

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """SELECT id, google_event_id FROM appointments
           WHERE client_id = %s AND doctor_id = %s AND status = 'confirmed'""",
        (client["id"], doctor["id"])
    )
    existing_appointment = cursor.fetchone()

    if existing_appointment is None:
        cursor.close()
        connection.close()
        return f"We couldn't find an existing appointment with {doctor['full_name']} to cancel."

    service = get_service()
    delete_calendar_event(service, existing_appointment["google_event_id"])

    cursor.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = %s",
        (existing_appointment["id"],)
    )
    connection.commit()

    cursor.close()
    connection.close()

    return f"Your appointment with {doctor['full_name']} has been cancelled."


@mcp.tool(name="list_appointments")
def list_appointments(identifier: str) -> str:
    """
    Lists all of a client's upcoming confirmed appointments.

    identifier: the client's telegram_id or whatsapp_number
    """
    client = get_client_by_identifier(identifier)

    if client is None:
        return "We couldn't find your client record yet. Please send a message first so we can register you."

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """SELECT a.start_time, d.full_name, d.specialization
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.client_id = %s AND a.status = 'confirmed' AND a.start_time >= NOW()
        ORDER BY a.start_time""",
        (client["id"],)
    )
    appointments = cursor.fetchall()

    cursor.close()
    connection.close()

    if not appointments:
        return "You have no upcoming appointments."

    lines = [
        f"- {appt['start_time'].strftime('%Y-%m-%d %H:%M')} with {appt['full_name']} ({appt['specialization']})"
        for appt in appointments
    ]

    return "Your upcoming appointments:\n" + "\n".join(lines)


@mcp.prompt(name="appointment_classification_prompt")
def appointment_classification_prompt(user_input: str, history: str = "") -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_weekday = datetime.now().strftime("%A")

    return f"""
        You are an assistant working for a medical center. Your role is to read the
        patient's message, identify which tool (if any) corresponds to what they're
        asking, and extract the arguments needed to call that tool.

        You are only allowed to return a JSON object containing the tool name and its
        corresponding arguments — no additional text, explanation, or formatting.

        Note: some arguments (like identifier) are added automatically on the client
        side (by the Flask webhook, from the Telegram chat_id or WhatsApp phone
        number) after your response — you do NOT need to extract or include them.
        Only extract arguments that are actually present in the user's message, or
        that you can resolve from the conversation history.

        Today's date is {today_str} ({today_weekday}). Use this as the reference
        point for resolving any relative date the patient mentions (e.g. "tomorrow",
        "next Monday", "in two days").

        IMPORTANT — date and time format:
        Every date argument MUST be extracted and returned in the format "YYYY-MM-DD".
        Every time argument MUST be extracted and returned in 24-hour format "HH:MM".
        Never return a date or time in any other format (no "March 5th", no "3pm",
        no "tomorrow") — always convert it yourself before returning the JSON.

        Available tools:

        - search_doctors_by_symptoms
            - args: symptom_description (str) — the patient's described symptom or
            health concern, in their own words.
            - function: Finds doctors whose specialization matches the described
            symptoms.

        - book_appointment
            - args: doctor_identifier (str) — the doctor's full name (or partial
            name), or their numeric id if the patient specifies it directly.
                    date (str, optional) — the appointment date, format "YYYY-MM-DD".
                    time (str, optional) — the appointment start time, format "HH:MM".
            - function: Books a 30-minute appointment with a specific doctor. If date
            or time is missing, the tool itself will ask the patient to provide
            them — do not invent a date or time that wasn't mentioned.

        - add_client_email
            - args: client_email (str) — the email address the patient provided.
            - function: Sets or updates the patient's email address, required before
            any appointment can be booked.

        - reschedule_appointment
            - args: doctor_identifier (str) — the doctor's full name (or partial
            name), or their numeric id if ambiguous.
                    date (str, optional) — the new date, format "YYYY-MM-DD".
                    time (str, optional) — the new time, format "HH:MM".
            - function: Moves the patient's existing confirmed appointment with that
            doctor to a new date/time.

        - cancel_appointment
            - args: doctor_identifier (str) — the doctor's full name (or partial
            name), or their numeric id if ambiguous.
            - function: Cancels the patient's existing confirmed appointment with
            that doctor.

        - list_appointments
            - args: none.
            - function: Lists all of the patient's upcoming confirmed appointments.

        Return format:
        You must return ONLY a valid JSON object, with no extra text.

        If a tool matches, return:
            {{
                "tool_name": "tool_name_here",
                "args": {{
                    "argument_name": "value extracted from the query"
                }}
            }}

        If no relevant tool is identified (e.g. a general question, a greeting, or
        something unrelated to booking/managing appointments), return:
            {{
                "tool_name": null
            }}

        ── Examples: general tool matching ──

        Query: "I have red spots on my skin, who should I see?"
        Output: {{"tool_name": "search_doctors_by_symptoms", "args": {{"symptom_description": "red spots on my skin"}}}}

        Query: "My email is jean.dupont@example.com"
        Output: {{"tool_name": "add_client_email", "args": {{"client_email": "jean.dupont@example.com"}}}}

        Query: "Cancel my appointment with Dr. Martin"
        Output: {{"tool_name": "cancel_appointment", "args": {{"doctor_identifier": "Dr. Martin"}}}}

        Query: "What appointments do I have coming up?"
        Output: {{"tool_name": "list_appointments", "args": {{}}}}

        Query: "Show me my bookings"
        Output: {{"tool_name": "list_appointments", "args": {{}}}}

        Query: "What are your opening hours?"
        Output: {{"tool_name": null}}

        Query: "Hello, how are you?"
        Output: {{"tool_name": null}}

        ── Examples: date and time extraction (this is the part to get exactly right) ──

        Assume today is {today_str} in every example below.

        Query: "I want an appointment with Dr. Martin at 3pm tomorrow"
        Reasoning: "tomorrow" → {today_str} + 1 day. "3pm" → 15:00.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Martin", "date": "<tomorrow's date in YYYY-MM-DD>", "time": "15:00"}}}}

        Query: "Book me with Dr. Dupont next Monday at 9"
        Reasoning: resolve the date of the next upcoming Monday from today. "9" with
        no am/pm, in a working-hours context, means 9:00 AM.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Dupont", "date": "<next Monday's date in YYYY-MM-DD>", "time": "09:00"}}}}

        Query: "Reschedule my appointment with Dr. Sophie Martin to 2:30pm on March 5th"
        Reasoning: "2:30pm" → 14:30. "March 5th" → the year is the current year unless
        already past, in which case use next year. Format as YYYY-MM-DD.
        Output: {{"tool_name": "reschedule_appointment", "args": {{"doctor_identifier": "Dr. Sophie Martin", "date": "<2026 or 2027>-03-05", "time": "14:30"}}}}

        Query: "Can I see Dr. Karim in two days at half past ten in the morning?"
        Reasoning: "in two days" → {today_str} + 2 days. "half past ten in the
        morning" → 10:30.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Karim", "date": "<today + 2 days in YYYY-MM-DD>", "time": "10:30"}}}}

        Query: "I'd like to book Dr. Bernard for noon on the 20th of September"
        Reasoning: "noon" → 12:00. "the 20th of September" → YYYY-09-20.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Bernard", "date": "<year>-09-20", "time": "12:00"}}}}

        Query: "Move my appointment with Dr. Lefevre to 4:45 in the afternoon this Friday"
        Reasoning: "this Friday" → resolve the date of the upcoming Friday. "4:45 in
        the afternoon" → 16:45.
        Output: {{"tool_name": "reschedule_appointment", "args": {{"doctor_identifier": "Dr. Lefevre", "date": "<this Friday's date in YYYY-MM-DD>", "time": "16:45"}}}}

        Query: "Book Dr. Amel for 9 in the evening"
        Reasoning: "9 in the evening" → 21:00. No date mentioned — leave date out of
        args entirely; the tool will ask for it.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Amel"}}}}

        Query: "I want to book Dr. Youssef"
        Reasoning: no date or time mentioned at all — do not guess or default to
        anything. Only include doctor_identifier.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Youssef"}}}}

        ── Example using conversation history ──

        History:
            Q1: "Do you have a good dermatologist?"
            A1: "Yes, Dr. Sophie Martin is available."
        Query: "Book me with her tomorrow at 2"
        Reasoning: "her" resolves to "Dr. Sophie Martin" from history. "tomorrow" →
        {today_str} + 1 day. "2" with no am/pm, in a daytime booking context, means
        14:00.
        Output: {{"tool_name": "book_appointment", "args": {{"doctor_identifier": "Dr. Sophie Martin", "date": "<tomorrow's date in YYYY-MM-DD>", "time": "14:00"}}}}

        Now process the following query and return only the JSON output.

        Conversation history:
        {history}

        Current query:
        {user_input}
        """

if __name__ == "__main__":
    mcp.run()