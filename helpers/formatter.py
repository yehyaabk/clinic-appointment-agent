def format_doctors(doctors: list[dict]) -> str:
    """Formats a list of doctor rows into a readable message for the patient."""
    lines = [
        f"- ID {doc['id']}: {doc['full_name']}, {doc['specialization']} "
        f"({doc['years_experience']} years of experience), {doc['description']}"
        for doc in doctors
    ]
 
    doctors_block = "\n".join(lines)
 
    return (
        f"Your possible doctors for your symptoms are the following:\n{doctors_block}\n\n"
        "To book an appointment, please reply with the doctor's ID or their full name "
        "(using the ID is recommended, as several doctors may share the same name), "
        "along with your email address if you haven't registered it yet."
    )
 