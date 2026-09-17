from mcp.server.fastmcp import FastMCP
from db.config import get_connection
from helpers.groq_functions import match_doctors_to_symptoms
from helpers.emails import *
from helpers.formatter import format_doctors
from datetime import datetime, timedelta
from helpers.booking_checks import *
from helpers.clients import *
from calendar_service.calendar_tools import *

import warnings

warnings.filterwarnings("ignore")

mcp = FastMCP("appointment-server")


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

    # Map list positions back to the REAL doctor ids
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
            f"You already have an appointment with Dr. {doctor['full_name']}. "
            "You can only have one appointment per doctor at a time — "
            "please reschedule or cancel the existing one first."
        )

    if has_conflicting_appointment(doctor["id"], date, time):
        return (
            f"Dr. {doctor['full_name']} already has an appointment at {time} on {date}. "
            "Please choose a different time."
        )

    #     create Calendar event, insert appointment into MySQL
    client_email = client["email"]
    service = get_service()

    summary = f"Appointment: {client.get('full_name') or client_email} with Dr. {doctor['full_name']}"

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
        f"with Dr. {doctor['full_name']} ({doctor['specialization']}). "
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

    # Should not occur in practice, since the webhook route creates the client
    # before calling the agent. Kept as a defensive safeguard.
    if client is None:
        return "We couldn't find your client record yet. Please send a message first so we can register you."

    old_email = client.get("email")

    set_client_email(identifier, client_email)

    if old_email:
        update_attendee_email_in_appointments(client_id=client["id"], new_email=client_email)
        return f"Your email has been updated from {old_email} to {client_email}. Please check your new email to confirm your appointments."

    return "Your email has been saved successfully."



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

    # 1. Find the existing confirmed appointment to reschedule
    cursor.execute(
        """SELECT id, google_event_id FROM appointments
        WHERE client_id = %s AND doctor_id = %s AND status = 'confirmed'""",
        (client_id, doctor_id)
    )
    existing_appointment = cursor.fetchone()

    if existing_appointment is None:
        cursor.close()
        connection.close()
        return f"We couldn't find an existing appointment with Dr. {doctor['full_name']} to reschedule."

    # 2. Make sure the new slot doesn't collide with another appointment for this doctor
    if has_conflicting_appointment(doctor_id, date, time):
        cursor.close()
        connection.close()
        return f"Dr. {doctor['full_name']} already has an appointment at {time} on {date}. Please choose a different time."

    # 3. Recreate the Google Calendar event at the new time, remove the old one
    service = get_service()

    delete_calendar_event(service, existing_appointment["google_event_id"])

    summary = f"Appointment: {client.get('full_name') or client['email']} with Dr. {doctor['full_name']}"
    new_google_event_id = create_appointment_event(
        service=service,
        summary=summary,
        date=date,
        time=time,
        attendee_email=client["email"],
    )

    # 4. Update the appointment row with the new time and new event id
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
        f"Your appointment with Dr. {doctor['full_name']} has been rescheduled "
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
        return f"We couldn't find an existing appointment with Dr. {doctor['full_name']} to cancel."
 
    service = get_service()
    delete_calendar_event(service, existing_appointment["google_event_id"])

    cursor.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = %s",
        (existing_appointment["id"],)
    )
    connection.commit()

    cursor.close()
    connection.close()

    return f"Your appointment with Dr. {doctor['full_name']} has been cancelled."


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
        f"- {appt['start_time'].strftime('%Y-%m-%d %H:%M')} with Dr. {appt['full_name']} ({appt['specialization']})"
        for appt in appointments
    ]

    return "Your upcoming appointments:\n" + "\n".join(lines)


    

    


