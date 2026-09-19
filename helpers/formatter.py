import re

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


def markdown_to_whatsapp(text: str) -> str:
    """Converts common Markdown syntax to WhatsApp's formatting syntax."""
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)   
    text = re.sub(r"~~(.*?)~~", r"~\1~", text)         
    return text