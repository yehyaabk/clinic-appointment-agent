from mcp.server.fastmcp import FastMCP
from  db.config import get_connection
from helpers.groq_functions import match_doctors_to_symptoms
from helpers.formatter import format_doctors
from datetime import datetime
from helpers.booking_checks import *
from helpers.clients import *

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
        f"SELECT full_name, specialization, years_experience, description FROM doctors WHERE id IN ({placeholders})",
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

    if has_conflicting_appointment(doctor["id"], date, time):
        return (
            f"Dr. {doctor['full_name']} already has an appointment at {time} on {date}. "
            "Please choose a different time."
        )

    


