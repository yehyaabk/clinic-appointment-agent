from mcp.server.fastmcp import FastMCP
from  db.config import get_connection
from helpers.groq_functions import match_doctors_to_symptoms
from helpers.formatter import format_doctors

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







    


