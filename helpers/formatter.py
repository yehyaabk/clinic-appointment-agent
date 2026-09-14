def format_doctors(doctors: list[dict]) -> str:
    """Formats a list of doctor rows into a readable message for the patient."""
    lines = [
        f"- {doc['full_name']}, {doc['specialization']} ({doc['years_experience']} years of experience), {doc['description']}"
        for doc in doctors
    ]

    doctors_block = "\n".join(lines)

    return f"Your possible doctors for your symptoms are the following:\n{doctors_block}"